# Document-level access control

Document sets keep their existing `view`, `edit`, and `manage` grants. Administrators can also grant one of these levels to a specific document from **Users → Access**.

## Effective access

- Organization admins can access documents in their organization.
- If a document has no direct grants, access is inherited from its knowledge sets.
- As soon as at least one direct grant exists for a document, that document is restricted to users with an explicit document grant. A set grant no longer grants access to that document.
- A direct document grant also lets the user open the containing knowledge set as a filtered scope. The set view, document list, search, RAG answers, research, assistants, and conversation retrieval include only documents the user can access.
- `edit` and `manage` apply to document operations at that level. Set-level management remains separately controlled by set grants.
- Team shares require the viewer to have access to every cited document. Public link shares require the creator to have `manage` access to every cited document, and are hidden if that access is later revoked.
- Previously shared conversations that contain source excerpts without document IDs cannot be safely checked and are unavailable after this change. New shares carry document IDs for authorization checks.

## Rollout

Apply the database migration with `alembic upgrade head`. Existing set permissions and documents are unchanged; documents with no explicit document grants continue to inherit their set permissions. The administration dialog supports searching the organization’s document catalog and loading additional pages.
