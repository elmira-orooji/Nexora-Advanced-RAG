from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.document_set import DocumentSet, document_set_documents
from app.models.document_set_permission import DocumentSetPermission


class DocumentSetRepository:
    def __init__(self, db):
        self.db = db

    def get(self, set_id, organization_id, *, with_documents=False):
        statement = select(DocumentSet).where(DocumentSet.id == set_id, DocumentSet.organization_id == organization_id)
        if with_documents:
            statement = statement.options(selectinload(DocumentSet.documents))
        return self.db.scalar(statement)

    def list_counts(self, organization_id, allowed):
        statement = (select(DocumentSet, func.count(Document.id), func.count(Document.id).filter(Document.status == "indexed"))
                     .outerjoin(document_set_documents, DocumentSet.id == document_set_documents.c.document_set_id)
                     .outerjoin(Document, Document.id == document_set_documents.c.document_id)
                     .group_by(DocumentSet.id).where(DocumentSet.organization_id == organization_id)
                     .order_by(DocumentSet.updated_at.desc()))
        if allowed is not None:
            statement = statement.where(DocumentSet.id.in_(allowed))
        return self.db.execute(statement).all()

    def permissions(self, user_id):
        return dict(self.db.execute(select(DocumentSetPermission.document_set_id, DocumentSetPermission.permission).where(
            DocumentSetPermission.user_id == user_id)).all())

    def add(self, item):
        self.db.add(item)

    def delete(self, item):
        self.db.delete(item)

    def refresh(self, item):
        self.db.refresh(item)
