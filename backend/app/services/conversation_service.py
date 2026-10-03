from app.core.application_errors import ApplicationError
import uuid
from datetime import datetime, timezone


from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.document_set_access import accessible_set_ids, require_document_access, require_set_access
from app.models.answer_feedback import AnswerRecord
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import ChatMessageCreate, ConversationCreate, ConversationUpdate
from app.schemas.search import SearchHit
from app.services.openrouter import OpenRouterError
from app.services.ports import ProviderFactoryPort
from app.services.qdrant import QdrantError
from app.services.provider_failures import provider_error
from app.services.query_rewriting import should_rewrite
from app.services.retrieval import hybrid_search
from app.services.transactions import commit_or_rollback
from app.services.document_visuals import wants_document_image


class ConversationService:
    """Business rules for conversations, scoped retrieval, and generated answers."""

    def __init__(self, db: Session, providers: ProviderFactoryPort, repository: ConversationRepository | None = None):
        self.db = db
        self.providers = providers
        self.repository = repository or ConversationRepository(db)

    def create(self, payload: ConversationCreate, user: User) -> Conversation:
        scopes = sum(value is not None for value in (payload.document_id, payload.document_set_id, payload.assistant_id)) + int(payload.workspace_scope) + int(bool(payload.document_set_ids))
        if scopes != 1:
            raise ApplicationError(kind="validation_error", detail="Choose exactly one document, knowledge set, assistant, or workspace scope")
        if payload.document_id:
            require_document_access(self.db, user, payload.document_id)
        if payload.document_set_id:
            if not self.repository.document_set_exists(payload.document_set_id, user.organization_id):
                raise ApplicationError(kind="not_found", detail="Document set not found")
            require_set_access(self.db, user, payload.document_set_id)
        if payload.assistant_id:
            assistant = self.repository.get_assistant(payload.assistant_id, user.organization_id)
            if assistant is None:
                raise ApplicationError(kind="not_found", detail="Assistant not found")
            self._assistant_set_ids(assistant, user)
        selected_ids = list(dict.fromkeys(payload.document_set_ids))
        for set_id in selected_ids:
            if not self.repository.document_set_exists(set_id, user.organization_id):
                raise ApplicationError(kind="not_found", detail="Document set not found")
            require_set_access(self.db, user, set_id)
        conversation = Conversation(user_id=user.id, title=payload.title or "New conversation", document_id=payload.document_id, document_set_id=payload.document_set_id, assistant_id=payload.assistant_id, workspace_scope=payload.workspace_scope, document_set_ids=[str(value) for value in selected_ids])
        self.repository.save(conversation)
        return conversation

    def list(self, user: User, offset: int, limit: int) -> list[Conversation]:
        return self.repository.list_for_user(user.id, offset, limit)

    def get(self, conversation_id: uuid.UUID, user: User, *, with_messages: bool = False) -> Conversation:
        conversation = self.repository.get_owned(conversation_id, user.id, with_messages=with_messages)
        if conversation is None:
            raise ApplicationError(kind="not_found", detail="Conversation not found")
        return conversation

    def update(self, conversation_id: uuid.UUID, payload: ConversationUpdate, user: User) -> Conversation:
        conversation = self.get(conversation_id, user)
        conversation.title = payload.title.strip()
        conversation.updated_at = datetime.now(timezone.utc)
        self.repository.save(conversation)
        return conversation

    def delete(self, conversation_id: uuid.UUID, user: User) -> None:
        self.repository.delete(self.get(conversation_id, user))

    def send_message(self, conversation_id: uuid.UUID, payload: ChatMessageCreate, user: User) -> Message:
        conversation = self.get(conversation_id, user, with_messages=True)
        history = [{"role": message.role, "content": message.content} for message in conversation.messages[-8:]]
        document_id, document_ids, model_id, instructions, hybrid = self._resolve_scope(conversation, user)
        retrieval_query = payload.content
        if (document_id or document_ids) and should_rewrite(payload.content, history):
            try:
                retrieval_query = self.providers.language_model(model=model_id).rewrite_query(payload.content, history)
            except OpenRouterError:
                retrieval_query = payload.content
        try:
            points = []
            if document_id or document_ids:
                vector_store = self.providers.vector_store()
                vector_store.ensure_collection()
                points = hybrid_search(self.db, query=retrieval_query, limit=payload.limit, document_id=document_id, document_ids=document_ids, vector_store=vector_store)
        except QdrantError as exc:
            raise provider_error(exc) from exc
        sources = [SearchHit(score=point["score"], **point["payload"]) for point in points]
        answer_basis = ("hybrid" if sources else "general") if hybrid else "sources"
        if sources and wants_document_image(payload.content):
            sources = sources[:1]
            sources[0].visual_query = payload.content
            answer_basis = "sources"
            answer = ("در حال آماده‌سازی تصویر بخش مرتبط از فایل اصلی هستم. نتیجه یا دلیل در دسترس نبودن تصویر در پایین نمایش داده می‌شود. [Source 1]" if any("\u0600" <= char <= "\u06ff" for char in payload.content) else "Preparing the relevant region from the original document. The image or an explanation will appear below. [Source 1]")
        elif sources or hybrid:
            try:
                answer = self.providers.language_model(model=model_id).answer(payload.content, [source.model_dump(mode="json", exclude={"ocr_provenance"}) for source in sources], history=history, instructions=instructions, hybrid=hybrid)
            except OpenRouterError as exc:
                raise provider_error(exc) from exc
        else:
            answer = self._no_results_message(payload.content)
        record = AnswerRecord(user_id=user.id, assistant_id=conversation.assistant_id, document_set_id=conversation.document_set_id, question=payload.content, answer=answer, grounded=bool(sources), citation_count=len(sources))
        try:
            self.db.add(record)
            self.db.flush()
            assistant_message = Message(role="assistant", content=answer, sources=[source.model_dump(mode="json") for source in sources] or None, answer_basis=answer_basis, answer_id=record.id)
            conversation.messages.extend([Message(role="user", content=payload.content), assistant_message])
            if conversation.title == "New conversation":
                conversation.title = payload.content[:200]
            conversation.updated_at = datetime.now(timezone.utc)
            commit_or_rollback(self.db)
        except SQLAlchemyError as exc:
            raise ApplicationError(kind="internal_error", detail="Could not save the conversation message") from exc
        self.db.refresh(assistant_message)
        return assistant_message

    def _resolve_scope(self, conversation: Conversation, user: User) -> tuple[str | None, list[str] | None, str | None, str | None, bool]:
        if getattr(conversation, "document_set_ids", None):
            selected_ids = [uuid.UUID(value) for value in conversation.document_set_ids]
            for set_id in selected_ids:
                require_set_access(self.db, user, set_id)
            return None, self.repository.indexed_document_ids_for_sets(selected_ids), None, None, False
        if conversation.document_id:
            require_document_access(self.db, user, conversation.document_id)
            return str(conversation.document_id), None, None, None, False
        if conversation.document_set_id:
            require_set_access(self.db, user, conversation.document_set_id)
            return None, self.repository.indexed_document_ids_for_set(conversation.document_set_id), None, None, False
        if conversation.assistant_id:
            assistant = self.repository.get_assistant(conversation.assistant_id, user.organization_id)
            if assistant is None:
                raise ApplicationError(kind="conflict", detail="Conversation assistant is unavailable")
            set_ids = self._assistant_set_ids(assistant, user)
            return None, self.repository.indexed_document_ids_for_sets(set_ids) if set_ids else [], assistant.model_id, assistant.instructions, assistant.answer_mode == "hybrid"
        if conversation.workspace_scope:
            set_ids = accessible_set_ids(self.db, user)
            if not set_ids and user.role != "admin":
                return None, [], None, None, False
            return None, self.repository.indexed_workspace_document_ids(user.organization_id, set_ids), None, None, False
        raise ApplicationError(kind="conflict", detail="Conversation has no valid knowledge scope")

    def _assistant_set_ids(self, assistant, user: User) -> list[uuid.UUID]:
        if not assistant.is_active:
            raise ApplicationError(kind="conflict", detail="Assistant is inactive")
        set_ids = [item.id for item in assistant.document_sets]
        allowed = accessible_set_ids(self.db, user)
        if allowed is not None:
            set_ids = [value for value in set_ids if value in allowed]
        if not set_ids and user.role != "admin":
            raise ApplicationError(kind="forbidden", detail="You do not have access to this assistant's knowledge")
        return set_ids

    @staticmethod
    def _no_results_message(question: str) -> str:
        if any("\u0600" <= character <= "\u06ff" for character in question):
            return "در اسناد مجاز اطلاعات مرتبطی برای پاسخ پیدا نشد."
        return "No relevant information was found in the permitted indexed documents."
