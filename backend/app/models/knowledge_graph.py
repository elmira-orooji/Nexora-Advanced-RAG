import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class KnowledgeEntity(Base):
    __tablename__ = "knowledge_graph_entities"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_kg_entity_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, default="entity")
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeGraphFact(Base):
    __tablename__ = "knowledge_graph_facts"
    __table_args__ = (
        UniqueConstraint("source_chunk_id", "subject_entity_id", "predicate", "object_entity_id", name="uq_kg_fact_evidence"),
        Index("ix_kg_fact_org_subject", "organization_id", "subject_entity_id"),
        Index("ix_kg_fact_org_object", "organization_id", "object_entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_graph_entities.id", ondelete="CASCADE"), nullable=False)
    predicate: Mapped[str] = mapped_column(String(160), nullable=False)
    object_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_graph_entities.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
