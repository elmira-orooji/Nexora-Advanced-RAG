from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services import indexing_reconciler


def test_stale_outbox_does_not_reindex_deleted_document():
    entry = SimpleNamespace(document_id=uuid4(), action="replace_document_chunks", payload={})
    db = MagicMock()
    db.scalars.return_value = [entry]
    db.scalar.return_value = None
    with patch.object(indexing_reconciler, "SessionLocal") as sessions, patch.object(indexing_reconciler, "QdrantClient") as client:
        sessions.return_value.__enter__.return_value = db
        assert indexing_reconciler.reconcile_indexing_outbox() == 0
        client.return_value.replace_document_chunks.assert_not_called()
