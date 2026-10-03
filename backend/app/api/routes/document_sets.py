import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.document_set import DocumentMembershipRequest, DocumentSetCreate, DocumentSetDetail, DocumentSetResponse, DocumentSetUpdate
from app.services import document_set_service

router = APIRouter(prefix="/document-sets", tags=["document-sets"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    return user


@router.get("", response_model=list[DocumentSetResponse])
def list_document_sets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.list_document_sets(db=db, user=user)


@router.post("", response_model=DocumentSetResponse, status_code=status.HTTP_201_CREATED)
def create_document_set(
    payload: DocumentSetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    return document_set_service.create_document_set(payload=payload, db=db, user=user)


@router.get("/{set_id}", response_model=DocumentSetDetail)
def get_document_set(
    set_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.get_document_set(set_id=set_id, db=db, user=user)


@router.patch("/{set_id}", response_model=DocumentSetResponse)
def update_document_set(
    set_id: uuid.UUID,
    payload: DocumentSetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.update_document_set(set_id=set_id, payload=payload, db=db, user=user)


@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_set(
    set_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.delete_document_set(set_id=set_id, db=db, user=user)


@router.post("/{set_id}/documents", response_model=DocumentSetDetail)
def add_document_to_set(
    set_id: uuid.UUID,
    payload: DocumentMembershipRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.add_document_to_set(set_id=set_id, payload=payload, db=db, user=user)


@router.delete("/{set_id}/documents/{document_id}", response_model=DocumentSetDetail)
def remove_document_from_set(
    set_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_set_service.remove_document_from_set(set_id=set_id, document_id=document_id, db=db, user=user)
