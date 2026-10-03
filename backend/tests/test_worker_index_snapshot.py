from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.models.notification import Notification
from app.repositories.document_repository import DocumentRepository
from app.services import document_jobs
from app.services.document_extractor import ExtractionResult


def test_worker_applies_newer_edit_and_only_notifies_after_apply():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        doc_id, job_id, user_id = uuid4(), uuid4(), uuid4()
        with sessions() as db:
            db.add(Document(id=doc_id, organization_id=uuid4(), filename="test.txt", storage_path="test.txt"))
            db.add(ProcessingJob(id=job_id, organization_id=uuid4(), document_id=doc_id, requested_by_id=user_id))
            db.commit()
        original = DocumentRepository.get_document
        def concurrent_edit(repository, *args, **kwargs):
            with sessions() as db:
                doc = db.get(Document, doc_id)
                doc.chunks[0].content = "newer edit"
                db.commit()
                assert db.scalar(select(Notification.id)) is None
            return original(repository, *args, **kwargs)
        generated = [("worker snapshot", 0, "parent")]
        with patch.object(document_jobs, "BASE_DIR", Path.cwd()), patch.object(document_jobs, "SessionLocal", sessions), patch.object(document_jobs, "extract_text_with_provenance", return_value=ExtractionResult("text", None)), patch("app.services.incremental_index.hierarchical_chunks", return_value=generated), patch("app.services.incremental_index.enrich_chunk", return_value=([], [])), patch("pathlib.Path.write_text"), patch.object(document_jobs, "get_vector_store") as factory, patch.object(DocumentRepository, "get_document", concurrent_edit):
            assert document_jobs.claim_document_job("worker") == job_id
            document_jobs.process_document_job(job_id, "worker")
        chunks = factory.return_value.replace_document_chunks.call_args.args[2]
        assert [chunk["content"] for chunk in chunks] == ["newer edit"]
        with sessions() as db:
            assert db.get(Document, doc_id).status == "indexed"
            assert db.scalar(select(Notification.kind)) == "document_processed"
    finally:
        engine.dispose()
