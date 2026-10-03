import json
from urllib.parse import urlparse, quote
from collections.abc import Iterator
from pathlib import Path
from . import transport
from .contracts import ConnectorSyncError, SourceSnapshot, ALLOWED_EXTENSIONS
from .contracts import MAX_GITHUB_FILES

def _github(source_url: str) -> SourceSnapshot:
    transport._validate_public_url(source_url, github_only=True)
    parts = [part for part in urlparse(source_url).path.split("/") if part]
    if len(parts) < 2: raise ConnectorSyncError("Use a GitHub repository URL such as https://github.com/owner/repo")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    api = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/git/trees/HEAD?recursive=1"
    data, _, _ = transport._fetch(api, "application/vnd.github+json")
    try:
        metadata = json.loads(data)
        tree = metadata.get("tree", [])
    except json.JSONDecodeError as exc: raise ConnectorSyncError("GitHub returned invalid repository metadata") from exc
    files = [item for item in tree if item.get("type") == "blob" and Path(item.get("path", "")).suffix.lower() in ALLOWED_EXTENSIONS and int(item.get("size", 0)) <= 300_000]
    all_blob_ids = {item["path"] for item in tree if item.get("type") == "blob"}
    is_complete = metadata.get("truncated") is False and len(files) <= MAX_GITHUB_FILES

    snapshot = SourceSnapshot(source_iterator=iter([]), observed_ids=all_blob_ids, complete=is_complete)

    def _iter() -> Iterator[tuple[str, str, str, str]]:
        yielded = 0
        for item in files:
            if yielded >= MAX_GITHUB_FILES: break
            path = item["path"]; raw = f"https://raw.githubusercontent.com/{quote(owner)}/{quote(repo)}/HEAD/{quote(path)}"
            body, _, final = transport._fetch(raw); text = body.decode("utf-8", errors="replace").strip()
            if len(text) >= 20:
                yield (path, f"{repo}: {path}"[:255], text, final)
                yielded += 1
        if yielded == 0: raise ConnectorSyncError("No supported text files were found in this repository")

    snapshot.source_iterator = _iter()
    return snapshot
