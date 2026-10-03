from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.application_errors import ApplicationError
from app.schemas.document_set import DocumentSetUpdate
from app.schemas.search import RetrieverComparisonRequest
from app.services import chat_share_service, document_set_service, search_service
from app.services.provider_errors import LanguageModelError


def share(visibility):
    return SimpleNamespace(id=uuid4(), owner_id=uuid4(), title="shared", visibility=visibility,
                           created_at=datetime.now(timezone.utc), expires_at=None, messages=[])


def test_public_share_resolution_uses_repository():
    db = MagicMock()
    item = share("link")
    db.scalar.return_value = item
    db.get.return_value = SimpleNamespace(username="owner")
    result = chat_share_service.view_public_share("token", db)
    assert result.id == item.id
    assert result.owner_username == "owner"


def test_team_share_cannot_cross_organization_boundary():
    db = MagicMock()
    db.scalar.return_value = share("team")
    db.get.return_value = SimpleNamespace(organization_id=uuid4())
    with pytest.raises(ApplicationError) as error:
        chat_share_service.view_team_share("token", db, SimpleNamespace(organization_id=uuid4()))
    assert error.value.kind == "not_found"


def test_expired_public_share_is_rejected():
    db = MagicMock()
    item = share("link")
    item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.scalar.return_value = item
    with pytest.raises(ApplicationError) as error:
        chat_share_service.view_public_share("token", db)
    assert error.value.kind == "not_found"


def test_invalid_combined_chunk_settings_roll_back_changes():
    db = MagicMock()
    item = SimpleNamespace(name="set", child_chunk_size=1000, chunk_overlap=200, parent_chunk_size=2000)
    with patch.object(document_set_service, "require_set_access"), patch.object(document_set_service, "_get_set", return_value=item), pytest.raises(ApplicationError):
        document_set_service.update_document_set(uuid4(), DocumentSetUpdate(child_chunk_size=200), db, SimpleNamespace())
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_second_variant_failure_never_saves_partial_usage():
    db = MagicMock()
    payload = RetrieverComparisonRequest(query="test", config_a={"name": "A"}, config_b={"name": "B"})
    user = SimpleNamespace(id=uuid4())
    def variant(*args):
        if args[-2] is payload.config_a:
            args[-1].append(SimpleNamespace())
            return SimpleNamespace(results=[])
        raise LanguageModelError("unavailable")
    with patch.object(search_service, "_scope", return_value=(None, [], 0)), patch.object(search_service, "_run_variant", side_effect=variant), patch.object(search_service, "record_usage") as usage, pytest.raises(ApplicationError):
        search_service.compare_retrievers(payload, db, user)
    usage.assert_not_called()
    db.commit.assert_not_called()


def test_comparison_usage_failure_rolls_back_both_results():
    db = MagicMock()
    payload = RetrieverComparisonRequest(query="test", config_a={"name": "A"}, config_b={"name": "B"})
    user = SimpleNamespace(id=uuid4())
    def variant(*args):
        args[-1].append(SimpleNamespace())
        return SimpleNamespace(results=[])
    with patch.object(search_service, "_scope", return_value=(None, [], 0)), patch.object(search_service, "_run_variant", side_effect=variant), patch.object(search_service, "record_usage", side_effect=[None, SQLAlchemyError("write failed")]), pytest.raises(SQLAlchemyError):
        search_service.compare_retrievers(payload, db, user)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
