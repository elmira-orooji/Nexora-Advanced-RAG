"""Opt-in public demo policy. Quotas fail closed and are shared by API replicas."""

import hashlib
import os
import re
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import HTTPException, Request

from app.core.config import APP_ENV, OPENROUTER_API_KEY, RATE_LIMIT_REDIS_URL, _boolean_setting

DEMO_ENABLED = _boolean_setting("DEMO_ENABLED", default=False)
DEMO_PROXY_SECRET = os.getenv("DEMO_PROXY_SECRET", "")
DEMO_ORGANIZATION_SLUG = "nexora-public-demo"
DEMO_SET_NAME = "Nexora demo handbook"
DEMO_SESSION_SECONDS = 3600
DEMO_QUESTION_LIMIT = 10
DEMO_DAILY_QUESTION_LIMIT = int(os.getenv("DEMO_DAILY_QUESTION_LIMIT", "100"))
DEMO_DAILY_SESSION_LIMIT = int(os.getenv("DEMO_DAILY_SESSION_LIMIT", "50"))
if DEMO_ENABLED:
    if not RATE_LIMIT_REDIS_URL:
        raise RuntimeError("DEMO_ENABLED requires RATE_LIMIT_REDIS_URL for shared quotas")
    if APP_ENV not in {"test", "development"} and len(DEMO_PROXY_SECRET) < 32:
        raise RuntimeError("Production demo requires DEMO_PROXY_SECRET of at least 32 characters")
    if APP_ENV not in {"test", "development"} and not OPENROUTER_API_KEY:
        raise RuntimeError("Production demo requires an OPENROUTER_API_KEY for real answers")
    if DEMO_DAILY_QUESTION_LIMIT < 1 or DEMO_DAILY_SESSION_LIMIT < 1:
        raise RuntimeError("Demo daily limits must be positive")

_UUID = r"[0-9a-fA-F-]{36}"
_CONVERSATION = re.compile(rf"/api/v1/conversations/{_UUID}")
_MESSAGE = re.compile(rf"/api/v1/conversations/{_UUID}/messages")
_READ = re.compile(rf"/api/v1/(?:document-sets(?:/{_UUID})?|documents(?:/{_UUID}(?:/(?:chunks|source|preview))?)?|conversations(?:/{_UUID})?|auth/me|notifications)")

# All counters are checked before any increment. Expiry is set in the same
# atomic operation; an over-budget request never creates extra counter keys.
_RESERVE = """
for i, key in ipairs(KEYS) do
  if tonumber(redis.call('GET', key) or '0') >= tonumber(ARGV[2*i-1]) then
    return i
  end
end
for i, key in ipairs(KEYS) do
  if redis.call('INCR', key) == 1 then redis.call('EXPIRE', key, ARGV[2*i]) end
end
return 0
"""


@lru_cache(maxsize=1)
def _quota_client():
    from redis import Redis
    return Redis.from_url(RATE_LIMIT_REDIS_URL, socket_timeout=2, socket_connect_timeout=2)


def reserve_limits(limits: list[tuple[str, int, int]]) -> None:
    try:
        from redis import RedisError
    except ImportError as exc:
        raise HTTPException(503, "Demo capacity checking is unavailable. Please try later.") from exc
    try:
        denied = _quota_client().eval(_RESERVE, len(limits), *[x[0] for x in limits], *[v for _, limit, ttl in limits for v in (limit, ttl)])
    except RedisError as exc:
        raise HTTPException(503, "Demo capacity checking is unavailable. Please try later.") from exc
    if denied:
        raise HTTPException(429, "Demo limit reached. Please try again later.", headers={"Retry-After": "3600"})


def reserve_demo_session(request: Request) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    # Only the authenticated proxy may supply this header in production.
    peer = request.headers.get("x-nexora-client-ip", "unknown") if DEMO_PROXY_SECRET else (request.client.host if request.client else "unknown")
    digest = hashlib.sha256(peer.encode()).hexdigest()
    reserve_limits([
        (f"nexora:demo:sessions:{day}", DEMO_DAILY_SESSION_LIMIT, 172800),
        (f"nexora:demo:ip:{day}:{digest}", 5, 172800),
    ])


def enforce_demo_access(request: Request, user) -> None:
    """Default-deny guest operations, including future paid/admin routes."""
    if not getattr(user, "is_demo", False):
        return
    if not DEMO_ENABLED:
        raise HTTPException(403, "The public demo is disabled.")
    path, method = request.url.path, request.method
    if method == "GET" and _READ.fullmatch(path):
        return
    message = method == "POST" and _MESSAGE.fullmatch(path)
    conversation = (method == "POST" and path == "/api/v1/conversations") or (method in {"PATCH", "DELETE"} and _CONVERSATION.fullmatch(path))
    if not (message or conversation):
        raise HTTPException(403, "Demo visitors can chat with sample documents; this action is unavailable.")
    limits = [(f"nexora:demo:operations:{user.id}", 40, 86400)]
    if message:
        day = datetime.now(timezone.utc).date().isoformat()
        limits.extend([
            (f"nexora:demo:questions:{user.id}", DEMO_QUESTION_LIMIT, 86400),
            (f"nexora:demo:questions:global:{day}", DEMO_DAILY_QUESTION_LIMIT, 172800),
        ])
    # Failed/cancelled generations also consume a slot: provider retries must
    # not make failure a free way around the demo spending admission limit.
    reserve_limits(limits)
