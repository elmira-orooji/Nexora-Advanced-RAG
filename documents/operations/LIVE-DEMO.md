# Nexora live demo on Vercel

The frontend and a small same-origin API gateway run on Vercel. The existing FastAPI API, PostgreSQL, Qdrant, Redis and document worker run together on a separate Docker host with persistent volumes. Vercel does not run this project's long-lived document worker or database containers. No public deployment has been created by these configuration files. The demo uses opt-in local multilingual embeddings because self-hosted Qdrant does not provide Qdrant Cloud's text-inference service. Ordinary installations retain the existing cloud-inference default. Keep the same embedding model in the API and indexing worker; changing it requires reindexing into a fresh collection.

## Demo behavior

- `DEMO_ENABLED` is off by default. Enabling it on a **dedicated demo database** exposes guest entry at `POST /api/v1/auth/demo`.
- Each visitor gets a distinct user and a revocable, HttpOnly, Secure, host-only session cookie valid for one hour. Regular password sign-in cannot authenticate guest accounts.
- Guests can read only permitted sample documents and create, read, rename or delete their own conversations. They cannot upload, edit knowledge, create connectors, change passwords, share conversations, leave feedback that creates evaluation cases, run deep research, or call other model endpoints. New API operations are denied by default for guests.
- Redis atomically reserves up to 10 answer requests and 40 conversation operations per guest, 100 answer requests globally per UTC day and 50 guest sessions globally per UTC day. At most 5 guest sessions per client IP per day are admitted. Failures and cancellations consume slots. Daily caps can be lowered using the example environment. These are request caps, not a currency-denominated billing guarantee; set a hard provider-side credit limit too.
- Only the Vercel gateway knows `DEMO_PROXY_SECRET`. Production demo API calls without this secret are rejected. Browser mutations also need an allowed Origin. Do not expose this secret with a `VITE_` prefix.
- Trusted English/Persian sample text is queued once by the seed service and processed by the normal indexing worker. Guest entry returns 503 until at least one sample document is indexed. Answers use the configured model and actual retrieval; there are no canned answers.
- The maintenance service removes explicitly marked demo users older than 24 hours and their dependent session/conversation records once per hour. Ordinary users and the sample custodian are excluded.

## 1. Prepare the backend host

Use a separate Docker host and DNS hostname for the demo API. Point the hostname to that host; ports 80 and 443 must reach Caddy for automatic TLS. No database, vector-store or Redis ports are published. Keep this stack separate from any existing Nexora data. Budget enough memory for the API and worker, which each have a 2 GB container limit, plus PostgreSQL and Qdrant. The initial embedding-model download and indexing can take time.

Copy `.env.demo.example` to `.env.demo` at the repository root. Set real values for `API_DOMAIN`, both matching database-password values, a random authentication secret, a separate random proxy secret, the Vercel production origin, and an OpenRouter key/model available to the account. Secrets must each contain at least 32 random characters. Do not commit `.env.demo` or copy private data into `backend/demo`. Keep OCR disabled. No provider API key belongs in the frontend.

```sh
docker compose --env-file .env.demo -f compose.demo.yml up --build -d
docker compose --env-file .env.demo -f compose.demo.yml logs -f seed document-worker
```

The `seed` container should exit successfully; the worker should finish indexing both sample TXT files. The API's `/health` endpoint is a process liveness check, not proof of working retrieval/model credentials. Verify the functional flow through the published demo before sharing its link. The demo stack intentionally omits connector scheduling because guests cannot create connectors.

## 2. Configure Vercel

Import this Git repository into the owner's Vercel account with:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend/app` |
| Framework | Vite |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node.js | 22 or 24 |

Use Fluid Compute with a function duration that permits the configured 120 seconds. The gateway aborts a backend request after 110 seconds; model timeouts may appear as a temporary-service message and still consume the demo request slot.

Set these **server-only** runtime environment variables in Vercel:

| Variable | Value |
| --- | --- |
| `NEXORA_API_ORIGIN` | The backend HTTPS origin, for example `https://api-demo.example.com`, without `/api` or a path |
| `DEMO_PROXY_SECRET` | Exactly the backend proxy secret |

Leave `VITE_API_URL` unset so the browser calls `/api/v1` on the Vercel host. API responses must never be cached. The included `vercel.json` keeps SPA `/home` and `/share` routes working on refresh. Restrict the production backend `FRONTEND_ORIGINS` to the actual production frontend origin; add a specific preview origin only when deliberately testing it. Redeploy after changing Vercel environment variables.

## 3. Release check

1. Open the Vercel production URL and choose **Try the live demo**. Confirm sample questions appear in English and Persian.
2. Ask a handbook question, inspect its citations, then ask an unrelated question. Confirm real model responses and a graceful no-source answer.
3. In a separate browser profile, enter as another visitor. Confirm conversation history is separate.
4. Confirm the guest cannot upload, change sample data, invoke deep research or change a password, including through direct API requests in a disposable test environment.
5. Confirm Redis request limits and maintenance work using dummy visitors. Verify provider-side spending controls. Do not generate paid traffic merely to exhaust quotas.
6. Confirm the browser receives only a host-only Secure/HttpOnly session cookie, and that direct backend API access without the proxy secret is denied.

## Operation

Redis uses AOF persistence and `noeviction`. Do not clear its data or volume to recover from a quota error: that resets admission counters. If Redis is unavailable, guest work fails closed. Caddy, PostgreSQL, Qdrant, document storage and model-cache data have dedicated volumes.

To disable new guest entry **and existing guest access**, set `DEMO_ENABLED=false` and recreate the API container after reviewing the environment; stop the dedicated maintenance service as well. Normal application installations keep this setting false. Stop the demo with `docker compose --env-file .env.demo -f compose.demo.yml stop`; do not remove volumes unless the owner intends to discard all demo records and quota state.

Implementation checks can run without real credentials or external calls. Public deployment, TLS, Vercel function routing, Redis concurrency/persistence, PostgreSQL migrations, embedding downloads, real model responses and the release checks above still require the owner's deployment environment.

Official platform references: [Vercel Node.js functions](https://vercel.com/docs/functions/runtimes/node-js), [Vercel request headers](https://vercel.com/docs/headers/request-headers), [Vercel function limits](https://vercel.com/docs/functions/limitations), [Vercel environment variables](https://vercel.com/docs/environment-variables), [Qdrant inference options](https://qdrant.tech/documentation/inference/).
