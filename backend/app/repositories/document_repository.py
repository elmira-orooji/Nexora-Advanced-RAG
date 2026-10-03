from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.processing_job import ProcessingJob


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_document(self, document_id, organization_id=None, *, with_chunks=False, lock=False):
        statement = select(Document).where(Document.id == document_id)
        if organization_id is not None:
            statement = statement.where(Document.organization_id == organization_id)
        if with_chunks:
            statement = statement.options(selectinload(Document.chunks))
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(statement)

    def get_set(self, set_id, organization_id):
        return self.db.scalar(select(DocumentSet).where(
            DocumentSet.id == set_id, DocumentSet.organization_id == organization_id))

    def list_documents(self, organization_id, set_id, offset, limit):
        statement = select(Document).where(Document.organization_id == organization_id)
        if set_id is not None:
            statement = statement.join(Document.document_sets).where(DocumentSet.id == set_id)
        return self.db.scalars(statement.order_by(Document.created_at.desc()).offset(offset).limit(limit)).all()

    def get_chunk(self, document_id, chunk_id, organization_id):
        return self.db.scalar(select(Chunk).join(Document, Document.id == Chunk.document_id).where(
            Chunk.id == chunk_id, Chunk.document_id == document_id, Document.organization_id == organization_id))

    def get_source_chunk(self, document_id, chunk_id):
        return self.db.scalar(select(Chunk).where(
            Chunk.id == chunk_id, Chunk.document_id == document_id, Chunk.is_active.is_(True)))

    def get_job(self, document_id, *, lock=False):
        statement = select(ProcessingJob).where(ProcessingJob.document_id == document_id)
        return self.db.scalar(statement.with_for_update() if lock else statement)

    def lock_job_then_document(self, document_id):
        self.db.scalar(select(ProcessingJob.id).where(ProcessingJob.document_id == document_id).with_for_update())
        self.db.scalar(select(Document.id).where(Document.id == document_id).with_for_update())

    def delete_jobs(self, document_id):
        self.db.execute(delete(ProcessingJob).where(ProcessingJob.document_id == document_id))

    def find_idempotent(self, organization_id, key):
        return self.db.scalar(select(Document).where(
            Document.organization_id == organization_id, Document.idempotency_key == key))

    def add(self, item):
        self.db.add(item)

    def delete(self, item):
        self.db.delete(item)

    def flush(self):
        self.db.flush()

    def refresh(self, item):
        self.db.refresh(item)
