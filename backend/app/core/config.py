from dotenv import load_dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_NON_PRODUCTION_ENVIRONMENTS = {"development", "test"}


def _load_environment(env_file: Path = BASE_DIR / ".env") -> None:
    """Load local defaults without replacing host-provided configuration."""
    load_dotenv(env_file, override=False)


def _boolean_setting(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise RuntimeError(f"{name} must be a boolean value")


def _validate_cookie_security(environment: str, secure: bool) -> None:
    if not secure and environment not in _NON_PRODUCTION_ENVIRONMENTS:
        raise RuntimeError(
            "AUTH_COOKIE_SECURE may only be disabled when APP_ENV is development or test"
        )


_load_environment()

DATABASE_URL = os.getenv("DATABASE_URL")
QDRANT_URL = os.getenv("QDRANT_URL", "").rstrip("/")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_chunks")
QDRANT_EMBEDDING_MODEL = os.getenv(
    "QDRANT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_INPUT_COST_PER_MILLION = float(os.getenv("OPENROUTER_INPUT_COST_PER_MILLION", "0"))
OPENROUTER_OUTPUT_COST_PER_MILLION = float(os.getenv("OPENROUTER_OUTPUT_COST_PER_MILLION", "0"))
_DEFAULT_DOCUMENT_STORAGE = (BASE_DIR / "storage" / "documents").resolve()
_DOCUMENT_STORAGE_ENV = os.getenv("DOCUMENT_STORAGE_DIR")
if _DOCUMENT_STORAGE_ENV:
    UPLOAD_DIR = Path(_DOCUMENT_STORAGE_ENV).expanduser().resolve()
else:
    UPLOAD_DIR = _DEFAULT_DOCUMENT_STORAGE

_LOG_FILE_ENV = os.getenv("LOG_FILE", "").strip()
LOG_FILE = Path(_LOG_FILE_ENV).expanduser().resolve() if _LOG_FILE_ENV else None
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL", "").strip()
TRUSTED_PROXY_IPS = frozenset(
    value.strip() for value in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if value.strip()
)
if LOG_MAX_BYTES <= 0 or LOG_BACKUP_COUNT < 1:
    raise RuntimeError("LOG_MAX_BYTES must be positive and LOG_BACKUP_COUNT must be at least 1")


def document_storage_relative(path: Path) -> str:
    """Return a storage-relative POSIX path that survives across replicas.

    Paths are stored relative to UPLOAD_DIR instead of BASE_DIR so deployments
    with an external/shared volume do not embed host-specific prefixes. Legacy
    entries written before this change remain readable via resolve_document_path.
    """
    try:
        return path.relative_to(UPLOAD_DIR).as_posix()
    except ValueError:
        # Fallback for callers that still hand in a BASE_DIR-relative path or
        # an absolute path outside the configured storage root.
        try:
            return path.relative_to(BASE_DIR).as_posix()
        except ValueError:
            return path.as_posix()


def resolve_document_path(stored: str) -> Path:
    """Resolve a persisted storage reference to an absolute filesystem path.

    Supports three formats for backward compatibility:
      * paths relative to UPLOAD_DIR (current default)
      * legacy paths relative to BASE_DIR
      * absolute paths (e.g. when DOCUMENT_STORAGE_DIR points outside BASE_DIR)
    """
    candidate = Path(stored)
    if candidate.is_absolute():
        return candidate.resolve()
    upload_candidate = (UPLOAD_DIR / candidate).resolve()
    try:
        upload_candidate.relative_to(UPLOAD_DIR)
        if upload_candidate.exists() or not (BASE_DIR / candidate).exists():
            return upload_candidate
    except ValueError:
        pass
    return (BASE_DIR / candidate).resolve()
MAX_UPLOAD_SIZE = 100 * 1024 * 1024
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
MALWARE_SCAN_MODE = os.getenv("MALWARE_SCAN_MODE", "required" if APP_ENV not in _NON_PRODUCTION_ENVIRONMENTS else "disabled").strip().lower()
if MALWARE_SCAN_MODE not in {"disabled", "required"}:
    raise RuntimeError("MALWARE_SCAN_MODE must be disabled or required")
if MALWARE_SCAN_MODE == "disabled" and APP_ENV not in _NON_PRODUCTION_ENVIRONMENTS:
    raise RuntimeError("MALWARE_SCAN_MODE may only be disabled when APP_ENV is development or test")
CLAMD_HOST = os.getenv("CLAMD_HOST", "clamav")
CLAMD_PORT = int(os.getenv("CLAMD_PORT", "3310"))
CLAMD_TIMEOUT_SECONDS = float(os.getenv("CLAMD_TIMEOUT_SECONDS", "15"))
MALWARE_RETAIN_DETECTED = _boolean_setting("MALWARE_RETAIN_DETECTED", default=False)
MALWARE_QUARANTINE_DIR = UPLOAD_DIR / ".quarantine"
if CLAMD_PORT < 1 or CLAMD_PORT > 65535 or CLAMD_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("CLAMD_PORT must be valid and CLAMD_TIMEOUT_SECONDS must be positive")
# Jina is the requested default for scanned files, with MinerU as fallback.
# Both providers are hosted services, so enabling this default sends document
# content outside the deployment. Set OCR_PROVIDER=disabled to opt out.
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "jina").strip().lower()
if OCR_PROVIDER not in {"disabled", "auto", "mineru", "jina", "google_vision", "azure_document_intelligence"}:
    raise RuntimeError("OCR_PROVIDER must be disabled, auto, mineru, jina, google_vision, or azure_document_intelligence")
OCR_LANGUAGE_HINTS = [
    language.strip()
    for language in os.getenv("OCR_LANGUAGE_HINTS", "fa,en").split(",")
    if language.strip()
]
OCR_TIMEOUT_SECONDS = float(os.getenv("OCR_TIMEOUT_SECONDS", "30"))
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "100"))
MINERU_API_TOKEN = os.getenv("MINERU_API_TOKEN", "")
MINERU_API_BASE_URL = os.getenv("MINERU_API_BASE_URL", "https://mineru.net/api/v4").rstrip("/")
MINERU_MODEL_VERSION = os.getenv("MINERU_MODEL_VERSION", "vlm").strip().lower()
MINERU_LANGUAGE = os.getenv("MINERU_LANGUAGE", "fa").strip().lower()
MINERU_TIMEOUT_SECONDS = float(os.getenv("MINERU_TIMEOUT_SECONDS", "300"))
MINERU_POLL_SECONDS = float(os.getenv("MINERU_POLL_SECONDS", "2"))
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_OCR_API_BASE_URL = os.getenv("JINA_OCR_API_BASE_URL", "https://api.jina.ai/v1").rstrip("/")
JINA_OCR_MODEL = os.getenv("JINA_OCR_MODEL", "jina-ocr-v1").strip()
if OCR_TIMEOUT_SECONDS <= 0 or OCR_MAX_PAGES < 1 or MINERU_TIMEOUT_SECONDS <= 0 or MINERU_POLL_SECONDS <= 0:
    raise RuntimeError("OCR_TIMEOUT_SECONDS, OCR_MAX_PAGES, MINERU_TIMEOUT_SECONDS, and MINERU_POLL_SECONDS must be positive")
if MINERU_MODEL_VERSION not in {"pipeline", "vlm"}:
    raise RuntimeError("MINERU_MODEL_VERSION must be pipeline or vlm")
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").rstrip("/")
AZURE_DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
if len(AUTH_SECRET_KEY) < 32:
    raise RuntimeError("AUTH_SECRET_KEY must be set to at least 32 characters")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "nexora_session")
AUTH_COOKIE_SECURE = _boolean_setting("AUTH_COOKIE_SECURE", default=True)
_validate_cookie_security(APP_ENV, AUTH_COOKIE_SECURE)
AUTH_SESSION_SECONDS = int(os.getenv("AUTH_SESSION_SECONDS", str(8 * 60 * 60)))
AUTH_REMEMBER_SECONDS = int(os.getenv("AUTH_REMEMBER_SECONDS", str(30 * 24 * 60 * 60)))
AUTH_FAILURE_WINDOW_SECONDS = int(os.getenv("AUTH_FAILURE_WINDOW_SECONDS", "900"))
AUTH_ACCOUNT_FAILURE_LIMIT = int(os.getenv("AUTH_ACCOUNT_FAILURE_LIMIT", "5"))
AUTH_IP_FAILURE_LIMIT = int(os.getenv("AUTH_IP_FAILURE_LIMIT", "30"))
AUTH_LOCK_BASE_SECONDS = int(os.getenv("AUTH_LOCK_BASE_SECONDS", "30"))
AUTH_LOCK_MAX_SECONDS = int(os.getenv("AUTH_LOCK_MAX_SECONDS", "900"))
DOCUMENT_JOB_POLL_SECONDS = float(os.getenv("DOCUMENT_JOB_POLL_SECONDS", "1"))
DOCUMENT_JOB_LEASE_SECONDS = int(os.getenv("DOCUMENT_JOB_LEASE_SECONDS", "3600"))
DOCUMENT_JOB_HEARTBEAT_SECONDS = float(os.getenv("DOCUMENT_JOB_HEARTBEAT_SECONDS", "30"))
if not 0 < DOCUMENT_JOB_HEARTBEAT_SECONDS < DOCUMENT_JOB_LEASE_SECONDS:
    raise RuntimeError("DOCUMENT_JOB_HEARTBEAT_SECONDS must be positive and shorter than DOCUMENT_JOB_LEASE_SECONDS")
DOCUMENT_JOB_MAX_ATTEMPTS = int(os.getenv("DOCUMENT_JOB_MAX_ATTEMPTS", "5"))
DOCUMENT_JOB_RETRY_BASE_SECONDS = int(os.getenv("DOCUMENT_JOB_RETRY_BASE_SECONDS", "30"))
DOCUMENT_JOB_RETRY_MAX_SECONDS = int(os.getenv("DOCUMENT_JOB_RETRY_MAX_SECONDS", "1800"))
if DOCUMENT_JOB_MAX_ATTEMPTS < 1:
    raise RuntimeError("DOCUMENT_JOB_MAX_ATTEMPTS must be at least 1")
if DOCUMENT_JOB_RETRY_BASE_SECONDS < 1 or DOCUMENT_JOB_RETRY_MAX_SECONDS < DOCUMENT_JOB_RETRY_BASE_SECONDS:
    raise RuntimeError("Document job retry delays must be positive and max must be at least base")
CONNECTOR_SYNC_MAX_ATTEMPTS = int(os.getenv("CONNECTOR_SYNC_MAX_ATTEMPTS", "5"))
CONNECTOR_SYNC_RETRY_BASE_SECONDS = int(os.getenv("CONNECTOR_SYNC_RETRY_BASE_SECONDS", "30"))
CONNECTOR_SYNC_RETRY_MAX_SECONDS = int(os.getenv("CONNECTOR_SYNC_RETRY_MAX_SECONDS", "1800"))
if CONNECTOR_SYNC_MAX_ATTEMPTS < 1:
    raise RuntimeError("CONNECTOR_SYNC_MAX_ATTEMPTS must be at least 1")
if CONNECTOR_SYNC_RETRY_BASE_SECONDS < 1 or CONNECTOR_SYNC_RETRY_MAX_SECONDS < CONNECTOR_SYNC_RETRY_BASE_SECONDS:
    raise RuntimeError("Connector sync retry delays must be positive and max must be at least base")
CONNECTOR_SCHEDULER_POLL_SECONDS = float(os.getenv("CONNECTOR_SCHEDULER_POLL_SECONDS", "60"))
WORKER_HEARTBEAT_SECONDS = float(os.getenv("WORKER_HEARTBEAT_SECONDS", "30"))
WORKER_STALE_THRESHOLD_SECONDS = int(os.getenv("WORKER_STALE_THRESHOLD_SECONDS", "120"))
READINESS_PROBE_TIMEOUT_SECONDS = float(os.getenv("READINESS_PROBE_TIMEOUT_SECONDS", "2"))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
CONNECTOR_SECRET_MANAGER_URL = os.getenv("CONNECTOR_SECRET_MANAGER_URL", "").rstrip("/")
CONNECTOR_SECRET_MANAGER_TOKEN = os.getenv("CONNECTOR_SECRET_MANAGER_TOKEN", "")
CONNECTOR_SECRET_MANAGER_TIMEOUT_SECONDS = float(
    os.getenv("CONNECTOR_SECRET_MANAGER_TIMEOUT_SECONDS", "3")
)

# Operational monitoring stays opt-in: no monitoring endpoint is exposed until
# an explicit bearer token is configured, and email delivery is asynchronous.
METRICS_BEARER_TOKEN = os.getenv("METRICS_BEARER_TOKEN", "")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
ALERT_RECIPIENTS = tuple(
    address.strip()
    for address in os.getenv("ALERT_RECIPIENTS", "").split(",")
    if address.strip()
)
SMTP_USE_TLS = _boolean_setting("SMTP_USE_TLS", default=True)
SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
OPERATIONAL_ALERT_COOLDOWN_SECONDS = int(os.getenv("OPERATIONAL_ALERT_COOLDOWN_SECONDS", "900"))
if SMTP_PORT < 1 or SMTP_PORT > 65535 or SMTP_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("SMTP_PORT must be valid and SMTP_TIMEOUT_SECONDS must be positive")
if OPERATIONAL_ALERT_COOLDOWN_SECONDS < 60:
    raise RuntimeError("OPERATIONAL_ALERT_COOLDOWN_SECONDS must be at least 60")

# Retention is opt-in because it irreversibly removes operational records.
# Content-bearing data (documents, chunks, embeddings and messages) is never
# included here: it requires an organization-approved deletion request.
DATA_RETENTION_ENABLED = _boolean_setting("DATA_RETENTION_ENABLED", default=False)
DATA_RETENTION_MAINTENANCE_SECONDS = int(
    os.getenv("DATA_RETENTION_MAINTENANCE_SECONDS", str(60 * 60))
)
DATA_RETENTION_SESSION_DAYS = int(os.getenv("DATA_RETENTION_SESSION_DAYS", "30"))
DATA_RETENTION_CHAT_SHARE_DAYS = int(os.getenv("DATA_RETENTION_CHAT_SHARE_DAYS", "30"))
DATA_RETENTION_READ_NOTIFICATION_DAYS = int(
    os.getenv("DATA_RETENTION_READ_NOTIFICATION_DAYS", "90")
)
DATA_RETENTION_LLM_USAGE_DAYS = int(os.getenv("DATA_RETENTION_LLM_USAGE_DAYS", "365"))
if DATA_RETENTION_MAINTENANCE_SECONDS < 60:
    raise RuntimeError("DATA_RETENTION_MAINTENANCE_SECONDS must be at least 60")
if min(
    DATA_RETENTION_SESSION_DAYS,
    DATA_RETENTION_CHAT_SHARE_DAYS,
    DATA_RETENTION_READ_NOTIFICATION_DAYS,
    DATA_RETENTION_LLM_USAGE_DAYS,
) < 1:
    raise RuntimeError("Data retention periods must be at least one day")


# --- Chunking Strategy ---
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "hierarchical").strip().lower()
if CHUNKING_STRATEGY not in {"hierarchical", "semantic"}:
    raise RuntimeError("CHUNKING_STRATEGY must be 'hierarchical' or 'semantic'")
SEMANTIC_CHUNK_MIN_SIZE = int(os.getenv("SEMANTIC_CHUNK_MIN_SIZE", "200"))
SEMANTIC_CHUNK_MAX_SIZE = int(os.getenv("SEMANTIC_CHUNK_MAX_SIZE", "1500"))
SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.45"))

