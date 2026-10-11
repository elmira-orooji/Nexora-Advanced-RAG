import hashlib
import hmac
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import (
    AUTH_ACCOUNT_FAILURE_LIMIT,
    AUTH_FAILURE_WINDOW_SECONDS,
    AUTH_IP_FAILURE_LIMIT,
    AUTH_LOCK_BASE_SECONDS,
    AUTH_LOCK_MAX_SECONDS,
    AUTH_SECRET_KEY,
)
from app.models.login_throttle import LoginThrottle

_cleanup_lock = threading.Lock()
_last_cleanup = 0.0
_CLEANUP_INTERVAL_SECONDS = 3600


def _key(kind: str, value: str) -> str:
    normalized = value.strip().lower()
    return hmac.new(AUTH_SECRET_KEY.encode(), f"{kind}:{normalized}".encode(), hashlib.sha256).hexdigest()


def throttle_keys(organization: str, username: str, client_ip: str) -> tuple[str, str]:
    return _key("account", f"{organization}:{username}"), _key("ip", client_ip or "unknown")


def retry_after(db: Session, keys: tuple[str, str], now: datetime | None = None) -> int | None:
    current = now or datetime.now(timezone.utc)
    locks = db.scalars(select(LoginThrottle.locked_until).where(LoginThrottle.key_hash.in_(keys), LoginThrottle.locked_until > current)).all()
    if not locks:
        return None
    return max(1, int(max(locks).timestamp() - current.timestamp()) + 1)


def _lock_seconds(failures: int, limit: int) -> int:
    if failures < limit:
        return 0
    return min(AUTH_LOCK_BASE_SECONDS * (2 ** (failures - limit)), AUTH_LOCK_MAX_SECONDS)


def _prune_expired_if_due(db: Session, current: datetime) -> None:
    global _last_cleanup
    monotonic_now = time.monotonic()
    with _cleanup_lock:
        if monotonic_now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        _last_cleanup = monotonic_now
        stale_before = current - timedelta(seconds=AUTH_FAILURE_WINDOW_SECONDS)
        db.execute(delete(LoginThrottle).where(LoginThrottle.updated_at < stale_before, (LoginThrottle.locked_until.is_(None)) | (LoginThrottle.locked_until < current)))


def record_failure(db: Session, keys: tuple[str, str], now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    _prune_expired_if_due(db, current)
    cutoff = current - timedelta(seconds=AUTH_FAILURE_WINDOW_SECONDS)
    longest_lock = 0
    for key_hash, limit in zip(keys, (AUTH_ACCOUNT_FAILURE_LIMIT, AUTH_IP_FAILURE_LIMIT), strict=True):
        statement = insert(LoginThrottle).values(key_hash=key_hash, failures=1, window_started_at=current, locked_until=None)
        statement = statement.on_conflict_do_update(
            index_elements=[LoginThrottle.key_hash],
            set_={
                "failures": case((LoginThrottle.window_started_at < cutoff, 1), else_=LoginThrottle.failures + 1),
                "window_started_at": case((LoginThrottle.window_started_at < cutoff, current), else_=LoginThrottle.window_started_at),
                "updated_at": current,
            },
        ).returning(LoginThrottle.failures)
        failures = db.scalar(statement)
        lock_seconds = _lock_seconds(int(failures), limit)
        if lock_seconds:
            locked_until = current + timedelta(seconds=lock_seconds)
            db.execute(update(LoginThrottle).where(LoginThrottle.key_hash == key_hash).values(locked_until=locked_until))
            longest_lock = max(longest_lock, lock_seconds)
    db.commit()
    return longest_lock


def clear_account_failures(db: Session, account_key: str) -> None:
    db.execute(delete(LoginThrottle).where(LoginThrottle.key_hash == account_key))
    db.commit()
