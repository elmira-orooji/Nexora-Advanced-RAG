import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.schemas.conversation import ChatMessageCreate, ConversationCreate
from app.services.conversation_service import ConversationService


class ConversationMultiSetTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
        self.repository = MagicMock()
        self.service = ConversationService(MagicMock(), MagicMock(), self.repository)
        self.ids = [uuid4(), uuid4()]

    def test_create_deduplicates_and_checks_every_selected_set(self):
        with patch("app.services.conversation_service.require_set_access") as access:
            result = self.service.create(ConversationCreate(document_set_ids=self.ids + self.ids), self.user)
        self.assertEqual(result.document_set_ids, [str(value) for value in self.ids])
        self.assertEqual(access.call_count, 2)
        self.repository.save.assert_called_once_with(result)

    def test_scope_retrieves_only_selected_sets(self):
        self.repository.indexed_document_ids_for_sets.return_value = ["document"]
        with patch("app.services.conversation_service.require_set_access") as access:
            result = self.service._resolve_scope(SimpleNamespace(document_set_ids=[str(value) for value in self.ids]), self.user)
        self.assertEqual(result, (None, ["document"], None, None, False))
        self.assertEqual(access.call_count, 2)
        self.repository.indexed_document_ids_for_sets.assert_called_once_with(self.ids)

    def test_revoked_access_prevents_retrieval(self):
        with patch("app.services.conversation_service.require_set_access", side_effect=HTTPException(403, "Forbidden")):
            with self.assertRaises(HTTPException):
                self.service._resolve_scope(SimpleNamespace(document_set_ids=[str(self.ids[0])]), self.user)
        self.repository.indexed_document_ids_for_sets.assert_not_called()

    def test_mixed_workspace_and_selected_scope_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            self.service.create(ConversationCreate(document_set_ids=self.ids, workspace_scope=True), self.user)
        self.assertEqual(error.exception.status_code, 422)
        self.repository.save.assert_not_called()


class ConversationAssistantTests(unittest.TestCase):
    def setUp(self):
        self.assistant = SimpleNamespace(id=uuid4(), is_active=True, document_sets=[],
                                         model_id="selected/model", answer_mode="hybrid", instructions="Custom instructions")
        self.user = SimpleNamespace(id=uuid4(), role="admin", organization_id=uuid4())
        self.conversation = SimpleNamespace(id=uuid4(), document_id=None, document_set_id=None,
                                             assistant_id=self.assistant.id, messages=[], title="Test")
        self.db = MagicMock()
        self.db.scalar.return_value = self.assistant
        self.db.scalars.return_value.all.return_value = []
        self.providers = MagicMock()
        self.qdrant = self.providers.vector_store
        self.client = self.providers.language_model
        self.service = ConversationService(self.db, providers=self.providers)
        stack = self.enterContext(ExitStack())
        stack.enter_context(patch.object(self.service.repository, "get_owned", return_value=self.conversation))
        stack.enter_context(patch("app.services.conversation_service.accessible_set_ids", return_value=None))
        self.rewrite = stack.enter_context(patch("app.services.conversation_service.should_rewrite", return_value=False))
        self.search = stack.enter_context(patch("app.services.conversation_service.hybrid_search", return_value=[]))
        self.client.return_value.answer.return_value = "Generated answer"
        self.client.return_value.rewrite_query.return_value = "Rewritten question"

    def send(self):
        return self.service.send_message(self.conversation.id, ChatMessageCreate(content="Test question"), self.user)

    def test_hybrid_without_documents_uses_selected_model(self):
        result = self.send()
        self.assertEqual(result.content, "Generated answer")
        self.client.assert_called_once_with(model="selected/model")
        self.assertTrue(self.client.return_value.answer.call_args.kwargs["hybrid"])
        self.search.assert_not_called()
        self.qdrant.assert_not_called()

    def test_sources_without_documents_does_not_generate_answer(self):
        self.assistant.answer_mode = "sources"
        self.send()
        self.client.assert_not_called()

    def test_selected_model_is_used_for_rewrite_and_answer_with_sources(self):
        set_id, document_id = uuid4(), uuid4()
        self.assistant.document_sets = [SimpleNamespace(id=set_id)]
        self.db.scalars.return_value.all.return_value = [document_id]
        self.rewrite.return_value = True
        self.search.return_value = [{"score": 0.9, "payload": {"chunk_id": uuid4(), "document_id": document_id, "filename": "test.txt", "chunk_index": 0, "content": "Source text"}}]
        self.assistant.answer_mode = "sources"
        self.send()
        self.assertTrue(all(call.kwargs == {"model": "selected/model"} for call in self.client.call_args_list))
        self.assertEqual(self.search.call_args.kwargs["query"], "Rewritten question")
        self.assertEqual(self.search.call_args.kwargs["document_ids"], [str(document_id)])
        kwargs = self.client.return_value.answer.call_args.kwargs
        self.assertFalse(kwargs["hybrid"])
        self.assertEqual(kwargs["instructions"], "Custom instructions")

    def test_inactive_assistant_cannot_trigger_rewrite(self):
        self.assistant.is_active = False
        self.rewrite.return_value = True
        with self.assertRaises(HTTPException) as raised:
            self.send()
        self.assertEqual(raised.exception.status_code, 409)
        self.client.assert_not_called()

    def test_image_request_persists_preview_intent_without_generation_provider(self):
        set_id, document_id = uuid4(), uuid4()
        self.assistant.document_sets = [SimpleNamespace(id=set_id)]
        self.db.scalars.return_value.all.return_value = [document_id]
        self.search.return_value = [{"score": 0.9, "payload": {"chunk_id": uuid4(), "document_id": document_id, "filename": "Insurance.pdf", "chunk_index": 0, "content": "Insurance commitments coverage"}}]
        result = self.service.send_message(self.conversation.id, ChatMessageCreate(content="Show an image of insurance commitments"), self.user)
        self.assertEqual(result.sources[0]["visual_query"], "Show an image of insurance commitments")
        self.assertEqual(result.answer_basis, "sources")
        self.client.assert_not_called()

    def test_hybrid_does_not_bypass_member_permissions(self):
        self.user.role = "user"
        with patch("app.services.conversation_service.accessible_set_ids", return_value=set()):
            with self.assertRaises(HTTPException) as raised:
                self.send()
        self.assertEqual(raised.exception.status_code, 403)
        self.client.assert_not_called()
