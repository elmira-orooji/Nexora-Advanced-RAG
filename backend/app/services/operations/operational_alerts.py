"""Durable, best-effort operational email delivery."""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import or_, select, update

from app.core.config import ALERT_RECIPIENTS, OPERATIONAL_ALERT_COOLDOWN_SECONDS, SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_TIMEOUT_SECONDS, SMTP_USERNAME, SMTP_USE_TLS
from app.db.database import SessionLocal
from app.models.operational_alert import OperationalAlert

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 60
LOCK_SECONDS = 300


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM_EMAIL and ALERT_RECIPIENTS)


def queue_operational_alert(key: str, subject: str, body: str) -> bool:
    """Persist one alert. Failure to queue never changes the caller's outcome."""
    if not is_configured():
        return False
    now = datetime.now(timezone.utc)
    try:
        with SessionLocal() as db:
            recent = db.scalar(select(OperationalAlert.id).where(
                OperationalAlert.deduplication_key == key,
                OperationalAlert.created_at >= now - timedelta(seconds=OPERATIONAL_ALERT_COOLDOWN_SECONDS),
                OperationalAlert.status.in_(("queued", "retrying", "sending", "sent")),
            ))
            if recent is not None:
                return False
            db.add(OperationalAlert(deduplication_key=key[:120], subject=subject[:240], body=body, status="queued", next_attempt_at=now))
            db.commit()
            return True
    except Exception:
        logger.exception("Could not persist operational alert", extra={"alert_key": key})
        return False


def deliver_due_operational_alerts(limit: int = 10) -> int:
    """Deliver due emails with retry state persisted before and after SMTP I/O."""
    if not is_configured():
        return 0
    delivered = 0
    _recover_expired_claims()
    for _ in range(limit):
        alert = _claim_due_alert()
        if alert is None:
            break
        try:
            _send_email(alert.subject, alert.body)
        except (OSError, smtplib.SMTPException) as exc:
            _mark_failed(alert.id, exc)
        else:
            _mark_delivered(alert.id)
            delivered += 1
    return delivered


def _recover_expired_claims() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=LOCK_SECONDS)
    with SessionLocal() as db:
        db.execute(update(OperationalAlert).where(OperationalAlert.status == "sending", OperationalAlert.locked_at < cutoff).values(status="retrying", locked_at=None, next_attempt_at=datetime.now(timezone.utc)))
        db.commit()


def _claim_due_alert() -> OperationalAlert | None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db, db.begin():
        alert = db.scalar(select(OperationalAlert).where(
            OperationalAlert.status.in_(("queued", "retrying")),
            or_(OperationalAlert.next_attempt_at.is_(None), OperationalAlert.next_attempt_at <= now),
        ).order_by(OperationalAlert.created_at).with_for_update(skip_locked=True).limit(1))
        if alert is None:
            return None
        alert.status = "sending"
        alert.attempts += 1
        alert.locked_at = now
        db.flush()
        db.expunge(alert)
        return alert


def _mark_delivered(alert_id) -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.execute(update(OperationalAlert).where(OperationalAlert.id == alert_id, OperationalAlert.status == "sending").values(status="sent", delivered_at=now, locked_at=None, last_error=None, next_attempt_at=None))
        db.commit()


def _mark_failed(alert_id, exc: Exception) -> None:
    with SessionLocal() as db:
        alert = db.get(OperationalAlert, alert_id)
        if alert is None or alert.status != "sending":
            return
        exhausted = alert.attempts >= MAX_ATTEMPTS
        delay = min(RETRY_BASE_SECONDS * (2 ** max(0, alert.attempts - 1)), 3600)
        alert.status = "dead_letter" if exhausted else "retrying"
        alert.locked_at = None
        alert.next_attempt_at = None if exhausted else datetime.now(timezone.utc) + timedelta(seconds=delay)
        alert.last_error = str(exc)[:500]
        db.commit()
        logger.warning("Operational alert delivery failed", extra={"alert_id": str(alert_id), "attempts": alert.attempts, "dead_letter": exhausted})


def _send_email(subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = f"[Nexora] {subject}"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = ", ".join(ALERT_RECIPIENTS)
    message.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as client:
        if SMTP_USE_TLS:
            client.starttls(context=ssl.create_default_context())
        if SMTP_USERNAME:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
        client.send_message(message)


# Backwards-compatible name for existing integrations. Calls are now durable.
send_operational_alert = queue_operational_alert
