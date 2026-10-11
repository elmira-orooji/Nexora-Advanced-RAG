import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.connectors import connector_secrets


class ConnectorSecretTests(unittest.TestCase):
    def test_service_token_is_never_sent_over_plain_http(self):
        with (
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_URL", "http://secrets.internal"),
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_TOKEN", "service-token"),
            patch.object(connector_secrets, "urlopen") as open_request,
            self.assertRaises(connector_secrets.ConnectorSecretError),
        ):
            connector_secrets.get_connector_credentials(uuid4(), "s3")

        open_request.assert_not_called()

    def test_fetch_is_scoped_to_organization_and_provider(self):
        organization_id = uuid4()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"client_id": "tenant-client", "client_secret": "secret"}
        ).encode()

        with (
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_URL", "https://secrets.internal"),
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_TOKEN", "service-token"),
            patch.object(connector_secrets, "urlopen", return_value=response) as open_request,
        ):
            credentials = connector_secrets.get_connector_credentials(
                organization_id,
                "google_drive",
            )

        request = open_request.call_args.args[0]
        self.assertEqual(
            request.full_url,
            f"https://secrets.internal/v1/organizations/{organization_id}/connectors/google_drive",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer service-token")
        self.assertEqual(credentials["client_id"], "tenant-client")

    def test_credentials_are_fetched_on_every_call_for_rotation(self):
        first = MagicMock()
        first.__enter__.return_value.read.return_value = b'{"secret":"old"}'
        second = MagicMock()
        second.__enter__.return_value.read.return_value = b'{"secret":"rotated"}'

        with (
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_URL", "https://secrets.internal"),
            patch.object(connector_secrets, "CONNECTOR_SECRET_MANAGER_TOKEN", "service-token"),
            patch.object(connector_secrets, "urlopen", side_effect=[first, second]) as open_request,
        ):
            old = connector_secrets.get_connector_credentials(uuid4(), "s3")
            rotated = connector_secrets.get_connector_credentials(uuid4(), "s3")

        self.assertEqual(open_request.call_count, 2)
        self.assertEqual(old["secret"], "old")
        self.assertEqual(rotated["secret"], "rotated")


if __name__ == "__main__":
    unittest.main()
