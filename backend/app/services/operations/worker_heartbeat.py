"""Worker registry heartbeat service.

Provides persistent liveness tracking for workers and schedulers.
Each worker upserts its record on startup and periodically updates
`last_heartbeat` regardless of whether it is actively processing jobs.
"""

import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import select, update

from app.db.database import SessionLocal
from app.models.worker_registry import WorkerRegistry

logger = logging.getLogger(__name__)


@contextmanager
def maintain_worker_heartbeat(
    worker_id: str,
    worker_type: str,
    metadata: dict | None,
    interval_seconds: float,
) -> Iterator[None]:
    """Send registry heartbeats independently of the worker's main loop."""
    stop_event = threading.Event()

    def heartbeat_loop() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                if not send_heartbeat(worker_id):
                    logger.warning(
                        "Failed to send heartbeat; re-registering",
                        extra={"worker_id": worker_id},
                    )
                    register_worker(worker_id, worker_type, metadata)
            except Exception:
                logger.exception(
                    "Worker heartbeat failed",
                    extra={"worker_id": worker_id},
                )

    thread = threading.Thread(
        target=heartbeat_loop,
        name=f"worker-heartbeat-{worker_id}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=max(interval_seconds, 1))


def register_worker(
    worker_id: str,
    worker_type: str,
    metadata: dict | None = None,
) -> None:
    """Register or re-register a worker with an initial heartbeat."""
    now = datetime.now(timezone.utc)
    meta_str = json.dumps(metadata) if metadata else None
    with SessionLocal() as db, db.begin():
        existing = db.scalar(
            select(WorkerRegistry).where(WorkerRegistry.id == worker_id)
        )
        if existing:
            existing.last_heartbeat = now
            existing.status = "active"
            existing.metadata_json = meta_str
        else:
            db.add(
                WorkerRegistry(
                    id=worker_id,
                    type=worker_type,
                    last_heartbeat=now,
                    status="active",
                    metadata_json=meta_str,
                )
            )
    logger.info(
        "Worker registered",
        extra={"worker_id": worker_id, "type": worker_type},
    )


def send_heartbeat(worker_id: str) -> bool:
    """Update the last_heartbeat timestamp for a worker.

    Returns True if the worker was found and updated, False otherwise.
    """
    now = datetime.now(timezone.utc)
    with SessionLocal() as db, db.begin():
        result = db.execute(
            update(WorkerRegistry)
            .where(WorkerRegistry.id == worker_id, WorkerRegistry.status == "active")
            .values(last_heartbeat=now)
        )
        return result.rowcount == 1


def deregister_worker(worker_id: str) -> None:
    """Mark a worker as stopped in the registry."""
    with SessionLocal() as db, db.begin():
        db.execute(
            update(WorkerRegistry)
            .where(WorkerRegistry.id == worker_id)
            .values(status="stopped")
        )
    logger.info("Worker deregistered", extra={"worker_id": worker_id})


def get_available_worker_types(threshold_seconds: int) -> set[str]:
    """Return worker types with at least one active, recent heartbeat."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
    with SessionLocal() as db:
        return set(
            db.scalars(
                select(WorkerRegistry.type).where(
                    WorkerRegistry.status == "active",
                    WorkerRegistry.last_heartbeat >= cutoff,
                )
            ).all()
        )


def get_stale_workers(threshold_seconds: int) -> list[dict]:
    """Return workers whose last heartbeat is older than threshold_seconds."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
    with SessionLocal() as db:
        rows = db.scalars(
            select(WorkerRegistry).where(
                WorkerRegistry.status == "active",
                WorkerRegistry.last_heartbeat < cutoff,
            )
        ).all()
        return [
            {
                "id": r.id,
                "type": r.type,
                "last_heartbeat": r.last_heartbeat.isoformat(),
                "status": r.status,
            }
            for r in rows
        ]
