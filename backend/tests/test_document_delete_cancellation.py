from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.sql.dml import Delete

from app.api.routes.documents import delete_document
from app.models.processing_job import ProcessingJob


def test_delete_document_removes_processing_job_in_same_transaction():
    document_id = uuid4()
    document = SimpleNamespace(id=document_id)
    db = MagicMock()
    db.scalar.return_value = document
    user = SimpleNamespace(role="admin", organization_id=uuid4())
    with patch("app.services.document_processing_service._get_document_directory", return_value=None), patch("app.services.document_processing_service.QdrantClient"):
        result = delete_document(document_id, db, user)
    statement = db.execute.call_args.args[0]
    assert isinstance(statement, Delete)
    assert statement.table.name == ProcessingJob.__tablename__
    db.delete.assert_called_once_with(document)
    db.commit.assert_called_once()
    assert result.status == "deleted"
