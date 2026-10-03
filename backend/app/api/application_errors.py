"""Translate application failures at the HTTP boundary."""

from fastapi import HTTPException

from app.core.application_errors import ApplicationError

_STATUS_BY_KIND = {
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "validation_error": 422,
    "internal_error": 500,
    "upstream_unavailable": 502,
    "service_unavailable": 503,
}


def to_http_exception(error: ApplicationError) -> HTTPException:
    return HTTPException(status_code=_STATUS_BY_KIND[error.kind], detail=error.detail)
