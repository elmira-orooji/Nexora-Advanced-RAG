from app.services.provider_factory import get_vector_store
import logging
import os
import hmac
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import analytics_router, assistants_router, auth_router, chat_shares_router, connectors_router, conversations_router, document_sets_router, documents_router, evaluations_router, feedback_router, notifications_router, rag_router, research_router, search_router, users_router
from app.core.config import FRONTEND_ORIGINS, METRICS_BEARER_TOKEN, READINESS_PROBE_TIMEOUT_SECONDS, UPLOAD_DIR, WORKER_STALE_THRESHOLD_SECONDS
from app.db.database import get_db
from app.models.connector import Connector
from app.models.llm_usage import LLMUsage
from app.models.processing_job import ProcessingJob
from app.models.indexing_outbox import IndexingOutbox
from app.models.operational_alert import OperationalAlert
from app.services.operational_metrics import increment, render
from app.services.performance_measurement import (
    begin_request_measurement,
    finish_request_measurement,
    process_memory_bytes,
    register_sqlalchemy_query_metrics,
)
from app.services.provider_errors import VectorStoreError
from app.services.worker_heartbeat import get_available_worker_types
from app.core.rate_limit import RateLimitMiddleware
from app.core.logging import configure_logging
from app.core.request_context import reset_request_id, set_request_id
from app.core.request_context import get_request_id
from app.api.contracts import API_MAJOR_VERSION, API_PREFIX, error_body
from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception

logger = logging.getLogger(__name__)

app = FastAPI(title="Nexora API", version="1.0.0")
register_sqlalchemy_query_metrics()
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def collect_request_metrics(request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = supplied_request_id[:128] if supplied_request_id and supplied_request_id.isprintable() else str(uuid.uuid4())
    request_token = set_request_id(request_id)
    measurement_token = begin_request_measurement(request.url.path)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        increment("http_errors_total", path=request.url.path, status="500")
        logger.exception("HTTP request failed", extra={"method": request.method, "path": request.url.path})
        if request.url.path.startswith(API_PREFIX):
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_body(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error",
                    request_id=request_id,
                ),
                headers={"X-Request-ID": request_id, "X-API-Version": API_MAJOR_VERSION},
            )
            return response
        raise
    else:
        if request.url.path.startswith(API_PREFIX):
            response.headers["X-API-Version"] = API_MAJOR_VERSION
        response.headers["X-Request-ID"] = request_id
        logger.info("HTTP request completed", extra={"method": request.method, "path": request.url.path, "status_code": response.status_code})
        if response.status_code >= 500:
            increment("http_errors_total", path=request.url.path, status=str(response.status_code))
        return response
    finally:
        increment("http_requests_total", path=request.url.path, method=request.method)
        elapsed_seconds = time.perf_counter() - started
        increment("http_request_duration_seconds_total", elapsed_seconds, path=request.url.path)
        measurement = finish_request_measurement(measurement_token, elapsed_seconds)
        if measurement is not None:
            logger.info(
                "HTTP request measurement",
                extra={
                    "path": request.url.path,
                    "duration_ms": round(elapsed_seconds * 1000, 2),
                    "db_query_count": measurement.query_count,
                    "db_query_duration_ms": round(measurement.query_duration_seconds * 1000, 2),
                    "memory_rss_bytes": process_memory_bytes(),
                },
            )
        reset_request_id(request_token)


@app.exception_handler(HTTPException)
async def api_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Add stable error metadata to v1 without breaking existing ``detail`` users."""
    if not request.url.path.startswith(API_PREFIX):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(status_code=exc.status_code, detail=exc.detail, request_id=get_request_id()),
        headers=exc.headers,
    )


@app.exception_handler(ApplicationError)
async def api_application_exception_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    return await api_http_exception_handler(request, to_http_exception(exc))


@app.exception_handler(RequestValidationError)
async def api_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Preserve FastAPI validation details and give clients a stable error code."""
    if not request.url.path.startswith(API_PREFIX):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
            request_id=get_request_id(),
        ),
    )


@app.on_event("startup")
async def startup_collection_setup():
    """Keep API startup independent from external vector-store availability.

    Collection creation belongs to the indexing worker or deployment setup.
    Readiness performs the bounded, read-only vector-store probe.
    """
    configure_logging()
    logger.info("API started; Qdrant collection setup is deferred to indexing")


app.include_router(auth_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(assistants_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(document_sets_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(connectors_router, prefix="/api/v1")
app.include_router(chat_shares_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "status": "API is running"
    }


@app.get("/health")
def health():
    """Lightweight, side-effect-free process liveness probe."""
    return {"status": "alive"}


@app.get("/api/metrics", include_in_schema=False)
@app.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Expose minimal operational metrics only with an explicitly configured token."""
    expected = f"Bearer {METRICS_BEARER_TOKEN}" if METRICS_BEARER_TOKEN else ""
    if not expected or not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        queue_depth = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status.in_(["queued", "retrying"]))) or 0
        active_jobs = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == "running")) or 0
        failed_jobs = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == "dead_letter")) or 0
        failed_connectors = db.scalar(select(func.count()).select_from(Connector).where(Connector.status == "dead_letter")) or 0
        total_cost = db.scalar(select(func.coalesce(func.sum(LLMUsage.estimated_cost_usd), 0))) or 0
        pending_outbox = db.scalar(select(func.count()).select_from(IndexingOutbox).where(IndexingOutbox.status == "pending")) or 0
        pending_alerts = db.scalar(select(func.count()).select_from(OperationalAlert).where(OperationalAlert.status.in_(("queued", "retrying", "sending")))) or 0
        dead_alerts = db.scalar(select(func.count()).select_from(OperationalAlert).where(OperationalAlert.status == "dead_letter")) or 0
    except SQLAlchemyError:
        logger.exception("Could not build operational metrics snapshot")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Metrics snapshot unavailable")
    return PlainTextResponse(render({
        "document_queue_depth": queue_depth,
        "document_jobs_running": active_jobs,
        "document_jobs_dead_letter": failed_jobs,
        "connectors_dead_letter": failed_connectors,
        "llm_estimated_cost_usd_total": total_cost,
        "indexing_outbox_pending": pending_outbox,
        "operational_alerts_pending": pending_alerts,
        "operational_alerts_dead_letter": dead_alerts,
    }), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/ready")
def readiness(response: Response, db: Session = Depends(get_db)):
    checks: dict[str, str] = {}
    failures: list[str] = []

    # Database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except SQLAlchemyError as exc:
        logger.warning("Health check database probe failed: %s", exc)
        checks["database"] = "unavailable"
        failures.append("database")

    # Qdrant vector store availability (critical for RAG)
    try:
        client = get_vector_store()
        client.check_ready(timeout_seconds=READINESS_PROBE_TIMEOUT_SECONDS)
        checks["qdrant"] = "connected"
    except VectorStoreError as exc:
        logger.warning("Health check qdrant probe failed: %s", exc)
        checks["qdrant"] = "unavailable"
        failures.append("qdrant")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check qdrant probe unexpected failure: %s", exc)
        checks["qdrant"] = "unavailable"
        failures.append("qdrant")

    # Document storage availability without creating or deleting probe files
    try:
        upload_root = Path(UPLOAD_DIR) if UPLOAD_DIR else None
        if upload_root is None:
            checks["storage"] = "misconfigured"
            failures.append("storage")
        elif not upload_root.is_dir() or not os.access(upload_root, os.W_OK):
            checks["storage"] = "unavailable"
            failures.append("storage")
        else:
            checks["storage"] = "writable"
    except OSError as exc:
        logger.warning("Health check storage probe failed: %s", exc)
        checks["storage"] = "unavailable"
        failures.append("storage")

    # Background workers required for ingestion and scheduled connector syncs
    required_worker_types = ("document_worker", "connector_scheduler")
    try:
        available_worker_types = get_available_worker_types(WORKER_STALE_THRESHOLD_SECONDS)
    except SQLAlchemyError as exc:
        logger.warning("Health check worker registry probe failed: %s", exc)
        available_worker_types = set()
    for worker_type in required_worker_types:
        available = worker_type in available_worker_types
        checks[worker_type] = "available" if available else "unavailable"
        if not available:
            failures.append(worker_type)

    overall_status = "healthy" if not failures else "degraded"
    status_code = status.HTTP_200_OK if not failures else status.HTTP_503_SERVICE_UNAVAILABLE
    response.status_code = status_code

    return {
        "status": overall_status,
        "checks": checks,
        "failures": failures,
    }
