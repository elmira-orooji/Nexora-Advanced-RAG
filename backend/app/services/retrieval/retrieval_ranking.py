"""Pure ranking rules for retrieval candidates."""

from collections.abc import Callable


def _proximity(query_terms: set[str], tokens: list[str]) -> float:
    positions = [index for index, token in enumerate(tokens) if token in query_terms]
    if len(positions) < 2:
        return 0.0
    return min(len(query_terms) / (positions[-1] - positions[0] + 1), 1.0)


def rerank(
    query: str,
    candidates: list[dict],
    limit: int,
    tokenize: Callable[[str], list[str]],
) -> list[dict]:
    """Score candidates using lexical coverage in addition to hybrid rank."""
    query_tokens = tokenize(query)
    query_terms = set(query_tokens)
    if not query_terms:
        return candidates[:limit]
    normalized_query = " ".join(query_tokens)
    reranked = []
    for candidate in candidates:
        payload = candidate["payload"]
        content_tokens = tokenize(payload.get("content", ""))
        content_terms = set(content_tokens)
        filename_terms = set(tokenize(payload.get("filename", "")))
        coverage = len(query_terms & content_terms) / len(query_terms)
        title_coverage = len(query_terms & filename_terms) / len(query_terms)
        phrase_match = normalized_query in " ".join(content_tokens)
        hybrid_score = float(candidate.get("score", 0.0))
        score = (
            0.50 * hybrid_score
            + 0.25 * coverage
            + 0.10 * _proximity(query_terms, content_tokens)
            + 0.10 * float(phrase_match)
            + 0.05 * title_coverage
        )
        reranked.append({
            **candidate,
            "score": min(score, 1.0),
            "retrieval": {
                **candidate.get("retrieval", {}),
                "reranked": True,
                "hybrid_score": round(hybrid_score, 6),
                "term_coverage": round(coverage, 6),
                "phrase_match": phrase_match,
            },
        })
    reranked.sort(key=lambda item: item["score"], reverse=True)
    return reranked[:limit]
