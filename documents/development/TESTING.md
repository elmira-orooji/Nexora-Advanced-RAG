# Testing strategy

Nexora uses a test pyramid so feedback is fast for business logic and browser tests are reserved for critical user journeys.

## Unit tests

Backend unit tests cover services, repositories, provider failure handling, idempotency, document-job ownership, retrieval/ranking and transaction behavior. Frontend Vitest tests cover utilities, services, component behavior, access control, localization and accessibility interactions.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -m unit -q

cd ..\frontend\app
npm run test:unit
```

Existing backend tests that do not require a live integration are intentionally runnable with the normal suite as well:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

## Integration tests

`backend/tests/test_api_integration.py` sends real HTTP requests through FastAPI, including middleware, validation, response serialization, login cookie handling and multipart document upload queuing. External dependencies are replaced at their ports, so the tests do not call Qdrant, MinerU/OCR or an LLM provider.

```powershell
cd backend
.\.venv\Scripts\python.exe -m "integration and not cloud" -q
```

Cloud OCR smoke tests have the separate `cloud` marker. They require explicitly configured provider credentials and should be selected only when those credentials are available.

## End-to-end tests

Playwright runs the application in Chromium with deterministic API stubs. The critical suite verifies:

- sign-in, validation and logout;
- file selection and upload acknowledgement;
- starting a conversation, sending a message and rendering a source-grounded answer.

The accessibility and responsive suite verifies landmark names for screen readers, keyboard opening and closing of the mobile navigation, the 44×44px mobile navigation target, reduced-motion behavior, RTL/LTR document semantics, and horizontal overflow at 320, 390, 768, 1024 and 1440px.

```powershell
cd frontend\app
npm run test:e2e:critical
npm run test:e2e:accessibility
```

For the complete browser suite, run `npm run test:e2e`. On a fresh machine, install the browser once with `npx playwright install chromium`. If the Playwright download is unavailable, use an installed Edge browser locally: `$env:PW_CHANNEL = "msedge"; npm run test:e2e:critical`.

## Continuous integration

GitHub Actions runs backend tests, frontend unit tests and the Playwright suite for pull requests and pushes to `dev` and `main`. Browser traces and screenshots are retained only when an E2E job fails.
