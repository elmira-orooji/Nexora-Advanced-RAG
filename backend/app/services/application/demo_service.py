"""Create a separate guest identity with view-only access to curated samples."""

from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo import DEMO_ORGANIZATION_SLUG, DEMO_SET_NAME, reserve_demo_session
from app.models.document_set import DocumentSet
from app.models.document_set_permission import DocumentSetPermission
from app.models.organization import Organization
from app.models.user import User


def create_demo_guest(db: Session, request: Request) -> tuple[User, Organization]:
    organization = db.scalar(select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG))
    sample_set = db.scalar(select(DocumentSet).where(DocumentSet.organization_id == organization.id, DocumentSet.name == DEMO_SET_NAME)) if organization else None
    if sample_set is None or not any(doc.status == "indexed" for doc in sample_set.documents):
        raise HTTPException(503, "The sample documents are being prepared. Please try later.")
    reserve_demo_session(request)
    user = User(id=uuid4(), organization_id=organization.id, username=f"guest-{uuid4().hex}", password_hash="!password-login-disabled", role="user", is_demo=True)
    db.add(user)
    db.flush()
    db.add(DocumentSetPermission(user_id=user.id, document_set_id=sample_set.id, permission="view", granted_by_id=sample_set.created_by_id))
    return user, organization
