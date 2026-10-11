"""Bounded retention for operational data that is safe to purge automatically."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_

from app.core.config import (
    DATA_RETENTION_CHAT_SHARE_DAYS,
    DATA_RETENTION_LLM_USAGE_DAYS,
    DATA_RETENTION_READ_NOTIFICATION_DAYS,
    DATA_RETENTION_SESSION_DAYS,
)
from app.db.database import SessionLocal
from app.models.auth_session import AuthSession
from app.models.chat_share import ChatShare
from app.models.llm_usage import LLMUsage
from app.models.notification import Notification
from app.services.operations.operational_metrics import increment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPurgeResult:
    sessions: int = 0
    chat_shares: int = 0
    notifications: int = 0
    llm_usage: int = 0

    @property
    def total(self) -> int:
        return self.sessions + self.chat_shares + self.notifications + self.llm_usage

    def as_dict(self) -> dict[str, int]:
        result = asdict(self)
        result["total"] = self.total
        return result


def purge_expired_operational_data(
    *,
    now: datetime | None = None,
    session_days: int = DATA_RETENTION_SESSION_DAYS,
    chat_share_days: int = DATA_RETENTION_CHAT_SHARE_DAYS,
    notification_days: int = DATA_RETENTION_READ_NOTIFICATION_DAYS,
    llm_usage_days: int = DATA_RETENTION_LLM_USAGE_DAYS,
) -> RetentionPurgeResult:
    """Atomically remove expired operational records.

    Original files, extracted text, chunks, embeddings, chat messages and audit
    trails are intentionally excluded. Their deletion has different recovery and
    legal implications and must use the organization deletion workflow.
    """
    current_time = now or datetime.now(timezone.utc)
    session_cutoff = current_time - timedelta(days=session_days)
    share_cutoff = current_time - timedelta(days=chat_share_days)
    notification_cutoff = current_time - timedelta(days=notification_days)
    usage_cutoff = current_time - timedelta(days=llm_usage_days)

    db = SessionLocal()
    try:
        sessions = db.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.expires_at < session_cutoff,
                    and_(AuthSession.revoked_at.is_not(None), AuthSession.revoked_at < session_cutoff),
                )
            )
        ).rowcount or 0
        chat_shares = db.execute(
            delete(ChatShare).where(
                or_(
                    and_(ChatShare.expires_at.is_not(None), ChatShare.expires_at < share_cutoff),
                    and_(ChatShare.revoked_at.is_not(None), ChatShare.revoked_at < share_cutoff),
                )
            )
        ).rowcount or 0
        notifications = db.execute(
            delete(Notification).where(
                Notification.read_at.is_not(None), Notification.read_at < notification_cutoff
            )
        ).rowcount or 0
        llm_usage = db.execute(delete(LLMUsage).where(LLMUsage.created_at < usage_cutoff)).rowcount or 0
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    result = RetentionPurgeResult(
        sessions=sessions,
        chat_shares=chat_shares,
        notifications=notifications,
        llm_usage=llm_usage,
    )
    for data_type, count in result.as_dict().items():
        if data_type != "total" and count:
            increment("retention_records_deleted_total", value=count, data_type=data_type)
    logger.info("Data retention cycle completed", extra={"retention": result.as_dict()})
    return result
