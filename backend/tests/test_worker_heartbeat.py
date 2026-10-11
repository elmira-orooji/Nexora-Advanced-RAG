import threading
import unittest
from unittest.mock import patch

from app.services.operations.worker_heartbeat import maintain_worker_heartbeat


class WorkerHeartbeatLoopTests(unittest.TestCase):
    def test_heartbeat_continues_while_main_work_is_blocked(self):
        heartbeat_sent = threading.Event()

        def send(_worker_id):
            heartbeat_sent.set()
            return True

        with patch("app.services.operations.worker_heartbeat.send_heartbeat", side_effect=send) as mocked_send:
            with maintain_worker_heartbeat(
                "worker-1",
                "document_worker",
                {"pid": 1},
                interval_seconds=0.01,
            ):
                self.assertTrue(heartbeat_sent.wait(timeout=1))

        mocked_send.assert_called()

    def test_missing_worker_is_registered_again(self):
        heartbeat_sent = threading.Event()

        def send(_worker_id):
            heartbeat_sent.set()
            return False

        with (
            patch("app.services.operations.worker_heartbeat.send_heartbeat", side_effect=send),
            patch("app.services.operations.worker_heartbeat.register_worker") as register,
        ):
            with maintain_worker_heartbeat(
                "worker-1",
                "connector_scheduler",
                {"pid": 1},
                interval_seconds=0.01,
            ):
                self.assertTrue(heartbeat_sent.wait(timeout=1))

        register.assert_called_with("worker-1", "connector_scheduler", {"pid": 1})


if __name__ == "__main__":
    unittest.main()
