from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception


def http_status(error):
    return to_http_exception(error).status_code if isinstance(error, ApplicationError) else error.status_code


from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.services import upload_security
from app.services.upload_security import MalwareDetectedError, UploadContentError, stage_and_scan_upload, validate_upload_content


class UploadSecurityTests(TestCase):
    def test_rejects_mismatched_pdf_signature(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "document.pdf"
            path.write_bytes(b"not a PDF")
            with self.assertRaises(UploadContentError):
                validate_upload_content(path, "application/pdf")

    def test_rejects_non_utf8_text(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "document.txt"
            path.write_bytes(b"\xff\xfe")
            with self.assertRaises(UploadContentError):
                validate_upload_content(path, "text/plain")

    def test_detected_file_stays_out_of_document_storage(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / "documents"
            quarantine = uploads / ".quarantine"

            def save_upload(_, destination: Path):
                destination.write_bytes(b"%PDF-1.7\nblocked")
                return destination.stat().st_size

            with patch.object(upload_security, "UPLOAD_DIR", uploads), patch.object(upload_security, "MALWARE_QUARANTINE_DIR", quarantine), patch.object(upload_security, "scan_for_malware", side_effect=MalwareDetectedError("Test-Signature")):
                with self.assertRaises(ApplicationError) as raised:
                    stage_and_scan_upload(object(), content_type="application/pdf", suffix=".pdf", filename="blocked.pdf", user_id=uuid4(), organization_id=uuid4(), save_upload=save_upload)

            self.assertEqual(http_status(raised.exception), 422)
            self.assertFalse(any(uploads.glob("*/original.pdf")))
