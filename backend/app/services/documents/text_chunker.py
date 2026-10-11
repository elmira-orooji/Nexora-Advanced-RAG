import re


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size")

    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        maximum_end = min(start + chunk_size, len(normalized))
        end = maximum_end

        if maximum_end < len(normalized):
            minimum_break = start + chunk_size // 2
            for separator in ("\n\n", "\n", ". ", " "):
                boundary = normalized.rfind(separator, minimum_break, maximum_end)
                if boundary != -1:
                    end = boundary + len(separator)
                    break

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)

    return chunks


def hierarchical_chunks(text: str, child_size: int = 800, child_overlap: int = 120, parent_size: int | None = None) -> list[tuple[str, int, str]]:
    """Returns (child text, parent index, parent text) for precise retrieval and broad context."""
    parent_size = parent_size or max(child_size * 3, 1800)
    parents = chunk_text(text, parent_size, 0)
    result: list[tuple[str, int, str]] = []
    for parent_index, parent in enumerate(parents):
        children = chunk_text(parent, child_size, min(child_overlap, child_size - 1))
        result.extend((child, parent_index, parent) for child in children)
    return result
