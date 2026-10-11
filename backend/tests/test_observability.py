import logging

from app.core.logging import JsonFormatter
from app.core.request_context import reset_request_id, set_request_id
from app.services.operations import operational_metrics


def test_structured_log_contains_request_id():
    token = set_request_id("request-123")
    try:
        record = logging.LogRecord("nexora.test", logging.INFO, "", 0, "Processed document", (), None)
        rendered = JsonFormatter().format(record)
    finally:
        reset_request_id(token)

    assert '"request_id": "request-123"' in rendered
    assert '"message": "Processed document"' in rendered


def test_duration_observation_exposes_count_and_sum():
    operational_metrics._counters.clear()
    operational_metrics.observe("document_ocr_duration", 0.25, result="success")

    metrics = operational_metrics.render()
    assert "nexora_document_ocr_duration_seconds_count" in metrics
    assert "nexora_document_ocr_duration_seconds_sum" in metrics
