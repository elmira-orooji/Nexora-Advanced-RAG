import re
from urllib.parse import urlparse, parse_qs, quote, urlencode
from collections.abc import Iterator
from pathlib import Path
from . import transport
from .contracts import ConnectorSyncError, SourceSnapshot, ALLOWED_EXTENSIONS

def _google_drive(source_url: str, credentials: dict[str, str]) -> SourceSnapshot:
    client_id = credentials.get("client_id", ""); client_secret = credentials.get("client_secret", ""); refresh_token = credentials.get("refresh_token", "")
    if not all((client_id, client_secret, refresh_token)): raise ConnectorSyncError("Google Drive OAuth configuration is missing for this organization")
    match = re.search(r"/folders/([\w-]+)", source_url); folder_id = match.group(1) if match else parse_qs(urlparse(source_url).query).get("id", [None])[0]
    if not folder_id: raise ConnectorSyncError("Use a Google Drive folder URL")
    token = transport._oauth_token("https://oauth2.googleapis.com/token", {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})
    query = quote(f"'{folder_id}' in parents and trashed=false")

    snapshot = SourceSnapshot(source_iterator=iter([]), complete=True)

    def _iter() -> Iterator[tuple[str, str, str, str]]:
        page_token = None
        complete = True
        while True:
            params: dict[str, str] = {"pageSize": "200", "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,webViewLink,modifiedTime)"}
            if page_token:
                params["pageToken"] = page_token
            data = transport._authorized_json(f"https://www.googleapis.com/drive/v3/files?q={query}&{urlencode(params)}", token)
            for item in data.get("files", []):
                snapshot.observed_ids.add(item["id"])
                mime = item.get("mimeType", ""); name = item.get("name", "Untitled")
                if mime == "application/vnd.google-apps.document": url = f"https://www.googleapis.com/drive/v3/files/{item['id']}/export?mimeType=text/plain"
                elif Path(name).suffix.lower() in ALLOWED_EXTENSIONS: url = f"https://www.googleapis.com/drive/v3/files/{item['id']}?alt=media"
                else: continue
                text = transport._bearer_download(url, token).decode("utf-8", errors="replace").strip()
                if len(text) >= 20:
                    yield (item["id"], name[:255], text, item.get("webViewLink") or source_url)
            if data.get("incompleteSearch"):
                complete = False
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        snapshot.complete = complete

    snapshot.source_iterator = _iter()
    return snapshot
