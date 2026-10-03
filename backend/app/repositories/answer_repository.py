"""Persistence primitives; the application service owns commit/rollback."""

from sqlalchemy.orm import Session

from app.models.answer_feedback import AnswerRecord


class AnswerRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, record: AnswerRecord) -> None:
        self.db.add(record)

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, record: object) -> None:
        self.db.refresh(record)
