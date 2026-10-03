from app.core.application_errors import ApplicationError
import shutil
import uuid
from pathlib import Path

from fastapi import Request, UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import document_storage_relative
from app.core.document_set_access import require_set_access
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.schemas.document import ChunkingRequest, DocumentResponse, IngestResponse
from app.services.document_upload import idempotency_key, save_upload, upload_fingerprint, upload_metadata
from app.services.upload_security import stage_and_scan_upload
from app.repositories.document_repository import DocumentRepository
from app.services.transactions import transaction


class DocumentIngestionService:
    """Queues a validated upload for asynchronous document processing."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = DocumentRepository(db)

    def ingest(self, request: Request, file: UploadFile, user: User, *, chunk_size: int, overlap: int, document_set_id: uuid.UUID | None) -> IngestResponse:
        target_set = self._target_set(user, document_set_id)
        chunking = self._chunking(chunk_size, overlap)
        committed = False
        document_dir: Path | None = None
        try:
            content_type, filename, suffix = upload_metadata(file)
            document_id, document_dir, original_path, _ = stage_and_scan_upload(file, content_type=content_type, suffix=suffix, filename=filename, user_id=user.id, organization_id=user.organization_id, save_upload=save_upload)
            fingerprint = upload_fingerprint(original_path, document_set_id, chunk_size, overlap)
            document = Document(
                id=document_id,
                organization_id=user.organization_id,
                filename=filename,
                content_type=content_type,
                storage_path=document_storage_relative(original_path),
                status="queued",
                processing_progress=0,
                processing_stage="queued",
                source_type="upload",
                tags=[],
                idempotency_key=idempotency_key(request),
                idempotency_fingerprint=fingerprint,
            )
            with transaction(self.db):
                self.repository.add(document)
                self.repository.flush()
                if target_set is not None:
                    document.document_sets.append(target_set)
                job = ProcessingJob(
                    organization_id=user.organization_id,
                    requested_by_id=user.id,
                    document_id=document.id,
                    chunk_size=target_set.child_chunk_size if target_set else chunking.chunk_size,
                    chunk_overlap=target_set.chunk_overlap if target_set else chunking.overlap,
                    parent_chunk_size=target_set.parent_chunk_size if target_set else None,
                )
                self.repository.add(job)
            committed = True
            self.repository.refresh(document)
            self.repository.refresh(job)
            return IngestResponse(**DocumentResponse.model_validate(document).model_dump(), job_id=job.id)
        except IntegrityError:
            self.db.rollback()
            if not committed:
                self._discard_stage(document_dir)
            return self._idempotent_result(user, idempotency_key(request), fingerprint)
        except ApplicationError:
            self.db.rollback()
            if not committed:
                self._discard_stage(document_dir)
            raise
        except (OSError, SQLAlchemyError) as exc:
            self.db.rollback()
            if not committed:
                self._discard_stage(document_dir)
            raise ApplicationError(kind="internal_error", detail="Could not queue document processing") from exc
        finally:
            file.file.close()

    def _target_set(self, user: User, document_set_id: uuid.UUID | None) -> DocumentSet | None:
        if document_set_id is None:
            if user.role != "admin":
                raise ApplicationError(kind="forbidden", detail="A permitted knowledge set is required")
            return None
        target_set = self.repository.get_set(document_set_id, user.organization_id)
        if target_set is None:
            raise ApplicationError(kind="not_found", detail="Document set not found")
        require_set_access(self.db, user, document_set_id, "edit")
        return target_set

    @staticmethod
    def _chunking(chunk_size: int, overlap: int) -> ChunkingRequest:
        try:
            return ChunkingRequest(chunk_size=chunk_size, overlap=overlap)
        except ValueError as exc:
            raise ApplicationError(kind="validation_error", detail=str(exc)) from exc

    def _idempotent_result(self, user: User, key: str | None, fingerprint: str) -> IngestResponse:
        existing = self.repository.find_idempotent(user.organization_id, key)
        if existing is None or existing.idempotency_fingerprint != fingerprint:
            raise ApplicationError(kind="conflict", detail="Idempotency-Key was already used for a different upload")
        job = self.repository.get_job(existing.id)
        if job is None:
            raise ApplicationError(kind="conflict", detail="The original upload is still being finalized; retry shortly")
        return IngestResponse(**DocumentResponse.model_validate(existing).model_dump(), job_id=job.id)

    @staticmethod
    def _discard_stage(document_dir: Path | None) -> None:
        if document_dir is not None:
            shutil.rmtree(document_dir, ignore_errors=True)
