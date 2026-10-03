import uuid
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.core.application_errors import ApplicationError
from app.core.document_set_access import require_set_access
from app.models.connector import Connector
from app.schemas.connector import ConnectorCreate, ConnectorScheduleUpdate, SyncResponse, WebhookConnectorCreate, WebhookConnectorCreated, WebhookEvent, WebhookEventResponse
from app.services.connector_sync import ConnectorSyncError, ingest_webhook_event
from app.services.connector_lock import connector_sync_lock
from app.services.provider_errors import VectorStoreError
from app.services.security_audit import audit_security_event
from app.repositories.connector_repository import ConnectorRepository
from app.services.transactions import transaction


def _next(interval: str) -> datetime:
    return datetime.now(timezone.utc) + {"hourly": timedelta(hours=1), "daily": timedelta(days=1), "weekly": timedelta(days=7)}[interval]


class ConnectorManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ConnectorRepository(db)

    def list_connectors(self, set_id, user):
        db = self.db
        require_set_access(db, user, set_id)
        return self.repository.list_for_set(set_id)

    def create_connector(self, set_id, payload, user):
        db = self.db
        if not self.repository.set_exists(set_id, user.organization_id): raise ApplicationError(kind="not_found", detail="Document set not found")
        require_set_access(db, user, set_id, "edit")
        item = Connector(document_set_id=set_id, created_by_id=user.id, connector_type=payload.connector_type, name=payload.name.strip(), source_url=str(payload.source_url), status="pending", schedule_enabled=payload.schedule_enabled, schedule_interval=payload.schedule_interval, next_sync_at=_next(payload.schedule_interval) if payload.schedule_enabled else None)
        with transaction(db):
            self.repository.add(item)
        self.repository.refresh(item)
        return item

    def create_webhook_connector(self, set_id, payload, base_url, user):
        db = self.db
        if not self.repository.set_exists(set_id, user.organization_id): raise ApplicationError(kind="not_found", detail="Document set not found")
        require_set_access(db, user, set_id, "edit")
        secret = secrets.token_urlsafe(32)
        item = Connector(document_set_id=set_id, created_by_id=user.id, connector_type="webhook", name=payload.name.strip(), source_url="pending", webhook_secret_hash=hashlib.sha256(secret.encode()).hexdigest(), status="ready", schedule_enabled=False, schedule_interval="daily")
        with transaction(db):
            self.repository.add(item)
            self.repository.flush()
            path = f"/api/v1/document-sets/{set_id}/connectors/{item.id}/events"
            endpoint = f"{base_url.rstrip('/')}{path}"
            item.source_url = endpoint
        self.repository.refresh(item)
        return WebhookConnectorCreated(connector=item, endpoint=endpoint, secret=secret)

    def receive_webhook_event(self, set_id, connector_id, payload, x_webhook_secret):
        db = self.db
        item = self.repository.get(connector_id)
        if item is None or item.document_set_id != set_id or item.connector_type != "webhook": raise ApplicationError(kind="not_found", detail="Webhook not found")
        supplied = hashlib.sha256((x_webhook_secret or "").encode()).hexdigest()
        if not item.webhook_secret_hash or not hmac.compare_digest(supplied, item.webhook_secret_hash):
            audit_security_event("webhook_authentication", "denied", reason="invalid_secret")
            raise ApplicationError(kind="unauthorized", detail="Invalid webhook secret")
        try: result = ingest_webhook_event(db, item, payload.action, payload.external_id, payload.title, payload.content, payload.source_url)
        except (ConnectorSyncError, VectorStoreError) as exc:
            db.rollback()
            with transaction(db):
                item = self.repository.get(connector_id)
                item.status = "failed"
                item.last_error = str(exc)[:500]
            raise ApplicationError(kind="validation_error" if isinstance(exc, ConnectorSyncError) else "upstream_unavailable", detail=str(exc)) from exc
        return WebhookEventResponse(connector_id=connector_id, action=payload.action, result=result)

    def sync(self, set_id, connector_id, user):
        db = self.db
        require_set_access(db, user, set_id, "edit")
        item = self.repository.get(connector_id)
        if item is None or item.document_set_id != set_id: raise ApplicationError(kind="not_found", detail="Connector not found")
        # A repeated click/request must not reset retry state or enqueue another run.
        if getattr(item, "status", None) == "syncing":
            return SyncResponse(connector_id=item.id, status="queued", message="Connector sync is already scheduled")
        with connector_sync_lock(db, connector_id) as acquired:
            if not acquired:
                raise ApplicationError(kind="conflict", detail="Connector is already syncing")
            with transaction(db):
                item.status = "syncing"
                item.last_error = None
                item.error_type = None
                item.attempts = 0
                item.dead_lettered_at = None
                item.next_attempt_at = None
                item.next_sync_at = _next(item.schedule_interval) if item.schedule_enabled else None
        # The actual sync now runs in the scheduler worker so the HTTP request returns
        # immediately and cannot be interrupted by client timeouts.
        return SyncResponse(connector_id=item.id, status="queued", message="Connector sync has been scheduled")

    def update_schedule(self, set_id, connector_id, payload, user):
        db = self.db
        require_set_access(db, user, set_id, "edit")
        item = self.repository.get(connector_id)
        if item is None or item.document_set_id != set_id: raise ApplicationError(kind="not_found", detail="Connector not found")
        with transaction(db):
            item.schedule_enabled = payload.schedule_enabled
            item.schedule_interval = payload.schedule_interval
            item.next_sync_at = _next(payload.schedule_interval) if payload.schedule_enabled else None
        self.repository.refresh(item)
        return item

    def delete_connector(self, set_id, connector_id, user):
        db = self.db
        require_set_access(db, user, set_id, "edit")
        item = self.repository.get(connector_id)
        if item is None or item.document_set_id != set_id: raise ApplicationError(kind="not_found", detail="Connector not found")
        with transaction(db):
            self.repository.delete(item)
