import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.contracts import set_offset_pagination_headers
from app.api.routes.auth import get_current_user
from app.core.document_set_access import require_document_access
from app.db.database import get_db
from app.models.user import User
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
# Retain the existing upload helper exports for callers.
from app.services.document_upload import ALLOWED_FILE_TYPES, save_upload as _save_upload
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_management_service import DocumentManagementService, _document_source_path

router = APIRouter(prefix="/documents", tags=["documents"])


@router.patch("/{document_id}/chunks/{chunk_id}", response_model=ChunkResponse)
def update_chunk(document_id: uuid.UUID, chunk_id: uuid.UUID, payload: ChunkUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).update_chunk(document_id, chunk_id, payload, user)


@router.post("/{document_id}/chunks/{chunk_id}/enrich", response_model=ChunkResponse)
def regenerate_chunk_enrichment(document_id: uuid.UUID, chunk_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).regenerate_chunk_enrichment(document_id, chunk_id, user)


@router.patch("/{document_id}/metadata", response_model=DocumentResponse)
def update_document_metadata(document_id: uuid.UUID, payload: DocumentMetadataUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).update_document_metadata(document_id, payload, user)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).create_document(payload, user)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    document_set_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = DocumentManagementService(db).list_documents(offset, limit, document_set_id, user)
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
    return DocumentManagementService(db).upload_document(file, user)


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
    return DocumentManagementService(db).retry_document(document_id, user)


@router.post("/{document_id}/pause", response_model=DocumentResponse)
def pause_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).pause_document(document_id, user)


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
    result = DocumentManagementService(db).get_source_region(document_id, payload, user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentManagementService(db).get_document(document_id, user)
