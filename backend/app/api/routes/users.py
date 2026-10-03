import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.user_management import SetPermissionItem, SetPermissionsUpdate, UserAdminCreate, UserAdminResponse, UserAdminUpdate

from app.services.user_management_service import UserManagementService

router = APIRouter(prefix="/users", tags=["users"])


def admin_only(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")
    return user


@router.get("", response_model=list[UserAdminResponse])
def list_users(db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserManagementService(db).list_users(admin)

@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserAdminCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserManagementService(db).create_user(payload, admin)

@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(user_id: uuid.UUID, payload: UserAdminUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserManagementService(db).update_user(user_id, payload, admin)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    UserManagementService(db).delete_user(user_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{user_id}/document-set-permissions", response_model=list[SetPermissionItem])
def get_permissions(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserManagementService(db).get_permissions(user_id, admin)

@router.put("/{user_id}/document-set-permissions", response_model=list[SetPermissionItem])
def replace_permissions(user_id: uuid.UUID, payload: SetPermissionsUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserManagementService(db).replace_permissions(user_id, payload, admin)
