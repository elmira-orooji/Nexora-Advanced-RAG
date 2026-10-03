import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant import Assistant
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.document_set import DocumentSet


class ConversationRepository:
    """Persistence operations for conversations and their knowledge scopes."""

    def __init__(self, db: Session):
        self.db = db

    def get_owned(self, conversation_id: uuid.UUID, user_id: uuid.UUID, *, with_messages: bool = False) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        if with_messages:
            statement = statement.options(selectinload(Conversation.messages))
        return self.db.scalar(statement)

    def list_for_user(self, user_id: uuid.UUID, offset: int, limit: int) -> list[Conversation]:
        statement = select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(statement).all())

    def get_assistant(self, assistant_id: uuid.UUID, organization_id: uuid.UUID) -> Assistant | None:
        statement = select(Assistant).options(selectinload(Assistant.document_sets)).where(Assistant.id == assistant_id, Assistant.organization_id == organization_id)
        return self.db.scalar(statement)

    def document_set_exists(self, set_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        return self.db.scalar(select(DocumentSet.id).where(DocumentSet.id == set_id, DocumentSet.organization_id == organization_id)) is not None

    def indexed_document_ids_for_set(self, set_id: uuid.UUID) -> list[str]:
        statement = select(Document.id).join(Document.document_sets).where(DocumentSet.id == set_id, Document.status == "indexed")
        return [str(value) for value in self.db.scalars(statement).all()]

    def indexed_document_ids_for_sets(self, set_ids: list[uuid.UUID]) -> list[str]:
        statement = select(Document.id).join(Document.document_sets).where(DocumentSet.id.in_(set_ids), Document.status == "indexed").distinct()
        return [str(value) for value in self.db.scalars(statement).all()]

    def indexed_workspace_document_ids(self, organization_id: uuid.UUID, set_ids: set[uuid.UUID] | None) -> list[str]:
        statement = select(Document.id).join(Document.document_sets).where(DocumentSet.organization_id == organization_id, Document.status == "indexed")
        if set_ids is not None:
            statement = statement.where(DocumentSet.id.in_(set_ids))
        return [str(value) for value in self.db.scalars(statement.distinct()).all()]

    def save(self, item: object) -> None:
        self.db.add(item)

    def delete(self, item: Conversation) -> None:
        self.db.delete(item)

    def refresh(self, item: object) -> None:
        self.db.refresh(item)
