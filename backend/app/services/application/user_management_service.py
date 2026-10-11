from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.application_errors import ApplicationError
from app.core.security import hash_password
from app.models.user import User
from app.models.document_set_permission import DocumentSetPermission
from app.repositories.user_repository import UserRepository
from app.schemas.user_management import SetPermissionItem
from app.services.transactions import transaction


class UserManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def list_users(self, admin):
        return self.repository.list_members(admin.organization_id)

    def _get(self, user_id, admin, *, lock=False):
        target = self.repository.get_member(user_id, admin.organization_id, lock=lock)
        if target is None:
            raise ApplicationError(kind="not_found", detail="User not found")
        return target

    def create_user(self, payload, admin):
        item = User(organization_id=admin.organization_id, username=payload.username.strip(),
                    job_title=payload.job_title.strip() if payload.job_title and payload.job_title.strip() else None,
                    password_hash=hash_password(payload.password), role=payload.role, is_active=payload.is_active)
        try:
            with transaction(self.db):
                self.repository.add(item)
        except IntegrityError as exc:
            raise ApplicationError(kind="conflict", detail="A member with this username already exists") from exc
        self.repository.refresh(item)
        return item

    def update_user(self, user_id, payload, admin):
        target = self._get(user_id, admin)
        if target.id == admin.id and not payload.is_active:
            raise ApplicationError(kind="forbidden", detail="You cannot deactivate your own account")
        with transaction(self.db):
            target.is_active = payload.is_active
            if not payload.is_active:
                self.repository.revoke_sessions(target.id)
        self.repository.refresh(target)
        return target

    def delete_user(self, user_id, admin):
        target = self._get(user_id, admin, lock=True)
        if target.role == "admin":
            raise ApplicationError(kind="forbidden", detail="Admin accounts cannot be deleted")
        try:
            with transaction(self.db):
                self.repository.delete(target)
        except IntegrityError as exc:
            raise ApplicationError(kind="conflict", detail="This member owns shared resources and cannot be deleted") from exc

    def get_permissions(self, user_id, admin):
        self._get(user_id, admin)
        return [SetPermissionItem(document_set_id=item.document_set_id, document_set_name=name, permission=item.permission)
                for item, name in self.repository.permission_rows(user_id, admin.organization_id)]

    def replace_permissions(self, user_id, payload, admin):
        target = self._get(user_id, admin)
        if target.role == "admin" and payload.permissions:
            raise ApplicationError(kind="validation_error", detail="Admins already have access to all knowledge sets")
        ids = {item.document_set_id for item in payload.permissions}
        if self.repository.existing_set_ids(ids, admin.organization_id) != ids:
            raise ApplicationError(kind="validation_error", detail="One or more knowledge sets do not exist")
        with transaction(self.db):
            self.repository.replace_permissions(user_id, [
                DocumentSetPermission(user_id=user_id, document_set_id=item.document_set_id,
                                      permission=item.permission, granted_by_id=admin.id)
                for item in payload.permissions
            ])
        return self.get_permissions(user_id, admin)
