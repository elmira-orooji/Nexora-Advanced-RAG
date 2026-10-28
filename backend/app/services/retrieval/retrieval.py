import math
import logging
import threading
import re
import uuid
from time import perf_counter
from collections import Counter, OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.core.config import GRAPH_RAG_ENABLED
from app.services.ports import VectorSearchPort
from app.services.providers.provider_factory import get_vector_store
from app.services.retrieval.retrieval_fusion import fuse_results
from app.services.retrieval.retrieval_ranking import rerank
from app.services.retrieval.graph_search import graph_search

TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
RRF_K = 60
BM25_CACHE_SCOPES = 16
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ChunkSnapshot:
    """Lightweight, session-independent chunk data for safe caching."""
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    parent_index: int | None
    content: str
    tokens: list[str]
    filename: str


@dataclass
class _LexicalCorpus:
    signature: tuple[tuple[str, str], ...]
    chunks: list[_ChunkSnapshot]
    document_lengths: list[int]
    average_length: float
    postings: dict[str, list[tuple[int, int]]]
    total_weight: int = 0  # For weighted LRU eviction


_LEXICAL_CACHE_MAX_WEIGHT = 256  # Weight-based limit instead of count-based
_lexical_cache: OrderedDict[tuple[str, ...], _LexicalCorpus] = OrderedDict()
_lexical_cache_lock = threading.RLock()  # RLock allows reentrant access
_lexical_cache_total_weight: int = 0


def _normalize(text: str) -> str:
    mapping = {"\u064a": "\u06cc", "\u0643": "\u06a9", "\u0629": "\u0647", "\u06c0": "\u0647"}
    return text.lower().translate(str.maketrans(mapping))


def _tokens(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(_normalize(text)) if len(token) > 1]


def _build_lexical_corpus(
    signature: tuple[tuple[str, str], ...],
    chunks: list[_ChunkSnapshot],
) -> _LexicalCorpus:
    """Build BM25 index from pre-tokenized chunk snapshots."""
    document_lengths: list[int] = []
    postings: dict[str, list[tuple[int, int]]] = {}
    for index, chunk in enumerate(chunks):
        frequencies = Counter(chunk.tokens)
        doc_len = sum(frequencies.values())
        document_lengths.append(doc_len)
        for token, frequency in frequencies.items():
            postings.setdefault(token, []).append((index, frequency))
    average_length = sum(document_lengths) / len(document_lengths) if document_lengths else 1.0
    # Weight = number of chunks (proxy for memory footprint)
    weight = max(1, len(chunks) // 10)
    return _LexicalCorpus(signature, chunks, document_lengths, average_length or 1.0, postings, total_weight=weight)


def _bm25(query: str, chunks: list[_ChunkSnapshot], limit: int, corpus: _LexicalCorpus | None = None) -> list[dict]:
    query_tokens = _tokens(query)
    if not query_tokens or not chunks:
        return []
    corpus = corpus or _build_lexical_corpus((), chunks)
    total = len(chunks)
    scores: dict[int, float] = {}
    for token in set(query_tokens):
        posting = corpus.postings.get(token, [])
        if not posting:
            continue
        document_frequency = len(posting)
        inverse_frequency = math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
        for index, frequency in posting:
            denominator = frequency + 1.5 * (
                0.25 + 0.75 * corpus.document_lengths[index] / corpus.average_length
            )
            scores[index] = scores.get(index, 0.0) + inverse_frequency * frequency * 2.5 / denominator
    scored = [(score, chunks[index]) for index, score in scores.items() if score > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": str(chunk.id),
            "score": score,
            "payload": {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "filename": chunk.filename,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            },
        }
        for score, chunk in scored[:limit]
    ]


def _lexical_corpus(db: Session, scoped_ids: list[uuid.UUID]) -> _LexicalCorpus:
    global _lexical_cache_total_weight
    scope_key = tuple(sorted(str(value) for value in scoped_ids))

    # Always obtain the current version signature. The corpus cache avoids the
    # expensive rebuild, while this lightweight query prevents stale answers
    # after document or chunk changes in the same process.
    versions = db.execute(
        select(Document.id, Document.updated_at).where(Document.id.in_(scoped_ids))
    ).all()
    signature = tuple(sorted(
        (str(document_id), updated_at.isoformat() if updated_at is not None else "")
        for document_id, updated_at in versions
    ))

    # Double-check after DB read (another thread may have populated cache)
    with _lexical_cache_lock:
        cached_corpus = _lexical_cache.get(scope_key)
        if cached_corpus is not None and cached_corpus.signature == signature:
            _lexical_cache.move_to_end(scope_key)
            return cached_corpus

    # Cache miss: build corpus from scratch with session-independent snapshots
    rows = list(db.execute(
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.document_id.in_(scoped_ids), Chunk.is_active.is_(True))
    ).all())

    # Create detached snapshots with pre-computed tokens
    snapshots = [
        _ChunkSnapshot(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            parent_index=getattr(chunk, "parent_index", None),
            content=chunk.content,
            tokens=_tokens(chunk.content),
            filename=filename,
        )
        for chunk, filename in rows
    ]

    corpus = _build_lexical_corpus(signature, snapshots)

    with _lexical_cache_lock:
        # Evict old entry if exists
        old = _lexical_cache.pop(scope_key, None)
        if old is not None:
            _lexical_cache_total_weight -= old.total_weight

        _lexical_cache[scope_key] = corpus
        _lexical_cache.move_to_end(scope_key)
        _lexical_cache_total_weight += corpus.total_weight

        # Weighted LRU eviction
        while _lexical_cache_total_weight > _LEXICAL_CACHE_MAX_WEIGHT and len(_lexical_cache) > 1:
            _, evicted = _lexical_cache.popitem(last=False)
            _lexical_cache_total_weight -= evicted.total_weight

    return corpus


def _rerank(query: str, candidates: list[dict], limit: int) -> list[dict]:
    """Compatibility wrapper that keeps tokenization configurable in this module."""
    return rerank(query, candidates, limit, _tokens)


def _expand_parents(chunks: list[_ChunkSnapshot], ranked_children: list[dict], limit: int) -> list[dict]:
    chunk_map = {str(c.id): c for c in chunks}
    parents: dict[tuple[str, int | None], list[_ChunkSnapshot]] = {}
    for chunk in chunk_map.values():
        parents.setdefault((str(chunk.document_id), chunk.parent_index), []).append(chunk)
    # Build parent texts from active snapshots only
    parent_texts = {
        key: "\n\n".join(c.content for c in sorted(children, key=lambda item: item.chunk_index))
        for key, children in parents.items()
    }
    seen_parents: set[tuple[str, int | None]] = set()
    expanded = []
    for child in ranked_children:
        payload = child["payload"]
        chunk = chunk_map.get(str(payload.get("chunk_id")))
        if chunk is None:
            continue
        parent_key = (str(chunk.document_id), chunk.parent_index)
        if parent_key in seen_parents:
            continue
        seen_parents.add(parent_key)
        expanded.append({
            **child,
            "payload": {
                **payload,
                "content": parent_texts[parent_key],
                "matched_child_content": chunk.content,
                "parent_index": chunk.parent_index,
            },
            "retrieval": {**child.get("retrieval", {}), "expanded_to_parent": True},
        })
        if len(expanded) >= limit:
            break
    return expanded


def hybrid_search(
    db: Session,
    query: str,
    limit: int,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
    trace: dict | None = None,
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0,
    use_reranker: bool = True,
    vector_store: VectorSearchPort | None = None,
    organization_id: str | None = None,
    include_graph: bool | None = None,
) -> list[dict]:
    """Retrieve scoped context, optionally using an injected vector-store adapter."""
    if vector_weight <= 0 and bm25_weight <= 0:
        raise ValueError("At least one retrieval weight must be greater than zero")
    if document_id:
        scoped_ids = [uuid.UUID(document_id)]
    elif document_ids is not None:
        if not document_ids:
            return []
        scoped_ids = [uuid.UUID(value) for value in document_ids]
    else:
        raise ValueError("Hybrid search requires an explicit document scope")
    candidate_limit = min(max(limit * 4, 20), 80)
    started = perf_counter()
    vector_results = (
        (vector_store or get_vector_store()).search(
            query=query,
            limit=candidate_limit,
            document_id=document_id,
            document_ids=document_ids,
        )
        if vector_weight > 0
        else []
    )
    vector_ms = round((perf_counter() - started) * 1000, 2) if vector_weight > 0 else 0.0
    started = perf_counter()
    corpus = _lexical_corpus(db, scoped_ids)
    chunks = corpus.chunks
    lexical_results = _bm25(query, chunks, candidate_limit, corpus) if bm25_weight > 0 else []
    active_chunks = {str(c.id): c for c in chunks}
    lexical_ms = round((perf_counter() - started) * 1000, 2)
    candidates = fuse_results(
        vector_results,
        lexical_results,
        active_chunks,
        vector_weight,
        bm25_weight,
        RRF_K,
    )
    graph_ms = 0.0
    graph_count = 0
    graph_enabled = GRAPH_RAG_ENABLED and organization_id is not None and include_graph is not False
    if graph_enabled:
        started = perf_counter()
        try:
            graph_candidates = graph_search(
                db,
                query,
                candidate_limit,
                organization_id,
                scoped_ids,
            )
            by_chunk_id = {str(item["payload"]["chunk_id"]): item for item in candidates}
            for candidate in graph_candidates:
                chunk_id = str(candidate["payload"]["chunk_id"])
                if chunk_id in by_chunk_id:
                    existing = by_chunk_id[chunk_id]
                    existing["score"] = max(float(existing["score"]), float(candidate["score"]))
                    existing["retrieval"] = {**existing.get("retrieval", {}), **candidate["retrieval"]}
                elif chunk_id in active_chunks:
                    candidates.append(candidate)
                    by_chunk_id[chunk_id] = candidate
            graph_count = len(graph_candidates)
        except SQLAlchemyError:
            db.rollback()
            logger.warning("Graph retrieval failed; falling back to hybrid retrieval", exc_info=True)
        graph_ms = round((perf_counter() - started) * 1000, 2)
    started = perf_counter()
    reranked_children = _rerank(query, candidates, candidate_limit) if use_reranker else candidates[:candidate_limit]
    rerank_ms = round((perf_counter() - started) * 1000, 2)
    expanded = _expand_parents(chunks, reranked_children, limit)
    ocr_provenance_by_document = dict(
        db.execute(
            select(Document.id, Document.ocr_provenance).where(Document.id.in_(scoped_ids))
        ).all()
    )
    for item in expanded:
        document_id = uuid.UUID(item["payload"]["document_id"])
        item["payload"]["ocr_provenance"] = ocr_provenance_by_document.get(document_id)
    if trace is not None:
        trace.update({"vector_ms": vector_ms, "bm25_ms": lexical_ms, "graph_ms": graph_ms, "graph_count": graph_count, "vector_count": len(vector_results), "bm25_count": len(lexical_results), "fused_count": len(candidates), "rerank_ms": rerank_ms, "reranked_count": len(reranked_children), "answer_context_count": len(expanded)})
    return expanded
