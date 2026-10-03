from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.application_errors import ApplicationError
from app.services import document_management_service as management
from app.services import document_ingestion_service as ingestion
from app.services.document_extractor import ExtractionResult


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize("module", [management, ingestion])
def test_upload_cleanup_only_before_commit(module, committed):
    db = MagicMock()
    failure = SQLAlchemyError("database unavailable")
    if committed:
        db.refresh.side_effect = failure
    else:
        db.commit.side_effect = failure
    upload = SimpleNamespace(file=BytesIO(b"content"))
    user = SimpleNamespace(id=uuid4(), role="admin", organization_id=uuid4())
    with patch.object(module, "upload_metadata", return_value=("text/plain", "test.txt", ".txt")), patch.object(module, "stage_and_scan_upload", return_value=(uuid4(), Path("staged"), Path("staged/original.txt"), None)), patch.object(module, "document_storage_relative", return_value="staged/original.txt"), patch.object(module.shutil, "rmtree") as cleanup:
        with pytest.raises(ApplicationError):
            if module is management:
                with patch.object(module, "extract_text_with_provenance", return_value=ExtractionResult("text", None)), patch.object(module, "atomic_write_text"):
                    module.DocumentManagementService(db).upload_document(upload, user)
            else:
                request = SimpleNamespace(headers={})
                with patch.object(module, "upload_fingerprint", return_value="fingerprint"):
                    module.DocumentIngestionService(db).ingest(request, upload, user, chunk_size=1000, overlap=200, document_set_id=None)
    assert cleanup.call_count == (0 if committed else 1)
    assert upload.file.closed
