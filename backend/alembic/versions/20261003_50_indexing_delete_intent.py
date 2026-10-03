"""Allow durable delete intents to survive deletion of their document."""
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261003_50"
down_revision = "20261002_49"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("indexing_outbox", "document_id", existing_type=UUID(as_uuid=True), nullable=True)


def downgrade():
    # Refuse a downgrade with retained delete intents rather than dropping them.
    op.alter_column("indexing_outbox", "document_id", existing_type=UUID(as_uuid=True), nullable=False)
