import uuid
import logging
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import selectinload

from app.core.config import BASE_DIR, DOCUMENT_JOB_HEARTBEAT_SECONDS, DOCUMENT_JOB_LEASE_SECONDS, DOCUMENT_JOB_MAX_ATTEMPTS, DOCUMENT_JOB_RETRY_BASE_SECONDS, DOCUMENT_JOB_RETRY_MAX_SECONDS, WORKER_STALE_THRESHOLD_SECONDS, document_storage_relative, resolve_document_path
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.indexing_outbox import IndexingOutbox
from app.models.processing_job import ProcessingJob
from app.services.document_extractor import ExtractionError, extract_text_with_provenance
from app.services.qdrant import QdrantClient, QdrantError
from app.services.text_chunker import hierarchical_chunks
from app.services.semantic_chunker import semantic_chunks
from app.services.operational_alerts import send_operational_alert
from app.services.operational_metrics import increment, observe
from app.services.notifications import create_notification
from app.services.incremental_index import checksum, incremental_chunks
from app.services.file_storage import atomic_write_text
from app.services.processing_cancellation import ProcessingCancelled, cancellation_scope
from app.core.config import CHUNKING_STRATEGY, SEMANTIC_CHUNK_MIN_SIZE, SEMANTIC_CHUNK_MAX_SIZE, SEMANTIC_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)


class DocumentJobOwnershipLost(ProcessingCancelled):
    pass


def check_document_job_ownership(job_id: uuid.UUID, worker_id: str) -> None:
    with SessionLocal() as db:
        owned = db.scalar(select(ProcessingJob.id).where(
            ProcessingJob.id == job_id,
            ProcessingJob.status == "running",
            ProcessingJob.worker_id == worker_id,
        ))
    if owned is None:
        raise DocumentJobOwnershipLost("Document processing was cancelled or ownership changed")


def _chunking_config() -> str:
    """Return the settings that determine a document's persisted chunks."""
    if CHUNKING_STRATEGY == "semantic":
        return (
            f"semantic:min={SEMANTIC_CHUNK_MIN_SIZE}:max={SEMANTIC_CHUNK_MAX_SIZE}:"
            f"threshold={SEMANTIC_SIMILARITY_THRESHOLD}"
        )
    return "hierarchical"


def _expired_document_job_ids(cutoff: datetime):
    return (
        select(ProcessingJob.id)
        .where(
            ProcessingJob.status == "running",
            (ProcessingJob.locked_at.is_(None)) | (ProcessingJob.locked_at < cutoff),
        )
        .with_for_update(skip_locked=True)
    )


def recover_document_jobs() -> int:
    """Atomically release expired claims without waiting on active heartbeats."""
    # Job heartbeats run independently of OCR; a dead process must not remain
    # marked extracting until a potentially hour-long lease expires.
    stale_seconds = min(DOCUMENT_JOB_LEASE_SECONDS, max(WORKER_STALE_THRESHOLD_SECONDS, 3 * DOCUMENT_JOB_HEARTBEAT_SECONDS))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
    expired = _expired_document_job_ids(cutoff).cte("expired_document_jobs")
    statement = (
        update(ProcessingJob)
        .where(
            ProcessingJob.id.in_(select(expired.c.id)),
            ProcessingJob.status == "running",
            (ProcessingJob.locked_at.is_(None)) | (ProcessingJob.locked_at < cutoff),
        )
        .values(status="queued", stage="queued", progress=0, worker_id=None, locked_at=None)
        .returning(ProcessingJob.id, ProcessingJob.document_id, ProcessingJob.attempts)
    )
    with SessionLocal() as db, db.begin():
        recovered = list(db.execute(statement))
        for job_id, document_id, attempts in recovered:
            exhausted = attempts >= DOCUMENT_JOB_MAX_ATTEMPTS
            message = "Document processing was interrupted; queued for another attempt."
            if exhausted:
                message = "Document processing was interrupted and reached its retry limit."
                db.execute(update(ProcessingJob).where(ProcessingJob.id == job_id).values(
                    status="dead_letter", stage="dead_letter", error=message,
                    error_type="WorkerUnavailable", completed_at=datetime.now(timezone.utc),
                    dead_lettered_at=datetime.now(timezone.utc),
                ))
            db.execute(update(Document).where(Document.id == document_id).values(
                status="failed" if exhausted else "queued",
                processing_stage="dead_letter" if exhausted else "requeued",
                processing_progress=0, processing_error=message,
            ))
        return len(recovered)


def claim_document_job(worker_id: str) -> uuid.UUID | None:
    """Atomically claim the oldest available job across competing workers."""
    with SessionLocal() as db, db.begin():
        now = datetime.now(timezone.utc)
        job = db.scalar(
            select(ProcessingJob)
            .where(
                ProcessingJob.status.in_(["queued", "retrying"]),
                or_(ProcessingJob.next_attempt_at.is_(None), ProcessingJob.next_attempt_at <= now),
            )
            .order_by(
                case((ProcessingJob.status == "queued", 0), else_=1),
                ProcessingJob.created_at,
                ProcessingJob.id,
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        job.started_at = now
        job.worker_id = worker_id
        job.locked_at = now
        job.next_attempt_at = None
        return job.id


def _retryable_document_error(exc: Exception) -> bool:
    if isinstance(exc, QdrantError):
        return exc.status_code is None or exc.status_code in {408, 429} or exc.status_code >= 500
    if isinstance(exc, ExtractionError):
        message = str(exc).lower()
        return "network error" in message or "timed out" in message or bool(re.search(r"jina ocr request failed \(http (?:408|429|5\d\d)\)", message))
    return isinstance(exc, (TimeoutError, ConnectionError))


def _retry_delay(attempts: int) -> int:
    return min(DOCUMENT_JOB_RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)), DOCUMENT_JOB_RETRY_MAX_SECONDS)


def _document_failure_values(exc: Exception, attempts: int, now: datetime) -> dict:
    retrying = _retryable_document_error(exc) and attempts < DOCUMENT_JOB_MAX_ATTEMPTS
    return {
        "status": "retrying" if retrying else "dead_letter",
        "stage": "retry_wait" if retrying else "dead_letter",
        "error": str(exc)[:500],
        "error_type": type(exc).__name__,
        "next_attempt_at": now + timedelta(seconds=_retry_delay(attempts)) if retrying else None,
        "dead_lettered_at": None if retrying else now,
        "completed_at": None if retrying else now,
        "worker_id": None,
        "locked_at": None,
    }


def refresh_document_job_lease(job_id: uuid.UUID, worker_id: str) -> bool:
    """Refresh a lease only while the same worker still owns the running job."""
    with SessionLocal() as db:
        result = db.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.id == job_id,
                ProcessingJob.status == "running",
                ProcessingJob.worker_id == worker_id,
            )
            .values(locked_at=datetime.now(timezone.utc))
        )
        db.commit()
        return result.rowcount == 1


@contextmanager
def maintain_document_job_lease(job_id: uuid.UUID, worker_id: str):
    """Keep the claim alive while blocking extraction and Qdrant calls run."""
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(DOCUMENT_JOB_HEARTBEAT_SECONDS):
            try:
                if not refresh_document_job_lease(job_id, worker_id):
                    logger.error("Document job lease ownership was lost", extra={"job_id": str(job_id), "worker_id": worker_id})
                    return
            except Exception:
                logger.exception("Document job heartbeat failed", extra={"job_id": str(job_id), "worker_id": worker_id})

    thread = threading.Thread(target=heartbeat, name=f"document-heartbeat-{job_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=DOCUMENT_JOB_HEARTBEAT_SECONDS + 1)


def _progress(
    db,
    document: Document,
    job: ProcessingJob,
    worker_id: str,
    value: int,
    stage: str,
    *,
    completed: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    with db.no_autoflush:
        result = db.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.id == job.id,
                ProcessingJob.status == "running",
                ProcessingJob.worker_id == worker_id,
            )
            .values(
                progress=value,
                stage=stage,
                status="completed" if completed else "running",
                completed_at=now if completed else None,
                worker_id=None if completed else worker_id,
                locked_at=None if completed else now,
            )
        )
    if result.rowcount != 1:
        db.rollback()
        raise DocumentJobOwnershipLost(f"Document job {job.id} is no longer owned by {worker_id}")
    document.processing_progress = value
    document.processing_stage = stage
    document.processing_error = None
    document.status = "processing" if value < 100 else "indexed"
    db.commit()


def process_document_job(
    job_id: uuid.UUID,
    worker_id: str,
) -> None:
    with SessionLocal() as db:
        job = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.id == job_id,
                ProcessingJob.status == "running",
                ProcessingJob.worker_id == worker_id,
            )
        )
        if job is None:
            return
        document = db.scalar(select(Document).options(selectinload(Document.chunks), selectinload(Document.document_sets)).where(Document.id == job.document_id))
        if document is None:
            return
        _progress(db, document, job, worker_id, 10, "extracting")
        outbox_payload: dict | None = None
        try:
            settings = document.document_sets[0] if document.document_sets else None
            chunk_size = job.chunk_size or (settings.child_chunk_size if settings else 800)
            overlap = job.chunk_overlap if job.chunk_overlap is not None else (settings.chunk_overlap if settings else 120)
            parent_size = job.parent_chunk_size or (settings.parent_chunk_size if settings else 2400)
            stored_source = document.storage_path or document.extracted_text_path
            if not stored_source:
                raise RuntimeError("Document file is unavailable")
            source_path = resolve_document_path(stored_source)
            extraction_started = time.perf_counter()
            try:
                with cancellation_scope(lambda: check_document_job_ownership(job_id, worker_id)):
                    extraction = extract_text_with_provenance(source_path, document.content_type or "")
            except Exception:
                observe("document_ocr_duration", time.perf_counter() - extraction_started, content_type=document.content_type or "unknown", result="failed")
                raise
            observe("document_ocr_duration", time.perf_counter() - extraction_started, content_type=document.content_type or "unknown", result="success")
            text = extraction.text
            if extraction.ocr_provenance:
                logger.info(
                    "Document OCR completed",
                    extra={"document_id": str(document.id), **extraction.ocr_provenance},
                )
            text_checksum = checksum(text)
            chunking_config = _chunking_config()
            chunking_is_unchanged = (
                document.indexed_child_chunk_size == chunk_size
                and document.indexed_chunk_overlap == overlap
                and document.indexed_parent_chunk_size == parent_size
                and document.indexed_chunking_config == chunking_config
            )
            if document.content_checksum == text_checksum and document.chunks and chunking_is_unchanged:
                document.processing_error = None
                _progress(db, document, job, worker_id, 100, "unchanged", completed=True)
                create_notification(db, user_id=job.requested_by_id, organization_id=job.organization_id, kind="document_processed", severity="success", title="Document is ready", body=f"{document.filename} is already indexed and ready to use.")
                db.commit()
                increment("document_jobs_completed_total", result="unchanged")
                return
            extracted_path = source_path.parent / "extracted.txt"
            # Serialize the filesystem write with deletion. Otherwise a late
            # extraction could recreate a directory after the delete succeeded.
            with db.no_autoflush:
                if db.scalar(select(ProcessingJob.id).where(
                    ProcessingJob.id == job_id,
                    ProcessingJob.status == "running",
                    ProcessingJob.worker_id == worker_id,
                ).with_for_update()) is None:
                    raise DocumentJobOwnershipLost("Document processing was cancelled")
                db.scalar(select(Document.id).where(Document.id == document.id).with_for_update())
            document.ocr_provenance = extraction.ocr_provenance
            atomic_write_text(extracted_path, text)
            document.extracted_text_path = document_storage_relative(extracted_path)
            document.content_checksum = None
            _progress(db, document, job, worker_id, 35, "chunking")
            if CHUNKING_STRATEGY == "semantic":
                # Semantic chunking produces flat chunks; normalize them for the
                # hierarchical storage schema while retaining each chunk as its parent.
                raw_semantic = semantic_chunks(
                    text,
                    min_chunk_size=SEMANTIC_CHUNK_MIN_SIZE,
                    max_chunk_size=SEMANTIC_CHUNK_MAX_SIZE,
                    similarity_threshold=SEMANTIC_SIMILARITY_THRESHOLD,
                )
                contents = [(chunk, index, chunk) for index, chunk in enumerate(raw_semantic)]
            else:
                contents = hierarchical_chunks(text, child_size=chunk_size, child_overlap=overlap, parent_size=parent_size)
            if not contents:
                raise RuntimeError("Document contains no text to index")
            _progress(db, document, job, worker_id, 65, "indexing")
            next_chunks, _, removed_ids = incremental_chunks(
                document, text, chunk_size, overlap, parent_size, generated_chunks=contents
            )
            pending_chunks = [
                {"id": str(chunk.id), "chunk_index": chunk.chunk_index, "content": chunk.content}
                for chunk in next_chunks
            ]
            for chunk in list(document.chunks):
                if str(chunk.id) in removed_ids:
                    db.delete(chunk)
            document.chunks = next_chunks
            document.content_checksum = text_checksum
            document.indexed_child_chunk_size = chunk_size
            document.indexed_chunk_overlap = overlap
            document.indexed_parent_chunk_size = parent_size
            document.indexed_chunking_config = chunking_config
            document.processing_error = None
            # Durable outbox: record intended Qdrant state in the SAME transaction
            outbox_payload = {
                "document_id": str(document.id),
                "filename": document.filename,
                "chunks": pending_chunks,
            }
            db.add(IndexingOutbox(
                document_id=document.id,
                job_id=job_id,
                action="replace_document_chunks",
                payload=outbox_payload,
                status="pending",
            ))
            _progress(db, document, job, worker_id, 100, "ready", completed=True)
            create_notification(db, user_id=job.requested_by_id, organization_id=job.organization_id, kind="document_processed", severity="success", title="Document is ready", body=f"{document.filename} has been indexed and is ready to use.")
            db.commit()
            increment("document_jobs_completed_total", result="indexed")
        except Exception as exc:
            db.rollback()
            if isinstance(exc, ProcessingCancelled):
                logger.warning("Stopped document processing after lease ownership changed", extra={"job_id": str(job_id), "worker_id": worker_id})
                return
            job = db.get(ProcessingJob, job_id)
            document = db.get(Document, job.document_id) if job else None
            if job and document:
                message = str(exc)[:500]
                now = datetime.now(timezone.utc)
                failure_values = _document_failure_values(exc, job.attempts, now)
                retrying = failure_values["status"] == "retrying"
                result = db.execute(
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.id == job_id,
                        ProcessingJob.status == "running",
                        ProcessingJob.worker_id == worker_id,
                    )
                    .values(**failure_values)
                )
                if result.rowcount != 1:
                    db.rollback()
                    return
                document.status = "queued" if retrying else "failed"; document.processing_error = message
                document.processing_stage = "retry_wait" if retrying else "dead_letter"; document.processing_progress = job.progress
                db.commit()
                if not retrying:
                    create_notification(db, user_id=job.requested_by_id, organization_id=job.organization_id, kind="document_failed", severity="error", title="Document processing failed", body=f"{document.filename} could not be processed. Review the document and retry it from Knowledge base.")
                    db.commit()
                failure_stage = "ocr" if isinstance(exc, ExtractionError) else "processing"
                increment("document_processing_failures_total", error_type=type(exc).__name__, stage=failure_stage)
                if not retrying:
                    category = "OCR" if "ocr" in message.lower() else "document processing"
                    send_operational_alert(
                        "document-dead-letter",
                        f"{category.title()} reached its retry limit",
                        f"Document job {job_id} failed after {job.attempts} attempts. Review the document-processing worker logs and retry the job after resolving the cause.",
                    )
            return

        # Transaction committed with outbox entry. Best-effort immediate apply.
        if outbox_payload is not None:
            try:
                with SessionLocal() as apply_db:
                    # Serialize indexing with deletion so a deleted document
                    # cannot be reintroduced into the vector store.
                    if apply_db.scalar(select(Document.id).where(Document.id == document.id).with_for_update()) is None:
                        return
                    qdrant = QdrantClient()
                    qdrant.ensure_collection()
                    qdrant.replace_document_chunks(
                        outbox_payload["document_id"],
                        outbox_payload["filename"],
                        outbox_payload["chunks"],
                    )
                    apply_db.execute(
                        update(IndexingOutbox)
                        .where(
                            IndexingOutbox.document_id == document.id,
                            IndexingOutbox.job_id == job_id,
                            IndexingOutbox.status == "pending",
                        )
                        .values(status="applied")
                    )
                    apply_db.commit()
            except Exception:
                logger.warning(
                    "Immediate Qdrant apply failed; reconciler will retry",
                    extra={"job_id": str(job_id), "document_id": str(document.id)},
                    exc_info=True,
                )
