from app.services.provider_factory import get_vector_store
from app.services.ports import VectorSearchPort
from app.services.connector_sources.contracts import ConnectorSyncError, SourceSnapshot, CLOUD_CONNECTORS
from app.services.connector_sources.website import _website
from app.services.connector_sources.github import _github
from app.services.connector_sources.google_drive import _google_drive
from app.services.connector_sources.sharepoint import _sharepoint
from app.services.connector_sources.s3 import _s3
import hashlib
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, UPLOAD_DIR, document_storage_relative
from app.db.database import SessionLocal
from app.models.chunk import Chunk
from app.models.connector import Connector, ConnectorItem
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.services.text_chunker import hierarchical_chunks
from app.services.chunk_enrichment import enrich_chunk
from app.services.incremental_index import checksum, incremental_chunks
from app.services.file_storage import atomic_write_text
from app.services.connector_secrets import ConnectorSecretError, get_connector_credentials

def _organization_credentials(organization_id: uuid.UUID, connector_type: str) -> dict[str, str]:
    try:
        return get_connector_credentials(organization_id, connector_type)
    except ConnectorSecretError as exc:
        raise ConnectorSyncError(str(exc)) from exc


# Maximum number of documents to hold in memory before flushing to DB.
# With true streaming fetchers this now bounds BOTH fetch and apply RAM.
STREAM_BATCH_SIZE = 50


@dataclass
class ExternalDocumentState:
    document_id: str
    filename: str
    chunks: list[dict[str, object]]
    directory: Path
    # Snapshot of the document directory stored on disk to avoid holding large
    # binary payloads in RAM during compensation.  ``snapshot_dir`` points to a
    # temporary folder that mirrors the original layout; it is cleaned up when
    # ``cleanup`` is invoked.
    snapshot_dir: Path | None
    existed: bool

    def cleanup(self) -> None:
        if self.snapshot_dir is not None and self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir, ignore_errors=True)
            self.snapshot_dir = None


def _chunk_payload(document: Document) -> list[dict[str, object]]:
    return [
        {"id": str(chunk.id), "chunk_index": chunk.chunk_index, "content": chunk.content}
        for chunk in document.chunks
    ]


def _capture_external_state(document: Document, existed: bool) -> ExternalDocumentState:
    directory = UPLOAD_DIR / str(document.id)
    snapshot_dir: Path | None = None
    if directory.is_dir():
        # Stream the existing files to a temporary directory instead of loading
        # them entirely into RAM.  This keeps compensation memory-safe even when
        # a batch contains very large documents.
        snapshot_dir = Path(tempfile.mkdtemp(prefix="connector_snapshot_"))
        for source_path in directory.rglob("*"):
            if not source_path.is_file():
                continue
            relative = source_path.relative_to(directory)
            destination = snapshot_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source_path.open("rb") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    return ExternalDocumentState(
        document_id=str(document.id),
        filename=document.filename,
        chunks=_chunk_payload(document),
        directory=directory,
        snapshot_dir=snapshot_dir,
        existed=existed,
    )


def _replace_document_vectors(qdrant: VectorSearchPort, document: Document) -> None:
    qdrant.replace_document_chunks(str(document.id), document.filename, _chunk_payload(document))


def _restore_external_states(
    qdrant: VectorSearchPort,
    states: list[ExternalDocumentState],
    original_error: Exception,
) -> None:
    compensation_errors: list[str] = []
    try:
        for state in reversed(states):
            try:
                if state.directory.exists():
                    shutil.rmtree(state.directory)
                if state.snapshot_dir is not None and state.snapshot_dir.exists():
                    # Stream the snapshot back to the document directory so we
                    # never hold an entire file tree in RAM during rollback.
                    state.directory.mkdir(parents=True, exist_ok=True)
                    for snapshot_path in state.snapshot_dir.rglob("*"):
                        if not snapshot_path.is_file():
                            continue
                        relative = snapshot_path.relative_to(state.snapshot_dir)
                        destination = state.directory / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with snapshot_path.open("rb") as src, destination.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
            except Exception as exc:
                compensation_errors.append(f"files for document {state.document_id}: {exc}")
            finally:
                # Always release the temporary snapshot regardless of success.
                state.cleanup()
            try:
                if state.existed:
                    qdrant.replace_document_chunks(state.document_id, state.filename, state.chunks)
                else:
                    qdrant.delete_document(state.document_id)
            except Exception as exc:
                compensation_errors.append(f"vectors for document {state.document_id}: {exc}")
    finally:
        # Belt-and-braces cleanup if the loop aborts unexpectedly.
        for state in states:
            state.cleanup()
    if compensation_errors and hasattr(original_error, "add_note"):
        original_error.add_note("External compensation errors: " + "; ".join(compensation_errors))


def sync_connector(connector_id: UUID) -> dict[str, int]:
    """Synchronise a connector's remote source into the local knowledge base.

    The Fetch phase reads connector metadata from a short-lived session and
    performs all remote I/O without holding any database connection.  The Apply
    phase opens its own session so that the caller's transaction is never
    closed, rolled back, or otherwise interfered with.
    """
    fetchers = {"website": _website, "github": _github, "google_drive": _google_drive, "s3": _s3, "sharepoint": _sharepoint}

    # --- Fetch phase -----------------------------------------------------------
    # Read only the immutable metadata we need to drive the remote fetch, then
    # release the connection immediately.
    with SessionLocal() as meta_db:
        connector = meta_db.get(Connector, connector_id)
        if connector is None:
            raise ConnectorSyncError("Connector no longer exists")
        connector_type = connector.connector_type
        source_url = connector.source_url
        document_set_id = connector.document_set_id
        organization_id = None
        if connector_type in CLOUD_CONNECTORS:
            document_set = meta_db.get(DocumentSet, document_set_id)
            if document_set is None:
                raise ConnectorSyncError("Connector knowledge set no longer exists")
            organization_id = document_set.organization_id

    fetcher = fetchers.get(connector_type)
    if fetcher is None:
        raise ConnectorSyncError("Unsupported connector type")

    if connector_type in CLOUD_CONNECTORS:
        credentials = _organization_credentials(organization_id, connector_type)
        snapshot = fetcher(source_url, credentials)
    else:
        snapshot = fetcher(source_url)

    # --- Apply phase (True Streaming Batch) ------------------------------------
    # Consume the source_iterator one item at a time, accumulating into
    # fixed-size batches.  Only STREAM_BATCH_SIZE documents are ever held in
    # RAM simultaneously — both fetch payloads and apply state are bounded.
    # Each batch gets its own DB session and Qdrant client so memory is
    # released before the next batch starts.  Deletion logic runs only once
    # after the iterator is fully exhausted.
    total_discovered = 0
    created = updated = unchanged = deleted = 0
    removed_directories: list[Path] = []
    batch: list[tuple[str, str, str, str]] = []

    def _apply_batch(items: list[tuple[str, str, str, str]]) -> tuple[int, int, int]:
        """Process one batch inside its own DB session. Returns (created, updated, unchanged)."""
        b_created = b_updated = b_unchanged = 0
        with SessionLocal() as db:
            connector = db.get(Connector, connector_id)
            if connector is None:
                raise ConnectorSyncError("Connector no longer exists")

            # OPTIMIZATION: Only query ConnectorItems whose external_id is in this batch.
            # Previously this loaded ALL ConnectorItems for the connector, causing O(Batches × TotalItems) reads.
            batch_external_ids = [item[0] for item in items]
            existing_query = select(ConnectorItem).where(
                and_(
                    ConnectorItem.connector_id == connector.id,
                    ConnectorItem.external_id.in_(batch_external_ids)
                )
            )
            existing = {item.external_id: item for item in db.scalars(existing_query).all()}

            journal: dict[str, ExternalDocumentState] = {}
            qdrant = get_vector_store(); qdrant.ensure_collection()
            document_set = db.get(DocumentSet, document_set_id)
            if document_set is None:
                raise ConnectorSyncError("Connector knowledge set no longer exists")
            try:
                for external_id, title, text, src_url in items:
                    digest = hashlib.sha256(text.encode()).hexdigest(); item = existing.get(external_id)
                    if item and item.content_hash == digest:
                        document = db.get(Document, item.document_id)
                        if document is not None and not document.storage_path and document.extracted_text_path:
                            document.storage_path = document.extracted_text_path
                        b_unchanged += 1
                        continue
                    document = db.get(Document, item.document_id) if item else Document(organization_id=document_set.organization_id, filename=title, content_type="text/plain", status="chunked", source_type=connector.connector_type, tags=[])
                    if not item: db.add(document); db.flush(); document.document_sets.append(document_set)
                    document_id = str(document.id)
                    if document_id not in journal:
                        journal[document_id] = _capture_external_state(document, existed=item is not None)
                    directory = UPLOAD_DIR / document_id; directory.mkdir(parents=True, exist_ok=True); extracted = directory / "extracted.txt"; atomic_write_text(extracted, text)
                    source_path = document_storage_relative(extracted)
                    document.storage_path = source_path; document.extracted_text_path = source_path; document.filename = title; document.processing_error = None
                    next_chunks, _, removed_ids = incremental_chunks(document, text, document_set.child_chunk_size, document_set.chunk_overlap, document_set.parent_chunk_size)
                    for chunk in list(document.chunks):
                        if str(chunk.id) in removed_ids: db.delete(chunk)
                    document.chunks = next_chunks; document.content_checksum = checksum(text)
                    document.indexed_child_chunk_size = document_set.child_chunk_size
                    document.indexed_chunk_overlap = document_set.chunk_overlap
                    document.indexed_parent_chunk_size = document_set.parent_chunk_size
                    document.indexed_chunking_config = "hierarchical"
                    db.flush(); _replace_document_vectors(qdrant, document); document.status = "indexed"
                    if item: item.content_hash = digest; item.source_url = src_url; item.title = title; b_updated += 1
                    else: db.add(ConnectorItem(connector_id=connector.id, document_id=document.id, external_id=external_id, content_hash=digest, source_url=src_url, title=title)); b_created += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                _restore_external_states(qdrant, list(journal.values()), exc)
                raise
        return b_created, b_updated, b_unchanged

    for source_tuple in snapshot.source_iterator:
        snapshot.observed_ids.add(source_tuple[0])
        batch.append(source_tuple)
        total_discovered += 1
        if len(batch) >= STREAM_BATCH_SIZE:
            c, u, n = _apply_batch(batch)
            created += c; updated += u; unchanged += n
            batch.clear()

    # Flush remaining items that didn't fill a complete batch.
    if batch:
        c, u, n = _apply_batch(batch)
        created += c; updated += u; unchanged += n
        batch.clear()

    # --- Deletion & Summary phase ----------------------------------------------
    # Runs once after all batches.  To avoid loading every ConnectorItem into RAM
    # at once (which defeated streaming for very large connectors), we page through
    # the items in fixed-size chunks and only materialise the small window that is
    # currently being evaluated.  Each page gets its own journal so a failure only
    # needs to restore the documents touched in that window.
    if not snapshot.complete:
        result = {"discovered": total_discovered, "created": created, "updated": updated, "unchanged": unchanged, "deleted": deleted, "deletion_skipped": 1}
        with SessionLocal() as db:
            connector = db.get(Connector, connector_id)
            if connector is None:
                raise ConnectorSyncError("Connector no longer exists")
            connector.last_sync_summary = result
            db.commit()
    else:
        deletion_page_size = STREAM_BATCH_SIZE
        last_external_id: str | None = None
        while True:
            with SessionLocal() as db:
                connector = db.get(Connector, connector_id)
                if connector is None:
                    raise ConnectorSyncError("Connector no longer exists")
                query = select(ConnectorItem).where(ConnectorItem.connector_id == connector.id).order_by(ConnectorItem.external_id).limit(deletion_page_size)
                if last_external_id is not None:
                    query = query.where(ConnectorItem.external_id > last_external_id)
                page_items = list(db.scalars(query).all())
                if not page_items:
                    break
                journal: dict[str, ExternalDocumentState] = {}
                qdrant = get_vector_store(); qdrant.ensure_collection()
                try:
                    for item in page_items:
                        if item.external_id in snapshot.observed_ids:
                            continue
                        document = db.get(Document, item.document_id)
                        if document is not None:
                            other_sets = [value for value in document.document_sets if value.id != document_set_id]
                            if other_sets:
                                document.document_sets = other_sets
                                db.delete(item)
                            else:
                                document_id = str(document.id)
                                if document_id not in journal:
                                    journal[document_id] = _capture_external_state(document, existed=True)
                                qdrant.delete_document(document_id)
                                removed_directories.append(UPLOAD_DIR / document_id)
                                db.delete(document)
                        else:
                            db.delete(item)
                        deleted += 1
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    _restore_external_states(qdrant, list(journal.values()), exc)
                    raise
                last_external_id = page_items[-1].external_id
        with SessionLocal() as db:
            connector = db.get(Connector, connector_id)
            if connector is None:
                raise ConnectorSyncError("Connector no longer exists")
            result = {"discovered": total_discovered, "created": created, "updated": updated, "unchanged": unchanged, "deleted": deleted, "deletion_skipped": 0}
            connector.last_sync_summary = result
            db.commit()
    for document_dir in removed_directories:
        if document_dir.is_dir(): shutil.rmtree(document_dir, ignore_errors=True)
    return result


def ingest_webhook_event(db: Session, connector: Connector, action: str, external_id: str, title: str | None = None, content: str | None = None, source_url: str | None = None) -> str:
    """Apply one webhook event without treating omitted remote items as deleted."""
    if connector.connector_type != "webhook": raise ConnectorSyncError("Connector does not accept webhook events")
    item = db.scalar(select(ConnectorItem).where(ConnectorItem.connector_id == connector.id, ConnectorItem.external_id == external_id))
    qdrant = get_vector_store(); qdrant.ensure_collection()
    if action == "delete":
        if item is None: return "not_found"
        journal: list[ExternalDocumentState] = []
        directory = None
        try:
            document = db.get(Document, item.document_id)
            if document is not None:
                other_sets = [value for value in document.document_sets if value.id != connector.document_set_id]
                if other_sets: document.document_sets = other_sets; db.delete(item)
                else:
                    journal.append(_capture_external_state(document, existed=True))
                    qdrant.delete_document(str(document.id)); directory = UPLOAD_DIR / str(document.id); db.delete(document)
            else: db.delete(item)
            db.commit()
        except Exception as exc:
            db.rollback(); _restore_external_states(qdrant, journal, exc); raise
        if directory is not None: shutil.rmtree(directory, ignore_errors=True)
        return "deleted"
    text = (content or "").strip(); digest = hashlib.sha256(text.encode()).hexdigest()
    if item and item.content_hash == digest: return "unchanged"
    document_set = db.get(DocumentSet, connector.document_set_id)
    if document_set is None: raise ConnectorSyncError("Knowledge base no longer exists")
    created = item is None
    document = db.get(Document, item.document_id) if item else None
    journal: list[ExternalDocumentState] = []
    try:
        if document is None:
            document = Document(organization_id=document_set.organization_id, filename=(title or external_id)[:255], content_type="text/plain", status="chunked", source_type="webhook", tags=[])
            db.add(document); db.flush(); document.document_sets.append(document_set)
        journal.append(_capture_external_state(document, existed=not created))
        directory = UPLOAD_DIR / str(document.id); directory.mkdir(parents=True, exist_ok=True); extracted = directory / "extracted.txt"; atomic_write_text(extracted, text)
        source_path = document_storage_relative(extracted)
        document.storage_path = source_path; document.extracted_text_path = source_path; document.filename = (title or external_id)[:255]; document.processing_error = None
        next_chunks, _, removed_ids = incremental_chunks(document, text, document_set.child_chunk_size, document_set.chunk_overlap, document_set.parent_chunk_size)
        for chunk in list(document.chunks):
            if str(chunk.id) in removed_ids: db.delete(chunk)
        document.chunks = next_chunks; document.content_checksum = checksum(text)
        document.indexed_child_chunk_size = document_set.child_chunk_size
        document.indexed_chunk_overlap = document_set.chunk_overlap
        document.indexed_parent_chunk_size = document_set.parent_chunk_size
        document.indexed_chunking_config = "hierarchical"
        db.flush(); _replace_document_vectors(qdrant, document); document.status = "indexed"
        resolved_source = source_url or f"webhook:{external_id}"
        if item: item.content_hash = digest; item.source_url = resolved_source; item.title = document.filename
        else: db.add(ConnectorItem(connector_id=connector.id, document_id=document.id, external_id=external_id, content_hash=digest, source_url=resolved_source, title=document.filename))
        connector.status = "ready"; connector.last_synced_at = datetime.now(timezone.utc); connector.last_error = None
        connector.last_sync_summary = {"discovered": 1, "created": int(created), "updated": int(not created), "unchanged": 0, "deleted": 0}
        db.commit()
    except Exception as exc:
        db.rollback(); _restore_external_states(qdrant, journal, exc); raise
    return "created" if created else "updated"
