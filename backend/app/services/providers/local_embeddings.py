"""Lazy, CPU-bound embeddings for self-hosted Qdrant installations."""

from functools import lru_cache
from threading import Lock

_lock = Lock()


@lru_cache(maxsize=1)
def _model(name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name, device="cpu", trust_remote_code=False)


def embed_texts(model: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    # Serialize initialization and encoding per process to bound simultaneous
    # model allocations. Qdrant adapters already pass batches of at most 32.
    with _lock:
        return _model(model).encode(texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).tolist()
