from app.core.application_errors import ApplicationError
import re


from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.document_set_access import require_document_access, require_set_access
from app.core.metadata_filters import filter_document_ids
from app.models.answer_feedback import AnswerRecord
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.user import User
from app.schemas.rag import Citation, RagRequest, RagResponse
from app.schemas.search import SearchHit
from app.services.openrouter import OpenRouterError
from app.services.operational_alerts import send_operational_alert
from app.services.operational_metrics import increment
from app.services.ports import ProviderFactoryPort
from app.services.qdrant import QdrantError
from app.services.provider_failures import provider_error
from app.services.retrieval import hybrid_search
from app.services.usage_tracking import record_usage
from app.services.transactions import commit_or_rollback


class RagService:
    """Application use case for source-grounded answers."""

    def __init__(self, db: Session, providers: ProviderFactoryPort):
        self.db = db
        self.providers = providers

    def answer(self, payload: RagRequest, user: User) -> RagResponse:
        if payload.document_id and (payload.document_set_id or payload.document_ids):
            raise ApplicationError(kind="validation_error", detail="Choose either a document or a document set scope")
        if payload.document_ids and not payload.document_set_id:
            raise ApplicationError(kind="validation_error", detail="Selected documents require a document set")
        if not payload.document_id and not payload.document_set_id:
            raise ApplicationError(kind="validation_error", detail="A permitted document or knowledge set is required")

        document_ids: list[str] | None = None
        if payload.document_id:
            require_document_access(self.db, user, payload.document_id)
        elif payload.document_set_id:
            require_set_access(self.db, user, payload.document_set_id)
            document_set = self.db.scalar(select(DocumentSet).where(DocumentSet.id == payload.document_set_id, DocumentSet.organization_id == user.organization_id))
            if document_set is None:
                raise ApplicationError(kind="not_found", detail="Document set not found")
            available_ids = set(self.db.scalars(select(Document.id).join(Document.document_sets).where(DocumentSet.id == payload.document_set_id, Document.status == "indexed")).all())
            available_ids = filter_document_ids(self.db, available_ids, payload.filters)
            if payload.document_ids:
                requested_ids = set(payload.document_ids)
                if requested_ids - available_ids:
                    raise ApplicationError(kind="validation_error", detail="One or more selected documents are unavailable or outside this set")
                document_ids = [str(item) for item in payload.document_ids]
            else:
                document_ids = [str(item) for item in available_ids]
        try:
            vector_store = self.providers.vector_store()
            vector_store.ensure_collection()
            points = hybrid_search(self.db, query=payload.question, limit=payload.limit, document_id=str(payload.document_id) if payload.document_id else None, document_ids=document_ids, vector_store=vector_store)
        except QdrantError as exc:
            increment("rag_failures_total", dependency="qdrant")
            send_operational_alert("qdrant-failure", "Vector store is unavailable", "A RAG request could not reach Qdrant. Check the Qdrant service and its network connection.")
            raise provider_error(exc) from exc

        sources = [SearchHit(score=point["score"], **point["payload"]) for point in points]
        if not sources:
            return self._save_no_results(payload, user)
        contexts = [source.model_dump(mode="json", exclude={"ocr_provenance"}) for source in sources]
        try:
            llm_result = self.providers.language_model().answer_with_usage(payload.question, contexts)
            answer = llm_result.content
            record_usage(self.db, user.id, payload.document_set_id, "rag_answer", llm_result)
        except OpenRouterError as exc:
            increment("model_failures_total", provider="openrouter")
            send_operational_alert("model-failure", "Model request failed", "A RAG request could not be completed by the configured model provider. Check provider status, credentials, quota, and request logs.")
            raise provider_error(exc) from exc

        answer, citation_ids = self._normalize_citations(answer, len(sources))
        citations = [Citation(id=index, chunk_id=source.chunk_id, document_id=source.document_id, filename=source.filename, chunk_index=source.chunk_index, excerpt=source.content, score=source.score, ocr_provenance=source.ocr_provenance) for index, source in enumerate(sources, start=1) if index in citation_ids]
        record = AnswerRecord(user_id=user.id, document_set_id=payload.document_set_id, question=payload.question, answer=answer, grounded=bool(citations), citation_count=len(citations))
        try:
            self.db.add(record)
            commit_or_rollback(self.db)
        except SQLAlchemyError as exc:
            raise ApplicationError(kind="internal_error", detail="Could not save the answer") from exc
        self.db.refresh(record)
        return RagResponse(response_id=record.id, question=payload.question, answer=answer, grounded=bool(citations), citations=citations, sources=sources)

    def _save_no_results(self, payload: RagRequest, user: User) -> RagResponse:
        message = "No relevant information was found in the indexed documents."
        record = AnswerRecord(user_id=user.id, document_set_id=payload.document_set_id, question=payload.question, answer=message, grounded=False, citation_count=0)
        try:
            self.db.add(record)
            commit_or_rollback(self.db)
        except SQLAlchemyError as exc:
            raise ApplicationError(kind="internal_error", detail="Could not save the answer") from exc
        self.db.refresh(record)
        return RagResponse(response_id=record.id, question=payload.question, answer=message, grounded=False, citations=[], sources=[])

    @staticmethod
    def _normalize_citations(answer: str, source_count: int) -> tuple[str, set[int]]:
        used: set[int] = set()

        def replace(match: re.Match[str]) -> str:
            number = int(match.group(1))
            if 1 <= number <= source_count:
                used.add(number)
                return f"[{number}]"
            return ""

        normalized = re.sub(r"\[\s*(?:Source\s*)?(\d+)\s*\]", replace, answer, flags=re.IGNORECASE)
        return re.sub(r"[ \t]{2,}", " ", normalized).strip(), used
