import hashlib
import uuid

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunk_enrichment import enrich_chunk
from app.services.ports import VectorSearchPort
from app.services.text_chunker import hierarchical_chunks

GeneratedChunk = tuple[str, int, str]


def checksum(value: str | bytes) -> str:
    data = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def incremental_chunks(
    document: Document,
    text: str,
    child_size: int,
    overlap: int,
    parent_size: int,
    generated_chunks: list[GeneratedChunk] | None = None,
) -> tuple[list[Chunk], list[str], list[str]]:
    """Merge supplied chunks into a document while preserving unchanged records.

    Callers that use an alternative chunking strategy provide its normalized
    ``(content, parent_index, parent_content)`` tuples. The hierarchical
    strategy remains the default for connector and legacy callers.
    """
    generated = generated_chunks if generated_chunks is not None else hierarchical_chunks(
        text, child_size=child_size, child_overlap=overlap, parent_size=parent_size
    )
    existing = {(chunk.chunk_index, chunk.content_checksum or checksum(chunk.content)): chunk for chunk in document.chunks}
    retained_ids: set[str] = set(); changed: list[Chunk] = []; output: list[Chunk] = []
    for index, (content, parent_index, parent_content) in enumerate(generated):
        digest = checksum(content); chunk = existing.get((index, digest))
        if chunk is None:
            keywords, questions = enrich_chunk(content)
            chunk = Chunk(id=uuid.uuid4(), chunk_index=index, content=content, parent_index=parent_index, parent_content=parent_content, content_checksum=digest, keywords=keywords, suggested_questions=questions)
            changed.append(chunk)
        else:
            chunk.parent_index = parent_index; chunk.parent_content = parent_content; chunk.content_checksum = digest
        output.append(chunk); retained_ids.add(str(chunk.id))
    removed = [str(chunk.id) for chunk in document.chunks if str(chunk.id) not in retained_ids]
    return output, [str(chunk.id) for chunk in changed], removed


def sync_incremental(client: VectorSearchPort, document: Document, changed_ids: list[str], removed_ids: list[str]) -> None:
    changed = [chunk for chunk in document.chunks if str(chunk.id) in set(changed_ids)]
    client.delete_points(removed_ids)
    client.upsert_chunks(str(document.id), document.filename, [{"id": str(chunk.id), "chunk_index": chunk.chunk_index, "content": chunk.content} for chunk in changed])
