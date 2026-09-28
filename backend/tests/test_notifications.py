from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.notifications import delete_notification


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
