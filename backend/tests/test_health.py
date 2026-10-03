import unittest
from unittest.mock import MagicMock, patch

from fastapi import Response, status
from sqlalchemy.exc import SQLAlchemyError

from app.main import health, readiness, startup_collection_setup
from app.services.qdrant import QdrantError


class HealthCheckTests(unittest.TestCase):
    def test_startup_does_not_connect_to_qdrant(self):
        with patch("app.main.get_vector_store") as qdrant:
            import asyncio
            asyncio.run(startup_collection_setup())

        qdrant.assert_not_called()

    def test_liveness_is_lightweight(self):
        with (
            patch("app.main.get_vector_store") as qdrant,
            patch("app.main.get_available_worker_types") as workers,
        ):
            payload = health()

        self.assertEqual(payload, {"status": "alive"})
        qdrant.assert_not_called()
        workers.assert_not_called()

    def test_dependency_failure_returns_service_unavailable(self):
        db = MagicMock()
        db.execute.side_effect = SQLAlchemyError("database unavailable")
        response = Response()

        with (
            patch("app.main.get_vector_store", side_effect=QdrantError("qdrant unavailable")),
            patch("app.main.UPLOAD_DIR", ""),
            patch("app.main.get_available_worker_types", return_value=set()),
        ):
            payload = readiness(response, db)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(
            payload["failures"],
            ["database", "qdrant", "storage", "document_worker", "connector_scheduler"],
        )

    def test_missing_required_workers_returns_service_unavailable(self):
        db = MagicMock()
        response = Response()
        upload_root = MagicMock()
        upload_root.is_dir.return_value = True

        with (
            patch("app.main.get_vector_store"),
            patch("app.main.Path", return_value=upload_root),
            patch("app.main.os.access", return_value=True),
            patch("app.main.UPLOAD_DIR", "uploads"),
            patch("app.main.get_available_worker_types", return_value=set()),
        ):
            payload = readiness(response, db)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(payload["checks"]["document_worker"], "unavailable")
        self.assertEqual(payload["checks"]["connector_scheduler"], "unavailable")

    def test_fresh_required_workers_keep_service_healthy(self):
        db = MagicMock()
        response = Response()
        upload_root = MagicMock()
        upload_root.is_dir.return_value = True

        with (
            patch("app.main.get_vector_store"),
            patch("app.main.Path", return_value=upload_root),
            patch("app.main.os.access", return_value=True),
            patch("app.main.UPLOAD_DIR", "uploads"),
            patch(
                "app.main.get_available_worker_types",
                return_value={"document_worker", "connector_scheduler"},
            ),
        ):
            payload = readiness(response, db)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["failures"], [])

    def test_readiness_storage_probe_does_not_write(self):
        db = MagicMock()
        response = Response()
        upload_root = MagicMock()
        upload_root.is_dir.return_value = True

        with (
            patch("app.main.get_vector_store"),
            patch("app.main.Path", return_value=upload_root),
            patch("app.main.os.access", return_value=True),
            patch("app.main.UPLOAD_DIR", "uploads"),
            patch(
                "app.main.get_available_worker_types",
                return_value={"document_worker", "connector_scheduler"},
            ),
        ):
            readiness(response, db)

        upload_root.mkdir.assert_not_called()
        upload_root.write_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
