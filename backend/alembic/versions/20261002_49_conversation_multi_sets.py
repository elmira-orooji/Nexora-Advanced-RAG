"""Persist explicitly selected knowledge sets for conversations."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_49"
down_revision = "20260924_48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("document_set_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("conversations", "document_set_ids")
