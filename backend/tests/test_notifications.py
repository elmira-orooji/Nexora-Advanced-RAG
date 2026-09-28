from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes.notifications import delete_notification
from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.main import app


def test_user_can_delete_own_notification():
    notification_id = uuid4()
    item = SimpleNamespace(id=notification_id)
    db = MagicMock()

    db.scalar.return_value = item

    delete_notification(
        notification_id=notification_id,
        db=db,
        user=SimpleNamespace(id=uuid4(), organization_id=uuid4()),
    )

    db.delete.assert_called_once_with(item)
    db.commit.assert_called_once_with()


def test_user_cannot_delete_notification_outside_scope():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as error:
        delete_notification(
            notification_id=uuid4(),
            db=db,
            user=SimpleNamespace(id=uuid4(), organization_id=uuid4()),
        )

    assert error.value.status_code == 404
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_delete_notification_http_route_returns_no_content():
    notification_id = uuid4()
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(id=notification_id)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), organization_id=uuid4())
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.delete(f"/api/v1/notifications/{notification_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    db.delete.assert_called_once()
    db.commit.assert_called_once()
