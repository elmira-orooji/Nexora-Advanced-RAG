"""Mark isolated public-demo visitors explicitly."""

from alembic import op
import sqlalchemy as sa

revision = "20261023_52"
down_revision = "20261004_51"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    op.drop_column("users", "is_demo")
