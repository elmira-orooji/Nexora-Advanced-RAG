from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.indexing_outbox import IndexingOutbox
from app.services import indexing_reconciler


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def seed(sessions, *, newer=False):
    doc_id, entry_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    with sessions() as db:
        doc = Document(id=doc_id, organization_id=uuid4(), filename="test.txt", status="processing", processing_stage="indexing", processing_progress=95)
        doc.chunks = [Chunk(chunk_index=0, content="current", parent_content="current", is_active=True)]
        db.add(doc)
        db.flush()
        db.add(IndexingOutbox(id=entry_id, document_id=doc_id, action="replace_document_chunks", payload={"document_id": str(doc_id), "chunks": [{"content": "stale"}]}, attempts=9, created_at=now))
        if newer:
            db.add(IndexingOutbox(document_id=doc_id, action="replace_document_chunks", payload={}, created_at=now + timedelta(seconds=1)))
        db.commit()
    return doc_id, entry_id


@pytest.mark.parametrize("newer", [False, True])
@pytest.mark.parametrize("phase", ["ensure_collection", "replace_document_chunks"])
def test_terminal_failure_does_not_overwrite_newer_intent(sessions, newer, phase):
    doc_id, entry_id = seed(sessions, newer=newer)
    with patch.object(indexing_reconciler, "SessionLocal", sessions), patch.object(indexing_reconciler, "BATCH_SIZE", 1), patch.object(indexing_reconciler, "get_vector_store") as factory:
        getattr(factory.return_value, phase).side_effect = RuntimeError("offline")
        assert indexing_reconciler.reconcile_indexing_outbox() == 0
    with sessions() as db:
        assert db.get(IndexingOutbox, entry_id).status == "failed"
        doc = db.get(Document, doc_id)
        assert doc.status == ("processing" if newer else "failed")


def test_reconciliation_uses_current_sql_and_marks_ready(sessions):
    doc_id, entry_id = seed(sessions)
    with patch.object(indexing_reconciler, "SessionLocal", sessions), patch.object(indexing_reconciler, "get_vector_store") as factory:
        assert indexing_reconciler.reconcile_indexing_outbox() == 1
        chunks = factory.return_value.replace_document_chunks.call_args.args[2]
        assert [item["content"] for item in chunks] == ["current"]
    with sessions() as db:
        assert db.get(Document, doc_id).status == "indexed"
        assert db.get(IndexingOutbox, entry_id).status == "applied"


def test_detached_delete_intent_is_reconciled_after_document_is_gone(sessions):
    doc_id = uuid4()
    with sessions() as db:
        db.add(IndexingOutbox(document_id=None, action="delete_document", payload={"document_id": str(doc_id)}))
        db.commit()
    with patch.object(indexing_reconciler, "SessionLocal", sessions), patch.object(indexing_reconciler, "get_vector_store") as factory:
        assert indexing_reconciler.reconcile_indexing_outbox() == 1
        factory.return_value.delete_document.assert_called_once_with(str(doc_id))
