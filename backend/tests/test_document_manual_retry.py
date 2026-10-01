from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import documents


def test_manual_retry_releases_backoff_and_resets_attempt_budget():
    doc = SimpleNamespace(id=uuid4())
    job = SimpleNamespace(id=uuid4(), status="retrying", attempts=4, next_attempt_at="later")
    db = MagicMock()
    db.scalar.side_effect = [doc, job]
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    with patch.object(documents, "require_document_access"), patch.object(documents, "DocumentResponse") as response, patch.object(documents, "IngestResponse"):
        response.model_validate.return_value.model_dump.return_value = {}
        documents.retry_document(doc.id, db, user)
    assert job.next_attempt_at is None
    assert job.attempts == 0
    assert job.worker_id is None
    assert job.stage == "queued"
    assert doc.processing_error is None
    db.commit.assert_called_once()


@pytest.mark.parametrize("status", ["queued", "running"])
def test_manual_retry_cannot_duplicate_an_active_attempt(status):
    doc = SimpleNamespace(id=uuid4())
    db = MagicMock()
    db.scalar.side_effect = [doc, SimpleNamespace(status=status)]
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    with patch.object(documents, "require_document_access"), pytest.raises(HTTPException) as error:
        documents.retry_document(doc.id, db, user)
    assert error.value.status_code == 409
    db.commit.assert_not_called()
