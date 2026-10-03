import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.models.indexing_outbox import IndexingOutbox
from app.models.processing_job import ProcessingJob
from app.services.document_jobs import DocumentJobOwnershipLost, claim_document_job, recover_document_jobs, refresh_document_job_lease
from app.services import document_jobs
from app.services.document_extractor import ExtractionResult
from app.db.database import Base
from app.models.document import Document
from app.services.document_extractor import ExtractionError
from app.services.qdrant import QdrantError


class DocumentJobRecoveryTests(unittest.TestCase):
    def test_outbox_action_column_accepts_replacement_action(self):
        self.assertGreaterEqual(
            IndexingOutbox.__table__.c.action.type.length,
            len("replace_document_chunks"),
        )

    def setUp(self):
        self.engine = create_engine("sqlite://")
        ProcessingJob.__table__.create(self.engine)
        Document.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=True)
        self.addCleanup(self.engine.dispose)

    def test_only_abandoned_running_jobs_are_requeued(self):
        ids = {status: uuid4() for status in ("queued", "retrying", "completed", "failed")}
        stale_id, live_id = uuid4(), uuid4()
        with self.sessions() as db:
            for status, job_id in ids.items():
                db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=uuid4(), status=status, stage="original"))
            db.add(ProcessingJob(id=stale_id, organization_id=uuid4(), document_id=uuid4(), status="running", stage="indexing", worker_id="dead", locked_at=datetime.now(timezone.utc) - timedelta(hours=2)))
            db.add(ProcessingJob(id=live_id, organization_id=uuid4(), document_id=uuid4(), status="running", stage="indexing", worker_id="live", locked_at=datetime.now(timezone.utc)))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions), patch("app.services.document_jobs.DOCUMENT_JOB_LEASE_SECONDS", 3600):
            self.assertEqual(recover_document_jobs(), 1)
        with self.sessions() as db:
            stale = db.get(ProcessingJob, stale_id)
            self.assertEqual((stale.status, stale.stage, stale.worker_id, stale.locked_at), ("queued", "queued", None, None))
            self.assertEqual(db.get(ProcessingJob, live_id).status, "running")
            for status, job_id in ids.items():
                self.assertEqual(db.get(ProcessingJob, job_id).status, status)

    def test_recovery_query_uses_skip_locked(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        expired = document_jobs._expired_document_job_ids(cutoff)
        sql = str(expired.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)

    def test_empty_queue_returns_zero(self):
        with patch("app.services.document_jobs.SessionLocal", self.sessions):
            self.assertEqual(recover_document_jobs(), 0)

    def test_stale_heartbeat_recovery_updates_document_before_hour_long_lease(self):
        doc_id, job_id = uuid4(), uuid4()
        with self.sessions() as db:
            db.add(Document(id=doc_id, organization_id=uuid4(), filename="scan.pdf", status="processing", processing_stage="extracting", processing_progress=10))
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=doc_id, status="running", worker_id="dead", stage="extracting", attempts=1, locked_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
            db.commit()
        with patch.object(document_jobs, "SessionLocal", self.sessions), patch.object(document_jobs, "DOCUMENT_JOB_LEASE_SECONDS", 3600), patch.object(document_jobs, "WORKER_STALE_THRESHOLD_SECONDS", 120), patch.object(document_jobs, "DOCUMENT_JOB_HEARTBEAT_SECONDS", 30):
            self.assertEqual(recover_document_jobs(), 1)
        with self.sessions() as db:
            document = db.get(Document, doc_id)
            self.assertEqual((document.status, document.processing_stage, document.processing_progress), ("queued", "requeued", 0))
            self.assertIn("interrupted", document.processing_error)

    def test_interrupted_job_does_not_retry_forever(self):
        job_id = uuid4()
        with self.sessions() as db:
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=uuid4(), status="running", worker_id="dead", attempts=5, locked_at=datetime.now(timezone.utc) - timedelta(hours=2)))
            db.commit()
        with patch.object(document_jobs, "SessionLocal", self.sessions), patch.object(document_jobs, "DOCUMENT_JOB_MAX_ATTEMPTS", 5):
            self.assertEqual(recover_document_jobs(), 1)
        with self.sessions() as db:
            self.assertEqual(db.get(ProcessingJob, job_id).status, "dead_letter")

    def test_claim_persists_owner_and_attempt_before_returning(self):
        queued_id = uuid4()
        with self.sessions() as db:
            db.add(ProcessingJob(id=queued_id, organization_id=uuid4(), document_id=uuid4(), status="queued", chunk_size=900, chunk_overlap=100))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions):
            self.assertEqual(claim_document_job("worker-1"), queued_id)
            self.assertIsNone(claim_document_job("worker-2"))

        with self.sessions() as db:
            job = db.get(ProcessingJob, queued_id)
            self.assertEqual((job.status, job.worker_id, job.attempts), ("running", "worker-1", 1))
            self.assertIsNotNone(job.locked_at)

    def test_new_queued_job_is_not_blocked_by_a_retrying_job(self):
        retrying_id, queued_id = uuid4(), uuid4()
        with self.sessions() as db:
            db.add(ProcessingJob(id=retrying_id, organization_id=uuid4(), document_id=uuid4(), status="retrying", stage="retry_wait"))
            db.add(ProcessingJob(id=queued_id, organization_id=uuid4(), document_id=uuid4(), status="queued", stage="queued"))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions):
            self.assertEqual(claim_document_job("worker-1"), queued_id)

        with self.sessions() as db:
            self.assertEqual(db.get(ProcessingJob, retrying_id).status, "retrying")
            self.assertEqual(db.get(ProcessingJob, queued_id).status, "running")

    def test_future_retry_is_not_claimed_until_due(self):
        job_id = uuid4()
        with self.sessions() as db:
            db.add(ProcessingJob(
                id=job_id,
                organization_id=uuid4(),
                document_id=uuid4(),
                status="retrying",
                next_attempt_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            ))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions):
            self.assertIsNone(claim_document_job("worker"))

    def test_retry_policy_classifies_transient_and_permanent_errors(self):
        self.assertTrue(document_jobs._retryable_document_error(QdrantError("unavailable", status_code=503)))
        self.assertTrue(document_jobs._retryable_document_error(QdrantError("limited", status_code=429)))
        self.assertTrue(document_jobs._retryable_document_error(TimeoutError("timeout")))
        self.assertTrue(document_jobs._retryable_document_error(ExtractionError("OCR could not read this document. MinerU file upload failed: network error (timed out)")))
        self.assertFalse(document_jobs._retryable_document_error(QdrantError("bad request", status_code=400)))
        self.assertFalse(document_jobs._retryable_document_error(ExtractionError("Document contains no text to index")))
        self.assertFalse(document_jobs._retryable_document_error(ValueError("invalid document")))

    def test_retry_delay_is_exponential_and_capped(self):
        with patch("app.services.document_jobs.DOCUMENT_JOB_RETRY_BASE_SECONDS", 10), patch("app.services.document_jobs.DOCUMENT_JOB_RETRY_MAX_SECONDS", 25):
            self.assertEqual(document_jobs._retry_delay(1), 10)
            self.assertEqual(document_jobs._retry_delay(2), 20)
            self.assertEqual(document_jobs._retry_delay(3), 25)

    def test_transient_failures_exhaust_into_dead_letter(self):
        now = datetime.now(timezone.utc)
        with patch("app.services.document_jobs.DOCUMENT_JOB_MAX_ATTEMPTS", 3), patch("app.services.document_jobs.DOCUMENT_JOB_RETRY_BASE_SECONDS", 10):
            retry = document_jobs._document_failure_values(QdrantError("unavailable", status_code=503), 2, now)
            exhausted = document_jobs._document_failure_values(QdrantError("unavailable", status_code=503), 3, now)
            permanent = document_jobs._document_failure_values(ValueError("invalid document"), 1, now)

        self.assertEqual(retry["status"], "retrying")
        self.assertEqual(retry["next_attempt_at"], now + timedelta(seconds=20))
        self.assertIsNone(retry["dead_lettered_at"])
        self.assertEqual(exhausted["status"], "dead_letter")
        self.assertEqual(exhausted["dead_lettered_at"], now)
        self.assertEqual(permanent["status"], "dead_letter")

    def test_heartbeat_only_refreshes_the_current_owner(self):
        job_id = uuid4()
        old_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        with self.sessions() as db:
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=uuid4(), status="running", worker_id="worker-1", locked_at=old_time))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions):
            self.assertFalse(refresh_document_job_lease(job_id, "worker-2"))
            self.assertTrue(refresh_document_job_lease(job_id, "worker-1"))

        with self.sessions() as db:
            refreshed = db.get(ProcessingJob, job_id)
            self.assertEqual(refreshed.worker_id, "worker-1")
            self.assertGreater(refreshed.locked_at.replace(tzinfo=timezone.utc), old_time)

    def test_processing_cannot_bypass_claim_or_use_another_owner(self):
        job_id = uuid4()
        with self.sessions() as db:
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=uuid4(), status="queued"))
            db.commit()

        with patch("app.services.document_jobs.SessionLocal", self.sessions), patch.object(document_jobs, "_progress") as progress:
            document_jobs.process_document_job(job_id, "worker-without-claim")
            self.assertEqual(claim_document_job("owner"), job_id)
            document_jobs.process_document_job(job_id, "different-worker")

        progress.assert_not_called()

    def test_progress_is_fenced_by_current_owner(self):
        job_id = uuid4()
        document = SimpleNamespace(processing_progress=0, processing_stage="queued", status="queued")
        with self.sessions() as db:
            job = ProcessingJob(id=job_id, organization_id=uuid4(), document_id=uuid4(), status="running", worker_id="new-owner", locked_at=datetime.now(timezone.utc))
            db.add(job)
            db.commit()
            with self.assertRaises(DocumentJobOwnershipLost):
                document_jobs._progress(db, document, job, "old-owner", 65, "indexing")

        with self.sessions() as db:
            job = db.get(ProcessingJob, job_id)
            self.assertEqual((job.worker_id, job.progress, job.stage), ("new-owner", 0, "queued"))
        self.assertEqual((document.processing_progress, document.processing_stage, document.status), (0, "queued", "queued"))


class DocumentIndexRetryTests(unittest.TestCase):
    def test_outbox_created_when_qdrant_apply_fails(self):
        """With the outbox pattern, Qdrant failures during immediate apply do NOT
        fail the job. The SQL transaction commits with a pending outbox entry,
        and the reconciler is responsible for eventual consistency."""
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=True)
        document_id, job_id = uuid4(), uuid4()
        with sessions() as db:
            db.add(Document(id=document_id, organization_id=uuid4(), filename="test.txt", storage_path="test.txt"))
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=document_id))
            db.commit()
        generated = [("first chunk", 0, "parent"), ("second chunk", 0, "parent")]
        provenance = {"provider": "mineru", "model": "vlm", "completed_at": "2026-09-24T00:00:00+00:00"}
        with patch.object(document_jobs, "BASE_DIR", Path.cwd()), patch.object(document_jobs, "SessionLocal", sessions), patch.object(document_jobs, "extract_text_with_provenance", return_value=ExtractionResult("source text", provenance)), patch.object(document_jobs, "hierarchical_chunks", return_value=generated), patch("app.services.incremental_index.hierarchical_chunks", return_value=generated), patch("app.services.incremental_index.enrich_chunk", return_value=([], [])), patch("pathlib.Path.write_text"), patch.object(document_jobs, "get_vector_store") as factory:
            client = factory.return_value
            # Simulate Qdrant failure during immediate post-commit apply
            client.replace_document_chunks.side_effect = QdrantError("Connection lost")
            worker_id = "test-worker"
            self.assertEqual(document_jobs.claim_document_job(worker_id), job_id)
            document_jobs.process_document_job(job_id, worker_id)
            with sessions() as db:
                # Job should complete successfully despite Qdrant failure
                completed_job = db.get(ProcessingJob, job_id)
                self.assertEqual(completed_job.status, "completed")
                document = db.get(Document, document_id)
                self.assertEqual(document.status, "indexed")
                self.assertEqual(document.ocr_provenance, provenance)
                self.assertIsNotNone(document.content_checksum)
                self.assertEqual(len(document.chunks), 2)
                # Outbox entry should remain pending for reconciler
                outbox_entries = list(db.query(IndexingOutbox).filter_by(document_id=document_id, status="pending"))
                self.assertEqual(len(outbox_entries), 1)
                self.assertEqual(outbox_entries[0].action, "replace_document_chunks")
                self.assertEqual(outbox_entries[0].payload["document_id"], str(document_id))
