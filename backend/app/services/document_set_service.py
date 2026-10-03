from app.core.application_errors import ApplicationError
from app.services.transactions import transaction
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.document_set_access import accessible_set_ids, require_document_access, require_set_access
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.repositories.document_set_repository import DocumentSetRepository
from app.repositories.document_repository import DocumentRepository
from app.models.user import User
from app.schemas.document_set import (
    DocumentMembershipRequest,
    DocumentSetCreate,
    DocumentSetDetail,
    DocumentSetResponse,
    DocumentSetUpdate,
)


def _get_set(db: Session, set_id: uuid.UUID, user: User, with_documents: bool = False) -> DocumentSet:
    document_set = DocumentSetRepository(db).get(set_id, user.organization_id, with_documents=with_documents)
    if document_set is None:
        raise ApplicationError(kind="not_found", detail="Document set not found")
    return document_set


def _response(document_set: DocumentSet, document_count: int, indexed_count: int, access_level: str) -> DocumentSetResponse:
    return DocumentSetResponse(
        id=document_set.id,
        name=document_set.name,
        description=document_set.description,
        created_by_id=document_set.created_by_id,
        document_count=document_count,
        indexed_document_count=indexed_count,
        access_level=access_level,
        child_chunk_size=document_set.child_chunk_size,
        chunk_overlap=document_set.chunk_overlap,
        parent_chunk_size=document_set.parent_chunk_size,
        created_at=document_set.created_at,
        updated_at=document_set.updated_at,
    )


def list_document_sets(
    db: Session,
    user: User,
):
    allowed = accessible_set_ids(db, user)
    rows = DocumentSetRepository(db).list_counts(user.organization_id, allowed)
    permission_map = {} if user.role == "admin" else DocumentSetRepository(db).permissions(user.id)
    return [_response(item, total, indexed, "manage" if user.role == "admin" else permission_map[item.id]) for item, total, indexed in rows]


def create_document_set(
    payload: DocumentSetCreate,
    db: Session,
    user: User,
):
    item = DocumentSet(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        created_by_id=user.id,
        organization_id=user.organization_id,
        child_chunk_size=payload.child_chunk_size,
        chunk_overlap=payload.chunk_overlap,
        parent_chunk_size=payload.parent_chunk_size,
    )
    try:
        with transaction(db):
            DocumentSetRepository(db).add(item)
        DocumentSetRepository(db).refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise ApplicationError(kind="conflict", detail="A document set with this name already exists") from exc
    return _response(item, 0, 0, "manage")


def get_document_set(
    set_id: uuid.UUID,
    db: Session,
    user: User,
):
    access_level = require_set_access(db, user, set_id)
    item = _get_set(db, set_id, user, with_documents=True)
    return DocumentSetDetail(
        **_response(item, len(item.documents), sum(doc.status == "indexed" for doc in item.documents), access_level).model_dump(),
        documents=item.documents,
    )


def update_document_set(
    set_id: uuid.UUID,
    payload: DocumentSetUpdate,
    db: Session,
    user: User,
):
    access_level = require_set_access(db, user, set_id, "manage")
    item = _get_set(db, set_id, user, with_documents=True)
    try:
        with transaction(db):
            if payload.name is not None:
                item.name = payload.name.strip()
            if "description" in payload.model_fields_set:
                item.description = payload.description.strip() if payload.description else None
            for field in ("child_chunk_size", "chunk_overlap", "parent_chunk_size"):
                value = getattr(payload, field)
                if value is not None:
                    setattr(item, field, value)
            if item.chunk_overlap >= item.child_chunk_size or item.parent_chunk_size < item.child_chunk_size:
                raise ApplicationError(kind="validation_error", detail="Invalid chunking settings")
        DocumentSetRepository(db).refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise ApplicationError(kind="conflict", detail="A document set with this name already exists") from exc
    return _response(item, len(item.documents), sum(doc.status == "indexed" for doc in item.documents), access_level)


def delete_document_set(
    set_id: uuid.UUID,
    db: Session,
    user: User,
):
    require_set_access(db, user, set_id, "manage")
    item = _get_set(db, set_id, user)
    with transaction(db):
        DocumentSetRepository(db).delete(item)


def add_document_to_set(
    set_id: uuid.UUID,
    payload: DocumentMembershipRequest,
    db: Session,
    user: User,
):
    access_level = require_set_access(db, user, set_id, "edit")
    item = _get_set(db, set_id, user, with_documents=True)
    if user.role == "admin":
        # Organization admins may also organize documents not yet in any set.
        document = DocumentRepository(db).get_document(payload.document_id, user.organization_id)
        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
    else:
        # Attaching a document grants the destination's members access to it.
        document = require_document_access(db, user, payload.document_id, "manage")
    if all(existing.id != document.id for existing in item.documents):
        with transaction(db):
            item.documents.append(document)
        DocumentSetRepository(db).refresh(item)
    return DocumentSetDetail(
        **_response(item, len(item.documents), sum(doc.status == "indexed" for doc in item.documents), access_level).model_dump(),
        documents=item.documents,
    )


def remove_document_from_set(
    set_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session,
    user: User,
):
    access_level = require_set_access(db, user, set_id, "edit")
    item = _get_set(db, set_id, user, with_documents=True)
    document = next((doc for doc in item.documents if doc.id == document_id), None)
    if document is None:
        raise ApplicationError(kind="not_found", detail="Document is not in this set")
    with transaction(db):
        item.documents.remove(document)
    return DocumentSetDetail(
        **_response(item, len(item.documents), sum(doc.status == "indexed" for doc in item.documents), access_level).model_dump(),
        documents=item.documents,
    )
