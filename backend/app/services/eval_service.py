"""Lightweight RAG evaluation pipeline using LLM-as-Judge via OpenRouter."""

from __future__ import annotations
from app.services.provider_factory import get_language_model

import json
import re
import uuid
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_set import DocumentSet
from app.models.evaluation_case import EvaluationCase
from app.services.openrouter import OpenRouterError
from app.services.ports import LanguageModelPort
from app.services.retrieval import hybrid_search


@dataclass
class EvalMetricResult:
    name: str
    score: float
    reason: str = ""


@dataclass
class EvalCaseResult:
    case_id: uuid.UUID
    question: str
    generated_answer: str
    contexts: list[dict[str, Any]]
    metrics: list[EvalMetricResult] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0

    @property
    def overall_score(self) -> float:
        if not self.metrics:
            return 0.0
        return sum(m.score for m in self.metrics) / len(self.metrics)


def _keyword_score(answer: str, keywords: list[str]) -> EvalMetricResult:
    if not keywords:
        return EvalMetricResult(name="keyword_score", score=1.0, reason="No keywords defined")
    normalized = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in normalized)
    ratio = hits / len(keywords)
    return EvalMetricResult(name="keyword_score", score=ratio, reason=f"{hits}/{len(keywords)} keywords found")


def _context_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> EvalMetricResult:
    if not relevant_ids:
        return EvalMetricResult(name="context_precision", score=1.0, reason="No relevant chunks defined")
    if not retrieved_ids:
        return EvalMetricResult(name="context_precision", score=0.0, reason="No chunks retrieved")
    relevant_set = set(relevant_ids)
    hits = 0
    precision_sum = 0.0
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_set:
            hits += 1
            precision_sum += hits / rank
    if hits == 0:
        return EvalMetricResult(name="context_precision", score=0.0, reason="No relevant chunks retrieved")
    score = precision_sum / min(len(relevant_set), len(retrieved_ids))
    return EvalMetricResult(name="context_precision", score=min(score, 1.0), reason=f"{hits}/{len(relevant_set)} relevant in top-{len(retrieved_ids)}")


_JUDGE_SYSTEM = (
    "You are an impartial evaluator. Respond with valid JSON only, no markdown. "
    'Schema: {"score": <float 0-1>, "reason": <short explanation>}. Be strict but fair.'
)

_FAITHFULNESS_PROMPT = (
    "Evaluate FAITHFULNESS of this RAG answer.\n\n"
    "Question: {question}\n\nRetrieved Contexts:\n{contexts}\n\n"
    "Generated Answer:\n{answer}\n\n"
    "Is every factual claim in the answer directly supported by the retrieved contexts?\n"
    "Score 1.0 if fully grounded, 0.0 if completely hallucinated."
)

_RELEVANCY_PROMPT = (
    "Evaluate ANSWER RELEVANCY.\n\nQuestion: {question}\n\n"
    "Generated Answer:\n{answer}\n\n"
    "Does the answer directly and completely address what was asked?\n"
    "Score 1.0 if perfectly relevant, 0.0 if completely off-topic."
)


def _parse_judge_response(raw: str) -> tuple[float, str]:
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        score = float(data.get("score", 0.0))
        reason = str(data.get("reason", ""))
        return max(0.0, min(1.0, score)), reason
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.0, f"Failed to parse judge response: {raw[:200]}"


def _llm_judge(client: LanguageModelPort, prompt: str) -> tuple[float, str]:
    try:
        raw = client.complete(prompt, system_prompt=_JUDGE_SYSTEM, temperature=0.0, max_tokens=300)
        return _parse_judge_response(raw)
    except (OpenRouterError, KeyError, IndexError, TypeError) as exc:
        return 0.0, f"Judge call failed: {exc}"


def run_evaluation(
    db: Session,
    document_set_id: uuid.UUID,
    case_ids: list[uuid.UUID] | None = None,
    model: str | None = None,
    limit: int = 50,
) -> list[EvalCaseResult]:
    query = select(EvaluationCase).where(EvaluationCase.document_set_id == document_set_id)
    if case_ids:
        query = query.where(EvaluationCase.id.in_(case_ids))
    cases = db.scalars(query.order_by(EvaluationCase.created_at).limit(limit)).all()
    if not cases:
        return []

    doc_set = db.scalar(select(DocumentSet).where(DocumentSet.id == document_set_id))
    if doc_set is None:
        return [EvalCaseResult(case_id=c.id, question=c.question, generated_answer="",
                               contexts=[], error="Document set not found") for c in cases]

    document_ids = [str(d.id) for d in doc_set.documents] if doc_set.documents else []
    client = get_language_model(model=model)
    results: list[EvalCaseResult] = []

    for case in cases:
        started = perf_counter()
        try:
            contexts: list[dict[str, Any]] = []
            retrieved_ids: list[str] = []
            if document_ids:
                points = hybrid_search(db, query=case.question, limit=8,
                                       document_ids=document_ids, use_reranker=True)
                contexts = [{"content": p["payload"]["content"]} for p in points]
                retrieved_ids = [str(p["payload"].get("chunk_id", p.get("id", ""))) for p in points]

            answer = client.answer(case.question, contexts)
            metrics: list[EvalMetricResult] = []
            metrics.append(_keyword_score(answer, case.expected_keywords or []))
            metrics.append(_context_precision(retrieved_ids, case.relevant_chunk_ids or []))

            if contexts:
                ctx_text = "\n---\n".join(c["content"][:1500] for c in contexts[:5])
                f_score, f_reason = _llm_judge(client, _FAITHFULNESS_PROMPT.format(
                    question=case.question, contexts=ctx_text, answer=answer))
                metrics.append(EvalMetricResult(name="faithfulness", score=f_score, reason=f_reason))

            r_score, r_reason = _llm_judge(client, _RELEVANCY_PROMPT.format(
                question=case.question, answer=answer))
            metrics.append(EvalMetricResult(name="answer_relevancy", score=r_score, reason=r_reason))

            elapsed = round((perf_counter() - started) * 1000, 1)
            results.append(EvalCaseResult(case_id=case.id, question=case.question,
                                          generated_answer=answer, contexts=contexts,
                                          metrics=metrics, elapsed_ms=elapsed))
        except Exception as exc:
            elapsed = round((perf_counter() - started) * 1000, 1)
            results.append(EvalCaseResult(case_id=case.id, question=case.question,
                                          generated_answer="", contexts=[],
                                          error=str(exc), elapsed_ms=elapsed))
    return results
