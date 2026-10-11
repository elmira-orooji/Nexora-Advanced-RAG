"""Structured, privacy-preserving security audit events."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def audit_security_event(event: str, outcome: str, *, actor_id: str | None = None, client_ip: str | None = None, reason: str | None = None) -> None:
    fingerprint = hashlib.sha256(client_ip.encode()).hexdigest()[:16] if client_ip else None
    logger.warning(
        "Security audit event",
        extra={
            "security_event": event,
            "outcome": outcome,
            "actor_id": actor_id,
            "client_fingerprint": fingerprint,
            "reason": reason,
        },
    )
