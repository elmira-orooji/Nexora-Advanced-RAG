from app.core.application_errors import ApplicationError
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import documents
from app.services import document_management_service as management
from app.services.document_jobs import check_document_job_ownership, DocumentJobOwnershipLost
from app.services import document_jobs
from app.models.processing_job import ProcessingJob
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.mark.parametrize("status", ["queued", "running", "retrying", "paused"])
def test_pause_releases_claim_and_preserves_document(status):
    document = SimpleNamespace(id=uuid4(), processing_progress=10, storage_path="original.pdf")
    job = SimpleNamespace(status=status, worker_id="worker", locked_at="now", next_attempt_at="later")
    db = MagicMock()
    db.scalar.return_value = job
    user = SimpleNamespace(id=uuid4())
    with patch.object(management, "require_document_access", return_value=document):
        assert documents.pause_document(document.id, db, user) is document
    assert (job.status, job.stage, job.worker_id, job.locked_at, job.next_attempt_at) == ("paused", "paused", None, None, None)
    assert document.status == "paused"
    assert document.processing_progress == 10
    assert document.storage_path == "original.pdf"
    db.delete.assert_not_called()
    db.commit.assert_called_once()


def test_completed_job_cannot_be_paused():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(status="completed")
    with patch.object(management, "require_document_access", return_value=SimpleNamespace(id=uuid4())), pytest.raises(ApplicationError) as error:
        documents.pause_document(uuid4(), db, SimpleNamespace())
    assert error.value.kind == "conflict"
    db.commit.assert_not_called()


def test_paused_job_is_not_claimed_or_recovered_and_old_owner_stops():
    engine = create_engine("sqlite://")
    ProcessingJob.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    job_id = uuid4()
    try:
        with sessions() as db:
            db.add(ProcessingJob(id=job_id, document_id=uuid4(), organization_id=uuid4(), status="paused", stage="paused", worker_id=None))
            db.commit()
        with patch.object(document_jobs, "SessionLocal", sessions):
            assert document_jobs.claim_document_job("other") is None
            assert document_jobs.recover_document_jobs() == 0
            with pytest.raises(DocumentJobOwnershipLost):
                check_document_job_ownership(job_id, "old-worker")
    finally:
        engine.dispose()
