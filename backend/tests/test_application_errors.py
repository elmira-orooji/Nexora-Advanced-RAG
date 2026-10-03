import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.application_errors import to_http_exception
from app.api.routes.auth import get_current_user
from app.core.application_errors import ApplicationError
from app.core.rate_limit import general_limiter
from app.db.database import get_db
from app.main import app


@pytest.mark.parametrize("kind,status", [
    ("bad_request", 400), ("forbidden", 403), ("not_found", 404),
    ("conflict", 409), ("payload_too_large", 413),
    ("unsupported_media_type", 415), ("validation_error", 422),
    ("internal_error", 500), ("upstream_unavailable", 502),
    ("service_unavailable", 503),
])
def test_application_error_http_contract(kind, status):
    error = ApplicationError(kind=kind, detail="Existing error message")
    assert to_http_exception(error).status_code == status
    assert not hasattr(error, "status_code")
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    general_limiter._buckets.clear()
    try:
        with patch("app.api.routes.research.ResearchService.run", side_effect=error):
            with TestClient(app) as client:
                response = client.post("/api/v1/research/run", json={
                    "question": "Research a question", "document_set_id": str(uuid4())
                }, headers={"X-Request-ID": "application-error-test"})
        assert response.status_code == status
        assert response.json() == {
            "detail": error.detail,
            "error": {"code": kind, "message": error.detail, "request_id": "application-error-test"},
        }
        assert response.headers["X-Request-ID"] == "application-error-test"
        assert response.headers["X-API-Version"] == "1"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        general_limiter._buckets.clear()


def test_services_do_not_import_web_exception_types():
    services = Path(__file__).resolve().parents[1] / "app" / "services"
    violations = []
    for path in services.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom) and node.module in {"fastapi", "starlette.exceptions"}:
                if any(item.name in {"HTTPException", "status"} for item in node.names):
                    violations.append(path.name)
    assert violations == []
