from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception


def http_status(error):
    return to_http_exception(error).status_code if isinstance(error, ApplicationError) else error.status_code


from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.core.config import UPLOAD_DIR
from app.schemas.document import ChunkingRequest
from app.services.document_processing_service import DocumentProcessingService
from app.services.qdrant import QdrantError


@pytest.mark.parametrize("operation", ["create_chunks", "index", "delete"])
def test_operations_reject_non_admin_before_database_access(operation):
    db = MagicMock()
    service = DocumentProcessingService(db)
    user = SimpleNamespace(role="user", organization_id=uuid4())
    args = (uuid4(), ChunkingRequest(), user) if operation == "create_chunks" else (uuid4(), user)
    with pytest.raises(ApplicationError) as exc:
        getattr(service, operation)(*args)
    assert http_status(exc.value) == 403
    db.scalar.assert_not_called()


def test_index_saves_status_after_vector_write():
    chunk = SimpleNamespace(id=uuid4(), chunk_index=0, content="Policy text")
    document = SimpleNamespace(id=uuid4(), filename="policy.pdf", chunks=[chunk], status="chunked", processing_error="old")
    db = MagicMock()
    db.scalar.return_value = document
    user = SimpleNamespace(role="admin", organization_id=uuid4())
    with patch("app.services.document_processing_service.get_vector_store") as factory:
        result = DocumentProcessingService(db).index(document.id, user)
        factory.return_value.replace_document_chunks.assert_called_once_with(str(document.id), "policy.pdf", [{"id": str(chunk.id), "chunk_index": 0, "content": "Policy text"}])
    assert result.status == "indexed"
    assert result.processing_error is None
    db.commit.assert_called_once()


def test_index_does_not_commit_when_provider_fails():
    document = SimpleNamespace(id=uuid4(), filename="policy.pdf", chunks=[SimpleNamespace(id=uuid4(), chunk_index=0, content="Text")], status="chunked")
    db = MagicMock()
    db.scalar.return_value = document
    with patch("app.services.document_processing_service.get_vector_store") as factory:
        factory.return_value.ensure_collection.side_effect = QdrantError("Unavailable")
        with pytest.raises(ApplicationError) as exc:
            DocumentProcessingService(db).index(document.id, SimpleNamespace(role="admin", organization_id=uuid4()))
    assert http_status(exc.value) == 502
    assert document.status == "chunked"
    db.commit.assert_not_called()


def test_chunking_preserves_enrichment_and_transaction():
    document = SimpleNamespace(id=uuid4(), chunks=[], extracted_text_path="document/extracted.txt", status="extracted", processing_error=None)
    db = MagicMock()
    db.scalar.return_value = document
    path = MagicMock()
    path.parents = [UPLOAD_DIR.resolve()]
    path.is_file.return_value = True
    path.read_text.return_value = "Policy text"
    user = SimpleNamespace(role="admin", organization_id=uuid4())
    with patch("app.services.document_processing_service.resolve_document_path", return_value=path), patch("app.services.document_processing_service.hierarchical_chunks", return_value=[("Policy text", 0, "Parent")]), patch("app.services.document_processing_service.enrich_chunk", return_value=(["policy"], ["What?"])):
        result = DocumentProcessingService(db).create_chunks(document.id, ChunkingRequest(), user)
    assert result.status == "chunked"
    assert result.chunks[0].keywords == ["policy"]
    assert result.chunks[0].suggested_questions == ["What?"]
    db.commit.assert_called_once()
