"""Small transaction boundary helpers for application services."""

from contextlib import contextmanager
from collections.abc import Iterator
from sqlalchemy.orm import Session


def commit_or_rollback(db: Session) -> None:
    """Commit all pending changes, or leave no partial database write behind."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    """Service-owned write unit, including failures before commit.

    Reuses SQLAlchemy's current/autobegun transaction. Do not nest or perform
    provider/file operations here: rollback only covers database writes.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
