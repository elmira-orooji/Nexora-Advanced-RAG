from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services.document_processing_service import DocumentProcessingService
from app.services.document_indexing_service import DocumentIndexingService


def document():
    return SimpleNamespace(id=uuid4(), filename="test.txt", status="chunked",
                           chunks=[SimpleNamespace(id=uuid4(), chunk_index=0, content="current", is_active=True)])


def test_commit_failure_never_mutates_vector_store():
    db = MagicMock()
    doc = document()
    db.scalar.return_value = doc
    db.commit.side_effect = SQLAlchemyError("commit failed")
    with patch("app.services.document_indexing_service.get_vector_store") as factory, pytest.raises(SQLAlchemyError):
        DocumentProcessingService(db).index(doc.id, SimpleNamespace(role="admin", organization_id=uuid4()))
    factory.assert_not_called()
    db.rollback.assert_called_once()


def test_older_outbox_intent_applies_current_active_sql_content():
    db = MagicMock()
    doc = document()
    doc.chunks.append(SimpleNamespace(id=uuid4(), chunk_index=1, content="inactive", is_active=False))
    db.scalar.return_value = doc
    entry = SimpleNamespace(status="pending", job_id=None, payload={"chunks": [{"content": "stale"}]})
    with patch("app.services.document_indexing_service.get_vector_store") as factory:
        DocumentIndexingService(db).apply(entry, doc.id)
    chunks = factory.return_value.replace_document_chunks.call_args.args[2]
    assert [chunk["content"] for chunk in chunks] == ["current"]
    assert entry.status == "applied"


def test_deleted_document_is_not_reintroduced():
    db = MagicMock()
    db.scalar.return_value = None
    with patch("app.services.document_indexing_service.get_vector_store") as factory:
        DocumentIndexingService(db).apply(SimpleNamespace(), uuid4())
    factory.assert_not_called()


def test_delete_commit_failure_never_removes_vectors():
    db = MagicMock()
    doc = document()
    db.scalar.return_value = doc
    db.commit.side_effect = SQLAlchemyError("commit failed")
    with patch("app.services.document_processing_service._get_document_directory", return_value=None), patch("app.services.document_indexing_service.get_vector_store") as factory, pytest.raises(Exception):
        DocumentProcessingService(db).delete(doc.id, SimpleNamespace(role="admin", organization_id=uuid4()))
    factory.assert_not_called()


def test_delete_provider_failure_retains_detached_pending_intent():
    db = MagicMock()
    doc = document()
    db.scalar.return_value = doc
    with patch("app.services.document_processing_service._get_document_directory", return_value=None), patch("app.services.document_indexing_service.get_vector_store") as factory:
        factory.return_value.delete_document.side_effect = RuntimeError("offline")
        result = DocumentProcessingService(db).delete(doc.id, SimpleNamespace(role="admin", organization_id=uuid4()))
    intent = db.add.call_args.args[0]
    assert intent.document_id is None
    assert intent.payload["document_id"] == str(doc.id)
    assert intent.status == "pending"
    assert result.status == "deleted"
    db.commit.assert_called_once()
