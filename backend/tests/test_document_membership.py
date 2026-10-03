from app.core.application_errors import ApplicationError
from app.api.application_errors import to_http_exception


def http_status(error):
    return to_http_exception(error).status_code if isinstance(error, ApplicationError) else error.status_code


import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.document_sets import add_document_to_set, get_document_set
from app.schemas.document_set import DocumentMembershipRequest


class DocumentMembershipTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role="user", organization_id=uuid4())
        self.target = SimpleNamespace(id=uuid4(), documents=[])
        self.source_id = uuid4()
        self.document = SimpleNamespace(
            id=uuid4(), organization_id=self.user.organization_id,
            document_sets=[SimpleNamespace(id=self.source_id)], status="indexed",
        )
        self.db = MagicMock()
        self.db.scalar.side_effect = [self.target, self.document]

    def call_route(self):
        # Keep the real permission helpers; only omit response serialization.
        with patch("app.api.routes.document_sets._response") as response, patch(
            "app.api.routes.document_sets.DocumentSetDetail", side_effect=lambda **values: values
        ):
            response.return_value.model_dump.return_value = {}
            return add_document_to_set(
                self.target.id, DocumentMembershipRequest(document_id=self.document.id),
                self.db, self.user,
            )

    def test_target_editor_cannot_attach_restricted_document(self):
        self.db.execute.return_value.all.return_value = [(self.target.id, "edit")]
        with self.assertRaises((HTTPException, ApplicationError)) as raised:
            self.call_route()
        self.assertEqual(http_status(raised.exception), 403)
        self.assertEqual(self.target.documents, [])
        self.db.commit.assert_not_called()

    def test_source_view_or_edit_does_not_grant_redistribution(self):
        for level in ("view", "edit"):
            with self.subTest(level=level):
                self.db.scalar.side_effect = [self.target, self.document]
                self.db.execute.return_value.all.return_value = [
                    (self.target.id, "edit"), (self.source_id, level),
                ]
                with self.assertRaises((HTTPException, ApplicationError)) as raised:
                    self.call_route()
                self.assertEqual(http_status(raised.exception), 403)
                self.assertEqual(self.target.documents, [])
                self.db.commit.assert_not_called()

    def test_source_manager_can_attach_document_to_editable_target(self):
        self.db.execute.return_value.all.return_value = [
            (self.target.id, "edit"), (self.source_id, "manage"),
        ]
        self.call_route()
        self.assertEqual(self.target.documents, [self.document])
        self.db.commit.assert_called_once()

    def test_source_manager_still_needs_target_edit_access(self):
        self.db.execute.return_value.all.return_value = [
            (self.target.id, "view"), (self.source_id, "manage"),
        ]
        with self.assertRaises((HTTPException, ApplicationError)) as raised:
            self.call_route()
        self.assertEqual(http_status(raised.exception), 403)
        self.db.scalar.assert_not_called()
        self.db.commit.assert_not_called()

    def test_admin_can_attach_own_organization_unassigned_document(self):
        self.user.role = "admin"
        self.document.document_sets = []
        self.db.scalars.return_value.all.return_value = [self.target.id]
        self.call_route()
        self.assertEqual(self.target.documents, [self.document])
        self.db.commit.assert_called_once()

    def test_admin_document_lookup_is_organization_scoped(self):
        self.user.role = "admin"
        self.db.scalars.return_value.all.return_value = [self.target.id]
        self.db.scalar.side_effect = [self.target, None]
        with self.assertRaises((HTTPException, ApplicationError)) as raised:
            self.call_route()
        self.assertEqual(http_status(raised.exception), 404)
        query = self.db.scalar.call_args.args[0]
        params = query.compile().params
        self.assertIn(self.user.organization_id, params.values())
        self.assertIn(self.document.id, params.values())
        self.assertEqual(self.target.documents, [])
        self.db.commit.assert_not_called()


class DocumentSetDetailAccessTests(unittest.TestCase):
    def test_detail_returns_members_actual_access_level(self):
        set_id = uuid4()
        user = SimpleNamespace(id=uuid4(), role="user", organization_id=uuid4())
        item = SimpleNamespace(id=set_id, documents=[])
        db = MagicMock()
        db.execute.return_value.all.return_value = [(set_id, "view")]

        with patch("app.api.routes.document_sets._get_set", return_value=item), patch(
            "app.api.routes.document_sets._response"
        ) as response, patch(
            "app.api.routes.document_sets.DocumentSetDetail", side_effect=lambda **values: values
        ):
            response.return_value.model_dump.return_value = {"access_level": "view"}
            result = get_document_set(set_id, db, user)

        self.assertEqual(response.call_args.args[3], "view")
        self.assertEqual(result["access_level"], "view")
