"""Semantic chunking based on sentence embedding similarity.

This module provides a chunking strategy that splits text at points where
the semantic similarity between consecutive sentences drops significantly,
ensuring each chunk contains topically coherent content.
"""
import re
from typing import Optional

# Lazy-loaded to avoid heavy import cost when not used
_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use the same model family as Qdrant for consistency if possible,
            # but all-MiniLM-L6-v2 is lightweight and effective for segmentation.
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for semantic chunking. "
                "Install it with: pip install sentence-transformers"
            ) from exc
    return _model


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics supporting Persian/English."""
    # Simple sentence splitter that handles .!? and Persian punctuation
    pattern = r'(?<=[.!?؟۔])\s+|\n\s*\n'
    raw_parts = re.split(pattern, text.strip())
    return [part.strip() for part in raw_parts if part.strip()]


def semantic_chunks(
    text: str,
    min_chunk_size: int = 200,
    max_chunk_size: int = 1500,
    similarity_threshold: float = 0.45,
) -> list[str]:
    """Split text into semantically coherent chunks.

    Args:
        text: Input document text.
        min_chunk_size: Minimum characters per chunk (avoid tiny fragments).
        max_chunk_size: Hard limit to prevent oversized chunks.
        similarity_threshold: Cosine similarity cutoff. Splits occur when
                              similarity between adjacent sentences falls below this.

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    model = _load_model()
    embeddings = model.encode(sentences, normalize_embeddings=True, show_progress_bar=False)

    chunks: list[str] = []
    current_chunk_sentences: list[str] = [sentences[0]]
    current_length = len(sentences[0])

    for i in range(1, len(sentences)):
        # Calculate cosine similarity between current sentence and previous
        # Since embeddings are normalized, dot product == cosine similarity
        similarity = float(sum(a * b for a, b in zip(embeddings[i - 1], embeddings[i])))

        next_sentence = sentences[i]
        next_length = current_length + len(next_sentence) + 1  # +1 for space

        should_split = (
            similarity < similarity_threshold
            or next_length > max_chunk_size
        )

        if should_split and current_length >= min_chunk_size:
            chunks.append(" ".join(current_chunk_sentences))
            current_chunk_sentences = [next_sentence]
            current_length = len(next_sentence)
        else:
            current_chunk_sentences.append(next_sentence)
            current_length = next_length

    # Flush remaining
    if current_chunk_sentences:
        final = " ".join(current_chunk_sentences)
        if final.strip():
            chunks.append(final)

    return chunks
