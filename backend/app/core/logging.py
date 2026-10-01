"""Application logging with optional bounded on-disk retention."""

import logging
import json
from logging.handlers import RotatingFileHandler

from app.core.config import LOG_BACKUP_COUNT, LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES
from app.core.request_context import get_request_id


class JsonFormatter(logging.Formatter):
    """Compact structured logs suitable for local files and log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for key in ("job_id", "worker_id", "document_id", "connector_id", "user_id", "organization_id", "provider", "error_summary", "error_type", "method", "path", "status_code", "security_event", "outcome", "actor_id", "client_fingerprint", "reason", "duration_ms", "db_query_count", "db_query_duration_ms", "memory_rss_bytes"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = str(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Configure console logging and an optional rotating file handler once."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    formatter = JsonFormatter()
    if not root.handlers:
        logging.basicConfig(level=level)
    for handler in root.handlers:
        handler.setFormatter(formatter)
    if LOG_FILE is None:
        return

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    resolved_path = str(LOG_FILE.resolve())
    if any(getattr(handler, "baseFilename", None) == resolved_path for handler in root.handlers):
        return

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
