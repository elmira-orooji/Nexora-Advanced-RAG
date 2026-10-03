from app.services.provider_factory import get_vector_store
import shutil
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pypdf import PdfReader
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import UPLOAD_DIR, document_storage_relative, resolve_document_path
from app.core.document_set_access import require_document_access, require_set_access
from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.user import User
from app.models.processing_job import ProcessingJob
from app.schemas.document import (
    ChunkingRequest,
    ChunkResponse,
    ChunkUpdate,
    DeleteDocumentResponse,
    DocumentCreate,
    DocumentDetail,
    DocumentResponse,
    DocumentMetadataUpdate,
    IngestResponse,
)
from app.services.document_extractor import ExtractionError, extract_text_with_provenance
from app.services.qdrant import QdrantError
from app.services.chunk_enrichment import enrich_chunk
from app.services.upload_security import stage_and_scan_upload
from app.services.file_storage import atomic_write_text
from app.services.document_upload import (
    ALLOWED_FILE_TYPES,
    idempotency_key as get_idempotency_key,
    save_upload as _save_upload,
    upload_fingerprint,
    upload_metadata,
)
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.document_processing_service import DocumentProcessingService, _get_document_directory
from app.api.contracts import set_offset_pagination_headers

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
def _sync_active_chunks(document: Document) -> None:
    client = get_vector_store()
    client.ensure_collection()
    client.replace_document_chunks(str(document.id), document.filename, [{"id": str(chunk.id), "chunk_index": chunk.chunk_index, "content": chunk.content} for chunk in document.chunks if chunk.is_active])


@router.patch("/{document_id}/chunks/{chunk_id}", response_model=ChunkResponse)
def update_chunk(document_id: uuid.UUID, chunk_id: uuid.UUID, payload: ChunkUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    document = db.scalar(select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id, Document.organization_id == user.organization_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunk = next((item for item in document.chunks if item.id == chunk_id), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    if payload.content is not None:
        chunk.content = payload.content
        chunk.token_count = len(payload.content.split())
        chunk.keywords, chunk.suggested_questions = enrich_chunk(payload.content)
    if payload.is_active is not None:
        chunk.is_active = payload.is_active
    document.updated_at = datetime.now(timezone.utc)
    try:
        db.flush()
        _sync_active_chunks(document)
        db.commit()
        db.refresh(chunk)
    except QdrantError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update chunk") from exc
    return chunk


@router.post("/{document_id}/chunks/{chunk_id}/enrich", response_model=ChunkResponse)
def regenerate_chunk_enrichment(document_id: uuid.UUID, chunk_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    chunk = db.scalar(select(Chunk).join(Document, Document.id == Chunk.document_id).where(Chunk.id == chunk_id, Chunk.document_id == document_id, Document.organization_id == user.organization_id))
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    chunk.keywords, chunk.suggested_questions = enrich_chunk(chunk.content)
    db.commit(); db.refresh(chunk)
    return chunk


@router.patch("/{document_id}/metadata", response_model=DocumentResponse)
def update_document_metadata(document_id: uuid.UUID, payload: DocumentMetadataUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = require_document_access(db, user, document_id, "edit")
    document.author = payload.author
    document.language = payload.language
    document.source_type = payload.source_type
    document.document_date = payload.document_date
    document.tags = payload.tags
    db.commit(); db.refresh(document)
    return document


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    document = Document(
        organization_id=user.organization_id,
        filename=payload.filename,
        content_type=payload.content_type,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    document_set_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and document_set_id is None:
        raise HTTPException(status_code=403, detail="A permitted knowledge set is required")
    statement = select(Document).where(Document.organization_id == user.organization_id)
    if document_set_id is not None:
        if db.scalar(select(DocumentSet).where(DocumentSet.id == document_set_id, DocumentSet.organization_id == user.organization_id)) is None:
            raise HTTPException(status_code=404, detail="Document set not found")
        require_set_access(db, user, document_set_id)
        statement = statement.join(Document.document_sets).where(DocumentSet.id == document_set_id)
    statement = (
        statement
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = db.scalars(statement).all()
    set_offset_pagination_headers(response, offset=offset, limit=limit, returned=len(items))
    return items


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content_type, safe_filename, suffix = upload_metadata(file)

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
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except ExtractionError as exc:
        db.rollback()
        if document_dir is not None: shutil.rmtree(document_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        if document_dir is not None: shutil.rmtree(document_dir, ignore_errors=True)
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        if document_dir is not None: shutil.rmtree(document_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Could not save document") from exc
    finally:
        file.file.close()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    chunk_size: int = Query(default=1000, ge=200, le=4000),
    overlap: int = Query(default=200, ge=0, le=1000),
    document_set_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return DocumentIngestionService(db).ingest(
        request,
        file,
        user,
        chunk_size=chunk_size,
        overlap=overlap,
        document_set_id=document_set_id,
    )


@router.post("/{document_id}/retry", response_model=IngestResponse)
def retry_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == user.organization_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_document_access(db, user, document_id, "edit")
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == document_id).with_for_update())
    if job is None:
        job = ProcessingJob(organization_id=user.organization_id, requested_by_id=user.id, document_id=document.id)
        db.add(job)
    elif job.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Document processing is already active")
    job.status = "retrying"; job.progress = 0; job.stage = "queued"; job.error = None; job.error_type = None; job.completed_at = None
    job.requested_by_id = user.id
    job.next_attempt_at = None; job.dead_lettered_at = None
    job.attempts = 0
    job.worker_id = None; job.locked_at = None
    document.status = "queued"; document.processing_progress = 0; document.processing_stage = "queued"; document.processing_error = None
    db.commit(); db.refresh(job); db.refresh(document)
    return IngestResponse(**DocumentResponse.model_validate(document).model_dump(), job_id=job.id)


@router.post("/{document_id}/pause", response_model=DocumentResponse)
def pause_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = require_document_access(db, user, document_id, "edit")
    # Same lock order as claiming/deletion. Removing ownership makes existing
    # extraction checkpoints stop, without deleting the document or its source.
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == document_id).with_for_update())
    if job is None or job.status not in {"queued", "running", "retrying", "paused"}:
        raise HTTPException(status_code=409, detail="Document processing cannot be paused in its current state")
    job.status = "paused"; job.stage = "paused"
    job.worker_id = None; job.locked_at = None; job.next_attempt_at = None
    document.status = "paused"; document.processing_stage = "paused"
    db.commit(); db.refresh(document)
    return document


@router.post("/{document_id}/chunks", response_model=DocumentDetail)
def create_document_chunks(
    document_id: uuid.UUID,
    payload: ChunkingRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return DocumentProcessingService(db).create_chunks(document_id, payload, user)


@router.post("/{document_id}/index", response_model=DocumentDetail)
def index_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    return DocumentProcessingService(db).index(document_id, user)


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentProcessingService(db).delete(document_id, user)




def _document_source_path(document: Document) -> Path:
    stored_source = document.storage_path or document.extracted_text_path
    if not stored_source:
        raise HTTPException(status_code=404, detail="Original document is unavailable")
    _get_document_directory(document)
    source_path = resolve_document_path(stored_source)
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Original document is unavailable")
    return source_path


@router.get("/{document_id}/content")
def get_document_content(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = require_document_access(db, user, document_id)
    source_path = _document_source_path(document)
    return FileResponse(source_path, media_type=document.content_type or "application/octet-stream", filename=document.filename, content_disposition_type="inline")


class SourceRegionRequest(BaseModel):
    chunk_id: uuid.UUID
    query: str = Field(min_length=2, max_length=4000)


@router.post("/{document_id}/source-region")
def get_source_region(document_id: uuid.UUID, payload: SourceRegionRequest, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.document_visuals import source_region, VisualUnavailable
    document = require_document_access(db, user, document_id)
    chunk = db.scalar(select(Chunk).where(Chunk.id == payload.chunk_id, Chunk.document_id == document_id, Chunk.is_active.is_(True)))
    if chunk is None:
        raise HTTPException(404, "Source passage is unavailable")
    path = _document_source_path(document)
    try:
        region = source_region(path, document.content_type or "", payload.query, chunk.content)
    except VisualUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.warning("Source image rendering failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(422, "Could not render the original source region") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"filename": document.filename, **region}


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id, Document.organization_id == user.organization_id)
    )
    document = db.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if user.role != "admin":
        allowed = False
        for document_set in document.document_sets:
            try:
                require_set_access(db, user, document_set.id)
                allowed = True
                break
            except HTTPException:
                continue
        if not allowed:
            raise HTTPException(status_code=403, detail="You do not have access to this document")

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
