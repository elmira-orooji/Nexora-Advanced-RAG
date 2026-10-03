import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_set import DocumentSet


class KnowledgeScopeRepository:
    """Queries shared by answer workflows; access policies stay in services."""

    def __init__(self, db: Session):
        self.db = db

    def get_set(self, set_id: uuid.UUID, organization_id: uuid.UUID) -> DocumentSet | None:
        return self.db.scalar(select(DocumentSet).where(
            DocumentSet.id == set_id, DocumentSet.organization_id == organization_id
        ))

    def indexed_document_ids(self, set_id: uuid.UUID) -> set[uuid.UUID]:
        statement = select(Document.id).join(Document.document_sets).where(
            DocumentSet.id == set_id, Document.status == "indexed"
        )
        return set(self.db.scalars(statement).all())
