import uuid

from sqlalchemy.orm import Session

from app.models.llm_usage import LLMUsage
from app.services.providers.openrouter import LLMResult


def record_usage(db: Session, user_id: uuid.UUID, document_set_id: uuid.UUID | None, operation: str, result: LLMResult) -> LLMUsage:
    item = LLMUsage(user_id=user_id, document_set_id=document_set_id, operation=operation, model=result.model, latency_ms=result.latency_ms, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens, total_tokens=result.total_tokens, estimated_cost_usd=result.estimated_cost_usd)
    db.add(item)
    return item
