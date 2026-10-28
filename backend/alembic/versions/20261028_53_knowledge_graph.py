"""Create organization-scoped graph facts with chunk provenance."""

from alembic import op
import sqlalchemy as sa


revision = "20261028_53"
down_revision = "20261023_52"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_graph_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_kg_entity_org_name"),
    )
    op.create_table(
        "knowledge_graph_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("subject_entity_id", sa.Uuid(), nullable=False),
        sa.Column("predicate", sa.String(160), nullable=False),
        sa.Column("object_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_chunk_id", sa.Uuid(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_entity_id"], ["knowledge_graph_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["object_entity_id"], ["knowledge_graph_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_chunk_id", "subject_entity_id", "predicate", "object_entity_id", name="uq_kg_fact_evidence"),
    )
    op.create_index("ix_kg_fact_org_subject", "knowledge_graph_facts", ["organization_id", "subject_entity_id"])
    op.create_index("ix_kg_fact_org_object", "knowledge_graph_facts", ["organization_id", "object_entity_id"])


def downgrade():
    op.drop_index("ix_kg_fact_org_object", table_name="knowledge_graph_facts")
    op.drop_index("ix_kg_fact_org_subject", table_name="knowledge_graph_facts")
    op.drop_table("knowledge_graph_facts")
    op.drop_table("knowledge_graph_entities")
