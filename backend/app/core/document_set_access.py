from app.core.application_errors import ApplicationError
import uuid


from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app.models.document_permission import DocumentPermission
from app.models.document_set_permission import DocumentSetPermission
from app.models.document import Document
from app.models.document_set import DocumentSet, document_set_documents
from app.models.user import User

LEVELS = {"view": 1, "edit": 2, "manage": 3}


def accessible_set_ids(db: Session, user: User, minimum: str = "view") -> set[uuid.UUID] | None:
    if user.role == "admin":
        return set(db.scalars(select(DocumentSet.id).where(DocumentSet.organization_id == user.organization_id)).all())
    threshold = LEVELS[minimum]
    permitted_levels = [level for level, value in LEVELS.items() if value >= threshold]
    rows = db.execute(select(DocumentSetPermission.document_set_id, DocumentSetPermission.permission).where(DocumentSetPermission.user_id == user.id)).all()
    allowed = {set_id for set_id, level in rows if LEVELS[level] >= threshold}
    document_sets = db.scalars(
        select(document_set_documents.c.document_set_id)
        .join(Document, Document.id == document_set_documents.c.document_id)
        .join(DocumentPermission, DocumentPermission.document_id == Document.id)
        .where(
            Document.organization_id == user.organization_id,
            DocumentPermission.user_id == user.id,
            DocumentPermission.permission.in_(permitted_levels),
        )
        .distinct()
    ).all()
    return allowed.union(document_sets)


def document_access_predicate(user: User, minimum: str = "view"):
    """SQL predicate for effective document grants, including set inheritance."""
    if user.role == "admin":
        return Document.organization_id == user.organization_id
    permitted_levels = [level for level, value in LEVELS.items() if value >= LEVELS[minimum]]
    has_set_grant = exists(
        select(1)
        .select_from(document_set_documents)
        .join(DocumentSetPermission, DocumentSetPermission.document_set_id == document_set_documents.c.document_set_id)
        .where(
            document_set_documents.c.document_id == Document.id,
            DocumentSetPermission.user_id == user.id,
            DocumentSetPermission.permission.in_(permitted_levels),
        )
    )
    has_explicit_grants = exists(
        select(1).where(DocumentPermission.document_id == Document.id)
    )
    has_explicit_user_grant = exists(
        select(1).where(
            DocumentPermission.document_id == Document.id,
            DocumentPermission.user_id == user.id,
            DocumentPermission.permission.in_(permitted_levels),
        )
    )
    return and_(
        Document.organization_id == user.organization_id,
        or_(and_(has_set_grant, ~has_explicit_grants), has_explicit_user_grant),
    )


def require_knowledge_scope_access(db: Session, user: User, set_id: uuid.UUID) -> str:
    """Allow a document-only grant to open a set as a filtered document scope."""
    try:
        return require_set_access(db, user, set_id)
    except ApplicationError as exc:
        if exc.kind != "forbidden" or user.role == "admin":
            raise
    allowed_document = db.scalar(
        select(Document.id)
        .join(document_set_documents, document_set_documents.c.document_id == Document.id)
        .where(
            document_set_documents.c.document_set_id == set_id,
            Document.organization_id == user.organization_id,
            document_access_predicate(user),
        )
        .limit(1)
    )
    if allowed_document is None:
        raise ApplicationError(kind="forbidden", detail="View access to this knowledge set or one of its documents is required")
    return "view"


def require_set_access(db: Session, user: User, set_id: uuid.UUID, minimum: str = "view") -> str:
    if user.role == "admin":
        allowed = accessible_set_ids(db, user, minimum)
        if set_id not in allowed:
            raise ApplicationError(kind="forbidden", detail=f"{minimum.capitalize()} access to this knowledge set is required")
        return "manage"

    rows = db.execute(
        select(DocumentSetPermission.document_set_id, DocumentSetPermission.permission)
        .where(DocumentSetPermission.user_id == user.id)
    ).all()
    access_level = next((level for item_id, level in rows if item_id == set_id), None)
    if access_level is None or LEVELS[access_level] < LEVELS[minimum]:
        raise ApplicationError(kind="forbidden", detail=f"{minimum.capitalize()} access to this knowledge set is required")
    return access_level


def require_document_access(db: Session, user: User, document_id: uuid.UUID, minimum: str = "view") -> Document:
    document = db.scalar(select(Document).where(
        Document.id == document_id,
        Document.organization_id == user.organization_id,
        document_access_predicate(user, minimum),
    ))
    if document is None:
        exists_in_organization = db.scalar(select(Document.id).where(
            Document.id == document_id, Document.organization_id == user.organization_id
        ))
        if exists_in_organization is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
        raise ApplicationError(kind="forbidden", detail="You do not have access to this document")
    return document
