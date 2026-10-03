from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from app.services.transactions import commit_or_rollback
from app.services.transactions import transaction
import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select
from sqlalchemy.orm import Session


def test_commit_failure_rolls_back_the_whole_unit_of_work():
    db = MagicMock()
    db.commit.side_effect = SQLAlchemyError("database unavailable")

    try:
        commit_or_rollback(db)
    except SQLAlchemyError:
        pass
    else:
        raise AssertionError("Expected commit failure")

    db.rollback.assert_called_once_with()


def test_transaction_commits_once_on_success():
    db = MagicMock()
    with transaction(db):
        db.add(object())
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("phase", ["add", "flush", "commit"])
def test_transaction_rolls_back_failures_before_and_during_commit(phase):
    db = MagicMock()
    getattr(db, phase).side_effect = SQLAlchemyError("write failure")
    with pytest.raises(SQLAlchemyError):
        with transaction(db):
            db.add(object())
            db.flush()
    db.rollback.assert_called_once_with()
    if phase != "commit":
        db.commit.assert_not_called()


def test_transaction_rolls_back_non_database_failure():
    db = MagicMock()
    with pytest.raises(ValueError):
        with transaction(db):
            raise ValueError("invalid operation")
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_real_database_rollback_removes_flushed_rows():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    items = Table("items", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)
    with Session(engine) as db:
        with pytest.raises(ValueError):
            with transaction(db):
                db.execute(insert(items).values(id=1))
                db.flush()
                raise ValueError("fail after writing")
        assert db.execute(select(items)).all() == []
        with transaction(db):
            db.execute(insert(items).values(id=2))
        assert db.execute(select(items)).all() == [(2,)]
    engine.dispose()
