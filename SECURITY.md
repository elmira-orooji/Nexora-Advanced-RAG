# Security policy

Nexora processes organization-scoped documents, conversations, retrieval data, and optional connector credentials. A secure deployment therefore depends on both the application and its operating environment.

## Reporting a vulnerability

Do not disclose vulnerabilities, proof-of-concept exploits, credentials, or sensitive data in public GitHub issues, pull requests, discussions, or commits.

Report a suspected vulnerability through a private channel agreed with the Nexora project owner. Include the affected component, the relevant version or commit, reproduction steps, the expected and observed behavior, likely impact, and any evidence needed to validate the report. Share only the minimum sensitive information necessary.

The project owner will assess the report, coordinate remediation, and determine whether a public advisory is appropriate after a fix is available.

## Supported versions

Security fixes are applied to the current development branch and released versions when the affected code is still maintained. This repository does not currently publish a separate long-term-support release line.

## Deployment baseline

Production deployments must use HTTPS, set `APP_ENV=production`, set `AUTH_COOKIE_SECURE=true`, and provide a unique `AUTH_SECRET_KEY` with at least 32 random characters. `FRONTEND_ORIGINS` must contain only the deployed frontend origins. PostgreSQL, Qdrant, document storage, and internal worker endpoints must not be exposed directly to the public internet.

Store secrets in a deployment secret manager or protected environment variables. Do not place passwords, API keys, OAuth tokens, connector credentials, JWTs, private keys, or production configuration in the repository, Docker image, logs, tickets, or screenshots. Rotate any credential that may have been exposed.

The API should run behind a trusted reverse proxy or ingress that terminates TLS and supplies compatible security headers. Trust `X-Forwarded-For` only when it is set by that controlled proxy.

## Authentication and authorization

Nexora stores password hashes rather than plaintext passwords. Sessions are issued through signed, `HttpOnly`, `SameSite=Lax` cookies and are checked against the active server-side session record. Logout revokes the current session; a password change invalidates the user’s other sessions.

Authorization is enforced by the API. Interface visibility is not an access-control mechanism. Administrative operations require the `admin` role. Access to document sets, conversations, assistants, and connector data must remain constrained by organization context and the user’s assigned permissions.

Login throttling is configurable through the `AUTH_*` environment variables. Application-level rate limiting is process-local; multi-replica deployments should additionally enforce limits in a shared layer such as a reverse proxy, WAF, or Redis-backed limiter.

## File handling and malware scanning

The application accepts PDF, TXT, JPEG, PNG, and TIFF documents subject to file-name normalization, extension/MIME validation, file-signature checks where applicable, UTF-8 validation for text files, and a 100 MB per-file limit. The reverse proxy allows 110 MB per request to accommodate multipart overhead. Files are stored under generated identifiers and storage paths are resolved to prevent path traversal.

These controls do not detect malware. Before accepting untrusted files in production, deploy a quarantine-and-scan workflow:

1. Place each upload in isolated quarantine storage.
2. Scan it before text extraction, OCR, indexing, download, or connector processing.
3. Promote only files with a recorded clean result.
4. Block processing if the scanner is unavailable in production.
5. Log the scan result, timestamp, file hash, and rejection reason without recording document contents or secrets.

When cloud OCR is enabled, the original document may be sent to the selected provider. Enable it only when the organization’s data classification, processing agreement, and retention policy permit that transfer.

## Connectors and sharing

Configure connectors with least-privilege service accounts, narrowly scoped permissions, domain allowlists, and short-lived credentials where available. Do not permit web connectors to reach private networks, metadata services, or unapproved destinations.

Shared conversation links are read-only snapshots. Anyone with a public link token can access its content until the link expires or is revoked. Do not create public links for conversations containing sensitive information. Owners and organization administrators should be able to revoke links promptly.

## Logging, retention, and recovery

Logs must not contain passwords, session tokens, cookies, authorization headers, API keys, full document text, or full conversation content. Security-relevant events should include failed sign-ins, account lockouts, password changes, access denials, connector failures, and shared-link revocations, with an event identifier and timestamp.

Retention and deletion procedures must cover original documents, extracted text, vectors, conversations, backups, and logs. Deleting a document must remove its associated stored content and retrieval vectors according to the organization’s retention policy. See [DATA_RETENTION_AND_PRIVACY.md](DATA_RETENTION_AND_PRIVACY.md) and [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).

## Security verification

Before a release or production deployment, verify the following:

- tests and CI checks pass;
- dependency updates and known vulnerabilities are reviewed;
- organization isolation and role-based access are tested at the API boundary;
- TLS, CORS, secure cookies, reverse-proxy headers, and rate limits are validated in staging;
- uploaded-file limits and the malware quarantine workflow are tested with safe test fixtures, including EICAR only after an antivirus service is configured;
- connector scopes, secret storage, and outbound network restrictions are reviewed;
- backup restoration is tested using the documented recovery procedure.

## Public repository notice

Nexora is proprietary, source-available software. Public access to this repository does not grant permission to use, copy, modify, distribute, deploy, or contribute to the software. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).

Before changing repository visibility, rotate real credentials used in development or deployment, review repository history and media for sensitive information, and confirm that `.env` files, uploaded data, backups, keys, and local storage are not tracked. Enable GitHub secret scanning and push protection when the repository and account plan support them.
