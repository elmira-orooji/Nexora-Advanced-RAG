from app.core.application_errors import ApplicationError
from app.services.provider_factory import get_vector_store
import uuid
import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from app.core.config import UPLOAD_DIR, resolve_document_path
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from app.models.processing_job import ProcessingJob
from app.schemas.document import ChunkingRequest, DeleteDocumentResponse
from app.services.qdrant import QdrantError
from app.services.text_chunker import hierarchical_chunks
from app.services.chunk_enrichment import enrich_chunk


class DocumentProcessingService:
    """Manual chunking and indexing, independent of HTTP route handlers."""

    def __init__(self, db: Session):
        self.db = db

    def create_chunks(self, document_id: uuid.UUID, payload: ChunkingRequest, user: User | None) -> Document:
        if user is not None and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        statement = select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id)
        if user is not None:
            statement = statement.where(Document.organization_id == user.organization_id)
        document = self.db.scalar(statement)

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
            for existing_chunk in list(document.chunks):
                self.db.delete(existing_chunk)
            self.db.flush()
            document.chunks.clear()
            document.chunks.extend(
                Chunk(chunk_index=index, content=child, parent_index=parent_index, parent_content=parent, keywords=enrich_chunk(child)[0], suggested_questions=enrich_chunk(child)[1])
                for index, (child, parent_index, parent) in enumerate(contents)
            )
            document.status = "chunked"
            document.processing_error = None
            self.db.commit()
            self.db.refresh(document)
            return document
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(kind="internal_error", detail="Could not save document chunks") from exc

    def index(self, document_id: uuid.UUID, user: User | None) -> Document:
        if user is not None and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        statement = select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id)
        if user is not None:
            statement = statement.where(Document.organization_id == user.organization_id)
        document = self.db.scalar(statement)

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
        except QdrantError as exc:
            raise ApplicationError(kind="upstream_unavailable",
                detail=str(exc),
            ) from exc

        document.status = "indexed"
        document.processing_error = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document_id: uuid.UUID, user: User) -> DeleteDocumentResponse:
        if user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = self.db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == user.organization_id))
        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")

        document_dir = _get_document_directory(document)
        # Match the worker's lock order (job, then document).
        self.db.scalar(select(ProcessingJob.id).where(ProcessingJob.document_id == document_id).with_for_update())
        self.db.scalar(select(Document.id).where(Document.id == document_id).with_for_update())
        try:
            qdrant = get_vector_store()
            qdrant.ensure_collection()
            qdrant.delete_document(str(document.id))
        except QdrantError as exc:
            raise ApplicationError(kind="upstream_unavailable",
                detail=str(exc),
            ) from exc

        try:
            # Delete queued/running jobs explicitly: workers detect the missing claim
            # at the next extraction checkpoint instead of continuing OCR/fallback.
            self.db.execute(delete(ProcessingJob).where(ProcessingJob.document_id == document_id))
            self.db.delete(document)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
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
