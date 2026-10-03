"""HTTP-level integration tests for the API's critical request boundaries.

These tests exercise FastAPI routing, request validation, middleware and response
serialization while substituting only persistence and external providers. They do
not need PostgreSQL, Qdrant, OCR, or an LLM service.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.core.rate_limit import auth_limiter, general_limiter
from app.db.database import get_db
from app.main import app
from app.services.openrouter import LLMResult


@pytest.fixture(autouse=True)
def api_test_state():
    """Keep global dependency overrides and in-memory rate limits isolated."""
    app.dependency_overrides.clear()
    auth_limiter._buckets.clear()
    general_limiter._buckets.clear()
    yield
    app.dependency_overrides.clear()
    auth_limiter._buckets.clear()
    general_limiter._buckets.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.integration
def test_health_endpoint_runs_through_application_middleware(client):
    response = client.get("/health", headers={"X-Request-ID": "critical-flow-test"})

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Request-ID"] == "critical-flow-test"


@pytest.mark.integration
def test_v1_validation_errors_keep_detail_and_expose_a_stable_error_contract(client):
    response = client.post("/api/v1/auth/login", json={"username": "a", "password": "short"})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-API-Version"] == "1"


@pytest.mark.integration
def test_unhandled_v1_errors_return_a_safe_body_and_request_id(client):
    def fail():
        raise RuntimeError("sensitive internal detail")

    app.add_api_route("/api/v1/test/unhandled", fail, methods=["GET"])
    try:
        response = client.get("/api/v1/test/unhandled", headers={"X-Request-ID": "trace-failure-test"})
    finally:
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/api/v1/test/unhandled"]

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["error"]["request_id"] == "trace-failure-test"
    assert response.headers["X-Request-ID"] == "trace-failure-test"
    assert "sensitive internal detail" not in response.text


@pytest.mark.integration
def test_search_trace_records_usage_and_returns_the_answer(client):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4(), role="admin")
    document_set_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: user
    db = MagicMock()
    db.scalar.return_value = object()
    db.scalars.return_value.all.return_value = [document_id]
    app.dependency_overrides[get_db] = lambda: db
    point = {
        "payload": {
            "chunk_id": str(chunk_id), "document_id": str(document_id), "filename": "guide.pdf",
            "chunk_index": 0, "content": "Evidence", "matched_child_content": "Evidence", "parent_index": 0,
        },
        "score": 0.9,
        "retrieval": {"method": "hybrid", "vector_rank": 1, "bm25_rank": 1},
    }
    llm_result = LLMResult(
        content="Supported answer [Source 1]", model="test/model", latency_ms=12,
        prompt_tokens=10, completion_tokens=5, total_tokens=15, estimated_cost_usd=0.001,
    )

    with (
        patch("app.services.search_service.require_set_access"),
        patch("app.services.search_service.hybrid_search", return_value=[point]),
        patch("app.services.openrouter.OpenRouterClient.answer_with_usage", return_value=llm_result),
    ):
        response = client.post(
            "/api/v1/search/trace",
            json={"query": "Question?", "document_set_id": str(document_set_id), "limit": 5},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Supported answer [1]"
    assert response.json()["usage"]["model"] == "test/model"
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.integration
def test_login_returns_a_cookie_backed_session_over_http(client):
    organization_id = uuid4()
    user = SimpleNamespace(
        id=uuid4(),
        organization_id=organization_id,
        username="admin",
        password_hash="stored-hash",
        role="admin",
        is_active=True,
    )
    organization = SimpleNamespace(id=organization_id, name="Nexora", slug="default")
    db = MagicMock()
    db.scalar.side_effect = [organization, user]

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with (
        patch("app.api.routes.auth.verify_password", return_value=True),
        patch("app.api.routes.auth.clear_account_failures"),
        patch("app.api.routes.auth.retry_after", return_value=None),
        patch("app.api.routes.auth.create_access_token", return_value="signed-session"),
    ):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct-password", "organization": "default"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "signed-session" in response.headers["set-cookie"]
    db.commit.assert_called_once()


@pytest.mark.integration
def test_upload_endpoint_accepts_multipart_and_queues_processing(client):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4(), role="admin")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    document_id, job_id = uuid4(), uuid4()
    queued_document = SimpleNamespace(
        id=document_id,
        filename="guide.txt",
        content_type="text/plain",
        status="queued",
        processing_error=None,
        processing_progress=0,
        processing_stage="queued",
        author=None,
        language=None,
        source_type="upload",
        document_date=None,
        tags=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        content_checksum=None,
        job_id=job_id,
    )

    with patch("app.api.routes.documents.DocumentIngestionService") as service_factory:
        service_factory.return_value.ingest.return_value = queued_document
        response = client.post(
            "/api/v1/documents/ingest",
            files={"file": ("guide.txt", b"Nexora knowledge", "text/plain")},
            headers={"Idempotency-Key": "upload-flow-1"},
        )

    assert response.status_code == 201
    assert response.json()["status"] == "queued"
    assert response.json()["job_id"] == str(job_id)
    service_factory.return_value.ingest.assert_called_once()


@pytest.mark.integration
def test_conversation_list_exposes_additive_offset_pagination_headers(client):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4(), role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    conversation = SimpleNamespace(
        id=uuid4(),
        title="Policy questions",
        document_id=None,
        document_set_id=None,
        assistant_id=None,
        workspace_scope=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch("app.api.routes.conversations.get_conversation_service") as service_factory:
        service_factory.return_value.list.return_value = [conversation]
        response = client.get("/api/v1/conversations?offset=20&limit=1")

    assert response.status_code == 200
    assert response.headers["X-Pagination-Offset"] == "20"
    assert response.headers["X-Pagination-Limit"] == "1"
    assert response.headers["X-Pagination-Returned"] == "1"
    assert response.headers["X-Pagination-Has-More"] == "true"


@pytest.mark.integration
def test_conversation_history_refreshes_ocr_provenance_for_saved_sources(client):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4(), role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    document_id = uuid4()
    conversation_id = uuid4()
    provenance = {"provider": "jina", "model": "jina-ocr-v1", "completed_at": "2026-09-24T10:00:00Z"}
    message = SimpleNamespace(
        id=uuid4(), role="assistant", content="Answer [Source 1]", answer_basis="sources",
        answer_id=uuid4(), created_at=datetime.now(timezone.utc),
        sources=[{
            "chunk_id": str(uuid4()), "document_id": str(document_id), "filename": "guide.pdf",
            "chunk_index": 0, "content": "Evidence", "score": 0.9,
        }],
    )
    conversation = SimpleNamespace(
        id=conversation_id, title="OCR question", document_id=None, document_set_id=None,
        assistant_id=None, workspace_scope=False, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), messages=[message],
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = [(document_id, provenance)]
    app.dependency_overrides[get_db] = lambda: db

    with patch("app.api.routes.conversations.get_conversation_service") as service_factory:
        service_factory.return_value.get.return_value = conversation
        response = client.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json()["messages"][0]["sources"][0]["ocr_provenance"]["provider"] == "jina"
