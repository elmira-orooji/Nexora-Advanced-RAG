import uuid
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.connector import ConnectorCreate, ConnectorResponse, ConnectorScheduleUpdate, SyncResponse, WebhookConnectorCreate, WebhookConnectorCreated, WebhookEvent, WebhookEventResponse
from app.core.rate_limit import rate_limit, webhook_limiter
from app.services.connector_management_service import ConnectorManagementService

router = APIRouter(prefix="/document-sets/{set_id}/connectors", tags=["connectors"])


@router.get("", response_model=list[ConnectorResponse])
def list_connectors(set_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ConnectorManagementService(db).list_connectors(set_id, user)

@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
def create_connector(set_id: uuid.UUID, payload: ConnectorCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ConnectorManagementService(db).create_connector(set_id, payload, user)

@router.post("/webhook", response_model=WebhookConnectorCreated, status_code=status.HTTP_201_CREATED)
def create_webhook_connector(set_id: uuid.UUID, payload: WebhookConnectorCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ConnectorManagementService(db).create_webhook_connector(set_id, payload, str(request.base_url), user)

@router.post("/{connector_id}/events", response_model=WebhookEventResponse, dependencies=[Depends(rate_limit(webhook_limiter))])
def receive_webhook_event(set_id: uuid.UUID, connector_id: uuid.UUID, payload: WebhookEvent, x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"), db: Session = Depends(get_db)):
    return ConnectorManagementService(db).receive_webhook_event(set_id, connector_id, payload, x_webhook_secret)

@router.post("/{connector_id}/sync", response_model=SyncResponse)
def sync(set_id: uuid.UUID, connector_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ConnectorManagementService(db).sync(set_id, connector_id, user)

@router.patch("/{connector_id}/schedule", response_model=ConnectorResponse)
def update_schedule(set_id: uuid.UUID, connector_id: uuid.UUID, payload: ConnectorScheduleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ConnectorManagementService(db).update_schedule(set_id, connector_id, payload, user)

@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connector(set_id: uuid.UUID, connector_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ConnectorManagementService(db).delete_connector(set_id, connector_id, user)
