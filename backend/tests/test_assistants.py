import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.assistants import list_assistants, answer_with_assistant
from app.schemas.assistant import AssistantAnswerRequest
from fastapi import HTTPException


class AssistantListingTests(unittest.TestCase):
    def test_admin_can_list_assistant_without_knowledge_sets(self):
        item = SimpleNamespace(
            id=uuid4(), name="Support", description=None, instructions="Help with support.",
            is_active=True, created_by_id=uuid4(), document_sets=[],
            model_id=None, answer_mode="sources",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        db = MagicMock()
        db.scalars.return_value.all.return_value = [item]
        with patch("app.api.routes.assistants.accessible_set_ids", return_value=set()):
            result = list_assistants(db=db, user=SimpleNamespace(role="admin", organization_id=uuid4()))
        self.assertEqual([assistant.id for assistant in result], [item.id])

    def test_member_cannot_list_assistant_without_accessible_sets(self):
        item = SimpleNamespace(document_sets=[])
        db = MagicMock()
        db.scalars.return_value.all.return_value = [item]
        with patch("app.api.routes.assistants.accessible_set_ids", return_value=set()):
            result = list_assistants(db=db, user=SimpleNamespace(role="user", organization_id=uuid4()))
        self.assertEqual(result, [])


class AssistantAnswerTests(unittest.TestCase):
    def setUp(self):
        self.item = SimpleNamespace(id=uuid4(), is_active=True, document_sets=[],
                                    model_id="openrouter/free", answer_mode="hybrid", instructions="Help with support.")
        self.user = SimpleNamespace(id=uuid4(), role="admin", organization_id=uuid4())
        self.db = MagicMock()
        self.db.refresh.side_effect = lambda record: setattr(record, "id", uuid4())

    def test_hybrid_without_documents_uses_selected_model_without_searching_other_sets(self):
        with patch("app.api.routes.assistants._get", return_value=self.item), patch("app.api.routes.assistants.accessible_set_ids", return_value=set()), patch("app.api.routes.assistants.hybrid_search") as search, patch("app.api.routes.assistants.get_language_model") as client:
            client.return_value.answer.return_value = "General knowledge [Source 1]"
            result = answer_with_assistant(self.item.id, AssistantAnswerRequest(question="Hello"), self.db, self.user)
            client.assert_called_once_with(model="openrouter/free")
            self.assertTrue(client.return_value.answer.call_args.kwargs["hybrid"])
            search.assert_not_called()
        self.assertEqual(result.answer_basis, "general")
        self.assertFalse(result.grounded)
        self.assertEqual(result.citations, [])
        self.assertNotIn("[1]", result.answer)

    def test_sources_only_without_documents_does_not_call_model(self):
        self.item.answer_mode = "sources"
        with patch("app.api.routes.assistants._get", return_value=self.item), patch("app.api.routes.assistants.accessible_set_ids", return_value=set()), patch("app.api.routes.assistants.get_language_model") as client:
            result = answer_with_assistant(self.item.id, AssistantAnswerRequest(question="Hello"), self.db, self.user)
            client.assert_not_called()
        self.assertEqual(result.answer_basis, "sources")

    def test_hybrid_with_documents_preserves_scoped_citations(self):
        set_id, document_id, chunk_id = uuid4(), uuid4(), uuid4()
        self.item.document_sets = [SimpleNamespace(id=set_id)]
        self.db.scalars.return_value.all.return_value = [document_id]
        point = {"score": 0.9, "payload": {
            "chunk_id": chunk_id, "document_id": document_id, "filename": "Guide.txt",
            "chunk_index": 0, "content": "Supported fact",
        }}
        with patch("app.api.routes.assistants._get", return_value=self.item), patch("app.api.routes.assistants.accessible_set_ids", return_value={set_id}), patch("app.api.routes.assistants.get_vector_store"), patch("app.api.routes.assistants.hybrid_search", return_value=[point]) as search, patch("app.api.routes.assistants.get_language_model") as client:
            client.return_value.answer.return_value = "Supported fact [Source 1]. General knowledge: example."
            result = answer_with_assistant(self.item.id, AssistantAnswerRequest(question="Explain"), self.db, self.user)
        self.assertEqual(search.call_args.kwargs["document_ids"], [str(document_id)])
        self.assertEqual(result.answer_basis, "hybrid")
        self.assertEqual(result.citations[0].document_id, document_id)
        self.assertIn("[1]", result.answer)

    def test_hybrid_does_not_bypass_member_permissions(self):
        self.user.role = "user"
        with patch("app.api.routes.assistants._get", return_value=self.item), patch("app.api.routes.assistants.accessible_set_ids", return_value=set()), patch("app.api.routes.assistants.get_language_model") as client:
            with self.assertRaises(HTTPException) as raised:
                answer_with_assistant(self.item.id, AssistantAnswerRequest(question="Hello"), self.db, self.user)
            self.assertEqual(raised.exception.status_code, 403)
            client.assert_not_called()
