import uuid
from datetime import datetime, timezone

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.auth_session import AuthSession
from app.models.document_set import DocumentSet
from app.models.document_set_permission import DocumentSetPermission
from app.models.document import Document
from app.models.document_permission import DocumentPermission
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_members(self, organization_id: uuid.UUID):
        rank = case((User.role == "admin", 0), else_=1)
        return self.db.scalars(select(User).where(User.organization_id == organization_id)
                               .order_by(rank, User.created_at.asc(), User.id.asc())).all()

    def get_member(self, user_id: uuid.UUID, organization_id: uuid.UUID, *, lock: bool = False):
        statement = select(User).where(User.id == user_id, User.organization_id == organization_id)
        return self.db.scalar(statement.with_for_update() if lock else statement)

    def permission_rows(self, user_id: uuid.UUID, organization_id: uuid.UUID):
        return self.db.execute(select(DocumentSetPermission, DocumentSet.name)
            .join(DocumentSet, DocumentSet.id == DocumentSetPermission.document_set_id)
            .where(DocumentSetPermission.user_id == user_id, DocumentSet.organization_id == organization_id)
            .order_by(DocumentSet.name)).all()

    def existing_set_ids(self, ids, organization_id):
        return set(self.db.scalars(select(DocumentSet.id).where(
            DocumentSet.id.in_(ids), DocumentSet.organization_id == organization_id)).all()) if ids else set()

    def document_catalog(self, user_id, organization_id, offset, limit, search):
        statement = select(Document).options(selectinload(Document.document_sets)).where(
            Document.organization_id == organization_id
        )
        count_statement = select(func.count(Document.id)).where(Document.organization_id == organization_id)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(Document.filename.ilike(pattern))
            count_statement = count_statement.where(Document.filename.ilike(pattern))
        total = self.db.scalar(count_statement) or 0
        documents = self.db.scalars(statement.order_by(Document.filename, Document.id).offset(offset).limit(limit)).all()
        ids = [document.id for document in documents]
        current = dict(self.db.execute(select(DocumentPermission.document_id, DocumentPermission.permission).where(
            DocumentPermission.user_id == user_id, DocumentPermission.document_id.in_(ids)
        )).all()) if ids else {}
        restricted = set(self.db.scalars(select(DocumentPermission.document_id).where(
            DocumentPermission.document_id.in_(ids)
        ).distinct()).all()) if ids else set()
        permissions = self.document_permission_rows(user_id, organization_id)
        return documents, current, restricted, total, permissions

    def document_permission_rows(self, user_id, organization_id):
        return self.db.execute(
            select(DocumentPermission, Document.filename)
            .join(Document, Document.id == DocumentPermission.document_id)
            .where(DocumentPermission.user_id == user_id, Document.organization_id == organization_id)
            .order_by(Document.filename)
        ).all()

    def existing_document_ids(self, ids, organization_id):
        return set(self.db.scalars(select(Document.id).where(
            Document.id.in_(ids), Document.organization_id == organization_id
        )).all()) if ids else set()

    def replace_permissions(self, user_id, items):
        self.db.execute(delete(DocumentSetPermission).where(DocumentSetPermission.user_id == user_id))
        self.db.add_all(items)

    def replace_document_permissions(self, user_id, items):
        self.db.execute(delete(DocumentPermission).where(DocumentPermission.user_id == user_id))
        self.db.add_all(items)

    def revoke_sessions(self, user_id):
        self.db.execute(update(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc)
        ).values(revoked_at=datetime.now(timezone.utc)))

    def add(self, item):
        self.db.add(item)

    def delete(self, item):
        self.db.delete(item)

    def refresh(self, item):
        self.db.refresh(item)
