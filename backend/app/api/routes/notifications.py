import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.organization_id == user.organization_id)
        .order_by(Notification.created_at.desc())
        .limit(30)
    ).all()


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id, Notification.organization_id == user.organization_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
    return item


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.organization_id == user.organization_id, Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    db.commit()


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.organization_id == user.organization_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    db.delete(item)
    db.commit()
