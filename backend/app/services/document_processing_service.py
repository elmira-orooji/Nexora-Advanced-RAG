from app.core.application_errors import ApplicationError
from app.services.provider_factory import get_vector_store
import uuid
import shutil
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import UPLOAD_DIR, resolve_document_path
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.services.transactions import transaction
from app.schemas.document import ChunkingRequest, DeleteDocumentResponse
from app.services.provider_errors import VectorStoreError
from app.services.text_chunker import hierarchical_chunks
from app.services.chunk_enrichment import enrich_chunk


class DocumentProcessingService:
    """Manual chunking and indexing, independent of HTTP route handlers."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = DocumentRepository(db)

    def create_chunks(self, document_id: uuid.UUID, payload: ChunkingRequest, user: User | None) -> Document:
        if user is not None and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = self.repository.get_document(document_id, user.organization_id if user else None, with_chunks=True)

        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
        if not document.extracted_text_path:
            raise ApplicationError(kind="conflict", detail="Document text has not been extracted")

        extracted_path = resolve_document_path(document.extracted_text_path)
        storage_root = UPLOAD_DIR.resolve()
        if storage_root not in extracted_path.parents or not extracted_path.is_file():
            raise ApplicationError(kind="conflict", detail="Extracted text file is unavailable")

        text = extracted_path.read_text(encoding="utf-8")
        contents = hierarchical_chunks(text, payload.chunk_size, payload.overlap)
        if not contents:
            raise ApplicationError(kind="validation_error", detail="Document contains no text to chunk")

        try:
            with transaction(self.db):
                for existing_chunk in list(document.chunks):
                    self.repository.delete(existing_chunk)
                self.repository.flush()
                document.chunks.clear()
                document.chunks.extend(
                    Chunk(chunk_index=index, content=child, parent_index=parent_index, parent_content=parent, keywords=enrich_chunk(child)[0], suggested_questions=enrich_chunk(child)[1])
                    for index, (child, parent_index, parent) in enumerate(contents)
                )
                document.status = "chunked"
                document.processing_error = None
            self.repository.refresh(document)
            return document
        except SQLAlchemyError as exc:
            raise ApplicationError(kind="internal_error", detail="Could not save document chunks") from exc

    def index(self, document_id: uuid.UUID, user: User | None) -> Document:
        if user is not None and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = self.repository.get_document(document_id, user.organization_id if user else None, with_chunks=True)

        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
        if not document.chunks:
            raise ApplicationError(kind="conflict", detail="Document has no chunks to index")

        chunks = [
            {
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk in document.chunks
        ]
        try:
            client = get_vector_store()
            client.ensure_collection()
            client.replace_document_chunks(str(document.id), document.filename, chunks)
        except VectorStoreError as exc:
            raise ApplicationError(kind="upstream_unavailable",
                detail=str(exc),
            ) from exc

        with transaction(self.db):
            document.status = "indexed"
            document.processing_error = None
        self.repository.refresh(document)
        return document

    def delete(self, document_id: uuid.UUID, user: User) -> DeleteDocumentResponse:
        if user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = self.repository.get_document(document_id, user.organization_id)
        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")

        document_dir = _get_document_directory(document)
        # Match the worker's lock order (job, then document).
        self.repository.lock_job_then_document(document_id)
        try:
            qdrant = get_vector_store()
            qdrant.ensure_collection()
            qdrant.delete_document(str(document.id))
        except VectorStoreError as exc:
            raise ApplicationError(kind="upstream_unavailable",
                detail=str(exc),
            ) from exc

        try:
            with transaction(self.db):
                # Delete queued/running jobs explicitly: workers detect the missing claim
                # at the next extraction checkpoint instead of continuing OCR/fallback.
                self.repository.delete_jobs(document_id)
                self.repository.delete(document)
        except SQLAlchemyError as exc:
            raise ApplicationError(kind="internal_error", detail="Could not delete document") from exc

        storage_removed = True
        if document_dir is not None and document_dir.exists():
            try:
                shutil.rmtree(document_dir)
            except OSError:
                storage_removed = False

        return DeleteDocumentResponse(
            id=document_id,
            status="deleted",
            storage_removed=storage_removed,
        )


def _get_document_directory(document: Document) -> Path | None:
    stored_source = document.storage_path or document.extracted_text_path
    if not stored_source:
        return None

    storage_root = UPLOAD_DIR.resolve()
    document_dir = resolve_document_path(stored_source).parent
    expected_dir = storage_root / str(document.id)
    if document_dir != expected_dir:
        raise ApplicationError(kind="conflict",
            detail="Document storage path failed safety validation",
        )
    return document_dir
