from app.services.openrouter import OpenRouterError
from app.services.provider_failures import provider_http_error
from app.services.qdrant import QdrantError
from app.services.http_resilience import CircuitOpenError, HttpStatusError, ResilientHttpError
from app.core.logging import JsonFormatter
from app.core.request_context import reset_request_id, set_request_id


def test_nested_http_failure_logs_status_and_request_id_without_secrets(caplog):
    underlying = HttpStatusError(401, b"secret-key private-document", {"Authorization": "secret-key"})
    transport = ResilientHttpError("private-document")
    transport.__cause__ = underlying
    error = OpenRouterError("secret-key private-document")
    error.__cause__ = transport
    token = set_request_id("test-provider-request")
    try:
        response = provider_http_error(error)
        record = caplog.records[-1]
        formatted = JsonFormatter().format(record)
    finally:
        reset_request_id(token)
    assert response.status_code == 503
    assert record.provider == "openrouter"
    assert record.status_code == 401
    assert record.reason == "http_error"
    assert "test-provider-request" in formatted
    assert "secret-key" not in formatted
    assert "private-document" not in formatted


def test_transport_failure_categories(caplog):
    for cause, reason in [(TimeoutError("secret"), "timeout"), (OSError("secret"), "network_error"), (CircuitOpenError("secret"), "circuit_open")]:
        error = OpenRouterError("secret")
        error.__cause__ = cause
        provider_http_error(error)
        assert caplog.records[-1].reason == reason
        assert "secret" not in JsonFormatter().format(caplog.records[-1])


def test_missing_configuration_is_logged(caplog):
    provider_http_error(OpenRouterError("OpenRouter configuration is missing"))
    assert caplog.records[-1].reason == "missing_configuration"


def test_qdrant_errors_do_not_expose_provider_details():
    response = provider_http_error(QdrantError("internal host unavailable"))

    assert response.status_code == 503
    assert response.detail == "Knowledge search is temporarily unavailable. Please retry shortly."


def test_model_errors_do_not_expose_provider_details():
    response = provider_http_error(OpenRouterError("credential rejected"))

    assert response.status_code == 503
    assert response.detail == "The AI response service is temporarily unavailable. Please retry shortly."
