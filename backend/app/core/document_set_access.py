from app.core.application_errors import ApplicationError
import uuid


from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_set_permission import DocumentSetPermission
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.user import User

LEVELS = {"view": 1, "edit": 2, "manage": 3}


def accessible_set_ids(db: Session, user: User, minimum: str = "view") -> set[uuid.UUID] | None:
    if user.role == "admin":
        return set(db.scalars(select(DocumentSet.id).where(DocumentSet.organization_id == user.organization_id)).all())
    threshold = LEVELS[minimum]
    rows = db.execute(select(DocumentSetPermission.document_set_id, DocumentSetPermission.permission).where(DocumentSetPermission.user_id == user.id)).all()
    return {set_id for set_id, level in rows if LEVELS[level] >= threshold}


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
    document = db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == user.organization_id))
    if document is None:
        raise ApplicationError(kind="not_found", detail="Document not found")
    allowed = accessible_set_ids(db, user, minimum) or set()
    memberships = {item.id for item in document.document_sets}
    if not memberships.intersection(allowed):
        raise ApplicationError(kind="forbidden", detail="You do not have access to this document")
    return document
