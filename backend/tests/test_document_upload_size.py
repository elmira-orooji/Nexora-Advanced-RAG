from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception


def http_status(error):
    return to_http_exception(error).status_code if isinstance(error, ApplicationError) else error.status_code


from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import MAX_UPLOAD_SIZE
from app.services.document_upload import save_upload


@pytest.mark.parametrize("size", [11 * 1024 * 1024, 100 * 1024 * 1024])
def test_accepts_upload_up_to_100_mb(size):
    assert MAX_UPLOAD_SIZE == 100 * 1024 * 1024
    upload = MagicMock()
    block = b"x" * (1024 * 1024)
    upload.file.read.side_effect = [block] * (size // len(block)) + [b""]
    destination = MagicMock()
    assert save_upload(upload, destination) == size


def test_rejects_upload_above_100_mb():
    upload = MagicMock()
    block = b"x" * (1024 * 1024)
    upload.file.read.side_effect = [block] * 100 + [b"x", b""]
    destination = MagicMock()
    with pytest.raises((HTTPException, ApplicationError)) as error:
        save_upload(upload, destination)
    assert http_status(error.value) == 413
    assert error.value.detail == "File size cannot exceed 100 MB"
    assert destination.open.return_value.__enter__.return_value.write.call_count == 100
