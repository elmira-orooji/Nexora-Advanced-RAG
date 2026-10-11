from collections.abc import Iterator
from dataclasses import dataclass, field

MAX_REMOTE_BYTES = 2 * 1024 * 1024
MAX_GITHUB_FILES = 40
ALLOWED_EXTENSIONS = {".md", ".txt", ".rst", ".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml"}
CLOUD_CONNECTORS = {"google_drive", "s3", "sharepoint"}

class ConnectorSyncError(RuntimeError):
    pass

@dataclass
class SourceSnapshot:
    """Streaming source contract.

    ``source_iterator`` yields ``(external_id, title, text, url)`` tuples one
    at a time so that only ``STREAM_BATCH_SIZE`` documents are ever held in
    RAM.  ``observed_ids`` is populated lazily as the iterator is consumed and
    **must** be read only after the iterator is exhausted (i.e. after the apply
    loop finishes).
    """
    source_iterator: Iterator[tuple[str, str, str, str]]
    observed_ids: set[str] = field(default_factory=set)
    complete: bool = False
