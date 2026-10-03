import copy
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.search_service import _playground_hit
from app.api.routes.search import retrieval_playground
from app.schemas.search import SearchRequest


class PlaygroundHitTests(unittest.TestCase):
    def setUp(self):
        self.point = {
            "score": 0.9,
            "payload": {"chunk_id": str(uuid4()), "document_id": str(uuid4()),
                        "filename": "test.txt", "chunk_index": 2, "content": "parent text",
                        "parent_index": 1, "matched_child_content": "child text"},
            "retrieval": {"method": "hybrid", "expanded_to_parent": True},
        }

    def test_parent_fields_are_preserved_without_mutating_payload(self):
        original = copy.deepcopy(self.point)
        result = _playground_hit(self.point)
        self.assertEqual(result.parent_index, 1)
        self.assertEqual(result.matched_child_content, "child text")
        self.assertTrue(result.diagnostics.expanded_to_parent)
        self.assertEqual(self.point, original)

    def test_missing_parent_fields_use_defaults(self):
        del self.point["payload"]["parent_index"]
        del self.point["payload"]["matched_child_content"]
        result = _playground_hit(self.point)
        self.assertEqual(result.parent_index, 0)
        self.assertEqual(result.matched_child_content, "parent text")

    def test_retrieval_score_and_diagnostics_override_payload_values(self):
        self.point["payload"].update(score=-1, diagnostics={})
        result = _playground_hit(self.point)
        self.assertEqual(result.score, 0.9)
        self.assertEqual(result.diagnostics.method, "hybrid")

    def test_playground_route_accepts_parent_expanded_result(self):
        with patch("app.services.search_service._scope", return_value=(None, [], 1)), patch("app.services.search_service.hybrid_search", return_value=[self.point]):
            result = retrieval_playground(SearchRequest(query="test query"), MagicMock(), MagicMock())
        self.assertEqual(result.result_count, 1)
        self.assertEqual(result.results[0].parent_index, 1)
        self.assertEqual(result.results[0].matched_child_content, "child text")
