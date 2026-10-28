"""Idempotent trusted sample seeding and scoped guest-data maintenance."""

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.core.config import UPLOAD_DIR, document_storage_relative
from app.core.demo import DEMO_ENABLED, DEMO_ORGANIZATION_SLUG, DEMO_SET_NAME
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.document_set import DocumentSet
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.services.storage.file_storage import atomic_write_text


def seed_samples(db) -> None:
    organization = db.scalar(select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG))
    if organization is None:
        organization = Organization(id=uuid4(), slug=DEMO_ORGANIZATION_SLUG, name="Nexora live demo")
        db.add(organization)
        db.flush()
    sample_set = db.scalar(select(DocumentSet).where(DocumentSet.organization_id == organization.id, DocumentSet.name == DEMO_SET_NAME))
    if sample_set is None:
        owner = User(id=uuid4(), organization_id=organization.id, username="sample-custodian", role="admin", is_active=False, password_hash="!password-login-disabled", is_demo=False)
        db.add(owner)
        db.flush()
        sample_set = DocumentSet(id=uuid4(), organization_id=organization.id, name=DEMO_SET_NAME, description="Public English and Persian sample documents for cited answers.", created_by_id=owner.id)
        db.add(sample_set)
        db.flush()
    existing = {doc.filename for doc in sample_set.documents}
    for language in ("en", "fa"):
        filename = f"nexora-handbook-{language}.txt"
        if filename in existing:
            continue
        text = (Path(__file__).resolve().parents[1] / "demo" / filename).read_text(encoding="utf-8")
        document_id = uuid4()
        source = UPLOAD_DIR / str(document_id) / "original.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(source, text)
        document = Document(id=document_id, organization_id=organization.id, filename=filename, content_type="text/plain", language=language, source_type="demo", storage_path=document_storage_relative(source), status="queued", processing_stage="queued", tags=["public-demo"])
        document.document_sets.append(sample_set)
        db.add(document)
        db.flush()
        db.add(ProcessingJob(organization_id=organization.id, requested_by_id=sample_set.created_by_id, document_id=document.id, chunk_size=800, chunk_overlap=120, parent_chunk_size=2400))
    db.commit()


def cleanup_guests(db) -> int:
    organization_id = db.scalar(select(Organization.id).where(Organization.slug == DEMO_ORGANIZATION_SLUG))
    if organization_id is None:
        return 0
    result = db.execute(delete(User).where(User.organization_id == organization_id, User.is_demo.is_(True), User.created_at < datetime.now(timezone.utc) - timedelta(hours=24)))
    db.commit()
    return result.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true", help="Delete only demo guests older than 24 hours and their cascading records")
    parser.add_argument("--loop", action="store_true", help="Repeat guest cleanup every hour")
    args = parser.parse_args()
    if not DEMO_ENABLED:
        raise SystemExit("Set DEMO_ENABLED=true on a dedicated demo installation first.")
    if args.loop and not args.cleanup:
        parser.error("--loop requires --cleanup")
    while True:
        with SessionLocal() as db:
            if args.cleanup:
                print(f"Removed {cleanup_guests(db)} expired demo guests", flush=True)
            else:
                seed_samples(db)
                print("Sample documents queued; wait for indexing before enabling guest traffic.", flush=True)
        if not args.loop:
            break
        time.sleep(3600)


if __name__ == "__main__":
    main()
