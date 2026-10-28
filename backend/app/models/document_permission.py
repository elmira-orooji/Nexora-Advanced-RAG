import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        CheckConstraint("permission IN ('view', 'edit', 'manage')", name="ck_document_permission_level"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(20), nullable=False, default="view")
    granted_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
