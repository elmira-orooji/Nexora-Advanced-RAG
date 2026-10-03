import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.application_errors import ApplicationError
from app.services.connector_management_service import ConnectorManagementService
from app.services.document_management_service import DocumentManagementService


@pytest.mark.parametrize("name", ["users", "connectors", "documents", "assistants", "document_sets", "chat_shares", "search"])
def test_administrative_routes_do_not_execute_database_operations(name):
    path = Path(__file__).parents[1] / "app" / "api" / "routes" / f"{name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    forbidden = {"commit", "rollback", "scalar", "scalars", "execute", "add", "delete", "flush", "refresh"}
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "db" and node.func.attr in forbidden]


@pytest.mark.parametrize("name", ["user", "connector", "document", "assistant", "document_set", "chat_share"])
def test_repositories_never_own_transaction_boundaries(name):
    path = Path(__file__).parents[1] / "app" / "repositories" / f"{name}_repository.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr in {"commit", "rollback"}]


@pytest.mark.parametrize("name", ["assistant", "document_set", "chat_share", "search"])
def test_services_have_no_duplicate_definitions_or_direct_sql(name):
    path = Path(__file__).parents[1] / "app" / "services" / f"{name}_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert len(names) == len(set(names))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "db" and node.func.attr in {"scalar", "scalars", "execute", "commit", "add", "delete"}]


def test_document_creation_rolls_back_even_if_repository_add_fails():
    db = MagicMock()
    db.add.side_effect = SQLAlchemyError("write failed")
    payload = SimpleNamespace(filename="test.txt", content_type="text/plain")
    user = SimpleNamespace(role="admin", organization_id=uuid4())
    with pytest.raises(SQLAlchemyError):
        DocumentManagementService(db).create_document(payload, user)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_metadata_commit_failure_rolls_back_without_refresh():
    db = MagicMock()
    db.commit.side_effect = SQLAlchemyError("commit failed")
    payload = SimpleNamespace(author=None, language="fa", source_type="upload", document_date=None, tags=[])
    with patch("app.services.document_management_service.require_document_access", return_value=SimpleNamespace()), pytest.raises(SQLAlchemyError):
        DocumentManagementService(db).update_document_metadata(uuid4(), payload, SimpleNamespace())
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


def test_connector_delete_rolls_back_if_delete_fails():
    db = MagicMock()
    set_id = uuid4()
    db.get.return_value = SimpleNamespace(document_set_id=set_id)
    db.delete.side_effect = SQLAlchemyError("delete failed")
    with patch("app.services.connector_management_service.require_set_access"), pytest.raises(SQLAlchemyError):
        ConnectorManagementService(db).delete_connector(set_id, uuid4(), SimpleNamespace())
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_wrong_webhook_secret_does_not_start_ingestion():
    db = MagicMock()
    set_id = uuid4()
    db.get.return_value = SimpleNamespace(document_set_id=set_id, connector_type="webhook", webhook_secret_hash="wrong")
    with patch("app.services.connector_management_service.ingest_webhook_event") as ingest, pytest.raises(ApplicationError) as error:
        ConnectorManagementService(db).receive_webhook_event(set_id, uuid4(), SimpleNamespace(), "secret")
    assert error.value.kind == "unauthorized"
    ingest.assert_not_called()
    db.commit.assert_not_called()


def test_chunk_enrichment_failure_is_inside_rollback_boundary():
    db = MagicMock()
    chunk = SimpleNamespace(id=uuid4(), content="old text")
    document = SimpleNamespace(chunks=[chunk])
    db.scalar.return_value = document
    user = SimpleNamespace(role="admin", organization_id=uuid4())
    payload = SimpleNamespace(content="new text", is_active=None)
    with patch("app.services.document_management_service.enrich_chunk", side_effect=RuntimeError("enrichment failed")), pytest.raises(RuntimeError):
        DocumentManagementService(db).update_chunk(uuid4(), chunk.id, payload, user)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    db.flush.assert_not_called()
