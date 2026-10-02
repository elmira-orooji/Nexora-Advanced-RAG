import uuid

from pydantic import BaseModel, Field
from app.schemas.metadata import MetadataFilters


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    document_id: uuid.UUID | None = None
    document_set_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    filters: MetadataFilters | None = None


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    content: str
    score: float
    ocr_provenance: dict[str, str] | None = None
    visual_query: str | None = Field(default=None, max_length=4000)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]


class RetrievalDiagnostics(BaseModel):
    method: str
    vector_rank: int | None = None
    bm25_rank: int | None = None
    hybrid_score: float
    reranker_score: float
    term_coverage: float
    phrase_match: bool
    expanded_to_parent: bool


class PlaygroundHit(SearchHit):
    parent_index: int
    matched_child_content: str
    diagnostics: RetrievalDiagnostics


class PlaygroundResponse(BaseModel):
    query: str
    scoped_document_count: int
    result_count: int
    results: list[PlaygroundHit]


class TraceStage(BaseModel):
    key: str
    duration_ms: float
    input_count: int
    output_count: int


class TraceCitation(BaseModel):
    id: int
    chunk_id: uuid.UUID
    filename: str


class UsageMetrics(BaseModel):
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class PipelineTraceResponse(BaseModel):
    question: str
    answer: str
    grounded: bool
    total_duration_ms: float
    stages: list[TraceStage]
    results: list[PlaygroundHit]
    citations: list[TraceCitation]
    usage: UsageMetrics | None = None


class RetrieverConfig(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    vector_weight: float = Field(default=1.0, ge=0, le=3)
    bm25_weight: float = Field(default=1.0, ge=0, le=3)
    use_reranker: bool = True
    top_k: int = Field(default=5, ge=1, le=8)


class RetrieverComparisonRequest(SearchRequest):
    config_a: RetrieverConfig
    config_b: RetrieverConfig


class RetrieverVariantResult(BaseModel):
    config: RetrieverConfig
    duration_ms: float
    answer: str
    grounded: bool
    results: list[PlaygroundHit]
    citations: list[TraceCitation]
    usage: UsageMetrics | None = None


class RetrieverComparisonResponse(BaseModel):
    question: str
    overlap_count: int
    rank_changes: dict[str, int]
    variant_a: RetrieverVariantResult
    variant_b: RetrieverVariantResult
