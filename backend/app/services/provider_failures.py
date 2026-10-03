from app.core.application_errors import ApplicationError
"""Translate infrastructure failures into stable, safe API responses."""

import logging



from app.services.openrouter import OpenRouterError
from app.services.qdrant import QdrantError
from app.services.http_resilience import CircuitOpenError, HttpStatusError

logger = logging.getLogger(__name__)


def _log_provider_failure(exc: Exception, provider: str) -> None:
    # Never log exception strings, response bodies, headers, prompts or tracebacks.
    # Providers may echo credentials or document contents in their error messages.
    current = exc
    seen: set[int] = set()
    reason = "invalid_response_or_provider_failure"
    status_code = None
    while id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HttpStatusError):
            status_code = current.status
            reason = "http_error"
            break
        if isinstance(current, CircuitOpenError):
            reason = "circuit_open"
            break
        if isinstance(current, TimeoutError):
            reason = "timeout"
            break
        if isinstance(current, OSError):
            reason = "network_error"
            break
        if current.__cause__ is None:
            break
        current = current.__cause__
    if isinstance(exc, OpenRouterError) and str(exc) == "OpenRouter configuration is missing":
        reason = "missing_configuration"
    logger.warning("Provider request failed", extra={
        "provider": provider,
        "error_type": type(current).__name__,
        "reason": reason,
        "status_code": status_code,
    })


def provider_error(exc: Exception) -> ApplicationError:
    if isinstance(exc, QdrantError):
        _log_provider_failure(exc, "qdrant")
        return ApplicationError(kind="service_unavailable",
            detail="Knowledge search is temporarily unavailable. Please retry shortly.",
        )
    if isinstance(exc, OpenRouterError):
        _log_provider_failure(exc, "openrouter")
        return ApplicationError(kind="service_unavailable",
            detail="The AI response service is temporarily unavailable. Please retry shortly.",
        )
    return ApplicationError(kind="upstream_unavailable", detail="A required service is currently unavailable.")
