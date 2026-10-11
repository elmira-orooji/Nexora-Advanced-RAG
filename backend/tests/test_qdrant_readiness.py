import unittest
from unittest.mock import MagicMock

from app.services.providers.qdrant import QdrantClient


class QdrantReadinessTests(unittest.TestCase):
    def test_check_ready_uses_bounded_read_only_request(self):
        client = QdrantClient.__new__(QdrantClient)
        client.collection = "documents"
        client._request = MagicMock(return_value={"result": {}})

        client.check_ready(timeout_seconds=2)

        client._request.assert_called_once_with(
            "GET",
            "/collections/documents",
            timeout_seconds=2,
        )


if __name__ == "__main__":
    unittest.main()
