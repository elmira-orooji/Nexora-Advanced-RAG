"""Backfill GraphRAG facts for documents indexed before graph retrieval was enabled."""

import argparse
import logging
import uuid

from sqlalchemy import select

from app.core.config import GRAPH_RAG_ENABLED
from app.db.database import SessionLocal
from app.models.document import Document
from app.services.providers.provider_factory import get_language_model
from app.services.retrieval.graph_indexer import index_document_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", type=uuid.UUID, help="Limit indexing to one organization")
    args = parser.parse_args()
    if not GRAPH_RAG_ENABLED:
        parser.error("Set GRAPH_RAG_ENABLED=true before building the graph index")

    with SessionLocal() as db:
        statement = select(Document.id).where(Document.status == "indexed").order_by(Document.created_at)
        if args.organization_id:
            statement = statement.where(Document.organization_id == args.organization_id)
        document_ids = list(db.scalars(statement))

    model = get_language_model()
    succeeded = 0
    failed = 0
    for document_id in document_ids:
        try:
            with SessionLocal() as db:
                count = index_document_graph(db, document_id, model)
            succeeded += 1
            logger.info("Graph index updated", extra={"document_id": str(document_id), "fact_count": count})
        except Exception:
            failed += 1
            logger.exception("Graph indexing failed", extra={"document_id": str(document_id)})
    logger.info("Graph indexing complete", extra={"succeeded": succeeded, "failed": failed})
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
