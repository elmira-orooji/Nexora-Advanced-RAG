# Repository organization

## Entry points

- `backend/app/main.py`: FastAPI application. Run backend commands from `backend/`.
- `backend/app/workers/`: document-processing and connector-scheduling processes.
- `frontend/app/`: the `nexora-web` React package. Run npm commands here.
- `compose.yml` and `.github/workflows/`: deployment and continuous integration.

## Backend

Keep HTTP parsing and response contracts in `app/api/`, configuration and access policies in `app/core/`, SQLAlchemy entities in `app/models/`, Pydantic contracts in `app/schemas/`, and database operations in `app/repositories/`.

`app/services/` contains responsibility-specific packages:

- `application/`: assistant, conversation, sharing, document-set, evaluation, notification, and user workflows.
- `documents/`: upload validation, extraction, OCR, chunking, indexing, and processing jobs.
- `retrieval/`: search, ranking, fusion, RAG, research, and query rewriting.
- `providers/`: model/vector adapters, factory, provider errors, and HTTP resilience.
- `connectors/`: source synchronization, scheduling, secrets, leases, and `sources/` adapters.
- `operations/`: metrics, alerts, retention, usage tracking, audit, and worker heartbeats.
- `security/`: login throttling.
- `storage/`: filesystem storage operations.

`ports.py` and `transactions.py` stay at the service root because multiple packages use these shared contracts and transaction helpers.

Keep database migrations in `backend/alembic/`, maintenance commands in `backend/scripts/`, and tests/fixtures in `backend/tests/`. `backend/ocr_lab/` is a separate, related experiment; it is not part of application startup.

## Frontend

`src/pages/` holds routed screens; `src/layouts/` holds the app shell and sidebar. Domain-specific components, API clients, hooks, schemas, and types belong to `src/features/<feature>/`. Current features are auth, chat, knowledge, users, assistants, analytics, evaluation, and notifications.

Use `src/components/` for shared UI, `src/hooks/` for shared React hooks, and `src/lib/` for framework-independent shared utilities, confirmation handling, and the common API transport. Do not recreate overlapping `utils/` or `services/` buckets.

Shared theme and page CSS remain in `src/styles/`; component-specific CSS stays beside its component. Translation resources stay in `src/locales/`, configuration in `src/config/`, and assets in `src/assets/`. Tests stay beside the source they cover; browser tests stay in `e2e/`.

## Documentation and local data

Keep project documentation under `documents/`; its [index](../README.md) explains the categories. Root README, contribution guidance, license, and security policy remain discoverable at the repository root.

Generated dependencies, caches, uploaded documents, and environment secrets are local data, not source folders. They remain ignored by Git. Preserved settings from the retired Prisma scaffold live locally in `.local/legacy/prisma/`; this is not an application dependency and must not be committed.

After changing a path, update import statements, test mocks, documentation links, CI working directories, and Docker build contexts together. Run the frontend build and both test suites before committing.
