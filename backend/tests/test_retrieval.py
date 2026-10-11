import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.retrieval import retrieval
from app.services.retrieval.retrieval import _expand_parents, _ChunkSnapshot, hybrid_search


class RetrievalContextTests(unittest.TestCase):
    def setUp(self):
        self.document_id = uuid4()
        retrieval._lexical_cache.clear()
        retrieval._lexical_cache_total_weight = 0

    @staticmethod
    def result(rows):
        result = MagicMock()
        result.all.return_value = rows
        return result

    def chunk(self, index, content, document_id=None):
        return SimpleNamespace(id=uuid4(), document_id=document_id or self.document_id,
                               chunk_index=index, parent_index=0, content=content,
                               parent_content="old text", is_active=True)

    def snapshot(self, index, content, document_id=None):
        cid = uuid4()
        did = document_id or self.document_id
        return _ChunkSnapshot(
            id=cid, document_id=did, chunk_index=index, parent_index=0,
            content=content, tokens=retrieval._tokens(content), filename="test.txt",
        )

    def point(self, snap):
        return {"id": str(snap.id), "score": 0.9, "payload": {
            "chunk_id": str(snap.id), "document_id": str(snap.document_id),
            "chunk_index": snap.chunk_index, "filename": "test.txt", "content": "stale vector text"}}

    def test_parent_context_uses_current_active_siblings_in_order(self):
        edited = self.snapshot(0, "edited text")
        active = self.snapshot(2, "current neighbor")
        other_document = self.snapshot(0, "other document", document_id=uuid4())
        chunks = [active, other_document, edited]
        results = _expand_parents(chunks, [self.point(active), self.point(edited)], 5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payload"]["content"], "edited text\n\ncurrent neighbor")
        self.assertEqual(results[0]["payload"]["matched_child_content"], "current neighbor")

    def test_missing_chunk_in_snapshot_is_skipped(self):
        existing = self.snapshot(0, "existing text")
        missing_point = {"id": str(uuid4()), "score": 0.9, "payload": {
            "chunk_id": str(uuid4()), "document_id": str(self.document_id),
            "chunk_index": 0, "filename": "test.txt", "content": "ghost"}}
        results = _expand_parents([existing], [missing_point], 5)
        self.assertEqual(results, [])

    def test_hybrid_search_reranks_current_database_text_only(self):
        edited = self.chunk(0, "edited text")
        edited_snap = _ChunkSnapshot(
            id=edited.id, document_id=edited.document_id, chunk_index=0, parent_index=0,
            content="edited text", tokens=retrieval._tokens("edited text"), filename="test.txt",
        )
        db = MagicMock()
        db.execute.side_effect = [
            self.result([(self.document_id, datetime.now(timezone.utc))]),
            self.result([(edited, "test.txt")]),
            self.result([(self.document_id, {"provider": "jina", "model": "jina-ocr-v1", "completed_at": "2026-09-24T10:00:00Z"})]),
        ]
        stale_point = {"id": str(uuid4()), "score": 0.9, "payload": {
            "chunk_id": str(uuid4()), "document_id": str(self.document_id),
            "chunk_index": 1, "filename": "test.txt", "content": "stale disabled"}}
        with patch("app.services.retrieval.retrieval.get_vector_store") as client, \
             patch("app.services.retrieval.retrieval._rerank", side_effect=lambda q, c, l: c) as rerank:
            client.return_value.search.return_value = [stale_point, self.point(edited_snap)]
            results = hybrid_search(db, "edited", 5, document_id=str(self.document_id))
        candidates = rerank.call_args.args[1]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["payload"]["content"], "edited text")
        self.assertEqual(results[0]["payload"]["content"], "edited text")
        self.assertEqual(results[0]["payload"]["ocr_provenance"]["provider"], "jina")

    def test_zero_vector_weight_skips_qdrant(self):
        chunk = self.chunk(0, "lexical match")
        db = MagicMock()
        db.execute.side_effect = [
            self.result([(self.document_id, datetime.now(timezone.utc))]),
            self.result([(chunk, "test.txt")]),
            self.result([(self.document_id, None)]),
        ]
        with patch("app.services.retrieval.retrieval.get_vector_store") as client:
            results = hybrid_search(
                db, "lexical", 5, document_id=str(self.document_id),
                vector_weight=0, bm25_weight=1, use_reranker=False,
            )
        client.assert_not_called()
        self.assertEqual(results[0]["payload"]["content"], "lexical match")

    def test_hybrid_search_accepts_an_injected_vector_store(self):
        chunk = self.chunk(0, "injected result")
        db = MagicMock()
        db.execute.side_effect = [
            self.result([(self.document_id, datetime.now(timezone.utc))]),
            self.result([(chunk, "test.txt")]),
            self.result([(self.document_id, None)]),
        ]
        store = MagicMock()
        store.search.return_value = []

        hybrid_search(db, "injected", 5, document_id=str(self.document_id), vector_store=store)

        store.search.assert_called_once()

    def test_unchanged_scope_reuses_cached_corpus_after_version_check(self):
        chunk = self.chunk(0, "cached lexical text")
        version = datetime.now(timezone.utc)
        db = MagicMock()
        # The second call checks the current version but reuses the corpus.
        db.execute.side_effect = [
            self.result([(self.document_id, version)]),
            self.result([(chunk, "test.txt")]),
            self.result([(self.document_id, None)]),
            self.result([(self.document_id, version)]),
            self.result([(self.document_id, None)]),
        ]
        with patch("app.services.retrieval.retrieval.get_vector_store") as client, patch(
            "app.services.retrieval.retrieval._tokens", wraps=retrieval._tokens
        ) as tokens:
            client.return_value.search.return_value = []
            hybrid_search(db, "cached", 5, document_id=str(self.document_id), use_reranker=False)
            hybrid_search(db, "cached", 5, document_id=str(self.document_id), use_reranker=False)

        corpus_tokenizations = [
            call for call in tokens.call_args_list if call.args[0] == "cached lexical text"
        ]
        self.assertEqual(len(corpus_tokenizations), 1)
        self.assertEqual(db.execute.call_count, 5)

    def test_changed_document_version_rebuilds_cached_corpus(self):
        original = self.chunk(0, "old text")
        updated = self.chunk(0, "new text")
        before = datetime(2026, 1, 1, tzinfo=timezone.utc)
        after = datetime(2026, 1, 2, tzinfo=timezone.utc)
        db = MagicMock()
        db.execute.side_effect = [
            self.result([(self.document_id, before)]),
            self.result([(original, "test.txt")]),
            self.result([(self.document_id, after)]),
            self.result([(updated, "test.txt")]),
        ]

        first = retrieval._lexical_corpus(db, [self.document_id])
        second = retrieval._lexical_corpus(db, [self.document_id])

        self.assertEqual(first.chunks[0].content, "old text")
        self.assertEqual(second.chunks[0].content, "new text")
