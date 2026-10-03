from urllib.parse import urlparse
from collections.abc import Iterator
from pathlib import Path
from . import transport
from .contracts import ConnectorSyncError, SourceSnapshot, ALLOWED_EXTENSIONS

def _sharepoint(source_url: str, credentials: dict[str, str]) -> SourceSnapshot:
    tenant_id = credentials.get("tenant_id", ""); client_id = credentials.get("client_id", ""); client_secret = credentials.get("client_secret", "")
    if not all((tenant_id, client_id, client_secret)): raise ConnectorSyncError("SharePoint OAuth configuration is missing for this organization")
    parsed = urlparse(source_url)
    if parsed.hostname != "graph.microsoft.com" or "/children" not in parsed.path: raise ConnectorSyncError("Use a Microsoft Graph drive folder children URL")
    token = transport._oauth_token(f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token", {"client_id": client_id, "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})

    snapshot = SourceSnapshot(source_iterator=iter([]))

    def _iter() -> Iterator[tuple[str, str, str, str]]:
        next_url: str | None = source_url
        complete = True
        while next_url:
            data = transport._authorized_json(next_url, token)
            for item in data.get("value", []):
                snapshot.observed_ids.add(item["id"])
                name = item.get("name", ""); download = item.get("@microsoft.graph.downloadUrl")
                if not download or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS: continue
                body, _, final = transport._fetch(download); text = body.decode("utf-8", errors="replace").strip()
                if len(text) >= 20:
                    yield (item["id"], name[:255], text, item.get("webUrl") or final)
            next_url = data.get("@odata.nextLink")
            if not next_url:
                complete = "value" in data
        snapshot.complete = complete

    snapshot.source_iterator = _iter()
    return snapshot
