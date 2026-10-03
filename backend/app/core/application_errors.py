"""Application failures independent of HTTP and web frameworks."""

from typing import Any, Literal

ErrorKind = Literal[
    "bad_request", "unauthorized", "forbidden", "not_found", "conflict", "payload_too_large",
    "unsupported_media_type", "validation_error", "internal_error",
    "upstream_unavailable", "service_unavailable",
]


class ApplicationError(Exception):
    def __init__(self, *, kind: ErrorKind, detail: Any):
        super().__init__(str(detail))
        self.kind = kind
        self.detail = detail
