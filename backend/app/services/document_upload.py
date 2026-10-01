"""Upload-specific validation and persistence helpers.

The API route owns HTTP orchestration; this module owns the reusable details of
accepting an upload safely and deriving idempotency information from it.
"""

import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile, status

from app.core.config import MAX_UPLOAD_SIZE

ALLOWED_FILE_TYPES = {
    "application/pdf": (".pdf",),
    "text/plain": (".txt",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/tiff": (".tif", ".tiff"),
}


def upload_metadata(file: UploadFile) -> tuple[str, str, str]:
    """Validate the declared type and filename, returning safe file metadata."""
    content_type = file.content_type or ""
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    expected_suffixes = ALLOWED_FILE_TYPES.get(content_type)
    if expected_suffixes is None or suffix not in expected_suffixes:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, UTF-8 TXT, JPEG, PNG, and TIFF files are supported",
        )
    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    return content_type, filename, suffix


def idempotency_key(request: Request) -> str | None:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        return None
    if len(value) > 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key must be at most 128 characters")
    return value


def upload_fingerprint(path: Path, document_set_id: uuid.UUID | None, chunk_size: int, overlap: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    digest.update(f"|{document_set_id or ''}|{chunk_size}|{overlap}".encode())
    return digest.hexdigest()


def save_upload(file: UploadFile, destination: Path) -> int:
    """Write a spooled upload with a hard byte limit."""
    total_size = 0
    with destination.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File size cannot exceed {MAX_UPLOAD_SIZE // (1024 * 1024)} MB",
                )
            output.write(chunk)
    return total_size
