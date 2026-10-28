import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException, Response
from redis import RedisError
from starlette.requests import Request

from app.core.demo import enforce_demo_access, reserve_limits
from app.core.rate_limit import _get_client_ip
from app.services.application.demo_service import create_demo_guest
from app.api.routes.auth import demo_login


def request(path, method="GET"):
    return Request({"type": "http", "method": method, "path": path, "query_string": b"", "headers": [], "scheme": "https", "server": ("demo.test", 443), "client": ("127.0.0.1", 1)})


class DemoPolicyTests(unittest.TestCase):
    def setUp(self):
        self.guest = SimpleNamespace(id=uuid4(), is_demo=True)

    def test_demo_client_ip_is_trusted_only_after_gateway_authentication(self):
        req = request("/api/v1/auth/demo", "POST")
        req.scope["headers"] = [(b"x-nexora-client-ip", b"192.0.2.10")]
        self.assertEqual(_get_client_ip(req), "127.0.0.1")
        req.state.demo_proxy_verified = True
        self.assertEqual(_get_client_ip(req), "192.0.2.10")

    @patch("app.core.demo.DEMO_ENABLED", True)
    @patch("app.core.demo.reserve_limits")
    def test_new_and_existing_generation_paths_cannot_bypass_question_budget(self, reserve):
        enforce_demo_access(request(f"/api/v1/conversations/{uuid4()}/messages", "POST"), self.guest)
        self.assertEqual(len(reserve.call_args.args[0]), 3)
        self.assertTrue(any(":questions:global:" in key for key, _, _ in reserve.call_args.args[0]))
        for path in ("/api/v1/rag/answer", "/api/v1/research/run", "/api/v1/search/compare", "/api/v1/future-paid-route"):
            with self.subTest(path=path), self.assertRaises(HTTPException) as caught:
                enforce_demo_access(request(path, "POST"), self.guest)
            self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(reserve.call_count, 1)

    @patch("app.core.demo.DEMO_ENABLED", True)
    @patch("app.core.demo.reserve_limits")
    def test_guests_cannot_upload_modify_samples_share_or_change_password(self, reserve):
        for path, method in [("/api/v1/documents/upload", "POST"), (f"/api/v1/document-sets/{uuid4()}", "PATCH"), ("/api/v1/auth/change-password", "POST"), ("/api/v1/chat-shares", "POST"), (f"/api/v1/answers/{uuid4()}/feedback", "PUT")]:
            with self.subTest(path=path), self.assertRaises(HTTPException):
                enforce_demo_access(request(path, method), self.guest)
        reserve.assert_not_called()

    @patch("app.core.demo.DEMO_ENABLED", True)
    @patch("app.core.demo.reserve_limits")
    def test_sample_reads_and_own_conversation_actions_remain_available(self, reserve):
        enforce_demo_access(request("/api/v1/document-sets"), self.guest)
        enforce_demo_access(request(f"/api/v1/documents/{uuid4()}/chunks"), self.guest)
        reserve.assert_not_called()
        enforce_demo_access(request("/api/v1/conversations", "POST"), self.guest)
        enforce_demo_access(request(f"/api/v1/conversations/{uuid4()}", "DELETE"), self.guest)
        self.assertEqual(reserve.call_count, 2)

    @patch("app.core.demo.DEMO_ENABLED", False)
    def test_disabling_demo_invalidates_guest_access_without_restricting_normal_users(self):
        with self.assertRaises(HTTPException):
            enforce_demo_access(request("/api/v1/auth/me"), self.guest)
        enforce_demo_access(request("/api/v1/research/run", "POST"), SimpleNamespace(is_demo=False))

    @patch("app.core.demo._quota_client")
    def test_shared_quota_failure_and_unavailability_fail_closed(self, client):
        client.return_value.eval.return_value = 1
        with self.assertRaises(HTTPException) as caught:
            reserve_limits([("dummy", 1, 60)])
        self.assertEqual(caught.exception.status_code, 429)
        client.return_value.eval.side_effect = RedisError("unavailable")
        with self.assertRaises(HTTPException) as caught:
            reserve_limits([("dummy", 1, 60)])
        self.assertEqual(caught.exception.status_code, 503)


class DemoGuestTests(unittest.TestCase):
    @patch("app.api.routes.auth.DEMO_ENABLED", False)
    @patch("app.api.routes.auth.create_demo_guest")
    def test_guest_entry_is_disabled_by_default(self, create_guest):
        with self.assertRaises(HTTPException) as caught:
            demo_login(Response(), request("/api/v1/auth/demo", "POST"), MagicMock())
        self.assertEqual(caught.exception.status_code, 404)
        create_guest.assert_not_called()

    @patch("app.api.routes.auth.DEMO_ENABLED", True)
    @patch("app.api.routes.auth.create_demo_guest")
    def test_guest_login_issues_a_short_cookie_session_without_a_password(self, create_guest):
        organization = SimpleNamespace(id=uuid4(), name="Demo", slug="nexora-public-demo")
        guest = SimpleNamespace(id=uuid4(), username="guest", role="user", is_demo=True)
        create_guest.return_value = guest, organization
        response, db = Response(), MagicMock()
        result = demo_login(response, request("/api/v1/auth/demo", "POST"), db)
        self.assertEqual(result.expires_in, 3600)
        self.assertTrue(result.user.is_demo)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertNotIn("Domain=", response.headers["set-cookie"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        db.commit.assert_called_once()

    @patch("app.services.application.demo_service.reserve_demo_session")
    def test_visitors_receive_distinct_identities_and_only_view_grants(self, reserve):
        organization = SimpleNamespace(id=uuid4())
        sample = SimpleNamespace(id=uuid4(), created_by_id=uuid4(), documents=[SimpleNamespace(status="indexed")])
        users = []
        for _ in range(2):
            db = MagicMock()
            db.scalar.side_effect = [organization, sample]
            user, _ = create_demo_guest(db, request("/api/v1/auth/demo", "POST"))
            users.append(user)
            grant = db.add.call_args_list[1].args[0]
            self.assertEqual(grant.permission, "view")
            self.assertEqual(grant.user_id, user.id)
            self.assertEqual(grant.document_set_id, sample.id)
            self.assertTrue(user.is_demo)
            self.assertEqual(user.role, "user")
        self.assertNotEqual(users[0].id, users[1].id)
        self.assertEqual(reserve.call_count, 2)

    @patch("app.services.application.demo_service.reserve_demo_session")
    def test_unready_samples_do_not_create_visitors_or_consume_capacity(self, reserve):
        db = MagicMock()
        db.scalar.return_value = None
        with self.assertRaises(HTTPException) as caught:
            create_demo_guest(db, request("/api/v1/auth/demo", "POST"))
        self.assertEqual(caught.exception.status_code, 503)
        reserve.assert_not_called()
        db.add.assert_not_called()
