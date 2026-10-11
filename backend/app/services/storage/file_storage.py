"""Crash-safe helpers for files owned by the document pipeline."""

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write ``content`` to a same-directory temporary file, then replace it.

    A reader sees either the previous complete file or the new complete file,
    never a partially written extraction. The temporary file stays on the same
    filesystem so ``os.replace`` is atomic.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
