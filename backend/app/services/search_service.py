from app.core.application_errors import ApplicationError
from app.services.transactions import transaction
from app.services.provider_factory import get_language_model
import re
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.document_set_access import require_document_access, require_set_access
from app.core.metadata_filters import filter_document_ids
from app.repositories.knowledge_scope_repository import KnowledgeScopeRepository
from app.models.user import User
from app.schemas.search import PipelineTraceResponse, PlaygroundHit, PlaygroundResponse, RetrievalDiagnostics, RetrieverComparisonRequest, RetrieverComparisonResponse, RetrieverVariantResult, SearchHit, SearchRequest, SearchResponse, TraceCitation, TraceStage, UsageMetrics
from app.services.provider_errors import LanguageModelError
from app.services.provider_errors import VectorStoreError
from app.services.retrieval import hybrid_search
from app.services.usage_tracking import record_usage


def _playground_hit(point: dict) -> PlaygroundHit:
    meta = point.get("retrieval", {})
    data = dict(point["payload"])
    data.setdefault("parent_index", 0)
    data.setdefault("matched_child_content", data["content"])
    data["score"] = point["score"]
    data["diagnostics"] = RetrievalDiagnostics(
        method=meta.get("method", "hybrid"),
        vector_rank=meta.get("vector_rank"),
        bm25_rank=meta.get("bm25_rank"),
        hybrid_score=meta.get("hybrid_score", point["score"]),
        reranker_score=point["score"],
        term_coverage=meta.get("term_coverage", 0),
        phrase_match=meta.get("phrase_match", False),
        expanded_to_parent=meta.get("expanded_to_parent", False),
    )
    return PlaygroundHit(**data)


def _scope(payload: SearchRequest, db: Session, user: User) -> tuple[str | None, list[str] | None, int]:
    if payload.document_id and (payload.document_set_id or payload.document_ids): raise ApplicationError(kind="validation_error", detail="Choose either a document or a document-set scope")
    if payload.document_ids and not payload.document_set_id: raise ApplicationError(kind="validation_error", detail="Selected documents require a document set")
    if not payload.document_id and not payload.document_set_id: raise ApplicationError(kind="validation_error", detail="A permitted document or knowledge set is required")
    if payload.document_id:
        require_document_access(db, user, payload.document_id)
        return str(payload.document_id), None, 1
    assert payload.document_set_id is not None
    if KnowledgeScopeRepository(db).get_set(payload.document_set_id, user.organization_id) is None: raise ApplicationError(kind="not_found", detail="Document set not found")
    require_set_access(db, user, payload.document_set_id)
    available = KnowledgeScopeRepository(db).indexed_document_ids(payload.document_set_id)
    available = filter_document_ids(db, available, payload.filters)
    if payload.document_ids:
        requested = set(payload.document_ids)
        if requested - available: raise ApplicationError(kind="validation_error", detail="Selected documents are unavailable or outside this set")
        available = requested
    return None, [str(value) for value in available], len(available)


def semantic_search(payload: SearchRequest, db: Session, user: User):
    document_id, document_ids, _ = _scope(payload, db, user)
    try:
        # Removed: client = get_vector_store(); client.ensure_collection()
        points = hybrid_search(db, query=payload.query, limit=payload.limit, document_id=document_id, document_ids=document_ids)
    except VectorStoreError as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    return SearchResponse(query=payload.query, results=[SearchHit(score=point["score"], **point["payload"]) for point in points])


def retrieval_playground(payload: SearchRequest, db: Session, user: User):
    document_id, document_ids, scoped_count = _scope(payload, db, user)
    # Removed: get_vector_store().ensure_collection()
    try:
        points = hybrid_search(db, payload.query, payload.limit, document_id=document_id, document_ids=document_ids)
    except VectorStoreError as exc: raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    results = [_playground_hit(point) for point in points]
    return PlaygroundResponse(query=payload.query, scoped_document_count=scoped_count, result_count=len(results), results=results)


def pipeline_trace(payload: SearchRequest, db: Session, user: User):
    total_started = perf_counter(); scope_started = perf_counter()
    document_id, document_ids, scoped_count = _scope(payload, db, user)
    scope_ms = round((perf_counter() - scope_started) * 1000, 2)
    metrics: dict = {}
    # Removed: get_vector_store().ensure_collection()
    try:
        points = hybrid_search(db, payload.query, payload.limit, document_id=document_id, document_ids=document_ids, trace=metrics)
    except VectorStoreError as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    results = [_playground_hit(point) for point in points]
    answer_started = perf_counter()
    if results:
        try:
            llm_result = get_language_model().answer_with_usage(payload.query, [result.model_dump(mode="json") for result in results])
            answer = llm_result.content

        except LanguageModelError as exc:
            raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    else:
        answer = "No relevant information was found in the indexed documents."; llm_result = None
    answer_ms = round((perf_counter() - answer_started) * 1000, 2)
    used = {int(value) for value in re.findall(r"\[\s*(?:Source\s*)?(\d+)\s*\]", answer, flags=re.IGNORECASE) if 1 <= int(value) <= len(results)} if results else set()
    answer = re.sub(r"\[\s*Source\s*(\d+)\s*\]", r"[\1]", answer, flags=re.IGNORECASE)
    citations = [TraceCitation(id=index, chunk_id=result.chunk_id, filename=result.filename) for index, result in enumerate(results, 1) if index in used]
    stages = [
        TraceStage(key="question", duration_ms=scope_ms, input_count=1, output_count=scoped_count),
        TraceStage(key="retrieval", duration_ms=metrics.get("vector_ms", 0) + metrics.get("bm25_ms", 0), input_count=scoped_count, output_count=metrics.get("fused_count", 0)),
        TraceStage(key="rerank", duration_ms=metrics.get("rerank_ms", 0), input_count=metrics.get("fused_count", 0), output_count=len(results)),
        TraceStage(key="answer", duration_ms=answer_ms, input_count=len(results), output_count=len(citations)),
    ]
    if llm_result is not None:
        with transaction(db):
            record_usage(db, user.id, payload.document_set_id, "pipeline_trace", llm_result)
    return PipelineTraceResponse(question=payload.query, answer=answer, grounded=bool(citations), total_duration_ms=round((perf_counter() - total_started) * 1000, 2), stages=stages, results=results, citations=citations, usage=UsageMetrics(**llm_result.__dict__) if llm_result else None)


def _run_variant(db: Session, payload: RetrieverComparisonRequest, document_id: str | None, document_ids: list[str] | None, config, user: User, usage_results) -> RetrieverVariantResult:
    started = perf_counter()
    points = hybrid_search(db, payload.query, config.top_k, document_id=document_id, document_ids=document_ids, vector_weight=config.vector_weight, bm25_weight=config.bm25_weight, use_reranker=config.use_reranker)
    results = [_playground_hit(point) for point in points]
    if results:
        llm_result = get_language_model().answer_with_usage(payload.query, [result.model_dump(mode="json") for result in results])
        answer = llm_result.content
        usage_results.append(llm_result)
    else:
        answer = "No relevant information was found in the indexed documents."; llm_result = None
    used = {int(value) for value in re.findall(r"\[\s*(?:Source\s*)?(\d+)\s*\]", answer, flags=re.IGNORECASE) if 1 <= int(value) <= len(results)} if results else set()
    answer = re.sub(r"\[\s*Source\s*(\d+)\s*\]", r"[\1]", answer, flags=re.IGNORECASE)
    citations = [TraceCitation(id=index, chunk_id=result.chunk_id, filename=result.filename) for index, result in enumerate(results, 1) if index in used]
    return RetrieverVariantResult(config=config, duration_ms=round((perf_counter() - started) * 1000, 2), answer=answer, grounded=bool(citations), results=results, citations=citations, usage=UsageMetrics(**llm_result.__dict__) if llm_result else None)


def compare_retrievers(payload: RetrieverComparisonRequest, db: Session, user: User):
    if payload.config_a.vector_weight + payload.config_a.bm25_weight <= 0 or payload.config_b.vector_weight + payload.config_b.bm25_weight <= 0:
        raise ApplicationError(kind="validation_error", detail="At least one retrieval weight must be greater than zero")
    document_id, document_ids, _ = _scope(payload, db, user)
    # Removed: get_vector_store().ensure_collection()
    usage_results = []
    try:
        variant_a = _run_variant(db, payload, document_id, document_ids, payload.config_a, user, usage_results)
        variant_b = _run_variant(db, payload, document_id, document_ids, payload.config_b, user, usage_results)
    except (VectorStoreError, LanguageModelError) as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    ranks_a = {str(item.chunk_id): index for index, item in enumerate(variant_a.results, 1)}
    ranks_b = {str(item.chunk_id): index for index, item in enumerate(variant_b.results, 1)}
    common = ranks_a.keys() & ranks_b.keys()
    with transaction(db):
        for result in usage_results:
            record_usage(db, user.id, payload.document_set_id, "retriever_compare", result)
    return RetrieverComparisonResponse(question=payload.query, overlap_count=len(common), rank_changes={chunk_id: ranks_a[chunk_id] - ranks_b[chunk_id] for chunk_id in common}, variant_a=variant_a, variant_b=variant_b)
