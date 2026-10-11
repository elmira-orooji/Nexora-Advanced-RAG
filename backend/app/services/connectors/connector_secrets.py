"""On-demand, organization-scoped connector credential retrieval."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import (
    CONNECTOR_SECRET_MANAGER_TIMEOUT_SECONDS,
    CONNECTOR_SECRET_MANAGER_TOKEN,
    CONNECTOR_SECRET_MANAGER_URL,
)


class ConnectorSecretError(RuntimeError):
    pass


def get_connector_credentials(
    organization_id: UUID,
    connector_type: str,
) -> dict[str, str]:
    """Fetch only one organization's provider credentials for the current sync."""
    if not CONNECTOR_SECRET_MANAGER_URL or not CONNECTOR_SECRET_MANAGER_TOKEN:
        raise ConnectorSecretError("Connector secret manager is not configured")
    if urlparse(CONNECTOR_SECRET_MANAGER_URL).scheme != "https":
        raise ConnectorSecretError("Connector secret manager must use HTTPS")

    organization = quote(str(organization_id), safe="")
    provider = quote(connector_type, safe="")
    request = Request(
        f"{CONNECTOR_SECRET_MANAGER_URL}/v1/organizations/{organization}/connectors/{provider}",
        method="GET",
        headers={
            "Authorization": f"Bearer {CONNECTOR_SECRET_MANAGER_TOKEN}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=CONNECTOR_SECRET_MANAGER_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ConnectorSecretError(
            f"Secret manager returned HTTP {exc.code} for this organization and provider"
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ConnectorSecretError("Connector secret manager is unavailable") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorSecretError("Secret manager returned an invalid response") from exc

    if not isinstance(payload, dict) or not payload:
        raise ConnectorSecretError(
            f"{connector_type} credentials are not configured for this organization"
        )
    return {str(key): str(value) for key, value in payload.items()}
