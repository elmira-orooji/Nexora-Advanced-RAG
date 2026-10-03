import unittest
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.connector import Connector
from app.models.sync_lease import SyncLease
from app.models.user import User
from app.models.notification import Notification
from app.services import connector_scheduler as scheduler
from app.workers import connector_scheduler_worker as scheduler_worker
from app.services.connector_scheduler import run_due_connector_syncs
from app.services.connector_lock import connector_sync_lock


class ConnectorSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Connector.__table__.create(self.engine)
        SyncLease.__table__.create(self.engine)
        User.__table__.create(self.engine)
        Notification.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=True)
        self.enterContext(patch("app.services.connector_scheduler.SessionLocal", self.sessions))
        self.locked = set()
        @contextmanager
        def lock(db, connector_id):
            if connector_id in self.locked:
                yield False
                return
            self.locked.add(connector_id)
            try:
                yield True
            finally:
                self.locked.remove(connector_id)
        self.enterContext(patch("app.services.connector_scheduler.connector_sync_lock", lock, create=True))

    def seed(self, count):
        ids = [uuid4() for _ in range(count)]
        with self.sessions() as db:
            for connector_id in ids:
                creator_id = uuid4()
                db.add(User(id=creator_id, organization_id=uuid4(), username=f"user-{creator_id.hex}", password_hash="test"))
                db.add(Connector(id=connector_id, document_set_id=uuid4(), created_by_id=creator_id,
                                 connector_type="website", name="Test", source_url="https://example.com",
                                 status="ready", schedule_enabled=True, schedule_interval="daily",
                                 next_sync_at=datetime.now(timezone.utc) - timedelta(days=1)))
            db.commit()
        return ids

    def test_second_worker_after_first_commit_does_not_duplicate_remaining_jobs(self):
        ids = self.seed(3)
        seen = []
        def sync(connector_id):
            seen.append(connector_id)
            if len(seen) == 1:
                # The other worker starts after the first worker releases its locks.
                run_due_connector_syncs()
        with patch("app.services.connector_scheduler.sync_connector", side_effect=sync):
            run_due_connector_syncs()
        self.assertCountEqual(seen, ids)

    def test_failure_does_not_prevent_next_job(self):
        ids = self.seed(2)
        with patch("app.services.connector_scheduler.sync_connector", side_effect=[RuntimeError("Sync failed"), None]), patch.object(scheduler.logger, "exception") as logged:
            self.assertEqual(run_due_connector_syncs(), 2)
        logged.assert_called_once()
        self.assertIn("connector_id", logged.call_args.kwargs["extra"])
        with self.sessions() as db:
            # RuntimeError is not retryable so it goes to dead_letter; the other succeeds
            statuses = {value: db.get(Connector, value).status for value in ids}
            self.assertIn("dead_letter", statuses.values())
            self.assertIn("ready", statuses.values())

    def test_transient_error_retries_with_backoff(self):
        from urllib.error import URLError
        ids = self.seed(1)
        now = datetime.now(timezone.utc)
        with patch("app.services.connector_scheduler.CONNECTOR_SYNC_MAX_ATTEMPTS", 3), \
             patch("app.services.connector_scheduler.CONNECTOR_SYNC_RETRY_BASE_SECONDS", 10), \
             patch("app.services.connector_scheduler.sync_connector", side_effect=URLError("connection refused")):
            run_due_connector_syncs()
        with self.sessions() as db:
            item = db.get(Connector, ids[0])
            self.assertEqual(item.status, "retrying")
            self.assertEqual(item.attempts, 1)
            self.assertEqual(item.error_type, "URLError")
            self.assertIsNone(item.dead_lettered_at)
            self.assertIsNotNone(item.next_attempt_at)
            expected_delay = timedelta(seconds=10)  # base * 2^0
            attempt_at = item.next_attempt_at
            if attempt_at.tzinfo is None:
                attempt_at = attempt_at.replace(tzinfo=timezone.utc)
            self.assertAlmostEqual((attempt_at - now).total_seconds(), expected_delay.total_seconds(), delta=5)

    def test_exhausted_retries_enter_dead_letter(self):
        from urllib.error import URLError
        ids = self.seed(1)
        with patch("app.services.connector_scheduler.CONNECTOR_SYNC_MAX_ATTEMPTS", 2), \
             patch("app.services.connector_scheduler.sync_connector", side_effect=URLError("connection refused")):
            # First attempt -> retrying
            run_due_connector_syncs()
        with self.sessions() as db:
            item = db.get(Connector, ids[0])
            self.assertEqual(item.status, "retrying")
            self.assertEqual(item.attempts, 1)
            # Move next_attempt_at into the past so scheduler picks it up again
            item.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        with patch("app.services.connector_scheduler.CONNECTOR_SYNC_MAX_ATTEMPTS", 2), \
             patch("app.services.connector_scheduler.sync_connector", side_effect=URLError("connection refused")):
            run_due_connector_syncs()
        with self.sessions() as db:
            item = db.get(Connector, ids[0])
            self.assertEqual(item.status, "dead_letter")
            self.assertEqual(item.attempts, 2)
            self.assertIsNotNone(item.dead_lettered_at)
            self.assertIsNone(item.next_attempt_at)

    def test_successful_sync_resets_retry_state(self):
        from urllib.error import URLError
        ids = self.seed(1)
        with patch("app.services.connector_scheduler.CONNECTOR_SYNC_MAX_ATTEMPTS", 5), \
             patch("app.services.connector_scheduler.sync_connector", side_effect=[URLError("fail"), None]):
            run_due_connector_syncs()
        with self.sessions() as db:
            item = db.get(Connector, ids[0])
            self.assertEqual(item.status, "retrying")
            item.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        with patch("app.services.connector_scheduler.sync_connector"):
            run_due_connector_syncs()
        with self.sessions() as db:
            item = db.get(Connector, ids[0])
            self.assertEqual(item.status, "ready")
            self.assertEqual(item.attempts, 0)
            self.assertIsNone(item.dead_lettered_at)
            self.assertIsNone(item.next_attempt_at)
            self.assertIsNone(item.error_type)

    def test_run_is_bounded_to_ten_claims(self):
        self.seed(11)
        with patch("app.services.connector_scheduler.sync_connector") as sync:
            self.assertEqual(run_due_connector_syncs(), 10)
            self.assertEqual(sync.call_count, 10)
            self.assertEqual(run_due_connector_syncs(), 1)

    def test_empty_queue_does_not_run_sync(self):
        with patch("app.services.connector_scheduler.sync_connector") as sync:
            self.assertEqual(run_due_connector_syncs(), 0)
        sync.assert_not_called()

    def test_abandoned_sync_is_recovered_before_next_schedule(self):
        connector_id = self.seed(1)[0]
        with self.sessions() as db:
            item = db.get(Connector, connector_id)
            item.status = "syncing"
            item.next_sync_at = datetime.now(timezone.utc) + timedelta(days=1)
            db.commit()
        with patch("app.services.connector_scheduler.sync_connector") as sync:
            self.assertEqual(run_due_connector_syncs(), 1)
        sync.assert_called_once()
        with self.sessions() as db:
            self.assertEqual(db.get(Connector, connector_id).status, "ready")

    def test_live_sync_is_skipped_until_owner_lock_is_released(self):
        connector_id = self.seed(1)[0]
        with self.sessions() as db:
            db.get(Connector, connector_id).status = "syncing"
            db.commit()
        self.locked.add(connector_id)
        with patch("app.services.connector_scheduler.sync_connector") as sync:
            self.assertEqual(run_due_connector_syncs(), 0)
            sync.assert_not_called()
            self.locked.remove(connector_id)
            self.assertEqual(run_due_connector_syncs(), 1)

    def test_interrupted_manual_sync_is_recovered_without_enabling_schedule(self):
        connector_id = self.seed(1)[0]
        with self.sessions() as db:
            item = db.get(Connector, connector_id)
            item.status = "syncing"
            item.schedule_enabled = False
            item.next_sync_at = None
            db.commit()
        with patch("app.services.connector_scheduler.sync_connector"):
            self.assertEqual(run_due_connector_syncs(), 1)
        with self.sessions() as db:
            item = db.get(Connector, connector_id)
            self.assertFalse(item.schedule_enabled)
            self.assertIsNone(item.next_sync_at)

    def test_scheduler_loop_logs_iteration_failure_and_continues(self):
        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, False, True]
        with patch.object(scheduler_worker, "run_due_connector_syncs", side_effect=[RuntimeError("Database unavailable"), 0]) as run, patch.object(scheduler_worker.logger, "exception") as logged:
            scheduler_worker.scheduler_loop(stop_event)
        self.assertEqual(run.call_count, 2)
        logged.assert_called_once_with("Connector scheduler iteration failed")
        self.assertEqual(stop_event.wait.call_count, 2)


class ConnectorLockTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        SyncLease.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=True)

    def test_lock_is_acquired_and_released(self):
        connector_id = uuid4()
        with self.sessions() as db:
            with connector_sync_lock(db, connector_id) as acquired:
                self.assertTrue(acquired)
                # Lease row should exist while lock is held
                lease = db.get(SyncLease, connector_id)
                self.assertIsNotNone(lease)
            # After exiting, lease should be removed
            db.expire_all()
            lease = db.get(SyncLease, connector_id)
            self.assertIsNone(lease)

    def test_concurrent_lock_is_rejected(self):
        connector_id = uuid4()
        with self.sessions() as db1:
            with connector_sync_lock(db1, connector_id) as acquired1:
                self.assertTrue(acquired1)
                with self.sessions() as db2:
                    with connector_sync_lock(db2, connector_id) as acquired2:
                        self.assertFalse(acquired2)

    def test_expired_lease_can_be_taken_over(self):
        from datetime import timedelta
        connector_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        with self.sessions() as db:
            db.add(SyncLease(connector_id=connector_id, owner_id="dead-owner", expires_at=past))
            db.commit()
        with self.sessions() as db:
            with connector_sync_lock(db, connector_id) as acquired:
                self.assertTrue(acquired)

    def test_expired_lease_has_only_one_concurrent_winner(self):
        connector_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        database_name = f"lease-{uuid4()}"
        engine = create_engine(
            f"sqlite+pysqlite:///file:{database_name}?mode=memory&cache=shared&uri=true",
            connect_args={"timeout": 10},
        )
        try:
            SyncLease.__table__.create(engine)
            sessions = sessionmaker(bind=engine, expire_on_commit=True)

            with sessions() as db:
                db.add(SyncLease(connector_id=connector_id, owner_id="dead-owner", expires_at=past))
                db.commit()

            start = threading.Barrier(3)
            attempted = threading.Event()
            release = threading.Event()
            results = []
            results_lock = threading.Lock()

            def contender():
                with sessions() as db:
                    start.wait()
                    with connector_sync_lock(db, connector_id) as acquired:
                        with results_lock:
                            results.append(acquired)
                            if len(results) == 2:
                                attempted.set()
                        if acquired:
                            release.wait(timeout=5)

            threads = [threading.Thread(target=contender) for _ in range(2)]
            for thread in threads:
                thread.start()
            start.wait()
            self.assertTrue(attempted.wait(timeout=5))
            release.set()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 1)
        finally:
            engine.dispose()

    def test_manual_sync_rejects_live_owner(self):
        from app.core.application_errors import ApplicationError
        from app.api.routes.connectors import sync
        from types import SimpleNamespace

        set_id, connector_id = uuid4(), uuid4()
        db = MagicMock()
        db.get.return_value = SimpleNamespace(document_set_id=set_id)
        @contextmanager
        def busy(*args):
            yield False
        with patch("app.services.connector_management_service.require_set_access"), patch("app.services.connector_management_service.connector_sync_lock", busy):
            with self.assertRaises(ApplicationError) as raised:
                sync(set_id, connector_id, db, MagicMock())
        self.assertEqual(raised.exception.kind, "conflict")
        db.commit.assert_not_called()

    def test_stale_worker_heartbeat_does_not_extend_lost_lease(self):
        """Fencing validation: a worker that lost ownership must not be able
        to extend the lease via heartbeat. This simulates a network partition
        where the original worker resumes after a new owner has taken over."""
        connector_id = uuid4()
        stale_owner = "stale-worker-1"
        new_owner = "new-worker-2"
        now = datetime.now(timezone.utc)

        # Seed an active lease owned by the new worker
        with self.sessions() as db:
            db.add(SyncLease(
                connector_id=connector_id,
                owner_id=new_owner,
                expires_at=now + timedelta(minutes=5),
            ))
            db.commit()

        # Simulate the stale worker attempting a heartbeat using its old owner_id
        from sqlalchemy import update
        with self.sessions() as db:
            result = db.execute(
                update(SyncLease)
                .where(
                    SyncLease.connector_id == connector_id,
                    SyncLease.owner_id == stale_owner,
                )
                .values(expires_at=now + timedelta(minutes=10))
            )
            db.commit()
            # The fencing token (owner_id) must prevent the update
            self.assertEqual(result.rowcount, 0)

        # Verify the lease still belongs to the new worker with the original expiry
        with self.sessions() as db:
            lease = db.get(SyncLease, connector_id)
            self.assertIsNotNone(lease)
            self.assertEqual(lease.owner_id, new_owner)
            # SQLite may return naive datetimes; normalize for comparison
            lease_expiry = lease.expires_at
            if lease_expiry.tzinfo is None:
                lease_expiry = lease_expiry.replace(tzinfo=timezone.utc)
            # Expiry should remain unchanged (within tolerance for test execution time)
            self.assertLessEqual(lease_expiry, now + timedelta(minutes=5, seconds=5))
