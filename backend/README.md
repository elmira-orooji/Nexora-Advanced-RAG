# Backend processes

Apply database migrations before starting either process:

```powershell
alembic upgrade head
```

Run the API and durable document worker as separate services that share the same
database, document storage, and Qdrant configuration:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.workers.document_worker
python -m app.workers.connector_scheduler_worker
```

More than one document worker may run at the same time. Jobs are claimed with
database row locks, and abandoned claims return to the queue after
`DOCUMENT_JOB_LEASE_SECONDS`. Active workers refresh their lease every
`DOCUMENT_JOB_HEARTBEAT_SECONDS`, including during blocking extraction and
Qdrant operations. Transient failures use exponential backoff up to
`DOCUMENT_JOB_MAX_ATTEMPTS`; permanent and exhausted jobs enter the
`dead_letter` state and can still be retried manually.

The connector scheduler is also a separate process. Run one scheduler instance;
it handles `SIGINT` and `SIGTERM` cleanly and is independent of the number of API
workers. Remote connector discovery releases its SQLAlchemy Session connection
while OAuth and network downloads are in progress.

## GraphRAG pilot

Graph augmentation is opt-in and disabled by default. Set `GRAPH_RAG_ENABLED=true`
only after approving the additional processing and model cost for document chunks.
Apply migrations with `alembic upgrade head`; new document and connector indexing
then extracts entities and explicitly supported relations. Extraction failures do
not block ordinary vector/BM25 indexing. Each graph fact retains its source chunk,
and graph retrieval is restricted to the current organization's permitted,
active documents.

Build graph facts for documents already indexed before enabling the feature:

```powershell
python -m scripts.reindex_graph
```

Use the knowledge-set Retriever comparison to compare the same query and source
scope with GraphRAG disabled in one configuration and enabled in the other. The
graph path only adds evidence for relationship-oriented questions (or questions
with multiple matched entities); all generated answers still cite original
document chunks. `GRAPH_QUERY_MAX_HOPS` is limited to 1 or 2 and defaults to 2.
See [the GraphRAG pilot guide](../documents/architecture/GRAPHRAG-PILOT.md).

## Document-level access

Administrators can grant users `view`, `edit`, or `manage` access to individual
documents from the Users page. A document with any direct grants is restricted
to explicitly granted users; documents without direct grants continue to inherit
access from their knowledge sets. Retrieval scopes, document content, citations,
conversation history, and shared chats enforce these grants. See
[the document access guide](../documents/architecture/DOCUMENT-ACCESS-CONTROL.md).

## OCR for scanned documents

PDFs with an embedded text layer are extracted locally. By default, scanned
PDFs and images are sent to Jina OCR first, then to MinerU if Jina is unavailable,
fails, times out, or returns no text. Configure `JINA_API_KEY` and
`MINERU_API_TOKEN`; both are hosted services and receive document content, so
enable this route only when approved by the organisation's data policy. Use
`OCR_PROVIDER=disabled` to disable hosted OCR, or `OCR_PROVIDER=mineru` to use
MinerU only. Set `MINERU_LANGUAGE=fa` for Persian documents.

Set `OCR_PROVIDER=auto` to try configured MinerU, Google Vision, then Azure
Document Intelligence. The API also accepts JPEG, PNG, and TIFF images when OCR
is configured.

The ordinary test suite mocks cloud providers. To run the opt-in live smoke
test, set a provider credential and its explicit switch, then run:

```powershell
$env:RUN_GOOGLE_VISION_OCR_INTEGRATION=1
.\.venv\Scripts\python.exe -m pytest -m integration
```

The test sends one synthetic image containing `NEXORA OCR 2026`; it does not
upload a user document. Use `RUN_AZURE_OCR_INTEGRATION=1` for Azure instead.
