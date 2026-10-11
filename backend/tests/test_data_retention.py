import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth_session import AuthSession
from app.models.chat_share import ChatShare
from app.models.llm_usage import LLMUsage
from app.models.notification import Notification
from app.services.operations import data_retention


class DataRetentionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        for model in (AuthSession, ChatShare, Notification, LLMUsage):
            model.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.enterContext(patch.object(data_retention, "SessionLocal", self.sessions))

    def test_purge_removes_only_expired_operational_records(self):
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        user_id = uuid4()
        old = now - timedelta(days=100)
        recent = now - timedelta(days=1)
        with self.sessions() as db:
            old_session = AuthSession(id=uuid4(), user_id=user_id, expires_at=old)
            recent_session = AuthSession(id=uuid4(), user_id=user_id, expires_at=recent)
            old_share = ChatShare(id=uuid4(), owner_id=user_id, title="old", visibility="link", token_hash="a" * 64, messages=[], expires_at=old)
            recent_share = ChatShare(id=uuid4(), owner_id=user_id, title="recent", visibility="link", token_hash="b" * 64, messages=[], expires_at=recent)
            old_notification = Notification(id=uuid4(), user_id=user_id, organization_id=uuid4(), kind="document", severity="success", title="old", body="old", read_at=old)
            unread_notification = Notification(id=uuid4(), user_id=user_id, organization_id=uuid4(), kind="document", severity="success", title="unread", body="unread")
            old_usage = LLMUsage(id=uuid4(), user_id=user_id, operation="chat", model="test", latency_ms=1, prompt_tokens=1, completion_tokens=1, total_tokens=2, estimated_cost_usd=0, created_at=old)
            recent_usage = LLMUsage(id=uuid4(), user_id=user_id, operation="chat", model="test", latency_ms=1, prompt_tokens=1, completion_tokens=1, total_tokens=2, estimated_cost_usd=0, created_at=recent)
            old_session_id, recent_session_id = old_session.id, recent_session.id
            old_share_id, recent_share_id = old_share.id, recent_share.id
            old_notification_id, unread_notification_id = old_notification.id, unread_notification.id
            old_usage_id, recent_usage_id = old_usage.id, recent_usage.id
            db.add_all([old_session, recent_session, old_share, recent_share, old_notification, unread_notification, old_usage, recent_usage])
            db.commit()

        result = data_retention.purge_expired_operational_data(
            now=now,
            session_days=30,
            chat_share_days=30,
            notification_days=30,
            llm_usage_days=30,
        )

        self.assertEqual(result.as_dict(), {"sessions": 1, "chat_shares": 1, "notifications": 1, "llm_usage": 1, "total": 4})
        with self.sessions() as db:
            self.assertIsNone(db.get(AuthSession, old_session_id))
            self.assertIsNotNone(db.get(AuthSession, recent_session_id))
            self.assertIsNone(db.get(ChatShare, old_share_id))
            self.assertIsNotNone(db.get(ChatShare, recent_share_id))
            self.assertIsNone(db.get(Notification, old_notification_id))
            self.assertIsNotNone(db.get(Notification, unread_notification_id))
            self.assertIsNone(db.get(LLMUsage, old_usage_id))
            self.assertIsNotNone(db.get(LLMUsage, recent_usage_id))

    def test_purge_rolls_back_when_a_delete_fails(self):
        session = self.sessions()
        session.close()
        with patch.object(data_retention, "SessionLocal", return_value=session), patch.object(session, "execute", side_effect=RuntimeError("database unavailable")), patch.object(session, "rollback") as rollback:
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                data_retention.purge_expired_operational_data()
        rollback.assert_called_once()
