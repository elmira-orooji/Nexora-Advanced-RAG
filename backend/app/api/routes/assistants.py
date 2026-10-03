import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.assistant import AssistantAnswerRequest, AssistantCreate, AssistantResponse, AssistantUpdate
from app.schemas.rag import RagResponse
from app.services import assistant_service

router = APIRouter(prefix="/assistants", tags=["assistants"])


def _admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    return user


@router.get("/models")
def available_models(user: User = Depends(_admin)):
    return assistant_service.available_models(user=user)


@router.get("", response_model=list[AssistantResponse])
def list_assistants(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return assistant_service.list_assistants(db=db, user=user)


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
def create_assistant(payload: AssistantCreate, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return assistant_service.create_assistant(payload=payload, db=db, user=user)


@router.patch("/{assistant_id}", response_model=AssistantResponse)
def update_assistant(assistant_id: uuid.UUID, payload: AssistantUpdate, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return assistant_service.update_assistant(assistant_id=assistant_id, payload=payload, db=db, user=user)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assistant(assistant_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(_admin)):
    return assistant_service.delete_assistant(assistant_id=assistant_id, db=db, user=user)


@router.post("/{assistant_id}/answer", response_model=RagResponse)
def answer_with_assistant(assistant_id: uuid.UUID, payload: AssistantAnswerRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return assistant_service.answer_with_assistant(assistant_id=assistant_id, payload=payload, db=db, user=user)
