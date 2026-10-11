import unittest
from unittest.mock import MagicMock, patch

from app.services.providers.http_resilience import (
    CircuitOpenError,
    HttpResponse,
    ResilientHttpClient,
    ResilientHttpError,
)


class HttpResilienceTests(unittest.TestCase):
    def test_transient_failure_retries_with_backoff(self):
        client = ResilientHttpClient(max_attempts=3, backoff_seconds=0.5)
        client._send = MagicMock(
            side_effect=[
                OSError("temporary"),
                HttpResponse(status=503, body=b"unavailable", headers={}),
                HttpResponse(status=200, body=b"ok", headers={}),
            ]
        )

        with (
            patch("app.services.providers.http_resilience.random.uniform", return_value=0),
            patch("app.services.providers.http_resilience.time.sleep") as sleep,
        ):
            response = client.request("GET", "https://service.example/data", timeout_seconds=2)

        self.assertEqual(response.body, b"ok")
        self.assertEqual(client._send.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_rate_limit_respects_retry_after(self):
        client = ResilientHttpClient(max_attempts=2)
        client._send = MagicMock(
            side_effect=[
                HttpResponse(status=429, body=b"limited", headers={"retry-after": "4"}),
                HttpResponse(status=200, body=b"ok", headers={}),
            ]
        )

        with patch("app.services.providers.http_resilience.time.sleep") as sleep:
            client.request("GET", "https://service.example/data", timeout_seconds=2)

        sleep.assert_called_once_with(4.0)

    def test_non_retryable_client_error_fails_immediately(self):
        client = ResilientHttpClient(max_attempts=3)
        client._send = MagicMock(
            return_value=HttpResponse(status=400, body=b"bad request", headers={})
        )

        with self.assertRaises(ResilientHttpError):
            client.request("GET", "https://service.example/data", timeout_seconds=2)

        client._send.assert_called_once()

    def test_circuit_opens_after_failure_threshold(self):
        client = ResilientHttpClient(max_attempts=1, failure_threshold=2, recovery_seconds=30)
        client._send = MagicMock(side_effect=OSError("down"))

        for _ in range(2):
            with self.assertRaises(ResilientHttpError):
                client.request("GET", "https://service.example/data", timeout_seconds=2)

        with self.assertRaises(CircuitOpenError):
            client.request("GET", "https://service.example/data", timeout_seconds=2)
        self.assertEqual(client._send.call_count, 2)

    def test_connection_is_reused_within_thread(self):
        client = ResilientHttpClient()
        parsed = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(
            "https://service.example/data"
        )
        connection = MagicMock()

        with patch("app.services.providers.http_resilience.HTTPSConnection", return_value=connection) as factory:
            first = client._connection(parsed, 2)
            second = client._connection(parsed, 3)

        self.assertIs(first, second)
        factory.assert_called_once()
        self.assertEqual(connection.timeout, 3)


if __name__ == "__main__":
    unittest.main()
