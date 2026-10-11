# Nexora API contract

The browser client communicates with the backend through `/api/v1`. The major version is part of the URL and is the compatibility boundary. Existing fields and endpoint behavior in a major version remain available. Additive fields, optional query parameters and new endpoints are permitted in v1. Removing or renaming a field, changing its type, changing an error code, or changing authorization semantics requires a new major version.

Every `/api/v1` response includes `X-API-Version: 1` and `X-Request-ID`. Clients should store the request ID when reporting a failed operation.

## Authentication and request conventions

The API uses the session cookie established by `POST /api/v1/auth/login`. Browser requests must use credentials. JSON request bodies use `application/json`; document ingestion uses multipart form data. State-changing upload requests accept `Idempotency-Key`, which must be reused only for a retry of the same upload.

Key endpoint groups are versioned under the same prefix:

| Area | Base endpoint | Contract notes |
| --- | --- | --- |
| Authentication | `/auth` | Login, logout, current user and password change. Login returns a user object and sets an HttpOnly cookie. |
| Conversations | `/conversations` | Conversation CRUD and `/{id}/messages` for source-grounded chat. |
| Knowledge | `/documents`, `/document-sets` | Uploads are queued; a successful ingestion response contains the document status and `job_id`. |
| Assistants | `/assistants` | Assistant CRUD and scoped answers. |
| Connectors | `/document-sets/{set_id}/connectors` | Create, inspect and synchronize external content sources. |
| Administration | `/users`, `/analytics`, `/notifications` | Administrator-only member management, reporting and operational notifications. |

The live OpenAPI document is available from `/openapi.json` and the interactive documentation from `/docs` in non-restricted deployments. The checked-in contract in this file defines compatibility behavior when generated documentation and implementation differ.

## Error contract

v1 preserves FastAPI's `detail` property for compatibility. API errors also include an additive `error` object:

```json
{
  "detail": "Incorrect username or password",
  "error": {
    "code": "unauthorized",
    "message": "Incorrect username or password",
    "request_id": "a request correlation ID"
  }
}
```

Validation failures keep `detail` as an array of field failures and set `error.code` to `validation_error`. Clients should branch on `error.code`, show `error.message` when it is present, and retain `detail` parsing during the v1 transition.

| HTTP status | Stable code | Client behavior |
| --- | --- | --- |
| 400 | `bad_request` | Correct the request before retrying. |
| 401 | `unauthorized` | Clear the local session and return to sign-in. |
| 403 | `forbidden` | Do not retry without a permission change. |
| 404 | `not_found` | Refresh the parent collection or show that the resource no longer exists. |
| 409 | `conflict` | Refresh state; retry only if the user explicitly resolves the conflict. |
| 422 | `validation_error` | Display actionable field or request feedback. |
| 429 | `rate_limited` | Respect `Retry-After` when it is present. |
| 502, 503 | `upstream_unavailable`, `service_unavailable` | Show a retryable service message; do not fabricate a result. |

## Offset pagination

`GET /conversations` and `GET /documents` accept `offset` and `limit`. `offset` starts at `0`; `limit` defaults to `20` and is constrained to `1..100`. Their v1 response body remains an array for compatibility.

Pagination metadata is returned in headers:

- `X-Pagination-Offset`: offset used for this response.
- `X-Pagination-Limit`: requested page size.
- `X-Pagination-Returned`: number of resources returned.
- `X-Pagination-Has-More`: `true` when the page is full and another request may return more items.
- `X-Pagination-Next-Offset`: present only when `X-Pagination-Has-More` is `true`.

A full page is only a candidate for another page; clients must stop when the next response is empty or has `Has-More: false`. A future major version may use an explicit body envelope with totals or cursors, but v1 arrays will not be changed.

## Deprecation process

Before an incompatible change, Nexora adds the replacement behavior in a new major API version, keeps the previous major version available for a published migration window, and documents the replacement endpoint, field mapping and removal date. The frontend must support both versions during that window. No undocumented behavioral change is a valid deprecation mechanism.
