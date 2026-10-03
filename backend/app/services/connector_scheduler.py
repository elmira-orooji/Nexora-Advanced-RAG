import logging
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError

from sqlalchemy import and_, or_, select

from app.core.config import (
    CONNECTOR_SYNC_MAX_ATTEMPTS,
    CONNECTOR_SYNC_RETRY_BASE_SECONDS,
    CONNECTOR_SYNC_RETRY_MAX_SECONDS,
)
from app.db.database import SessionLocal
from app.models.connector import Connector
from app.models.user import User
from app.services.connector_sync import ConnectorSyncError, sync_connector
from app.services.connector_lock import connector_sync_lock
from app.services.provider_errors import VectorStoreError
from app.services.operational_alerts import send_operational_alert
from app.services.operational_metrics import increment
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)


def _delay(interval: str) -> timedelta:
    return {"hourly": timedelta(hours=1), "daily": timedelta(days=1), "weekly": timedelta(days=7)}.get(interval, timedelta(days=1))


def _retryable_connector_error(exc: Exception) -> bool:
    """Classify transient connector errors that are worth retrying with backoff."""
    if isinstance(exc, VectorStoreError):
        return exc.status_code is None or exc.status_code in {408, 429} or exc.status_code >= 500
    if isinstance(exc, HTTPError):
        return exc.code in {408, 429} or exc.code >= 500
    if isinstance(exc, (URLError, TimeoutError, ConnectionError, OSError)):
        return True
    return False


def _connector_retry_delay(attempts: int) -> int:
    return min(CONNECTOR_SYNC_RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)), CONNECTOR_SYNC_RETRY_MAX_SECONDS)


def _connector_failure_values(exc: Exception, attempts: int, now: datetime) -> dict:
    retrying = _retryable_connector_error(exc) and attempts < CONNECTOR_SYNC_MAX_ATTEMPTS
    return {
        "status": "retrying" if retrying else "dead_letter",
        "error": str(exc)[:500],
        "error_type": type(exc).__name__,
        "next_attempt_at": now + timedelta(seconds=_connector_retry_delay(attempts)) if retrying else None,
        "dead_lettered_at": None if retrying else now,
    }


def run_due_connector_syncs() -> int:
    now = datetime.now(timezone.utc); processed = 0
    attempted = set()
    while processed < 10:
        with SessionLocal() as db:
            # Claim only the row we will process before commit releases its lock.
            item = db.scalar(select(Connector).where(
                Connector.connector_type != "webhook", Connector.id.not_in(attempted),
                Connector.dead_lettered_at.is_(None),
                or_(
                    Connector.status == "syncing",
                    and_(
                        Connector.schedule_enabled.is_(True),
                        or_(
                            Connector.next_attempt_at <= now,
                            Connector.next_sync_at <= now,
                        ),
                    ),
                ),
            ).order_by(Connector.status.desc(), Connector.next_attempt_at.nullslast(), Connector.next_sync_at, Connector.id).with_for_update(skip_locked=True).limit(1))
            if item is None:
                break
            connector_id = item.id
            attempted.add(connector_id)
            with connector_sync_lock(db, connector_id) as acquired:
                if not acquired:
                    continue
                item.status = "syncing"; item.last_error = None; item.error_type = None
                item.next_attempt_at = None
                item.attempts += 1
                scheduled_next = now + _delay(item.schedule_interval) if item.schedule_enabled else None
                item.next_sync_at = scheduled_next
                db.commit()
                try:
                    sync_connector(connector_id)
                    item = db.get(Connector, connector_id)
                    item.status = "ready"
                    item.last_synced_at = datetime.now(timezone.utc)
                    item.last_error = None
                    item.error_type = None
                    item.attempts = 0
                    item.dead_lettered_at = None
                    item.next_attempt_at = None
                    item.next_sync_at = scheduled_next
                    creator = db.get(User, item.created_by_id)
                    if creator is not None:
                        create_notification(db, user_id=creator.id, organization_id=creator.organization_id, kind="connector_synced", severity="success", title="Connector sync completed", body=f"{item.name} was synchronized successfully.")
                except Exception as exc:
                    logger.exception("Scheduled connector sync failed", extra={"connector_id": str(connector_id)})
                    increment("connector_sync_failures_total", connector_type=item.connector_type)
                    db.rollback()
                    item = db.get(Connector, connector_id)
                    failure = _connector_failure_values(exc, item.attempts, datetime.now(timezone.utc))
                    item.status = failure["status"]
                    item.last_error = failure["error"]
                    item.error_type = failure["error_type"]
                    item.next_attempt_at = failure["next_attempt_at"]
                    item.dead_lettered_at = failure["dead_lettered_at"]
                    if failure["status"] == "dead_letter":
                        item.next_sync_at = None
                        creator = db.get(User, item.created_by_id)
                        if creator is not None:
                            create_notification(db, user_id=creator.id, organization_id=creator.organization_id, kind="connector_failed", severity="error", title="Connector sync failed", body=f"{item.name} could not be synchronized after multiple attempts. Review its configuration and retry it.")
                        send_operational_alert(
                            "connector-dead-letter",
                            "Connector sync reached its retry limit",
                            f"Connector {connector_id} could not be synchronized after {item.attempts} attempts. Review its configuration and the service logs.",
                        )
                    elif item.schedule_enabled:
                        item.next_sync_at = scheduled_next
                    else:
                        item.next_sync_at = None
                db.commit(); processed += 1
    return processed
