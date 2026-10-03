import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.application_errors import ApplicationError
from app.core.config import document_storage_relative, resolve_document_path
from app.core.document_set_access import require_document_access, require_set_access
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentResponse, IngestResponse
from app.services.chunk_enrichment import enrich_chunk
from app.services.document_extractor import ExtractionError, extract_text_with_provenance
from app.services.document_processing_service import _get_document_directory
from app.services.document_upload import save_upload as _save_upload, upload_metadata
from app.services.file_storage import atomic_write_text
from app.services.provider_errors import VectorStoreError
from app.services.transactions import transaction
from app.services.document_indexing_service import DocumentIndexingService
from app.services.upload_security import stage_and_scan_upload


logger = logging.getLogger(__name__)

def _document_source_path(document: Document) -> Path:
    stored_source = document.storage_path or document.extracted_text_path
    if not stored_source:
        raise ApplicationError(kind="not_found", detail="Original document is unavailable")
    _get_document_directory(document)
    source_path = resolve_document_path(stored_source)
    if not source_path.is_file():
        raise ApplicationError(kind="not_found", detail="Original document is unavailable")
    return source_path

class DocumentManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DocumentRepository(db)

    def update_chunk(self, document_id, chunk_id, payload, user):
        db = self.db
        if user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = self.repository.get_document(document_id, user.organization_id, with_chunks=True, lock=True)
        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
        chunk = next((item for item in document.chunks if item.id == chunk_id), None)
        if chunk is None:
            raise ApplicationError(kind="not_found", detail="Chunk not found")
        try:
            with transaction(db):
                if payload.content is not None:
                    chunk.content = payload.content
                    chunk.token_count = len(payload.content.split())
                    chunk.keywords, chunk.suggested_questions = enrich_chunk(payload.content)
                if payload.is_active is not None:
                    chunk.is_active = payload.is_active
                document.updated_at = datetime.now(timezone.utc)
                self.repository.flush()
                entry = DocumentIndexingService(db).enqueue(document)
            DocumentIndexingService(db).apply(entry, document_id)
            self.repository.refresh(chunk)
        except VectorStoreError as exc:
            db.rollback()
            raise ApplicationError(kind="upstream_unavailable", detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise ApplicationError(kind="internal_error", detail="Could not update chunk") from exc
        return chunk

    def regenerate_chunk_enrichment(self, document_id, chunk_id, user):
        db = self.db
        if user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        chunk = self.repository.get_chunk(document_id, chunk_id, user.organization_id)
        if chunk is None:
            raise ApplicationError(kind="not_found", detail="Chunk not found")
        with transaction(db):
            chunk.keywords, chunk.suggested_questions = enrich_chunk(chunk.content)
        self.repository.refresh(chunk)
        return chunk

    def update_document_metadata(self, document_id, payload, user):
        db = self.db
        document = require_document_access(db, user, document_id, "edit")
        with transaction(db):
            document.author = payload.author
            document.language = payload.language
            document.source_type = payload.source_type
            document.document_date = payload.document_date
            document.tags = payload.tags
        self.repository.refresh(document)
        return document

    def create_document(self, payload, user):
        db = self.db
        if user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="Admin access is required")
        document = Document(
            organization_id=user.organization_id,
            filename=payload.filename,
            content_type=payload.content_type,
        )
        with transaction(db):
            self.repository.add(document)
        self.repository.refresh(document)
        return document

    def list_documents(self, offset, limit, document_set_id, user):
        db = self.db
        if user.role != "admin" and document_set_id is None:
            raise ApplicationError(kind="forbidden", detail="A permitted knowledge set is required")
        if document_set_id is not None:
            if self.repository.get_set(document_set_id, user.organization_id) is None:
                raise ApplicationError(kind="not_found", detail="Document set not found")
            require_set_access(db, user, document_set_id)
        return self.repository.list_documents(user.organization_id, document_set_id, offset, limit)

    def upload_document(self, file, user):
        db = self.db
        content_type, safe_filename, suffix = upload_metadata(file)

        committed = False
        document_dir: Path | None = None

        try:
            document_id, document_dir, original_path, _ = stage_and_scan_upload(file, content_type=content_type, suffix=suffix, filename=safe_filename, user_id=user.id, organization_id=user.organization_id, save_upload=_save_upload)
            extracted_path = document_dir / "extracted.txt"

            extraction = extract_text_with_provenance(original_path, content_type)
            atomic_write_text(extracted_path, extraction.text)
            if extraction.visual_layout:
                import json
                atomic_write_text(extracted_path.parent / "visual-layout.json", json.dumps(extraction.visual_layout, ensure_ascii=False))

            document = Document(
                id=document_id,
                organization_id=user.organization_id,
                filename=safe_filename,
                content_type=content_type,
                storage_path=document_storage_relative(original_path),
                extracted_text_path=document_storage_relative(extracted_path),
                status="extracted",
                ocr_provenance=extraction.ocr_provenance,
            )
            if extraction.ocr_provenance:
                logger.info(
                    "Document OCR completed",
                    extra={"document_id": str(document.id), **extraction.ocr_provenance},
                )
            with transaction(db):
                self.repository.add(document)
            committed = True
            self.repository.refresh(document)
            return document
        except ExtractionError as exc:
            db.rollback()
            if not committed and document_dir is not None:
                shutil.rmtree(document_dir, ignore_errors=True)
            raise ApplicationError(kind="validation_error", detail=str(exc)) from exc
        except ApplicationError:
            db.rollback()
            if not committed and document_dir is not None:
                shutil.rmtree(document_dir, ignore_errors=True)
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            if not committed and document_dir is not None:
                shutil.rmtree(document_dir, ignore_errors=True)
            raise ApplicationError(kind="internal_error", detail="Could not save document") from exc
        finally:
            file.file.close()

    def retry_document(self, document_id, user):
        db = self.db
        document = self.repository.get_document(document_id, user.organization_id)
        if document is None:
            raise ApplicationError(kind="not_found", detail="Document not found")
        require_document_access(db, user, document_id, "edit")
        with transaction(db):
            job = self.repository.get_job(document_id, lock=True)
            if job is None:
                job = ProcessingJob(organization_id=user.organization_id, requested_by_id=user.id, document_id=document.id)
                self.repository.add(job)
            elif job.status in {"queued", "running"}:
                raise ApplicationError(kind="conflict", detail="Document processing is already active")
            job.status = "retrying"
            job.progress = 0
            job.stage = "queued"
            job.error = None
            job.error_type = None
            job.completed_at = None
            job.requested_by_id = user.id
            job.next_attempt_at = None
            job.dead_lettered_at = None
            job.attempts = 0
            job.worker_id = None
            job.locked_at = None
            document.status = "queued"
            document.processing_progress = 0
            document.processing_stage = "queued"
            document.processing_error = None
        self.repository.refresh(job)
        self.repository.refresh(document)
        return IngestResponse(**DocumentResponse.model_validate(document).model_dump(), job_id=job.id)

    def pause_document(self, document_id, user):
        db = self.db
        document = require_document_access(db, user, document_id, "edit")
        # Same lock order as claiming/deletion. Removing ownership makes existing
        # extraction checkpoints stop, without deleting the document or its source.
        with transaction(db):
            job = self.repository.get_job(document_id, lock=True)
            if job is None or job.status not in {"queued", "running", "retrying", "paused"}:
                raise ApplicationError(kind="conflict", detail="Document processing cannot be paused in its current state")
            job.status = "paused"
            job.stage = "paused"
            job.worker_id = None
            job.locked_at = None
            job.next_attempt_at = None
            document.status = "paused"
            document.processing_stage = "paused"
        self.repository.refresh(document)
        return document

    def get_document(self, document_id, user):
        db = self.db
        document = self.repository.get_document(document_id, user.organization_id, with_chunks=True)

        if document is None:
            raise ApplicationError(kind="not_found",
                detail="Document not found",
            )

        if user.role != "admin":
            allowed = False
            for document_set in document.document_sets:
                try:
                    require_set_access(db, user, document_set.id)
                    allowed = True
                    break
                except ApplicationError:
                    continue
            if not allowed:
                raise ApplicationError(kind="forbidden", detail="You do not have access to this document")

        if document.content_type == "application/pdf" and document.storage_path:
            try:
                pages = [" ".join((page.extract_text() or "").split()).lower() for page in PdfReader(_document_source_path(document)).pages]
                for chunk in document.chunks:
                    needle = " ".join(chunk.content.split()).lower()[:180]
                    chunk.page_number = next((index for index, page in enumerate(pages, 1) if needle and needle in page), None)
            except Exception:
                for chunk in document.chunks:
                    chunk.page_number = None
        return document

    def get_source_region(self, document_id, payload, user):
        db = self.db
        from app.services.document_visuals import source_region, VisualUnavailable
        document = require_document_access(db, user, document_id)
        chunk = self.repository.get_source_chunk(document_id, payload.chunk_id)
        if chunk is None:
            raise ApplicationError(kind="not_found", detail= "Source passage is unavailable")
        path = _document_source_path(document)
        try:
            region = source_region(path, document.content_type or "", payload.query, chunk.content)
        except VisualUnavailable as exc:
            raise ApplicationError(kind="validation_error", detail= str(exc)) from exc
        except Exception as exc:
            logger.warning("Source image rendering failed", extra={"error_type": type(exc).__name__})
            raise ApplicationError(kind="validation_error", detail= "Could not render the original source region") from exc
        return {"filename": document.filename, **region}
