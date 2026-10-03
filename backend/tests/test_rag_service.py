from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.rag import RagRequest
from app.services.rag_service import RagService


def test_rag_service_uses_injected_vector_store():
    db = MagicMock()
    providers = MagicMock()
    result = MagicMock()
    service = RagService(db, providers=providers)
    service._save_no_results = MagicMock(return_value=result)
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    payload = RagRequest(question="What is Nexora?", document_id=uuid4())

    with patch("app.services.rag_service.require_document_access"), patch("app.services.rag_service.hybrid_search", return_value=[]):
        response = service.answer(payload, user)

    assert response is result
    providers.vector_store.assert_called_once_with()
    providers.vector_store.return_value.ensure_collection.assert_called_once_with()


def test_rag_service_normalizes_only_valid_citations():
    answer, citations = RagService._normalize_citations("Answer [Source 1] [4] [2]", 2)

    assert answer == "Answer [1] [2]"
    assert citations == {1, 2}


def test_no_evidence_answer_is_saved_in_one_transaction():
    db = MagicMock()
    db.refresh.side_effect = lambda record: setattr(record, "id", uuid4())
    user = SimpleNamespace(id=uuid4())
    payload = RagRequest(question="What is Nexora?", document_id=uuid4())
    result = RagService(db, MagicMock())._save_no_results(payload, user)
    assert not result.grounded
    assert result.sources == [] and result.citations == []
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
