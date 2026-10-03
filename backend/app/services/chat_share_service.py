from app.core.application_errors import ApplicationError
from app.services.transactions import transaction
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.chat_share import ChatShare
from app.models.user import User
from app.repositories.chat_share_repository import ChatShareRepository
from app.schemas.chat_share import ChatShareCreate, ChatShareCreated, ChatShareSummary, ChatShareView, SharedMessage


def _hash(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()


def _resolve(token: str, db: Session) -> ChatShare:
    item = ChatShareRepository(db).resolve(_hash(token))
    now = datetime.now(timezone.utc)
    if item is None or (item.expires_at is not None and item.expires_at <= now):
        raise ApplicationError(kind="not_found", detail="Shared conversation not found or expired")
    return item


def _view(item: ChatShare, db: Session) -> ChatShareView:
    owner = ChatShareRepository(db).owner(item.owner_id)
    return ChatShareView(id=item.id, title=item.title, owner_username=owner.username if owner else "Former member", visibility=item.visibility, messages=[SharedMessage.model_validate(value) for value in item.messages], created_at=item.created_at, expires_at=item.expires_at)


def create_share(payload: ChatShareCreate, db: Session, user: User):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
    item = ChatShare(owner_id=user.id, title=payload.title.strip(), visibility=payload.visibility, token_hash=_hash(token), messages=[value.model_dump(mode="json") for value in payload.messages], expires_at=expires_at)
    with transaction(db):
        ChatShareRepository(db).add(item)
    ChatShareRepository(db).refresh(item)
    return ChatShareCreated(id=item.id, share_token=token, visibility=item.visibility, expires_at=item.expires_at)


def list_active_shares(db: Session, user: User):
    now = datetime.now(timezone.utc)
    items = ChatShareRepository(db).list_active(user.id)
    return [ChatShareSummary(id=item.id, title=item.title, visibility=item.visibility, expires_at=item.expires_at, created_at=item.created_at) for item in items if item.expires_at is None or item.expires_at > now]


def view_team_share(token: str, db: Session, user: User):
    item = _resolve(token, db)
    if item.visibility != "team": raise ApplicationError(kind="not_found", detail="Shared conversation not found")
    owner = ChatShareRepository(db).owner(item.owner_id)
    if owner is None or owner.organization_id != user.organization_id: raise ApplicationError(kind="not_found", detail="Shared conversation not found")
    return _view(item, db)


def view_public_share(token: str, db: Session):
    item = _resolve(token, db)
    if item.visibility != "link": raise ApplicationError(kind="not_found", detail="Shared conversation not found")
    return _view(item, db)


def revoke_share(share_id: uuid.UUID, db: Session, user: User):
    item = ChatShareRepository(db).get(share_id)
    owner = ChatShareRepository(db).owner(item.owner_id) if item else None
    if item is None or owner is None or owner.organization_id != user.organization_id or (item.owner_id != user.id and user.role != "admin"): raise ApplicationError(kind="not_found", detail="Shared conversation not found")
    with transaction(db):
        item.is_active = False
        item.revoked_at = datetime.now(timezone.utc)
