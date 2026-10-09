from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception


def http_status(error):
    return to_http_exception(error).status_code if isinstance(error, ApplicationError) else error.status_code


from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.research import run_research
from app.schemas.research import ResearchRequest
from app.services import research_service as module
from app.services.openrouter import OpenRouterError
from app.services.qdrant import QdrantError


@pytest.mark.parametrize("question", ["سلام", "Hi", "چه؟"])
def test_research_accepts_short_questions(question):
    payload = ResearchRequest(question=question, document_set_id=uuid4())
    assert payload.question == question


@pytest.fixture
def context():
    db = MagicMock()
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    document_id = uuid4()
    payload = ResearchRequest(question="Research this question", document_set_id=uuid4())
    db.scalar.return_value = object()
    db.scalars.return_value.all.return_value = [document_id]
    db.refresh.side_effect = lambda record: setattr(record, "id", uuid4())
    with (
        patch.object(module, "require_set_access") as access,
        patch.object(module, "filter_document_ids", side_effect=lambda db, ids, filters: ids),
        patch.object(module, "get_language_model") as model,
        patch.object(module, "get_vector_store") as vector,
        patch.object(module, "hybrid_search") as search,
    ):
        model.return_value.research_plan.return_value = ["first", "second"]
        search.return_value = []
        yield SimpleNamespace(db=db, user=user, document_id=document_id, payload=payload,
                              access=access, model=model.return_value, vector=vector.return_value,
                              search=search)


def test_route_delegates_to_service():
    db, user, payload = MagicMock(), MagicMock(), MagicMock()
    with patch("app.api.routes.research.ResearchService") as service:
        assert run_research(payload, db, user) is service.return_value.run.return_value
        service.assert_called_once_with(db)
        service.return_value.run.assert_called_once_with(payload, user)


@pytest.mark.parametrize("condition,code", [("denied", 403), ("missing", 404), ("outside", 422), ("empty", 409)])
def test_invalid_scope_never_calls_provider(context, condition, code):
    c = context
    if condition == "denied":
        c.access.side_effect = ApplicationError(kind="forbidden", detail="Access denied")
    elif condition == "missing":
        c.db.scalar.return_value = None
    elif condition == "outside":
        c.payload.document_ids = [uuid4()]
    else:
        c.db.scalars.return_value.all.return_value = []
    with pytest.raises(ApplicationError) as error:
        module.ResearchService(c.db).run(c.payload, c.user)
    assert http_status(error.value) == code
    c.model.research_plan.assert_not_called()
    c.db.commit.assert_not_called()


def test_no_evidence_is_persisted_without_generating_answer(context):
    c = context
    result = module.ResearchService(c.db).run(c.payload, c.user)
    assert not result.grounded and result.citations == []
    assert result.evidence_reviewed == 0
    assert len(result.steps) == 2
    c.model.answer.assert_not_called()
    c.db.commit.assert_called_once()
    record = c.db.add.call_args.args[0]
    assert record.user_id == c.user.id
    assert record.document_set_id == c.payload.document_set_id
    assert record.answer == result.answer
    assert c.search.call_args.kwargs["document_ids"] == [str(c.document_id)]


def test_plan_failure_uses_fallback_queries(context):
    c = context
    c.model.research_plan.side_effect = OpenRouterError("plan unavailable")
    result = module.ResearchService(c.db).run(c.payload, c.user)
    assert [step.query for step in result.steps] == [
        c.payload.question, f"Evidence and details about: {c.payload.question}"
    ]


def point(document_id, chunk_id, score):
    return {"score": score, "payload": {
        "chunk_id": str(chunk_id), "document_id": str(document_id),
        "filename": "test.pdf", "chunk_index": 2, "content": "Evidence text"
    }}


def test_sources_are_deduplicated_and_citations_normalized(context):
    c = context
    chunk_id = uuid4()
    c.search.side_effect = [
        [point(c.document_id, chunk_id, 0.3)],
        [point(c.document_id, chunk_id, 0.9)],
    ]
    c.model.answer.return_value = "Finding [Source 1] [99]"
    result = module.ResearchService(c.db).run(c.payload, c.user)
    assert result.answer == "Finding [1]"
    assert result.grounded and result.evidence_reviewed == 1
    assert len(result.citations) == 1
    assert result.citations[0].score == 0.9
    assert result.citations[0].chunk_id == chunk_id
    c.db.commit.assert_called_once()
    assert "ocr_provenance" not in c.model.answer.call_args.args[1][0]


@pytest.mark.parametrize("provider", ["vector", "answer"])
def test_provider_failure_preserves_502_without_writes(context, provider):
    c = context
    if provider == "vector":
        c.vector.ensure_collection.side_effect = QdrantError("vector unavailable")
    else:
        c.search.return_value = [point(c.document_id, uuid4(), 0.8)]
        c.model.answer.side_effect = OpenRouterError("model unavailable")
    with pytest.raises(ApplicationError) as error:
        module.ResearchService(c.db).run(c.payload, c.user)
    assert http_status(error.value) == 502
    c.db.add.assert_not_called()
    c.db.commit.assert_not_called()
