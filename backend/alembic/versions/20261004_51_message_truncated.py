"""Persist whether model output reached its token limit."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_51"
down_revision = "20261003_50"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("messages", "truncated")
