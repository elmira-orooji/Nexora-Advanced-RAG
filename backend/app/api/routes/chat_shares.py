import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat_share import ChatShareCreate, ChatShareCreated, ChatShareSummary, ChatShareView
from app.services import chat_share_service

router = APIRouter(tags=["chat-sharing"])


@router.post("/chat-shares", response_model=ChatShareCreated, status_code=status.HTTP_201_CREATED)
def create_share(payload: ChatShareCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_share_service.create_share(payload=payload, db=db, user=user)


@router.get("/chat-shares", response_model=list[ChatShareSummary])
def list_active_shares(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_share_service.list_active_shares(db=db, user=user)


@router.get("/shared/team/{token}", response_model=ChatShareView)
def view_team_share(token: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_share_service.view_team_share(token=token, db=db, user=user)


@router.get("/shared/link/{token}", response_model=ChatShareView)
def view_public_share(token: str, db: Session = Depends(get_db)):
    return chat_share_service.view_public_share(token=token, db=db)


@router.delete("/chat-shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(share_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_share_service.revoke_share(share_id=share_id, db=db, user=user)
