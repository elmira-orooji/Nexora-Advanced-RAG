from app.core.application_errors import ApplicationError
from app.services.provider_factory import get_vector_store, get_language_model
import re

from sqlalchemy.orm import Session
from app.services.transactions import transaction
from app.repositories.answer_repository import AnswerRepository
from app.repositories.knowledge_scope_repository import KnowledgeScopeRepository

from app.core.document_set_access import require_set_access
from app.core.metadata_filters import filter_document_ids
from app.models.answer_feedback import AnswerRecord
from app.models.user import User
from app.schemas.rag import Citation
from app.schemas.research import ResearchRequest, ResearchResponse, ResearchStep
from app.schemas.search import SearchHit
from app.services.provider_errors import LanguageModelError
from app.services.provider_errors import VectorStoreError
from app.services.retrieval import hybrid_search

class ResearchService:
    """Coordinates access, retrieval, report generation and persistence."""

    def __init__(self, db: Session):
        self.db = db
        self.answers = AnswerRepository(db)
        self.scopes = KnowledgeScopeRepository(db)

    def run(self, payload: ResearchRequest, user: User) -> ResearchResponse:
        db = self.db
        require_set_access(db, user, payload.document_set_id)
        if self.scopes.get_set(payload.document_set_id, user.organization_id) is None: raise ApplicationError(kind="not_found", detail="Document set not found")
        available = self.scopes.indexed_document_ids(payload.document_set_id)
        available = filter_document_ids(db, available, payload.filters)
        if payload.document_ids:
            requested = set(payload.document_ids)
            if requested - available: raise ApplicationError(kind="validation_error", detail="Selected documents are unavailable or outside this set")
            document_ids = [str(value) for value in payload.document_ids]
        else: document_ids = [str(value) for value in available]
        if not document_ids: raise ApplicationError(kind="conflict", detail="This knowledge set has no indexed documents")
        client = get_language_model()
        try: queries = client.research_plan(payload.question, payload.max_steps)
        except LanguageModelError: queries = [payload.question, f"Evidence and details about: {payload.question}"]
        try:
            qdrant = get_vector_store(); qdrant.ensure_collection(); unique: dict[str, SearchHit] = {}; steps = []
            for query in queries:
                points = hybrid_search(db, query=query, limit=5, document_ids=document_ids)
                steps.append(ResearchStep(query=query, evidence_count=len(points)))
                for point in points:
                    hit = SearchHit(score=point["score"], **point["payload"]); key = str(hit.chunk_id)
                    if key not in unique or hit.score > unique[key].score: unique[key] = hit
        except VectorStoreError as exc: raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
        sources = sorted(unique.values(), key=lambda value: value.score, reverse=True)[:12]
        if not sources:
            message = "No sufficient evidence was found for this research question."
            record = AnswerRecord(user_id=user.id, document_set_id=payload.document_set_id, question=payload.question, answer=message, grounded=False, citation_count=0)
            self._save_answer(record)
            return ResearchResponse(response_id=record.id, question=payload.question, answer=message, grounded=False, citations=[], steps=steps, evidence_reviewed=0)
        instructions = "Write a structured research report with a short executive summary, findings, limitations, and conclusion. Synthesize across sources instead of listing them. Every factual claim must retain inline [Source N] citations. Explicitly state uncertainty or conflicting evidence."
        try: answer = client.answer(payload.question, [source.model_dump(mode="json", exclude={"ocr_provenance"}) for source in sources], instructions=instructions)
        except LanguageModelError as exc: raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
        used: set[int] = set()
        def normalize(match: re.Match[str]) -> str:
            number = int(match.group(1))
            if 1 <= number <= len(sources): used.add(number); return f"[{number}]"
            return ""
        answer = re.sub(r"\[\s*(?:Source\s*)?(\d+)\s*\]", normalize, answer, flags=re.I).strip()
        citations = [Citation(id=index, chunk_id=source.chunk_id, document_id=source.document_id, filename=source.filename, chunk_index=source.chunk_index, excerpt=source.content, score=source.score, ocr_provenance=source.ocr_provenance) for index, source in enumerate(sources, 1) if index in used]
        record = AnswerRecord(user_id=user.id, document_set_id=payload.document_set_id, question=payload.question, answer=answer, grounded=bool(citations), citation_count=len(citations))
        self._save_answer(record)
        return ResearchResponse(response_id=record.id, question=payload.question, answer=answer, grounded=bool(citations), citations=citations, steps=steps, evidence_reviewed=len(sources))

    def _save_answer(self, record: AnswerRecord) -> None:
        with transaction(self.db):
            self.answers.add(record)
        self.answers.refresh(record)
