"""Security gates for files before they enter document storage or processing."""

from __future__ import annotations
from app.core.application_errors import ApplicationError

import hashlib
import logging
import shutil
import socket
import struct
import uuid
from pathlib import Path



from app.core.config import (
    CLAMD_HOST,
    CLAMD_PORT,
    CLAMD_TIMEOUT_SECONDS,
    MALWARE_QUARANTINE_DIR,
    MALWARE_RETAIN_DETECTED,
    MALWARE_SCAN_MODE,
    UPLOAD_DIR,
)

logger = logging.getLogger(__name__)

_SIGNATURES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


class UploadContentError(ValueError):
    """The body does not match the declared upload content type."""


class MalwareDetectedError(RuntimeError):
    def __init__(self, signature: str):
        self.signature = signature
        super().__init__("Malware was detected")


class MalwareScannerUnavailable(RuntimeError):
    pass


def validate_upload_content(path: Path, content_type: str) -> None:
    """Check basic file signatures before sending untrusted content downstream."""
    with path.open("rb") as source:
        header = source.read(8192)
    expected = _SIGNATURES.get(content_type)
    if expected and not header.startswith(expected):
        raise UploadContentError("The file content does not match its declared type")
    if content_type == "image/tiff" and not (header.startswith(b"II*\x00") or header.startswith(b"MM\x00*")):
        raise UploadContentError("The file content does not match its declared type")
    if content_type == "text/plain":
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise UploadContentError("Text files must use UTF-8 encoding") from exc


def _scan_with_clamd(path: Path) -> None:
    try:
        with socket.create_connection((CLAMD_HOST, CLAMD_PORT), timeout=CLAMD_TIMEOUT_SECONDS) as connection:
            connection.settimeout(CLAMD_TIMEOUT_SECONDS)
            connection.sendall(b"zINSTREAM\0")
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    connection.sendall(struct.pack(">I", len(chunk)))
                    connection.sendall(chunk)
            connection.sendall(struct.pack(">I", 0))
            response = connection.recv(4096).decode("utf-8", errors="replace").strip()
    except OSError as exc:
        raise MalwareScannerUnavailable("The malware scanner is unavailable") from exc

    if response.endswith(" OK"):
        return
    if response.endswith(" FOUND"):
        signature = response.rsplit(":", 1)[-1].removesuffix(" FOUND").strip() or "unknown"
        raise MalwareDetectedError(signature)
    raise MalwareScannerUnavailable("The malware scanner returned an invalid response")


def scan_for_malware(path: Path) -> None:
    if MALWARE_SCAN_MODE == "disabled":
        return
    _scan_with_clamd(path)


def stage_and_scan_upload(file, *, content_type: str, suffix: str, filename: str, user_id: uuid.UUID, organization_id: uuid.UUID, save_upload) -> tuple[uuid.UUID, Path, Path, int]:
    """Save an upload in quarantine, validate it, then atomically promote it after a clean scan."""
    document_id = uuid.uuid4()
    quarantine_dir = MALWARE_QUARANTINE_DIR / str(document_id)
    staged_path = quarantine_dir / f"original{suffix}"
    size = 0
    try:
        quarantine_dir.mkdir(parents=True, exist_ok=False)
        size = save_upload(file, staged_path)
        if size == 0:
            raise ApplicationError(kind="bad_request", detail="The uploaded file is empty")
        validate_upload_content(staged_path, content_type)
        scan_for_malware(staged_path)
        document_dir = UPLOAD_DIR / str(document_id)
        document_dir.mkdir(parents=True, exist_ok=False)
        original_path = document_dir / staged_path.name
        shutil.move(str(staged_path), original_path)
        shutil.rmtree(quarantine_dir, ignore_errors=True)
        return document_id, document_dir, original_path, size
    except MalwareDetectedError as exc:
        _log_rejection(filename, content_type, size, staged_path, user_id, organization_id, "malware_detected", exc.signature)
        if MALWARE_RETAIN_DETECTED:
            retained = MALWARE_QUARANTINE_DIR / "rejected" / str(document_id)
            retained.parent.mkdir(parents=True, exist_ok=True)
            if quarantine_dir.exists(): shutil.move(str(quarantine_dir), retained)
        else:
            shutil.rmtree(quarantine_dir, ignore_errors=True)
        raise ApplicationError(kind="validation_error", detail="The uploaded file was blocked by malware scanning") from exc
    except MalwareScannerUnavailable as exc:
        _log_rejection(filename, content_type, size, staged_path, user_id, organization_id, "scanner_unavailable")
        shutil.rmtree(quarantine_dir, ignore_errors=True)
        raise ApplicationError(kind="service_unavailable", detail="Upload scanning is temporarily unavailable. The file was not accepted.") from exc
    except UploadContentError as exc:
        _log_rejection(filename, content_type, size, staged_path, user_id, organization_id, "content_type_mismatch")
        shutil.rmtree(quarantine_dir, ignore_errors=True)
        raise ApplicationError(kind="unsupported_media_type", detail=str(exc)) from exc
    except Exception:
        shutil.rmtree(quarantine_dir, ignore_errors=True)
        raise


def _log_rejection(filename: str, content_type: str, size: int, path: Path, user_id: uuid.UUID, organization_id: uuid.UUID, reason: str, signature: str | None = None) -> None:
    digest = _file_sha256(path)
    logger.warning("Upload rejected by security gate", extra={"reason": reason, "signature": signature, "upload_filename": filename, "content_type": content_type, "size": size, "sha256": digest, "user_id": str(user_id), "organization_id": str(organization_id)})


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
