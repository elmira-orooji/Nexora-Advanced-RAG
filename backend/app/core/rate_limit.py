"""Lightweight in-memory sliding-window rate limiter for FastAPI.

Uses a token-bucket approach per IP address with automatic cleanup of
stale entries to prevent unbounded memory growth.
"""

import time
import threading
import hashlib
from collections import OrderedDict
from functools import wraps
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import RATE_LIMIT_REDIS_URL, TRUSTED_PROXY_IPS
from app.services.operations.security_audit import audit_security_event


class RateLimiter:
    """Thread-safe sliding window rate limiter with LRU eviction."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60, max_entries: int = 10_000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_entries = max_entries
        self._buckets: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _cleanup(self, now: float) -> None:
        """Remove stale entries beyond the window and enforce max size."""
        cutoff = now - self.window_seconds
        # Remove expired buckets
        stale_keys = [
            key for key, timestamps in self._buckets.items()
            if not timestamps or timestamps[-1] < cutoff
        ]
        for key in stale_keys:
            del self._buckets[key]
        # Enforce max entries via LRU eviction
        while len(self._buckets) > self.max_entries:
            self._buckets.popitem(last=False)

    def check(self, key: str) -> tuple[bool, dict[str, str]]:
        """Check if request is allowed. Returns (allowed, headers)."""
        now = time.time()
        with self._lock:
            self._cleanup(now)
            timestamps = self._buckets.get(key, [])
            # Filter to current window
            cutoff = now - self.window_seconds
            timestamps = [t for t in timestamps if t >= cutoff]

            if len(timestamps) >= self.max_requests:
                retry_after = int(timestamps[0] - cutoff) + 1
                self._buckets[key] = timestamps
                return False, {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                }

            timestamps.append(now)
            self._buckets[key] = timestamps
            remaining = self.max_requests - len(timestamps)
            return True, {
                "X-RateLimit-Limit": str(self.max_requests),
                "X-RateLimit-Remaining": str(remaining),
            }


class RedisRateLimiter(RateLimiter):
    """Shared fixed-window limiter for multi-replica deployments."""
    def __init__(self, namespace: str, max_requests: int, window_seconds: int):
        super().__init__(max_requests, window_seconds)
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis is required when RATE_LIMIT_REDIS_URL is configured") from exc
        self.namespace = namespace
        self.client = redis.Redis.from_url(RATE_LIMIT_REDIS_URL, decode_responses=True)

    def check(self, key: str) -> tuple[bool, dict[str, str]]:
        digest = hashlib.sha256(key.encode()).hexdigest()
        bucket = f"nexora:rate-limit:{self.namespace}:{digest}:{int(time.time() // self.window_seconds)}"
        count = self.client.incr(bucket)
        if count == 1:
            self.client.expire(bucket, self.window_seconds)
        remaining = max(0, self.max_requests - count)
        headers = {"X-RateLimit-Limit": str(self.max_requests), "X-RateLimit-Remaining": str(remaining)}
        if count > self.max_requests:
            headers["Retry-After"] = str(self.window_seconds)
            return False, headers
        return True, headers


def _limiter(namespace: str, max_requests: int) -> RateLimiter:
    return RedisRateLimiter(namespace, max_requests, 60) if RATE_LIMIT_REDIS_URL else RateLimiter(max_requests=max_requests, window_seconds=60)


# Default limiters for different endpoint categories
rag_limiter = _limiter("rag", 20)
auth_limiter = _limiter("auth", 10)
general_limiter = _limiter("general", 60)
webhook_limiter = _limiter("webhook", 30)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    peer_ip = request.client.host if request.client else "unknown"
    if forwarded and peer_ip in TRUSTED_PROXY_IPS:
        return forwarded.split(",")[0].strip()
    return peer_ip


def rate_limit(limiter: RateLimiter) -> Callable:
    """FastAPI dependency that enforces rate limiting."""
    async def dependency(request: Request) -> None:
        key = _get_client_ip(request)
        allowed, headers = limiter.check(key)
        if not allowed:
            audit_security_event("rate_limit_exceeded", "blocked", client_ip=key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers=headers,
            )
        # Attach headers to response via state for middleware to pick up
        request.state.rate_limit_headers = headers
    return dependency

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches rate limit headers from request state to the response."""

    async def dispatch(self, request: Request, call_next):
        # Enforce a safe baseline on state-changing endpoints. More restrictive
        # endpoint limiters (auth/RAG/webhook) remain available as dependencies.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            key = _get_client_ip(request)
            allowed, headers = general_limiter.check(key)
            if not allowed:
                audit_security_event("rate_limit_exceeded", "blocked", client_ip=key)
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Rate limit exceeded. Please try again later."}, headers=headers)
        response = await call_next(request)
        headers = getattr(request.state, "rate_limit_headers", None)
        if headers:
            for key, value in headers.items():
                response.headers[key] = value
        return response
