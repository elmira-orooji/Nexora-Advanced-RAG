"""Shared resilient HTTP transport for external service clients."""

import random
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import urlsplit


class ResilientHttpError(RuntimeError):
    pass


class CircuitOpenError(ResilientHttpError):
    pass


class HttpStatusError(ResilientHttpError):
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body
        self.headers = headers


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]


class ResilientHttpClient:
    _RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0.25,
        failure_threshold: int = 5,
        recovery_seconds: float = 30,
    ) -> None:
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._local = threading.local()
        self._state_lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout_seconds: float,
    ) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("HTTP URL must include a valid http or https host")
        self._before_request()

        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                response = self._send(method, parsed, headers or {}, body, timeout_seconds)
                if response.status < 400:
                    self._record_success()
                    return response
                error = HttpStatusError(response.status, response.body, response.headers)
                if response.status not in self._RETRYABLE_STATUSES:
                    raise error
                last_error = error
            except (OSError, TimeoutError, HTTPException) as exc:
                self._discard_connection(parsed)
                last_error = exc
            except HttpStatusError:
                raise

            self._record_failure()
            if attempt + 1 >= self.max_attempts:
                break
            delay = self._retry_delay(attempt, last_error)
            time.sleep(delay)

        raise ResilientHttpError("External service request failed after retries") from last_error

    def _connections(self) -> dict[tuple[str, str, int | None], HTTPConnection]:
        if not hasattr(self._local, "connections"):
            self._local.connections = {}
        return self._local.connections

    def _connection(self, parsed, timeout_seconds: float) -> HTTPConnection:
        key = (parsed.scheme, parsed.hostname, parsed.port)
        connections = self._connections()
        connection = connections.get(key)
        if connection is None:
            connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
            connection = connection_type(parsed.hostname, parsed.port, timeout=timeout_seconds)
            connections[key] = connection
        else:
            connection.timeout = timeout_seconds
        return connection

    def _discard_connection(self, parsed) -> None:
        key = (parsed.scheme, parsed.hostname, parsed.port)
        connection = self._connections().pop(key, None)
        if connection is not None:
            connection.close()

    def _send(self, method, parsed, headers, body, timeout_seconds) -> HttpResponse:
        connection = self._connection(parsed, timeout_seconds)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read()
        return HttpResponse(
            status=response.status,
            body=response_body,
            headers={key.lower(): value for key, value in response.getheaders()},
        )

    def _before_request(self) -> None:
        with self._state_lock:
            if self._opened_at is None:
                return
            if time.monotonic() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("External service circuit is open")
            self._opened_at = None
            self._consecutive_failures = 0

    def _record_success(self) -> None:
        with self._state_lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def _record_failure(self) -> None:
        with self._state_lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    def _retry_delay(self, attempt: int, error: Exception | None) -> float:
        if isinstance(error, HttpStatusError):
            retry_after = error.headers.get("retry-after")
            if retry_after:
                parsed_delay = self._parse_retry_after(retry_after)
                if parsed_delay is not None:
                    return min(parsed_delay, 30)
        base = self.backoff_seconds * (2**attempt)
        return base + random.uniform(0, base / 2)

    @staticmethod
    def _parse_retry_after(value: str) -> float | None:
        try:
            return max(0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                return max(0, retry_at.timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                return None
