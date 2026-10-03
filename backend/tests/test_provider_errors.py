import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.connector_scheduler import _retryable_connector_error
from app.services.document_jobs import _retryable_document_error
from app.services.eval_service import _llm_judge
from app.services.openrouter import OpenRouterError
from app.services.provider_errors import LanguageModelError, VectorStoreError
from app.services.provider_failures import provider_error
from app.services.qdrant import QdrantError


def test_adapter_errors_implement_shared_contracts():
    assert isinstance(OpenRouterError("failure"), LanguageModelError)
    assert isinstance(QdrantError("failure", status_code=429), VectorStoreError)
    assert QdrantError("failure", status_code=429).status_code == 429


@pytest.mark.parametrize("status,retryable", [(None, True), (408, True), (429, True), (503, True), (401, False), (404, False)])
def test_alternative_vector_provider_retry_policy(status, retryable):
    error = VectorStoreError("alternative provider failure", status_code=status)
    assert _retryable_document_error(error) is retryable
    assert _retryable_connector_error(error) is retryable


@pytest.mark.parametrize("error,provider,message", [
    (LanguageModelError("sensitive credentials"), "language_model", "The AI response service"),
    (VectorStoreError("internal connection data"), "vector_store", "Knowledge search"),
])
def test_generic_provider_failures_remain_safe(error, provider, message, caplog):
    result = provider_error(error)
    assert result.kind == "service_unavailable"
    assert result.detail.startswith(message)
    assert str(error) not in result.detail
    assert str(error) not in caplog.text
    assert caplog.records[-1].provider == provider


def test_generic_configuration_reason_does_not_depend_on_message(caplog):
    provider_error(LanguageModelError("other model is unconfigured", reason="missing_configuration"))
    assert caplog.records[-1].reason == "missing_configuration"


def test_alternative_provider_status_is_logged_without_transport_dependency(caplog):
    provider_error(LanguageModelError("sensitive body", status_code=429))
    assert caplog.records[-1].status_code == 429
    assert caplog.records[-1].reason == "http_error"
    assert "sensitive body" not in caplog.text


def test_evaluation_catches_alternative_language_model_error():
    model = MagicMock()
    model.complete.side_effect = LanguageModelError("alternative failure")
    score, reason = _llm_judge(model, "judge this")
    assert score == 0
    assert reason == "Judge call failed: alternative failure"


def test_consumers_do_not_reference_adapter_error_names():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    violations = []
    for path in app_dir.rglob("*.py"):
        if path.name in {"openrouter.py", "qdrant.py"}:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Name) and node.id in {"OpenRouterError", "QdrantError"}:
                violations.append(str(path.relative_to(app_dir)))
            if isinstance(node, ast.ImportFrom):
                if any(item.name in {"OpenRouterError", "QdrantError"} for item in node.names):
                    violations.append(str(path.relative_to(app_dir)))
    assert violations == []
