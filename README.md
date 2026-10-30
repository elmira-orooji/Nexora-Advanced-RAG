# Nexora

[![Nexora product demo preview](documents/media/Nexora-preview.gif)](https://github.com/elmira-orooji/Nexora-Advanced-RAG/raw/refs/heads/dev/documents/media/Nexora-promo.mp4)

[Watch the full video](https://github.com/elmira-orooji/Nexora-Advanced-RAG/raw/refs/heads/dev/documents/media/Nexora-promo.mp4)

Nexora is a document-grounded AI workspace for teams. It turns approved documents and connected sources into knowledge collections that people can search, discuss, and verify through cited answers.

> [!CAUTION]
> This is proprietary, source-available software. Public access does not grant permission to use, copy, modify, distribute, deploy, or contribute to Nexora. See [LICENSE](LICENSE), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md).

The project follows a clear path from knowledge to answer:

```text
Create a knowledge set → add documents or sources → process and index content → ask a question → inspect sources and answer confidence
```

## What Nexora includes

- **Grounded conversations** — retrieve relevant document chunks and present answer sources alongside a confidence state.
- **Knowledge sets** — organize documents into focused collections with per-user access levels.
- **Document ingestion** — upload PDF, TXT, JPEG, PNG, and TIFF files; track queue, extraction, OCR, chunking, and indexing progress.
- **Optional OCR** — extract content from scanned documents with MinerU, Jina OCR, Google Vision, or Azure Document Intelligence.
- **Assistants** — connect assistant behavior to one or more permitted knowledge sets.
- **Controlled sharing and feedback** — publish revocable read-only conversation snapshots and collect answer feedback.
- **Connectors** — synchronize supported website, GitHub, Google Drive, S3, SharePoint, and webhook sources through a background scheduler.
- **Experimental GraphRAG** — optionally extract organization-scoped entities and evidence-linked relations to retrieve across documents for relationship questions.
- **Team boundaries** — separate organizations, roles, document-set permissions, and user sessions.
- **Cloud or local generation** — select OpenRouter or an LM Studio OpenAI-compatible server through backend configuration.
- **Bilingual interface** — Persian and English UI, light and dark themes, and responsive layouts.

## Architecture at a glance

Nexora uses a React/Vite frontend, a FastAPI backend, PostgreSQL for application data, and Qdrant for vector retrieval. The API, document worker, and connector scheduler are separate processes that share the same database, document storage, and Qdrant configuration.

```text
Browser → React UI → FastAPI API → PostgreSQL
                              ↘ → Qdrant
                              ↘ → OpenRouter or LM Studio (selected generation provider)

Document worker → storage → extraction/OCR → chunking and indexing → Qdrant + optional graph facts in PostgreSQL
Connector scheduler → permitted remote sources → document processing queue
```

See [ARCHITECTURE.md](documents/architecture/ARCHITECTURE.md) for component boundaries, data flow, worker behavior, and RAG retrieval details.
See [GraphRAG pilot](documents/architecture/GRAPHRAG-PILOT.md) for enablement, backfill, and baseline comparison steps.

## Language model configuration

Choose one generation provider in `backend/.env` for the native backend. Generation does not switch providers automatically when a request fails.

### OpenRouter (default)

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=openrouter/free
```

The key must have access to the selected model. A cloud provider can reject requests or apply rate limits even when earlier requests succeeded.

### LM Studio (local)

Load a chat model in LM Studio and start its Developer server. In `backend/.env`, set:

```dotenv
LLM_PROVIDER=lm_studio
LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1
LM_STUDIO_MODEL=your-model-api-identifier
LM_STUDIO_API_KEY=
```

Use the exact API model identifier shown by LM Studio. Restart the backend after changing these values. If server authentication is enabled, supply its key through `LM_STUDIO_API_KEY`. To switch back, set `LLM_PROVIDER=openrouter`. Local mode uses the configured local model regardless of cloud model IDs selected in existing conversations. Embedding, OCR and vector-store configuration are independent; this setting only changes language-model generation. Keep the LM Studio server running while using Nexora. For a backend running inside Docker, use a host address reachable from the container instead of `127.0.0.1`.

To list the model identifiers after starting the server:

```powershell
(Invoke-RestMethod http://127.0.0.1:1234/v1/models).data.id
```

The model identifier is different from the model file path. Use the public server address shown by LM Studio, not the internal model-worker port. Local generation requires enough RAM/VRAM for the selected model; performance and Persian answer quality depend on that model and the device.


## Quick start with Docker

For a public guest demo with a Vercel frontend and an isolated backend stack, see [Live demo deployment](documents/operations/LIVE-DEMO.md). Guest entry is disabled in normal installations.

Docker Compose starts PostgreSQL, Qdrant, Redis, the API, document worker, connector scheduler, and frontend together.

### Requirements

- Docker Desktop or Docker Engine with Docker Compose v2
- At least 4 GB of free memory for a comfortable local stack

### Configure the environment

From the repository root:

```powershell
Copy-Item .env.docker.example .env
```

Open `.env` and replace the database password in both `POSTGRES_PASSWORD` and `DATABASE_URL`. Also set a random `AUTH_SECRET_KEY` of at least 32 characters. Keep the included development cookie settings for local HTTP only.

### Start the stack

```powershell
docker compose up --build -d
docker compose ps
```

Open [http://localhost:5173](http://localhost:5173). The first start applies Alembic migrations before the API and workers begin.

To confirm that PostgreSQL, Qdrant, document storage, and both workers are ready:

```powershell
Invoke-WebRequest http://localhost:5173/api/ready | Select-Object -ExpandProperty Content
```

For logs from a single service:

```powershell
docker compose logs -f document-worker
```

The Compose setup limits the document worker to 0.75 CPU cores and 2 GB of memory by default. This limits local resource contention, but it can make indexing slower. Adjust those limits in `compose.yml` only after considering the capacity of the host.

## Run without Docker

Use this option when PostgreSQL and Qdrant are already available elsewhere.

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set, at minimum, the following values in `backend/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE
AUTH_SECRET_KEY=replace-with-a-random-value-of-at-least-32-characters
APP_ENV=development
AUTH_COOKIE_SECURE=false
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

QDRANT_URL=http://YOUR-QDRANT-HOST:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=rag_chunks

OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free
```

After configuring the environment, apply migrations from the backend directory:

```powershell
alembic upgrade head
```

Then open three separate terminals, each starting from the repository root.

Terminal 1 - API:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2 - document processing:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.workers.document_worker
```

Terminal 3 - scheduled source synchronization:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.workers.connector_scheduler_worker
```

### Frontend

In a separate terminal, starting from the repository root:

```powershell
cd frontend/app
npm ci
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
```

The development server runs on [http://localhost:5173](http://localhost:5173) and proxies `/api` calls to `http://127.0.0.1:8000`.

The frontend package is at `frontend/app`, not `frontend/my-rag-app`. If port 5173 is already in use, stop the existing frontend process before starting another one. Python's virtual environment is only needed for the backend and workers.

## Document processing and OCR

PDF files with a text layer and TXT files are extracted locally. For scanned files, the default OCR route tries Jina first and falls back to MinerU if Jina is unavailable, fails, times out, or returns no text. Both are hosted services and receive document content; set `OCR_PROVIDER=disabled` to disable cloud OCR.

To enable MinerU for Persian scanned documents:

```dotenv
OCR_PROVIDER=mineru
MINERU_API_TOKEN=your-token
MINERU_LANGUAGE=fa
MINERU_MODEL_VERSION=vlm
```

Set `OCR_PROVIDER=auto` to try configured providers in this order: MinerU, Google Vision, and Azure Document Intelligence. Before enabling a cloud OCR provider, confirm that sending the original document to that provider is permitted by the organization’s data policy.

Jina OCR can be configured as the primary provider without installing a local model. MinerU is used as its fallback when configured:

```dotenv
OCR_PROVIDER=jina
JINA_API_KEY=your-jina-api-key
JINA_OCR_MODEL=jina-ocr-v1
```

With `OCR_PROVIDER=jina`, Jina is attempted first and MinerU second. Use this route only when the organization approves sending document content to both providers. If either credential is missing, the configured provider list adjusts accordingly.

Uploads are staged in quarantine and can be scanned through ClamAV before they enter document storage and processing. Scanning is disabled by default in development and test environments; production requires `MALWARE_SCAN_MODE=required` and a reachable ClamAV service. When scanning is required, an unavailable scanner blocks the upload.

For Docker, enable the scanner service with `docker compose --profile security up --build -d` and configure `MALWARE_SCAN_MODE=required`, `CLAMD_HOST=clamav`, and `CLAMD_PORT=3310` in the environment. MIME checks and file-size limits are not antivirus controls. See [SECURITY.md](SECURITY.md) for security and deployment requirements.

## Operations

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Lightweight API liveness check. |
| `GET /ready` | Readiness check for PostgreSQL, Qdrant, writable document storage, document worker, and connector scheduler. |

`/ready` returns `503` until all required dependencies and worker heartbeats are available. This is intentional and makes it suitable for deployment readiness probes.

For production, use HTTPS, set `APP_ENV=production`, set `AUTH_COOKIE_SECURE=true`, restrict `FRONTEND_ORIGINS` to the real frontend origin, and keep PostgreSQL and Qdrant off the public network. Full deployment guidance is available in [DEPLOYMENT.md](documents/operations/DEPLOYMENT.md).

## Quality checks

The repository has separate backend and frontend checks:

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest

# Frontend unit tests and production build (from backend/)
cd ../frontend/app
npm run test
npm run build

# Frontend end-to-end tests
npm run test:e2e
```

GitHub Actions runs backend tests on pushes and pull requests to `dev` and `main`. A separate frontend workflow runs unit tests, a production build, and Playwright end-to-end tests on GitHub-hosted runners, so those checks do not consume local CPU while working on the project.

## Repository layout

```text
backend/                    FastAPI routes, models, migrations, workers, and tests
frontend/app/               React application, feature modules, and tests
documents/                  Architecture, operations, design, and deliverables
compose.yml                 Full local Docker Compose stack
SECURITY.md                 Security posture and operational requirements
```

## Documentation

- [Documentation index](documents/README.md)
- [Repository organization](documents/development/PROJECT_STRUCTURE.md)
- [Architecture](documents/architecture/ARCHITECTURE.md)
- [Deployment](documents/operations/DEPLOYMENT.md)
- [Security](SECURITY.md)
- [Contribution policy](CONTRIBUTING.md)
- [Backup and recovery](documents/operations/BACKUP_AND_RECOVERY.md)
- [Design system](documents/development/DESIGN.md)
- [Software requirements specification](documents/requirements/Nexora-SRS.pdf)
- [Editable SRS source](documents/requirements/Nexora-SRS.docx)
- [SRS regeneration instructions](documents/requirements/README.md)
- [Backend workers and OCR](backend/README.md)
- [Connector scheduler](documents/operations/CONNECTOR_SCHEDULER.md)

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| A document remains at 0% or 10% | Confirm `document-worker` is running, then inspect `/ready` and the document processing error. |
| A scanned document fails | Check `OCR_PROVIDER`, provider credentials, page limits, and OCR timeout settings. |
| The frontend reports `ECONNREFUSED 127.0.0.1:8000` | Start the FastAPI API on port 8000 or correct the development proxy target. |
| `/ready` returns 503 | Check PostgreSQL, Qdrant, writable storage, document worker, and connector scheduler. |
| Answer generation returns 503 | Inspect the provider failure log. OpenRouter 403 indicates a rejected request; 429 indicates rate limiting. For LM Studio, check that the server and model are running, the API identifier is correct, and the URL is reachable from the backend. |
| A connector does not synchronize | Check the scheduler, connector configuration, lease state, and the last synchronization error. |

## Security note

Do not commit `.env` files, passwords, API keys, OAuth refresh tokens, Qdrant keys, OCR credentials, uploaded data, or backups. Review [SECURITY.md](SECURITY.md) before exposing the application to users or connecting it to organization data. Report vulnerabilities privately; do not use public GitHub issues for sensitive security details.
