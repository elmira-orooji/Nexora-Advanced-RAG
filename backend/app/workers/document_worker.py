import logging
import os
import signal
import socket
import time
import uuid

from app.core.config import (
    DATA_RETENTION_ENABLED,
    DATA_RETENTION_MAINTENANCE_SECONDS,
    DOCUMENT_JOB_POLL_SECONDS,
    WORKER_HEARTBEAT_SECONDS,
)
from app.core.logging import configure_logging
from app.services.documents.document_jobs import claim_document_job, maintain_document_job_lease, process_document_job, recover_document_jobs
from app.services.operations.data_retention import purge_expired_operational_data
from app.services.documents.indexing_reconciler import reconcile_indexing_outbox
from app.services.operations.operational_alerts import deliver_due_operational_alerts
from app.services.operations.worker_heartbeat import deregister_worker, maintain_worker_heartbeat, register_worker

logger = logging.getLogger(__name__)
_stopping = False


def _stop(_signum, _frame) -> None:
    global _stopping
    _stopping = True


class DocumentWorker:
    """Small orchestration loop; job state transitions belong to document_jobs."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.metadata = {"hostname": socket.gethostname(), "pid": os.getpid()}
        self.next_recovery = 0.0
        self.next_reconcile = 0.0
        self.next_alert_delivery = 0.0
        self.next_retention = 0.0

    def run(self) -> None:
        register_worker(worker_id=self.worker_id, worker_type="document_worker", metadata=self.metadata)
        try:
            with maintain_worker_heartbeat(self.worker_id, "document_worker", self.metadata, WORKER_HEARTBEAT_SECONDS):
                self._recover_jobs()
                started_at = time.monotonic()
                self.next_recovery = started_at + 60
                self.next_reconcile = started_at + 10
                self.next_alert_delivery = started_at + 10
                self.next_retention = started_at + 60
                logger.info("Document worker started", extra={"worker_id": self.worker_id})
                while not _stopping:
                    self._run_due_maintenance()
                    if not self._process_next_job():
                        time.sleep(DOCUMENT_JOB_POLL_SECONDS)
        finally:
            deregister_worker(self.worker_id)
            logger.info("Document worker stopped", extra={"worker_id": self.worker_id})

    def _run_due_maintenance(self) -> None:
        now = time.monotonic()
        if now >= self.next_recovery:
            self._recover_jobs()
            self.next_recovery = now + 60
        if now >= self.next_reconcile:
            self._reconcile_outbox()
            self.next_reconcile = now + 30
        if now >= self.next_alert_delivery:
            self._deliver_alerts()
            self.next_alert_delivery = now + 30
        if DATA_RETENTION_ENABLED and now >= self.next_retention:
            self._run_data_retention()
            self.next_retention = now + DATA_RETENTION_MAINTENANCE_SECONDS

    def _recover_jobs(self) -> None:
        recovered = recover_document_jobs()
        if recovered:
            logger.warning("Recovered abandoned document jobs", extra={"recovered_jobs": recovered})

    def _reconcile_outbox(self) -> None:
        try:
            reconciled = reconcile_indexing_outbox()
            if reconciled:
                logger.info("Reconciled pending indexing outbox entries", extra={"reconciled": reconciled})
        except Exception:
            logger.exception("Indexing outbox reconciliation failed")

    def _deliver_alerts(self) -> None:
        try:
            delivered = deliver_due_operational_alerts()
            if delivered:
                logger.info("Delivered operational alerts", extra={"delivered_alerts": delivered})
        except Exception:
            logger.exception("Operational alert delivery cycle failed")

    def _run_data_retention(self) -> None:
        try:
            result = purge_expired_operational_data()
            if result.total:
                logger.info("Purged expired operational data", extra={"retention": result.as_dict()})
        except Exception:
            logger.exception("Data retention cycle failed")

    def _process_next_job(self) -> bool:
        job_id = claim_document_job(self.worker_id)
        if job_id is None:
            return False
        try:
            with maintain_document_job_lease(job_id, self.worker_id):
                process_document_job(job_id, self.worker_id)
        except Exception:
            logger.exception("Unhandled document job failure", extra={"job_id": str(job_id)})
        return True


def run() -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    DocumentWorker(worker_id).run()


if __name__ == "__main__":
    configure_logging()
    run()
