import logging
import os
import signal
import socket
import threading
import uuid

from app.core.config import CONNECTOR_SCHEDULER_POLL_SECONDS, WORKER_HEARTBEAT_SECONDS
from app.core.logging import configure_logging
from app.services.connectors.connector_scheduler import run_due_connector_syncs
from app.services.operations.worker_heartbeat import deregister_worker, maintain_worker_heartbeat, register_worker

logger = logging.getLogger(__name__)


def scheduler_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            run_due_connector_syncs()
        except Exception:
            logger.exception("Connector scheduler iteration failed")
        stop_event.wait(CONNECTOR_SCHEDULER_POLL_SECONDS)


def run() -> None:
    worker_id = f"scheduler:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    stop_event = threading.Event()

    def stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    # Register this scheduler in the persistent registry
    register_worker(
        worker_id=worker_id,
        worker_type="connector_scheduler",
        metadata={"hostname": socket.gethostname(), "pid": os.getpid()},
    )

    logger.info("Connector scheduler worker started", extra={"worker_id": worker_id})
    try:
        with maintain_worker_heartbeat(
            worker_id,
            "connector_scheduler",
            {"hostname": socket.gethostname(), "pid": os.getpid()},
            WORKER_HEARTBEAT_SECONDS,
        ):
            scheduler_loop(stop_event)
    finally:
        deregister_worker(worker_id)
        logger.info("Connector scheduler worker stopped", extra={"worker_id": worker_id})


if __name__ == "__main__":
    configure_logging()
    run()
