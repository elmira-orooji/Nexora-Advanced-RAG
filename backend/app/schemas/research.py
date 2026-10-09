import uuid
from pydantic import BaseModel, Field
from app.schemas.rag import Citation
from app.schemas.metadata import MetadataFilters


class ResearchRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    document_set_id: uuid.UUID
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    max_steps: int = Field(default=4, ge=2, le=6)
    filters: MetadataFilters | None = None


class ResearchStep(BaseModel):
    query: str
    evidence_count: int


class ResearchResponse(BaseModel):
    response_id: uuid.UUID
    question: str
    answer: str
    grounded: bool
    citations: list[Citation]
    steps: list[ResearchStep]
    evidence_reviewed: int
