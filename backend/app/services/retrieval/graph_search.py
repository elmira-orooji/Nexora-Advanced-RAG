"""Bounded graph expansion that always returns original, permission-scoped chunks."""

import re
import uuid

from sqlalchemy import or_, select, union
from sqlalchemy.orm import Session

from app.core.config import GRAPH_QUERY_MAX_HOPS
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_graph import KnowledgeEntity, KnowledgeGraphFact
from app.services.retrieval.graph_indexer import normalize_entity_name

_RELATION_CUES = re.compile(
    r"(?<!\w)(?:relationship|relations?|connect(?:ed|ion)?|dependenc(?:y|ies)|"
    r"across|between|compare|impact|affect(?:ed|s)?|interact(?:ion)?|"
    r"رابطه|ارتباط|مرتبط|به هم|بین|مقایسه|وابستگی|وابسته|اثر|تاثیر|تأثیر)(?!\w)",
    re.IGNORECASE,
)


def is_graph_query(query: str) -> bool:
    return bool(_RELATION_CUES.search(normalize_entity_name(query)))


def _matching_entities(db: Session, query: str, organization_id: uuid.UUID, document_ids: list[uuid.UUID]) -> list[KnowledgeEntity]:
    if not document_ids:
        return []
    scoped_chunks = select(Chunk.id).where(
        Chunk.document_id.in_(document_ids),
        Chunk.is_active.is_(True),
    )
    subject_ids = select(KnowledgeGraphFact.subject_entity_id).where(
        KnowledgeGraphFact.organization_id == organization_id,
        KnowledgeGraphFact.source_chunk_id.in_(scoped_chunks),
    )
    object_ids = select(KnowledgeGraphFact.object_entity_id).where(
        KnowledgeGraphFact.organization_id == organization_id,
        KnowledgeGraphFact.source_chunk_id.in_(scoped_chunks),
    )
    visible_ids = union(subject_ids, object_ids)
    entities = db.scalars(select(KnowledgeEntity).where(
        KnowledgeEntity.organization_id == organization_id,
        KnowledgeEntity.id.in_(visible_ids),
    )).all()
    normalized_query = normalize_entity_name(query)
    matches = []
    for entity in entities:
        names = [entity.canonical_name, *(entity.aliases or [])]
        if any(
            len(normalize_entity_name(name)) >= 2
            and re.search(rf"(?<!\w){re.escape(normalize_entity_name(name))}(?!\w)", normalized_query)
            for name in names
        ):
            matches.append(entity)
    matches.sort(key=lambda entity: max((len(normalize_entity_name(n)) for n in [entity.canonical_name, *(entity.aliases or [])]
                                        if re.search(rf"(?<!\w){re.escape(normalize_entity_name(n))}(?!\w)", normalized_query)), default=0), reverse=True)
    return matches[:8]


def _fact_evidence(
    db: Session,
    organization_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    entity_ids: set[uuid.UUID],
    limit: int,
) -> list[tuple[KnowledgeGraphFact, Chunk, str, dict | None]]:
    if not entity_ids or not document_ids:
        return []
    return list(db.execute(
        select(KnowledgeGraphFact, Chunk, Document.filename, Document.ocr_provenance)
        .join(Chunk, Chunk.id == KnowledgeGraphFact.source_chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            KnowledgeGraphFact.organization_id == organization_id,
            Document.organization_id == organization_id,
            Chunk.document_id.in_(document_ids),
            Chunk.is_active.is_(True),
            or_(
                KnowledgeGraphFact.subject_entity_id.in_(entity_ids),
                KnowledgeGraphFact.object_entity_id.in_(entity_ids),
            ),
        )
        .order_by(KnowledgeGraphFact.created_at.desc())
        .limit(limit)
    ).all())


def graph_search(
    db: Session,
    query: str,
    limit: int,
    organization_id: str,
    document_ids: list[uuid.UUID],
) -> list[dict]:
    """Find one- or two-hop evidence; each result is filtered to allowed active chunks."""
    if not document_ids or limit < 1:
        return []
    organization_uuid = uuid.UUID(organization_id)
    anchors = _matching_entities(db, query, organization_uuid, document_ids)
    if not is_graph_query(query) and len(anchors) < 2:
        return []
    if not anchors:
        return []
    anchor_ids = {entity.id for entity in anchors}
    direct = _fact_evidence(db, organization_uuid, document_ids, anchor_ids, max(limit * 12, 36))
    if not direct:
        return []

    rows: list[tuple[KnowledgeGraphFact, Chunk, str, dict | None, int]] = [(*row, 1) for row in direct]
    if GRAPH_QUERY_MAX_HOPS == 2:
        neighbors = {
            entity_id
            for fact, _, _, _ in direct
            for entity_id in (fact.subject_entity_id, fact.object_entity_id)
            if entity_id not in anchor_ids
        }
        second_hop = _fact_evidence(db, organization_uuid, document_ids, neighbors, max(limit * 12, 36))
        direct_ids = {fact.id for fact, _, _, _ in direct}
        rows.extend((*row, 2) for row in second_hop if row[0].id not in direct_ids)

    scores: dict[str, dict] = {}
    for fact, chunk, filename, ocr_provenance, hops in rows:
        chunk_id = str(chunk.id)
        score = 0.9 if hops == 1 else 0.68
        existing = scores.get(chunk_id)
        if existing and existing["score"] >= score:
            continue
        scores[chunk_id] = {
            "id": chunk_id,
            "score": score,
            "payload": {
                "chunk_id": chunk_id,
                "document_id": str(chunk.document_id),
                "filename": filename,
                "chunk_index": chunk.chunk_index,
                "content": chunk.parent_content or chunk.content,
                "matched_child_content": chunk.content,
                "parent_index": chunk.parent_index,
                "ocr_provenance": ocr_provenance,
            },
            "retrieval": {
                "method": "hybrid_graph",
                "graph_hops": hops,
                "graph_predicate": fact.predicate,
                "graph_fact_id": str(fact.id),
            },
        }
    return sorted(scores.values(), key=lambda item: item["score"], reverse=True)[:limit]
