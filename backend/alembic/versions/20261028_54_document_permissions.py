"""Add user-specific document access grants."""

from alembic import op
import sqlalchemy as sa


revision = "20261028_54"
down_revision = "20261028_53"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_permissions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(20), nullable=False),
        sa.Column("granted_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("permission IN ('view', 'edit', 'manage')", name="ck_document_permission_level"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "document_id"),
    )
    op.create_index("ix_document_permissions_document", "document_permissions", ["document_id"])


def downgrade():
    op.drop_index("ix_document_permissions_document", table_name="document_permissions")
    op.drop_table("document_permissions")
