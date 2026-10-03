import uuid
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.document_set_access import require_set_access
from app.db.database import get_db
from app.models.connector import Connector
from app.models.document_set import DocumentSet
from app.models.user import User
from app.schemas.connector import ConnectorCreate, ConnectorResponse, ConnectorScheduleUpdate, SyncResponse, WebhookConnectorCreate, WebhookConnectorCreated, WebhookEvent, WebhookEventResponse
from app.services.connector_sync import ConnectorSyncError, ingest_webhook_event
from app.services.connector_lock import connector_sync_lock
from app.services.provider_errors import VectorStoreError
from app.core.rate_limit import rate_limit, webhook_limiter
from app.services.security_audit import audit_security_event

router = APIRouter(prefix="/document-sets/{set_id}/connectors", tags=["connectors"])


def _next(interval: str) -> datetime:
    return datetime.now(timezone.utc) + {"hourly": timedelta(hours=1), "daily": timedelta(days=1), "weekly": timedelta(days=7)}[interval]


@router.get("", response_model=list[ConnectorResponse])
def list_connectors(set_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_set_access(db, user, set_id)
    return db.scalars(select(Connector).where(Connector.document_set_id == set_id).order_by(Connector.created_at.desc())).all()


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
def create_connector(set_id: uuid.UUID, payload: ConnectorCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(DocumentSet).where(DocumentSet.id == set_id, DocumentSet.organization_id == user.organization_id)) is None: raise HTTPException(status_code=404, detail="Document set not found")
    require_set_access(db, user, set_id, "edit")
    item = Connector(document_set_id=set_id, created_by_id=user.id, connector_type=payload.connector_type, name=payload.name.strip(), source_url=str(payload.source_url), status="pending", schedule_enabled=payload.schedule_enabled, schedule_interval=payload.schedule_interval, next_sync_at=_next(payload.schedule_interval) if payload.schedule_enabled else None)
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/webhook", response_model=WebhookConnectorCreated, status_code=status.HTTP_201_CREATED)
def create_webhook_connector(set_id: uuid.UUID, payload: WebhookConnectorCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(DocumentSet).where(DocumentSet.id == set_id, DocumentSet.organization_id == user.organization_id)) is None: raise HTTPException(status_code=404, detail="Document set not found")
    require_set_access(db, user, set_id, "edit")
    secret = secrets.token_urlsafe(32)
    item = Connector(document_set_id=set_id, created_by_id=user.id, connector_type="webhook", name=payload.name.strip(), source_url="pending", webhook_secret_hash=hashlib.sha256(secret.encode()).hexdigest(), status="ready", schedule_enabled=False, schedule_interval="daily")
    db.add(item); db.flush(); path = f"/api/v1/document-sets/{set_id}/connectors/{item.id}/events"; endpoint = f"{str(request.base_url).rstrip('/')}{path}"; item.source_url = endpoint
    db.commit(); db.refresh(item)
    return WebhookConnectorCreated(connector=item, endpoint=endpoint, secret=secret)


@router.post("/{connector_id}/events", response_model=WebhookEventResponse, dependencies=[Depends(rate_limit(webhook_limiter))])
def receive_webhook_event(set_id: uuid.UUID, connector_id: uuid.UUID, payload: WebhookEvent, x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"), db: Session = Depends(get_db)):
    item = db.get(Connector, connector_id)
    if item is None or item.document_set_id != set_id or item.connector_type != "webhook": raise HTTPException(status_code=404, detail="Webhook not found")
    supplied = hashlib.sha256((x_webhook_secret or "").encode()).hexdigest()
    if not item.webhook_secret_hash or not hmac.compare_digest(supplied, item.webhook_secret_hash):
        audit_security_event("webhook_authentication", "denied", reason="invalid_secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    try: result = ingest_webhook_event(db, item, payload.action, payload.external_id, payload.title, payload.content, payload.source_url)
    except (ConnectorSyncError, VectorStoreError) as exc:
        db.rollback(); item = db.get(Connector, connector_id); item.status = "failed"; item.last_error = str(exc)[:500]; db.commit()
        raise HTTPException(status_code=422 if isinstance(exc, ConnectorSyncError) else 502, detail=str(exc)) from exc
    return WebhookEventResponse(connector_id=connector_id, action=payload.action, result=result)


@router.post("/{connector_id}/sync", response_model=SyncResponse)
def sync(set_id: uuid.UUID, connector_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_set_access(db, user, set_id, "edit")
    item = db.get(Connector, connector_id)
    if item is None or item.document_set_id != set_id: raise HTTPException(status_code=404, detail="Connector not found")
    # A repeated click/request must not reset retry state or enqueue another run.
    if getattr(item, "status", None) == "syncing":
        return SyncResponse(connector_id=item.id, status="queued", message="Connector sync is already scheduled")
    with connector_sync_lock(db, connector_id) as acquired:
        if not acquired:
            raise HTTPException(status_code=409, detail="Connector is already syncing")
        item.status = "syncing"; item.last_error = None; item.error_type = None
        item.attempts = 0; item.dead_lettered_at = None; item.next_attempt_at = None
        item.next_sync_at = _next(item.schedule_interval) if item.schedule_enabled else None; db.commit()
    # The actual sync now runs in the scheduler worker so the HTTP request returns
    # immediately and cannot be interrupted by client timeouts.
    return SyncResponse(connector_id=item.id, status="queued", message="Connector sync has been scheduled")


@router.patch("/{connector_id}/schedule", response_model=ConnectorResponse)
def update_schedule(set_id: uuid.UUID, connector_id: uuid.UUID, payload: ConnectorScheduleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_set_access(db, user, set_id, "edit")
    item = db.get(Connector, connector_id)
    if item is None or item.document_set_id != set_id: raise HTTPException(status_code=404, detail="Connector not found")
    item.schedule_enabled = payload.schedule_enabled; item.schedule_interval = payload.schedule_interval; item.next_sync_at = _next(payload.schedule_interval) if payload.schedule_enabled else None
    db.commit(); db.refresh(item); return item


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connector(set_id: uuid.UUID, connector_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_set_access(db, user, set_id, "edit")
    item = db.get(Connector, connector_id)
    if item is None or item.document_set_id != set_id: raise HTTPException(status_code=404, detail="Connector not found")
    db.delete(item); db.commit()
