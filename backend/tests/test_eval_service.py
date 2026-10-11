import unittest
from uuid import uuid4

from app.services.application.eval_service import (
    EvalMetricResult,
    _context_precision,
    _keyword_score,
    _parse_judge_response,
)


class KeywordScoreTests(unittest.TestCase):
    def test_all_keywords_found(self):
        result = _keyword_score("The cat sat on the mat", ["cat", "mat"])
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.name, "keyword_score")

    def test_partial_match(self):
        result = _keyword_score("The cat sat", ["cat", "mat", "dog"])
        self.assertAlmostEqual(result.score, 1 / 3)

    def test_case_insensitive(self):
        result = _keyword_score("Python is GREAT", ["python", "great"])
        self.assertEqual(result.score, 1.0)

    def test_empty_keywords_returns_perfect(self):
        result = _keyword_score("anything", [])
        self.assertEqual(result.score, 1.0)

    def test_no_match(self):
        result = _keyword_score("hello world", ["foo", "bar"])
        self.assertEqual(result.score, 0.0)


class ContextPrecisionTests(unittest.TestCase):
    def test_perfect_ordering(self):
        relevant = ["a", "b"]
        retrieved = ["a", "b", "c", "d"]
        result = _context_precision(retrieved, relevant)
        # rank1: hit -> 1/1=1.0, rank2: hit -> 2/2=1.0 => avg=1.0
        self.assertAlmostEqual(result.score, 1.0)

    def test_relevant_at_end(self):
        relevant = ["x"]
        retrieved = ["a", "b", "c", "x"]
        result = _context_precision(retrieved, relevant)
        # rank4: hit -> 1/4=0.25
        self.assertAlmostEqual(result.score, 0.25)

    def test_no_relevant_retrieved(self):
        result = _context_precision(["a", "b"], ["x", "y"])
        self.assertEqual(result.score, 0.0)

    def test_empty_relevant_returns_perfect(self):
        result = _context_precision(["a"], [])
        self.assertEqual(result.score, 1.0)

    def test_empty_retrieved_returns_zero(self):
        result = _context_precision([], ["a"])
        self.assertEqual(result.score, 0.0)


class ParseJudgeResponseTests(unittest.TestCase):
    def test_valid_json(self):
        score, reason = _parse_judge_response('{"score": 0.85, "reason": "Good answer"}')
        self.assertAlmostEqual(score, 0.85)
        self.assertEqual(reason, "Good answer")

    def test_json_with_markdown_fence(self):
        raw = '```json\n{"score": 0.9, "reason": "Excellent"}\n```'
        score, reason = _parse_judge_response(raw)
        self.assertAlmostEqual(score, 0.9)

    def test_invalid_json_returns_zero(self):
        score, reason = _parse_judge_response("not json at all")
        self.assertEqual(score, 0.0)
        self.assertIn("Failed to parse", reason)

    def test_score_clamped_to_0_1(self):
        score, _ = _parse_judge_response('{"score": 1.5, "reason": "overflow"}')
        self.assertEqual(score, 1.0)
        score2, _ = _parse_judge_response('{"score": -0.3, "reason": "underflow"}')
        self.assertEqual(score2, 0.0)
