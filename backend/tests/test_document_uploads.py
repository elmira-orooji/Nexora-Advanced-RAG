from app.core.application_errors import ApplicationError
import inspect
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services import document_management_service as documents
from app.api.routes.documents import ALLOWED_FILE_TYPES, _save_upload, ingest_document, upload_document
from app.services.document_extractor import ExtractionResult


class DocumentUploadExecutionTests(unittest.TestCase):
    def test_blocking_upload_routes_are_sync_endpoints(self):
        self.assertFalse(inspect.iscoroutinefunction(upload_document))
        self.assertFalse(inspect.iscoroutinefunction(ingest_document))

    def test_save_upload_reads_from_sync_spooled_file(self):
        upload = SimpleNamespace(file=BytesIO(b"uploaded content"))
        destination = MagicMock()
        output = destination.open.return_value.__enter__.return_value

        size = _save_upload(upload, destination)

        self.assertEqual(size, len(b"uploaded content"))
        output.write.assert_called_once_with(b"uploaded content")

    def test_ocr_image_extensions_are_accepted(self):
        self.assertIn(".jpeg", ALLOWED_FILE_TYPES["image/jpeg"])
        self.assertIn(".tif", ALLOWED_FILE_TYPES["image/tiff"])

    def test_direct_upload_persists_ocr_provenance(self):
        document_id = uuid4()
        provenance = {"provider": "jina", "model": "jina-ocr-v1", "completed_at": "2026-09-24T00:00:00+00:00"}
        upload = SimpleNamespace(file=BytesIO(b"file"))
        db = MagicMock()
        user = SimpleNamespace(id=uuid4(), organization_id=uuid4())

        with patch.object(documents, "upload_metadata", return_value=("application/pdf", "scan.pdf", ".pdf")), patch.object(
            documents,
            "stage_and_scan_upload",
            return_value=(document_id, Path("staged"), Path("staged/original.pdf"), None),
        ), patch.object(documents, "extract_text_with_provenance", return_value=ExtractionResult("recognized text", provenance)), patch.object(
            documents, "document_storage_relative", side_effect=lambda path: str(path)
        ), patch.object(documents, "atomic_write_text"):
            result = upload_document(upload, db, user)

        self.assertEqual(result.ocr_provenance, provenance)
        db.add.assert_called_once()
        self.assertEqual(db.add.call_args.args[0].ocr_provenance, provenance)
