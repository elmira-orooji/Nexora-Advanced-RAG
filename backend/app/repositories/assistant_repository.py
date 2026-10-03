from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.assistant import Assistant
from app.models.document import Document
from app.models.document_set import DocumentSet


class AssistantRepository:
    def __init__(self, db):
        self.db = db

    def get(self, assistant_id, organization_id):
        return self.db.scalar(select(Assistant).options(selectinload(Assistant.document_sets)).where(
            Assistant.id == assistant_id, Assistant.organization_id == organization_id))

    def sets(self, ids, organization_id):
        return list(self.db.scalars(select(DocumentSet).where(
            DocumentSet.id.in_(set(ids)), DocumentSet.organization_id == organization_id)).all())

    def list(self, organization_id, *, active_only=False):
        statement = select(Assistant).options(selectinload(Assistant.document_sets)).where(
            Assistant.organization_id == organization_id).order_by(Assistant.updated_at.desc())
        if active_only:
            statement = statement.where(Assistant.is_active.is_(True))
        return list(self.db.scalars(statement).all())

    def indexed_document_ids(self, set_ids):
        return [str(value) for value in self.db.scalars(select(Document.id).join(Document.document_sets).where(
            DocumentSet.id.in_(set_ids), Document.status == "indexed").distinct()).all()]

    def add(self, item):
        self.db.add(item)

    def delete(self, item):
        self.db.delete(item)

    def refresh(self, item):
        self.db.refresh(item)
