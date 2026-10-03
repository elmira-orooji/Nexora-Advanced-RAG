"""Persist indexing intent before external writes; retry through the existing outbox."""
import logging

from app.models.indexing_outbox import IndexingOutbox
from app.models.processing_job import ProcessingJob
from app.repositories.document_repository import DocumentRepository
from app.services.provider_factory import get_vector_store
from app.services.transactions import transaction
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)


def indexing_payload(document):
    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "chunks": [{"id": str(chunk.id), "chunk_index": chunk.chunk_index, "content": chunk.content}
                   for chunk in document.chunks if chunk.is_active],
    }


def mark_indexed(db, document, entry):
    was_pending = document.status != "indexed"
    document.status = "indexed"
    document.processing_stage = "ready"
    document.processing_progress = 100
    document.processing_error = None
    if was_pending and entry.job_id is not None:
        job = db.get(ProcessingJob, entry.job_id)
        if job is not None:
            create_notification(db, user_id=job.requested_by_id, organization_id=job.organization_id,
                                kind="document_processed", severity="success", title="Document is ready",
                                body=f"{document.filename} has been indexed and is ready to use.")


class DocumentIndexingService:
    def __init__(self, db):
        self.db = db
        self.repository = DocumentRepository(db)

    def enqueue(self, document):
        """Caller owns the document-write transaction, including this intent."""
        entry = IndexingOutbox(document_id=document.id, action="replace_document_chunks",
                               payload=indexing_payload(document), status="pending")
        self.repository.add(entry)
        document.status = "processing"
        document.processing_stage = "indexing"
        document.processing_progress = 95
        return entry

    def apply(self, entry, document_id):
        """Post-commit best effort. Failure leaves a durable pending intent."""
        try:
            with transaction(self.db):
                document = self.repository.get_document(document_id, with_chunks=True, lock=True)
                if document is None:
                    return
                # Always use current SQL state: an older pending entry must not
                # overwrite a later edit or reintroduce inactive chunks.
                payload = indexing_payload(document)
                client = get_vector_store()
                client.ensure_collection()
                client.replace_document_chunks(payload["document_id"], payload["filename"], payload["chunks"])
                mark_indexed(self.db, document, entry)
                entry.status = "applied"
                entry.last_error = None
        except Exception:
            logger.warning("Immediate manual indexing failed; outbox will retry",
                           extra={"document_id": str(document_id)}, exc_info=True)

    def enqueue_delete(self, document_id):
        entry = IndexingOutbox(document_id=None, action="delete_document",
                               payload={"document_id": str(document_id)}, status="pending")
        self.repository.add(entry)
        return entry

    def apply_delete(self, entry, document_id):
        try:
            with transaction(self.db):
                client = get_vector_store()
                client.ensure_collection()
                client.delete_document(str(document_id))
                entry.status = "applied"
                entry.last_error = None
        except Exception:
            logger.warning("Immediate vector deletion failed; outbox will retry",
                           extra={"document_id": str(document_id)}, exc_info=True)
