from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services import cloud_ocr, document_jobs, document_extractor
from app.services.processing_cancellation import ProcessingCancelled, cancellation_scope, check_processing_cancelled


def test_deleted_job_cancels_processing():
    with patch.object(document_jobs, "SessionLocal") as sessions:
        sessions.return_value.__enter__.return_value.scalar.return_value = None
        with pytest.raises(document_jobs.DocumentJobOwnershipLost):
            document_jobs.check_document_job_ownership(uuid4(), "worker")


def test_jina_stops_before_next_page_and_does_not_fallback():
    cancelled = False

    def check():
        if cancelled:
            raise ProcessingCancelled("deleted")

    def page(_page, _content_type):
        nonlocal cancelled
        cancelled = True
        return "page one"

    with patch.object(cloud_ocr, "JINA_API_KEY", "test"), patch.object(cloud_ocr, "MINERU_API_TOKEN", "test"), patch.object(cloud_ocr, "OCR_PROVIDER", "jina"), patch.object(cloud_ocr, "_vision_pages", return_value=[b"one", b"two"]), patch.object(cloud_ocr, "_jina_page", side_effect=page) as request, patch.object(cloud_ocr, "_mineru") as fallback:
        with pytest.raises(ProcessingCancelled), cancellation_scope(check):
            cloud_ocr.extract_scanned_document_text_with_provenance(Path("scan.pdf"), "application/pdf")
        assert request.call_count == 1
        fallback.assert_not_called()
    check_processing_cancelled()  # Scope must not leak into subsequent jobs.


def test_mineru_polling_stops_without_another_request():
    def check():
        raise ProcessingCancelled("deleted")
    with patch.object(cloud_ocr, "_mineru_json_request") as request:
        with pytest.raises(ProcessingCancelled), cancellation_scope(check):
            cloud_ocr._mineru_wait_for_result("batch", {})
        request.assert_not_called()


def test_pdf_cancellation_is_not_wrapped_as_an_extraction_failure():
    checks = 0

    def check():
        nonlocal checks
        checks += 1
        if checks > 1:
            raise ProcessingCancelled("deleted")

    reader = MagicMock()
    reader.pages = [MagicMock(), MagicMock()]
    with patch.object(document_extractor, "PdfReader", return_value=reader), patch.object(document_extractor, "extract_scanned_document_text_with_provenance") as ocr:
        with pytest.raises(ProcessingCancelled), cancellation_scope(check):
            document_extractor.extract_text_with_provenance(Path("scan.pdf"), "application/pdf")
        reader.pages[0].extract_text.assert_not_called()
        ocr.assert_not_called()
