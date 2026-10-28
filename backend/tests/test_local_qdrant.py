import unittest
from unittest.mock import MagicMock, patch

from app.services.providers.qdrant import QdrantClient, QdrantError


class LocalQdrantTests(unittest.TestCase):
    def client(self, mode):
        client = QdrantClient.__new__(QdrantClient)
        client.collection = "demo"
        client.model = "dummy-384-model"
        client.inference_mode = mode
        client._request = MagicMock(return_value={"result": {"points": []}})
        return client

    @patch("app.services.providers.qdrant.embed_texts", return_value=[[0.5] * 384])
    def test_local_upsert_and_query_send_numeric_vectors_with_scope_filters(self, embed):
        client = self.client("local")
        client.upsert_chunks("doc", "sample.txt", [{"id": "chunk", "content": "sample", "chunk_index": 0}])
        self.assertEqual(client._request.call_args.args[2]["points"][0]["vector"]["dense"], [0.5] * 384)
        client.search("question", 5, document_ids=["doc"])
        body = client._request.call_args.args[2]
        self.assertEqual(body["query"], [0.5] * 384)
        self.assertEqual(body["filter"]["should"][0]["match"]["value"], "doc")
        self.assertEqual(embed.call_count, 2)

    @patch("app.services.providers.qdrant.embed_texts")
    def test_cloud_mode_and_empty_scope_never_load_local_model(self, embed):
        client = self.client("cloud")
        client.search("question", 5, document_ids=["doc"])
        self.assertEqual(client._request.call_args.args[2]["query"], {"text": "question", "model": client.model})
        client = self.client("local")
        self.assertEqual(client.search("question", 5, document_ids=[]), [])
        embed.assert_not_called()
        client._request.assert_not_called()

    @patch("app.services.providers.qdrant.embed_texts", return_value=[[0.5] * 768])
    def test_dimension_mismatch_is_rejected_before_network(self, embed):
        client = self.client("local")
        with self.assertRaises(QdrantError):
            client.search("question", 5)
        client._request.assert_not_called()
