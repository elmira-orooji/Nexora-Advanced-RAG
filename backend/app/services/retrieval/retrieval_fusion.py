"""Reciprocal-rank fusion for vector and lexical retrieval results."""

from collections.abc import Iterable


def fuse_results(
    vector_results: Iterable[dict],
    lexical_results: Iterable[dict],
    active_chunks: dict[str, object],
    vector_weight: float,
    bm25_weight: float,
    rrf_k: int,
) -> list[dict]:
    """Combine ranked lists while replacing stale vector payloads with DB data."""
    fused: dict[str, dict] = {}
    for source, source_name in ((vector_results, "vector"), (lexical_results, "bm25")):
        for rank, result in enumerate(source, 1):
            chunk_id = str(result.get("payload", {}).get("chunk_id") or result.get("id"))
            chunk = active_chunks.get(chunk_id)
            if chunk is None:
                continue
            result = {
                **result,
                "payload": {
                    "chunk_id": chunk_id,
                    "document_id": str(chunk.document_id),
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                },
            }
            item = fused.setdefault(chunk_id, {
                "point": result,
                "score": 0.0,
                "vector_rank": None,
                "lexical_rank": None,
            })
            item["score"] += (vector_weight if source_name == "vector" else bm25_weight) / (rrf_k + rank)
            if source_name == "vector":
                item["vector_rank"] = rank
                item["point"] = result
            else:
                item["lexical_rank"] = rank
                if item["vector_rank"] is None:
                    item["point"] = result

    maximum = (vector_weight + bm25_weight) / (rrf_k + 1)
    return [
        {
            **item["point"],
            "score": min(item["score"] / maximum, 1.0),
            "retrieval": {
                "method": "hybrid",
                "vector_rank": item["vector_rank"],
                "bm25_rank": item["lexical_rank"],
            },
        }
        for item in sorted(fused.values(), key=lambda item: item["score"], reverse=True)
    ]
