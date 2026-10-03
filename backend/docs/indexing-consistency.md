# Deploying durable document indexing

Before starting API and worker processes with this version, run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Revision `20261003_50` allows `indexing_outbox.document_id` to be null. Delete
intents deliberately use null and retain the immutable document ID in `payload`,
so document deletion cannot cascade away the retry intent. Do not start the new
API before applying this migration. Downgrade refuses to restore NOT NULL while
detached intents exist; it never silently discards pending deletions.

Manual indexing, chunk edits, and the document worker persist SQL changes and an
indexing intent before touching the vector store. Immediate apply and the
reconciler read the current active chunks under the document lock, rather than
replaying stale captured content. Failed immediate apply leaves the intent
pending. Keep the document worker running: its reconciliation loop
applies pending intents.

A document stays `processing / indexing / 95%` until vector apply succeeds. Only
then does it become `indexed / ready / 100%` and eligible for retrieval. Worker
success notifications are also deferred until apply. After ten reconciliation
failures, the latest replacement intent marks the document failed for manual
Retry; an older intent cannot overwrite a newer edit's state.

Deleting a document and its jobs commits together with its detached deletion
intent. Vector cleanup happens afterward and is retried if the provider is down.
The document is absent from SQL and authorized retrieval scopes during that
delay. Storage cleanup also follows commit; `storage_removed` reports its result.

Upload compensation removes staged files only before a successful SQL commit.
A response/refresh failure after commit does not erase a persisted document's
source. The request may still fail, but a later document-list refresh can recover
the committed result.
