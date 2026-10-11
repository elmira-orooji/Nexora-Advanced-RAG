"""Persistent, user-scoped in-product operation notifications."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    user_id: UUID | None,
    organization_id: UUID,
    kind: str,
    severity: str,
    title: str,
    body: str,
    target_path: str | None = "/home/knowledge",
) -> None:
    if user_id is None:
        return
    db.add(Notification(
        user_id=user_id,
        organization_id=organization_id,
        kind=kind,
        severity=severity,
        title=title[:160],
        body=body[:2000],
        target_path=target_path,
    ))
