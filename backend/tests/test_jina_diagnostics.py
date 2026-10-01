from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services import cloud_ocr
from app.services.document_extractor import ExtractionError
from app.services.document_jobs import _retryable_document_error


@pytest.mark.parametrize("error, expected", [
    (HTTPError("https://example.test", 403, "forbidden", {}, BytesIO(b"secret response")), "HTTP 403"),
    (TimeoutError(), "timed out"),
    (URLError(TimeoutError()), "timed out"),
    (URLError("sensitive network information"), "network error"),
])
def test_jina_errors_are_actionable_without_exposing_secrets(error, expected):
    image = MagicMock()
    image.read_bytes.return_value = b"png"
    with patch.object(cloud_ocr, "JINA_API_KEY", "secret-key"), patch.object(cloud_ocr, "urlopen", side_effect=error):
        with pytest.raises(cloud_ocr.OCRUnavailableError) as result:
            cloud_ocr._jina(image, "image/png")
    assert expected in str(result.value)
    assert "secret" not in str(result.value)
    assert "sensitive" not in str(result.value)


@pytest.mark.parametrize("status, retryable", [(408, True), (429, True), (500, True), (503, True), (401, False), (403, False)])
def test_jina_transient_http_errors_retry_but_authentication_errors_do_not(status, retryable):
    assert _retryable_document_error(ExtractionError(f"Jina OCR request failed (HTTP {status})")) is retryable
