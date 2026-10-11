import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, Response

from app.api.routes.auth import login
from app.schemas.auth import LoginRequest
from app.services.security.login_throttle import _key, _lock_seconds, throttle_keys
from tests.test_auth_cookies import login_request


class LoginThrottleTests(unittest.TestCase):
    def test_keys_do_not_store_raw_account_or_ip(self):
        account_key, ip_key = throttle_keys("Acme", "Alice", "203.0.113.10")
        self.assertEqual(len(account_key), 64)
        self.assertEqual(len(ip_key), 64)
        self.assertNotIn("alice", account_key)
        self.assertNotIn("203.0.113.10", ip_key)
        self.assertEqual(account_key, _key("account", "acme:alice"))

    def test_lock_duration_increases_and_is_capped(self):
        with patch("app.services.security.login_throttle.AUTH_LOCK_BASE_SECONDS", 30), patch("app.services.security.login_throttle.AUTH_LOCK_MAX_SECONDS", 900):
            self.assertEqual(_lock_seconds(4, 5), 0)
            self.assertEqual(_lock_seconds(5, 5), 30)
            self.assertEqual(_lock_seconds(7, 5), 120)
            self.assertEqual(_lock_seconds(20, 5), 900)

    def test_locked_login_returns_retry_after_without_password_check(self):
        payload = LoginRequest(username="alice", password="password123", organization="acme")
        with patch("app.api.routes.auth.retry_after", return_value=73), patch("app.api.routes.auth.verify_password") as verify:
            with self.assertRaises(HTTPException) as raised:
                login(payload, Response(), login_request(), MagicMock())
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.headers["Retry-After"], "73")
        verify.assert_not_called()

    def test_failed_login_is_recorded(self):
        payload = LoginRequest(username="alice", password="password123", organization="acme")
        db = MagicMock()
        db.scalar.return_value = None
        with patch("app.api.routes.auth.retry_after", return_value=None), patch("app.api.routes.auth.record_failure", return_value=30) as record, patch("app.api.routes.auth.verify_password", return_value=False):
            with self.assertRaises(HTTPException) as raised:
                login(payload, Response(), login_request(), db)
        self.assertEqual(raised.exception.status_code, 401)
        record.assert_called_once()
