from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.connectors import sync


def test_repeated_manual_connector_sync_keeps_existing_job_state():
    connector_id = uuid4()
    document_set_id = uuid4()
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=connector_id, document_set_id=document_set_id, status="syncing")

    with patch("app.services.connector_management_service.require_set_access"), patch("app.services.connector_management_service.connector_sync_lock") as lock:
        result = sync(document_set_id, connector_id, db, MagicMock())

    assert result.status == "queued"
    assert result.message == "Connector sync is already scheduled"
    lock.assert_not_called()
    db.commit.assert_not_called()
