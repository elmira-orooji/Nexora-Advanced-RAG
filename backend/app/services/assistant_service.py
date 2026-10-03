from app.core.application_errors import ApplicationError
from app.services.transactions import transaction
from app.services.provider_factory import get_vector_store, get_language_model
import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.document_set_access import accessible_set_ids
from app.models.assistant import Assistant
from app.models.answer_feedback import AnswerRecord
from app.models.document_set import DocumentSet
from app.models.user import User
from app.schemas.assistant import AssistantAnswerRequest, AssistantCreate, AssistantResponse, AssistantUpdate
from app.schemas.rag import Citation, RagResponse
from app.schemas.search import SearchHit
from app.services.provider_errors import LanguageModelError
from app.services.provider_errors import VectorStoreError
from app.services.retrieval import hybrid_search
from app.repositories.assistant_repository import AssistantRepository


def _get(db: Session, assistant_id: uuid.UUID, user: User) -> Assistant:
    item = AssistantRepository(db).get(assistant_id, user.organization_id)
    if item is None:
        raise ApplicationError(kind="not_found", detail="Assistant not found")
    return item


def _sets(db: Session, ids: list[uuid.UUID], user: User) -> list[DocumentSet]:
    if not ids:
        return []
    items = AssistantRepository(db).sets(ids, user.organization_id)
    if len(items) != len(set(ids)):
        raise ApplicationError(kind="validation_error", detail="One or more knowledge sets do not exist")
    return items


def _response(item: Assistant, allowed_set_ids: set[uuid.UUID] | None = None) -> AssistantResponse:
    visible_sets = item.document_sets if allowed_set_ids is None else [value for value in item.document_sets if value.id in allowed_set_ids]
    return AssistantResponse(
        id=item.id, name=item.name, description=item.description, instructions=item.instructions,
        is_active=item.is_active, created_by_id=item.created_by_id,
        model_id=item.model_id, answer_mode=item.answer_mode,
        document_set_ids=[value.id for value in visible_sets],
        document_set_names=[value.name for value in visible_sets],
        created_at=item.created_at, updated_at=item.updated_at,
    )


def available_models(user: User):
    try:
        return get_language_model().list_models()
    except LanguageModelError as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc


def list_assistants(db: Session, user: User):
    items = AssistantRepository(db).list(user.organization_id, active_only=user.role != "admin")
    allowed = accessible_set_ids(db, user)
    if user.role != "admin" and allowed is not None:
        items = [item for item in items if any(value.id in allowed for value in item.document_sets)]
    return [_response(item, allowed) for item in items]


def create_assistant(payload: AssistantCreate, db: Session, user: User):
    item = Assistant(organization_id=user.organization_id, name=payload.name.strip(), description=payload.description.strip() if payload.description else None,
                     instructions=payload.instructions.strip(), is_active=payload.is_active, created_by_id=user.id,
                     model_id=payload.model_id, answer_mode=payload.answer_mode)
    item.document_sets = _sets(db, payload.document_set_ids, user)
    try:
        with transaction(db):
            AssistantRepository(db).add(item)
        AssistantRepository(db).refresh(item)
    except IntegrityError as exc:
        db.rollback(); raise ApplicationError(kind="conflict", detail="An assistant with this name already exists") from exc
    return _response(_get(db, item.id, user))


def update_assistant(assistant_id: uuid.UUID, payload: AssistantUpdate, db: Session, user: User):
    item = _get(db, assistant_id, user)
    try:
        with transaction(db):
            for field in ("name", "description", "instructions", "is_active"):
                if field in payload.model_fields_set:
                    value = getattr(payload, field)
                    if isinstance(value, str): value = value.strip()
                    setattr(item, field, value or None if field == "description" else value)
            if payload.document_set_ids is not None:
                item.document_sets = _sets(db, payload.document_set_ids, user)
            if "model_id" in payload.model_fields_set:
                item.model_id = payload.model_id
            if payload.answer_mode is not None:
                item.answer_mode = payload.answer_mode
    except IntegrityError as exc:
        db.rollback(); raise ApplicationError(kind="conflict", detail="An assistant with this name already exists") from exc
    return _response(_get(db, item.id, user))


def delete_assistant(assistant_id: uuid.UUID, db: Session, user: User):
    item = _get(db, assistant_id, user)
    with transaction(db):
        AssistantRepository(db).delete(item)


def answer_with_assistant(assistant_id: uuid.UUID, payload: AssistantAnswerRequest, db: Session, user: User):
    item = _get(db, assistant_id, user)
    if not item.is_active:
        raise ApplicationError(kind="conflict", detail="Assistant is inactive")
    set_ids = [value.id for value in item.document_sets]
    allowed = accessible_set_ids(db, user)
    if allowed is not None:
        set_ids = [value for value in set_ids if value in allowed]
        if not set_ids and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="You do not have access to this assistant's knowledge")
    document_ids = AssistantRepository(db).indexed_document_ids(set_ids) if set_ids else []
    try:
        points = []
        if document_ids:
            qdrant = get_vector_store(); qdrant.ensure_collection()
            points = hybrid_search(db, payload.question, payload.limit, document_ids=document_ids)
    except VectorStoreError as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    sources = [SearchHit(score=point["score"], **point["payload"]) for point in points]
    if not sources and item.answer_mode != "hybrid":
        message = "No relevant information was found in this assistant's knowledge."
        record = AnswerRecord(user_id=user.id, assistant_id=item.id, question=payload.question, answer=message, grounded=False, citation_count=0)
        with transaction(db):
            AssistantRepository(db).add(record)
        AssistantRepository(db).refresh(record)
        return RagResponse(response_id=record.id, question=payload.question, answer=message, grounded=False, citations=[], sources=[])
    try:
        answer = get_language_model(model=item.model_id).answer(payload.question, [source.model_dump(mode="json", exclude={"ocr_provenance"}) for source in sources], instructions=item.instructions, hybrid=item.answer_mode == "hybrid")
    except LanguageModelError as exc:
        raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
    used = set()
    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if 1 <= number <= len(sources): used.add(number); return f"[{number}]"
        return ""
    answer = re.sub(r"\[\s*(?:Source\s*)?(\d+)\s*\]", replace, answer, flags=re.I).strip()
    citations = [Citation(id=index, chunk_id=source.chunk_id, document_id=source.document_id, filename=source.filename,
                          chunk_index=source.chunk_index, excerpt=source.content, score=source.score, ocr_provenance=source.ocr_provenance)
                 for index, source in enumerate(sources, 1) if index in used]
    record = AnswerRecord(user_id=user.id, assistant_id=item.id, question=payload.question, answer=answer, grounded=bool(citations), citation_count=len(citations))
    with transaction(db):
        AssistantRepository(db).add(record)
    AssistantRepository(db).refresh(record)
    basis = ("hybrid" if citations else "general") if item.answer_mode == "hybrid" else "sources"
    return RagResponse(response_id=record.id, question=payload.question, answer=answer, grounded=bool(citations), citations=citations, sources=sources, answer_basis=basis)
