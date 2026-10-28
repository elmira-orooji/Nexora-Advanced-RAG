import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.organization import Organization
from app.models.processing_job import ProcessingJob
from app.models.user import User
from scripts.prepare_demo import cleanup_guests, seed_samples


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        event.listen(self.engine, "connect", lambda dbapi, _: dbapi.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.scratch = Path(__file__).resolve().parents[1] / ".local" / "test-scratch"
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="demo-seed-", dir=self.scratch)
        self.root = Path(self.temp.name)
        self.storage = patch("scripts.prepare_demo.UPLOAD_DIR", self.root)
        self.relative = patch("app.core.config.UPLOAD_DIR", self.root)
        self.storage.start()
        self.relative.start()

    def tearDown(self):
        self.relative.stop()
        self.storage.stop()
        self.db.close()
        self.engine.dispose()
        self.assertTrue(self.root.resolve().is_relative_to(self.scratch.resolve()))
        self.temp.cleanup()

    def test_samples_are_queued_once_without_password_enabled_custodians(self):
        seed_samples(self.db)
        seed_samples(self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Document)), 2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ProcessingJob)), 2)
        custodian = self.db.scalar(select(User))
        self.assertFalse(custodian.is_active)
        for doc in self.db.scalars(select(Document)):
            self.assertTrue((self.root / doc.storage_path).is_file())
            self.assertEqual(doc.status, "queued")
            self.assertEqual(doc.organization_id, custodian.organization_id)

    def test_cleanup_deletes_only_expired_guests_of_the_dedicated_demo_org(self):
        seed_samples(self.db)
        demo_org = self.db.scalar(select(Organization))
        other_org = Organization(id=uuid4(), slug="private", name="Private")
        self.db.add(other_org)
        self.db.flush()
        old = datetime.now(timezone.utc) - timedelta(days=2)
        expired = User(id=uuid4(), organization_id=demo_org.id, username="expired", password_hash="!", is_demo=True, created_at=old)
        retained = [
            User(id=uuid4(), organization_id=demo_org.id, username="ordinary", password_hash="!", is_demo=False, created_at=old),
            User(id=uuid4(), organization_id=other_org.id, username="other-guest", password_hash="!", is_demo=True, created_at=old),
            User(id=uuid4(), organization_id=demo_org.id, username="active-guest", password_hash="!", is_demo=True),
        ]
        self.db.add_all([expired, *retained])
        self.db.flush()
        conversation_id = uuid4()
        self.db.add(Conversation(id=conversation_id, user_id=expired.id, title="Disposable"))
        self.db.commit()
        self.assertEqual(cleanup_guests(self.db), 1)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Conversation, conversation_id))
        self.assertTrue(all(self.db.get(User, user.id) for user in retained))
