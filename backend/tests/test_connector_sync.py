from app.services.connector_sources import transport, s3
import io
import hashlib
import json
import shutil
import socket
import ssl
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.request import Request
from types import SimpleNamespace
from uuid import uuid4

from app.services import connector_sync as sync


class ConnectorDeletionTests(unittest.TestCase):
    s3_credentials = {"access_key_id": "test", "secret_access_key": "test", "region": "us-east-1"}

    def run_github_sync(self, count, truncated=False):
        body = b"A supported document with enough text."
        tree = [{"type": "blob", "path": f"{i}.md", "size": 100} for i in range(count)]
        metadata = json.dumps({"tree": tree, "truncated": truncated}).encode()
        db = MagicMock()
        connector_id = uuid4()
        document_set_id = uuid4()
        connector = SimpleNamespace(id=connector_id, document_set_id=document_set_id, connector_type="github", source_url="https://github.com/owner/repo")
        items = [SimpleNamespace(external_id=f"{i}.md", document_id=uuid4(), content_hash=hashlib.sha256(body).hexdigest()) for i in range(count)]
        missing = SimpleNamespace(external_id="absent.md", document_id=uuid4())
        all_items = sorted(items + [missing], key=lambda it: it.external_id)

        def scalars_side_effect(query):
            # Support both the batched apply-phase queries (filtered by external_id list)
            # and the paginated deletion-phase queries (ordered + limited).
            mock_result = MagicMock()
            compiled = query.compile()
            params = compiled.params if hasattr(compiled, "params") else {}
            ordered = list(all_items)
            for key, value in params.items():
                if key.startswith("external_id_") and isinstance(value, list):
                    allowed = set(value)
                    ordered = [it for it in ordered if it.external_id in allowed]
                elif key.startswith("external_id_") and isinstance(value, str):
                    ordered = [it for it in ordered if it.external_id > value]
            limit_param = next((v for k, v in params.items() if k.startswith("param_") and isinstance(v, int)), None)
            if limit_param is not None:
                ordered = ordered[:limit_param]
            mock_result.all.return_value = ordered
            return mock_result

        db.scalars.side_effect = scalars_side_effect
        document = SimpleNamespace(
            id=missing.document_id,
            filename="absent.md",
            storage_path="uploads/absent/source.txt",
            extracted_text_path="uploads/absent/extracted.txt",
            chunks=[],
            document_sets=[SimpleNamespace(id=document_set_id)],
        )
        def get_side_effect(model, key):
            if model is sync.Connector:
                return connector
            if model is sync.DocumentSet:
                return SimpleNamespace(id=document_set_id, organization_id=uuid4())
            return document
        db.get.side_effect = get_side_effect
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch.object(sync, "SessionLocal", session_factory), patch.object(transport, "_validate_public_url"), patch.object(transport, "_fetch", side_effect=lambda url, *args: (metadata if "api.github.com" in url else body, "text/plain", url)), patch.object(sync, "get_vector_store") as qdrant, patch.object(sync.shutil, "rmtree") as remove:
            result = sync.sync_connector(connector_id)
        return result, db, qdrant.return_value, remove

    def test_github_limit_does_not_delete_unfetched_documents(self):
        result, db, qdrant, remove = self.run_github_sync(41)
        self.assertEqual(result["unchanged"], 40)
        self.assertEqual(result["deleted"], 0)
        db.delete.assert_not_called()
        qdrant.delete_document.assert_not_called()
        remove.assert_not_called()

    def test_github_truncated_tree_does_not_delete_documents(self):
        result, db, qdrant, remove = self.run_github_sync(2, truncated=True)
        self.assertEqual(result["deleted"], 0)
        db.delete.assert_not_called()
        qdrant.delete_document.assert_not_called()

    def test_complete_github_tree_still_deletes_missing_document(self):
        result, db, qdrant, remove = self.run_github_sync(2)
        self.assertEqual(result["deleted"], 1)
        qdrant.delete_document.assert_called_once()

    def test_s3_large_listing_without_truncation_is_complete(self):
        """With streaming, all items on a non-truncated page are consumed regardless of count."""
        listing = ("<ListBucketResult><IsTruncated>false</IsTruncated>" + "".join(f"<Contents><Key>{i}.md</Key></Contents>" for i in range(101)) + "</ListBucketResult>").encode()
        with patch.object(s3, "_aws_signed_get", side_effect=lambda url, credentials: listing if "list-type" in url else b"Enough text for this supported document."):
            result = sync._s3("https://bucket.s3.amazonaws.com/", self.s3_credentials)
            list(result.source_iterator)
        self.assertTrue(result.complete)
        self.assertIn("100.md", result.observed_ids)

    def test_s3_truncated_listing_is_incomplete(self):
        with patch.object(s3, "_aws_signed_get", return_value=b"<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>"):
            result = sync._s3("https://bucket.s3.amazonaws.com/", self.s3_credentials)
            list(result.source_iterator)
            self.assertFalse(result.complete)

    def test_google_drive_incomplete_search_disables_deletion(self):
        credentials = {"client_id": "test", "client_secret": "test", "refresh_token": "test"}
        responses = [{"files": [], "incompleteSearch": True}, {"files": []}]
        with patch.object(transport, "_oauth_token", return_value="token"), patch.object(transport, "_authorized_json", side_effect=responses) as request:
            result = sync._google_drive("https://drive.google.com/drive/folders/folder", credentials)
            list(result.source_iterator)
            self.assertFalse(result.complete)
            self.assertIn("incompleteSearch", request.call_args_list[0].args[0])

    def test_google_drive_pagination_is_fully_consumed(self):
        """With streaming, nextPageToken triggers further pages rather than marking incomplete."""
        credentials = {"client_id": "test", "client_secret": "test", "refresh_token": "test"}
        responses = [{"files": [], "nextPageToken": "next"}, {"files": []}]
        with patch.object(transport, "_oauth_token", return_value="token"), patch.object(transport, "_authorized_json", side_effect=responses) as request:
            result = sync._google_drive("https://drive.google.com/drive/folders/folder", credentials)
            list(result.source_iterator)
            self.assertTrue(result.complete)
            self.assertEqual(request.call_count, 2)

    def test_sharepoint_pagination_is_fully_consumed(self):
        """With streaming, @odata.nextLink triggers further pages rather than marking incomplete."""
        credentials = {"tenant_id": "test", "client_id": "test", "client_secret": "test"}
        responses = [{"value": [], "@odata.nextLink": "next"}, {"value": []}]
        with patch.object(transport, "_oauth_token", return_value="token"), patch.object(transport, "_authorized_json", side_effect=responses) as request:
            result = sync._sharepoint("https://graph.microsoft.com/drive/root/children", credentials)
            list(result.source_iterator)
            self.assertTrue(result.complete)
            self.assertEqual(request.call_count, 2)

    def test_seen_but_skipped_file_is_preserved_even_with_complete_listing(self):
        db = MagicMock()
        item = SimpleNamespace(external_id="short.md", document_id=uuid4())
        db.scalars.return_value.all.return_value = [item]
        connector_id = uuid4()
        document_set_id = uuid4()
        connector = SimpleNamespace(id=connector_id, document_set_id=document_set_id, connector_type="github", source_url="https://github.com/owner/repo")
        document_set = SimpleNamespace(id=document_set_id, organization_id=uuid4())
        metadata = json.dumps({"tree": [{"type": "blob", "path": "short.md", "size": 3}, {"type": "blob", "path": "large.md", "size": 400000}], "truncated": False}).encode()
        # A supported file keeps this fetch successful; the short and oversized
        # files must still be recorded as present in the source inventory.
        metadata = json.loads(metadata)
        metadata["tree"].append({"type": "blob", "path": "good.md", "size": 100})
        body = b"Enough content to index this supported file."
        db.scalars.return_value.all.return_value += [SimpleNamespace(external_id="good.md", document_id=uuid4(), content_hash=hashlib.sha256(body).hexdigest()), SimpleNamespace(external_id="large.md", document_id=uuid4())]
        all_items = sorted(db.scalars.return_value.all.return_value, key=lambda value: value.external_id)
        def scalars_page(query):
            items = all_items
            for key, value in query.compile().params.items():
                if key.startswith("external_id_"):
                    items = [item for item in items if item.external_id in value] if isinstance(value, list) else [item for item in items if item.external_id > value]
            result = MagicMock()
            result.all.return_value = items
            return result
        db.scalars.side_effect = scalars_page
        def fetch(url, *args):
            data = json.dumps(metadata).encode() if "api.github.com" in url else (b"abc" if "short.md" in url else body)
            return data, "text/plain", url
        def get_side_effect(model, key):
            if model is sync.Connector:
                return connector
            if model is sync.DocumentSet:
                return document_set
            return None
        db.get.side_effect = get_side_effect
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch.object(sync, "SessionLocal", session_factory), patch.object(transport, "_validate_public_url"), patch.object(transport, "_fetch", side_effect=fetch), patch.object(sync, "get_vector_store") as qdrant:
            result = sync.sync_connector(connector_id)
        self.assertEqual(result["deletion_skipped"], 0)
        self.assertEqual(result["deleted"], 0)
        db.delete.assert_not_called()
        qdrant.return_value.delete_document.assert_not_called()

    def test_failed_fetch_does_not_start_reconciliation(self):
        db = MagicMock()
        connector_id = uuid4()
        connector = SimpleNamespace(id=connector_id, document_set_id=uuid4(), connector_type="github", source_url="https://github.com/owner/repo")
        db.get.return_value = connector
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch.object(sync, "SessionLocal", session_factory), patch.object(sync, "_github", side_effect=sync.ConnectorSyncError("Download failed")), patch.object(sync, "get_vector_store") as qdrant:
            with self.assertRaises(sync.ConnectorSyncError):
                sync.sync_connector(connector_id)
        db.delete.assert_not_called()
        db.commit.assert_not_called()
        qdrant.assert_not_called()


class ConnectorCredentialIsolationTests(unittest.TestCase):
    def test_credentials_are_selected_by_organization_and_provider(self):
        first, second = uuid4(), uuid4()
        with patch.object(
            sync,
            "get_connector_credentials",
            side_effect=[{"client_id": "first"}, {"client_id": "second"}],
        ):
            self.assertEqual(sync._organization_credentials(first, "google_drive")["client_id"], "first")
            self.assertEqual(sync._organization_credentials(second, "google_drive")["client_id"], "second")

    def test_cloud_connector_has_no_global_credential_fallback(self):
        with patch.object(
            sync,
            "get_connector_credentials",
            side_effect=sync.ConnectorSecretError("missing"),
        ), self.assertRaises(sync.ConnectorSyncError):
            sync._organization_credentials(uuid4(), "s3")

    def test_sync_passes_only_owning_organizations_credentials(self):
        organization_id, set_id = uuid4(), uuid4()
        connector_id = uuid4()
        connector = SimpleNamespace(
            id=connector_id, document_set_id=set_id, connector_type="google_drive",
            source_url="https://drive.google.com/drive/folders/folder", last_sync_summary={},
        )
        document_set = SimpleNamespace(id=set_id, organization_id=organization_id)
        db = MagicMock()
        def get_side_effect(model, key):
            if model is sync.Connector:
                return connector
            if model is sync.DocumentSet:
                return document_set
            return None
        db.get.side_effect = get_side_effect
        db.scalars.return_value.all.return_value = []
        credentials = {"client_id": "owned", "client_secret": "secret", "refresh_token": "refresh"}
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)

        with patch.object(sync, "SessionLocal", session_factory), patch.object(sync, "get_connector_credentials", return_value=credentials), patch.object(
            sync, "_google_drive", return_value=sync.SourceSnapshot(source_iterator=iter([]), observed_ids=set(), complete=False)
        ) as fetch, patch.object(sync, "get_vector_store"):
            sync.sync_connector(connector_id)

        fetch.assert_called_once_with(connector.source_url, credentials)


class ConnectorConsistencyTests(unittest.TestCase):
    def test_connector_document_uses_extracted_file_as_retryable_source(self):
        document_id, set_id = uuid4(), uuid4()
        connector_id = uuid4()
        connector = SimpleNamespace(id=connector_id, document_set_id=set_id, connector_type="website", source_url="https://example.com", last_sync_summary={})
        item = SimpleNamespace(external_id="https://example.com", document_id=document_id, content_hash="old", source_url="", title="Old")
        document_set = SimpleNamespace(id=set_id, organization_id=uuid4(), child_chunk_size=800, chunk_overlap=120, parent_chunk_size=2400)
        document = SimpleNamespace(id=document_id, filename="Old", storage_path=None, extracted_text_path=None, chunks=[], document_sets=[document_set], processing_error=None, status="indexed", content_checksum=None)
        db = MagicMock()
        db.scalars.return_value.all.side_effect = [[item], [item], []]
        def get_side_effect(model, key):
            if model is sync.Connector:
                return connector
            if model is sync.DocumentSet:
                return document_set
            return document
        db.get.side_effect = get_side_effect
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        snapshot = sync.SourceSnapshot(source_iterator=iter([("https://example.com", "Page", "new content", "https://example.com")]), observed_ids={"https://example.com"}, complete=True)
        base = Path.cwd() / "storage" / f"connector-source-{uuid4()}"
        try:
            upload_dir = base / "uploads"
            with patch.object(sync, "SessionLocal", session_factory), patch.object(sync, "BASE_DIR", base), patch.object(sync, "UPLOAD_DIR", upload_dir), patch.object(sync, "document_storage_relative", side_effect=lambda path: path.relative_to(upload_dir).as_posix()), patch.object(sync, "_website", return_value=snapshot), patch.object(sync, "incremental_chunks", return_value=([], [], [])), patch.object(sync, "get_vector_store"):
                sync.sync_connector(connector_id)
            self.assertEqual(document.storage_path, document.extracted_text_path)
            apply_query = db.scalars.call_args_list[0].args[0]
            self.assertEqual(
                apply_query.compile().params["external_id_1"],
                ["https://example.com"],
            )
            resolved = (upload_dir / document.storage_path).resolve()
            self.assertTrue(resolved.is_file())
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def _run_failed_update(self, *, commit_failure=None, qdrant_failure=None):
        connector_id, set_id, document_id, chunk_id = uuid4(), uuid4(), uuid4(), uuid4()
        connector = SimpleNamespace(
            id=connector_id,
            document_set_id=set_id,
            connector_type="website",
            source_url="https://example.com",
            last_sync_summary={},
        )
        item = SimpleNamespace(
            external_id="https://example.com",
            document_id=document_id,
            content_hash="old-hash",
            source_url="https://example.com",
            title="Old title",
        )
        old_chunk = SimpleNamespace(id=chunk_id, chunk_index=0, content="old content")
        new_chunk = SimpleNamespace(id=uuid4(), chunk_index=0, content="new content")
        document_set = SimpleNamespace(
            id=set_id,
            organization_id=uuid4(),
            child_chunk_size=800,
            chunk_overlap=120,
            parent_chunk_size=2400,
        )
        document = SimpleNamespace(
            id=document_id,
            filename="Old title",
            chunks=[old_chunk],
            document_sets=[document_set],
            extracted_text_path=None,
            processing_error=None,
            status="indexed",
            content_checksum="old-checksum",
        )
        db = MagicMock()
        db.scalars.return_value.all.return_value = [item]
        def get_side_effect(model, key):
            if model is sync.Connector:
                return connector
            if model is sync.DocumentSet:
                return document_set
            return document
        db.get.side_effect = get_side_effect
        db.commit.side_effect = commit_failure
        session_factory = MagicMock(return_value=db)
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        snapshot = sync.SourceSnapshot(
            source_iterator=iter([("https://example.com", "New title", "new remote content", "https://example.com")]),
            observed_ids={"https://example.com"},
            complete=True,
        )
        base = Path.cwd() / "storage" / f"connector-consistency-{uuid4()}"
        base.mkdir(parents=True)
        try:
            upload = base / "uploads"
            extracted = upload / str(document_id) / "extracted.txt"
            extracted.parent.mkdir(parents=True)
            extracted.write_text("old extracted content", encoding="utf-8")
            document.extracted_text_path = extracted.relative_to(base).as_posix()
            with (
                patch.object(sync, "SessionLocal", session_factory),
                patch.object(sync, "BASE_DIR", base),
                patch.object(sync, "UPLOAD_DIR", upload),
                patch.object(sync, "_website", return_value=snapshot),
                patch.object(sync, "incremental_chunks", return_value=([new_chunk], [str(new_chunk.id)], [str(old_chunk.id)])),
                patch.object(sync, "get_vector_store") as factory,
            ):
                client = factory.return_value
                if qdrant_failure is not None:
                    client.replace_document_chunks.side_effect = [qdrant_failure, None]
                with self.assertRaises(Exception):
                    sync.sync_connector(connector_id)
                restored = extracted.read_text(encoding="utf-8")
        finally:
            shutil.rmtree(base, ignore_errors=True)
        return db, factory.return_value, document_id, chunk_id, restored

    def test_failed_sql_commit_restores_file_and_previous_vectors(self):
        db, qdrant, document_id, chunk_id, restored = self._run_failed_update(
            commit_failure=RuntimeError("commit failed")
        )
        db.rollback.assert_called_once()
        self.assertEqual(restored, "old extracted content")
        self.assertEqual(qdrant.replace_document_chunks.call_count, 2)
        compensation = qdrant.replace_document_chunks.call_args_list[-1].args
        self.assertEqual(compensation[0], str(document_id))
        self.assertEqual(compensation[2], [{"id": str(chunk_id), "chunk_index": 0, "content": "old content"}])

    def test_partial_qdrant_failure_restores_file_and_previous_vectors(self):
        db, qdrant, _, _, restored = self._run_failed_update(
            qdrant_failure=RuntimeError("partial qdrant write")
        )
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        self.assertEqual(restored, "old extracted content")
        self.assertEqual(qdrant.replace_document_chunks.call_count, 2)


def addresses(ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 443))]


class ConnectorNetworkTests(unittest.TestCase):
    def test_nonpublic_addresses_are_rejected(self):
        for ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "::ffff:127.0.0.1"):
            with self.subTest(ip=ip), patch.object(transport.socket, "getaddrinfo", return_value=addresses(ip)):
                with self.assertRaises(sync.ConnectorSyncError):
                    transport._validate_public_url("https://example.com")

    def test_empty_dns_result_is_rejected(self):
        with patch.object(transport.socket, "getaddrinfo", return_value=[]):
            with self.assertRaises(sync.ConnectorSyncError):
                transport._validate_public_url("https://example.com")

    def test_redirect_to_private_host_is_rejected_before_following(self):
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("127.0.0.1")):
            with self.assertRaises(sync.ConnectorSyncError):
                transport._PublicRedirectHandler().redirect_request(
                    Request("https://example.com"), None, 302, "Found", {}, "https://internal.local/"
                )

    def test_authenticated_redirect_is_rejected(self):
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("8.8.8.8")):
            with self.assertRaises(sync.ConnectorSyncError):
                transport._PublicRedirectHandler().redirect_request(
                    Request("https://example.com", headers={"Authorization": "Bearer secret"}),
                    None, 302, "Found", {}, "https://other.example/",
                )

    def test_public_redirect_is_allowed(self):
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("8.8.8.8")):
            result = transport._PublicRedirectHandler().redirect_request(
                Request("https://example.com"), None, 302, "Found", {}, "https://other.example/"
            )
        self.assertEqual(result.full_url, "https://other.example/")

    def test_connection_uses_validated_ip_without_second_dns_lookup(self):
        context = MagicMock()
        connection = transport._PublicHTTPSConnection("example.com", context=context)
        with patch.object(transport.socket, "getaddrinfo", side_effect=[addresses("8.8.8.8"), addresses("127.0.0.1")]) as dns, patch.object(transport.socket, "socket") as sock:
            connection.connect()
        dns.assert_called_once()
        sock.return_value.connect.assert_called_once_with(("8.8.8.8", 443))
        context.wrap_socket.assert_called_once_with(sock.return_value, server_hostname="example.com")

    def test_connection_blocks_private_dns_before_opening_socket(self):
        connection = transport._PublicHTTPSConnection("example.com")
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("10.0.0.1")), patch.object(transport.socket, "socket") as sock:
            with self.assertRaises(sync.ConnectorSyncError):
                connection.connect()
        sock.assert_not_called()

    def test_fetch_redirect_never_connects_to_internal_destination(self):
        def resolve(host, *args, **kwargs):
            return addresses("127.0.0.1" if host == "internal.local" else "8.8.8.8")

        with patch.object(transport.socket, "getaddrinfo", side_effect=resolve), patch.object(transport.socket, "socket") as sock, patch.object(ssl.SSLContext, "wrap_socket", side_effect=lambda value, **kwargs: value):
            sock.return_value.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 302 Found\r\nLocation: https://internal.local/\r\nContent-Length: 0\r\n\r\n"
            )
            with self.assertRaises(sync.ConnectorSyncError):
                transport._fetch("https://example.com")
            sock.return_value.connect.assert_called_once_with(("8.8.8.8", 443))

    def test_public_fetch_reads_response_through_safe_transport(self):
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("8.8.8.8")), patch.object(transport.socket, "socket") as sock, patch.object(ssl.SSLContext, "wrap_socket", side_effect=lambda value, **kwargs: value):
            sock.return_value.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n\r\nhello"
            )
            self.assertEqual(transport._fetch("https://example.com"), (b"hello", "text/plain", "https://example.com"))

    def test_all_cloud_helpers_block_private_dns(self):
        calls = (
            lambda: transport._authorized_json("https://example.com", "secret"),
            lambda: transport._bearer_download("https://example.com", "secret"),
            lambda: transport._oauth_token("https://example.com", {"secret": "value"}),
            lambda: s3._aws_signed_get("https://bucket.s3.amazonaws.com/key", {"access_key_id": "test", "secret_access_key": "test", "region": "us-east-1"}),
        )
        with patch.object(transport.socket, "getaddrinfo", return_value=addresses("10.0.0.1")), patch.object(transport.socket, "socket") as sock:
            for call in calls:
                with self.subTest(call=call), self.assertRaises(sync.ConnectorSyncError):
                    call()
            sock.assert_not_called()
