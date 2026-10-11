import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.storage.file_storage import atomic_write_text


class AtomicFileStorageTests(unittest.TestCase):
    def test_atomic_write_replaces_existing_complete_content(self):
        path = Path.cwd() / "extracted.txt"
        target = MagicMock()
        target.__enter__.return_value = target
        temporary = Path("temporary.txt")
        with patch("app.services.storage.file_storage.tempfile.mkstemp", return_value=(42, str(temporary))), patch(
            "app.services.storage.file_storage.os.fdopen", return_value=target
        ), patch("app.services.storage.file_storage.os.fsync") as fsync, patch(
            "app.services.storage.file_storage.os.replace"
        ) as replace:
            atomic_write_text(path, "replacement")

        target.write.assert_called_once_with("replacement")
        fsync.assert_called_once_with(target.fileno())
        replace.assert_called_once_with(temporary, path)
