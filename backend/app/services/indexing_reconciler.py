"""Durable reconciliation for indexing outbox entries.

Periodically picks up pending IndexingOutbox rows and applies them to Qdrant.
This guarantees eventual consistency when the primary document worker crashes
after committing SQL but before (or during) the external Qdrant mutation.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.database import SessionLocal
from app.models.indexing_outbox import IndexingOutbox
from app.models.document import Document
from app.services.qdrant import QdrantClient

logger = logging.getLogger(__name__)

MAX_RECONCILE_ATTEMPTS = 10
BATCH_SIZE = 50


def reconcile_indexing_outbox() -> int:
    """Apply pending outbox entries to Qdrant. Returns number of entries processed."""
    applied = 0
    with SessionLocal() as db:
        entries = list(db.scalars(
            select(IndexingOutbox)
            .where(IndexingOutbox.status == "pending")
            .order_by(IndexingOutbox.created_at)
            .limit(BATCH_SIZE)
        ))
        if not entries:
            return 0

        qdrant = QdrantClient()
        qdrant.ensure_collection()

        for entry in entries:
            try:
                payload = entry.payload
                action = entry.action
                if action == "replace_document_chunks":
                    # Share the document lock with deletion and immediate apply.
                    # A stale outbox snapshot must not recreate deleted vectors.
                    if db.scalar(select(Document.id).where(Document.id == entry.document_id).with_for_update()) is None:
                        db.rollback()
                        continue
                    qdrant.replace_document_chunks(
                        payload["document_id"],
                        payload["filename"],
                        payload["chunks"],
                    )
                elif action == "delete_document":
                    qdrant.delete_document(payload["document_id"])
                else:
                    logger.error("Unknown outbox action", extra={"outbox_id": str(entry.id), "action": action})
                    entry.status = "failed"
                    entry.last_error = f"Unknown action: {action}"
                    db.commit()
                    continue

                entry.status = "applied"
                entry.last_error = None
                db.commit()
                applied += 1
                logger.info(
                    "Reconciled indexing outbox entry",
                    extra={"outbox_id": str(entry.id), "document_id": str(entry.document_id), "action": action},
                )
            except Exception as exc:
                db.rollback()
                entry_attempts = (entry.attempts or 0) + 1
                error_msg = str(exc)[:1000]
                if entry_attempts >= MAX_RECONCILE_ATTEMPTS:
                    new_status = "failed"
                    logger.error(
                        "Indexing outbox entry exceeded max attempts",
                        extra={"outbox_id": str(entry.id), "document_id": str(entry.document_id), "attempts": entry_attempts},
                        exc_info=True,
                    )
                else:
                    new_status = "pending"
                    logger.warning(
                        "Indexing outbox reconciliation failed; will retry",
                        extra={"outbox_id": str(entry.id), "document_id": str(entry.document_id), "attempt": entry_attempts},
                        exc_info=True,
                    )
                with SessionLocal() as err_db:
                    err_db.execute(
                        update(IndexingOutbox)
                        .where(IndexingOutbox.id == entry.id)
                        .values(status=new_status, attempts=entry_attempts, last_error=error_msg, updated_at=datetime.now(timezone.utc))
                    )
                    err_db.commit()
    return applied
