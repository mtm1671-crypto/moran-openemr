# AgentForge Clinical Co-Pilot

Standalone MVP services for the Clinical Co-Pilot.

```text
copilot/
    api/       FastAPI service: auth, patient search, evidence retrieval, chat, verification
    web/       Next.js patient-scoped chat UI
    worker/    ETL, prefetch, and reindex entrypoints
```

OpenEMR remains the source of truth for identity and chart data. The Co-Pilot stores derived evidence, embeddings, encrypted conversations, and metadata in Postgres.

## Local Development Shape

```text
OpenEMR local/demo instance
    |
    +--> SMART/OAuth + FHIR
            |
            +--> api: FastAPI on localhost:8000
                    |
                    +--> Postgres with pgvector + pgcrypto
                    |
                    +--> LLM provider adapter
            |
            +--> web: Next.js on localhost:3000
```

## First Build Targets

1. `/healthz` returns service status.
2. `/api/capabilities` returns enabled roles, tools, and provider safety flags.
3. `/api/patients?query=` proxies OpenEMR FHIR patient search.
4. `/api/chat` retrieves demographics, active problems, recent labs, active medications, and allergies from FHIR, then streams a verified final answer.
5. `/api/chat` refuses treatment recommendation requests in the read-only MVP.
6. `/api/source/openemr/{resourceType}/{id}` re-reads cited source records from OpenEMR FHIR.
7. Worker can run an idempotent patient reindex job.

## Local OpenEMR Wiring

Start the OpenEMR development stack first. In this repo, use the clean runtime mount documented in `DEPLOYMENT_RUNBOOK.md`.

Register and enable a local-only OpenEMR OAuth client for password-grant smoke tests:

```powershell
cd copilot
.\scripts\register-openemr-dev-client.ps1
```

The script prints environment variables. Put them in `copilot/api/.env` or set them in the shell before starting the API.

Password grant is only for local development. Production must use SMART authorization code flow and pass the user's OpenEMR access token to the API.

Seed the serious demo patient:

```powershell
# From the repository root:
.\copilot\scripts\seed-openemr-demo-patient.ps1
```

The seeded patient is `Elena Morrison` with OpenEMR public id `AF-MVP-001`. Search for `mo` in the Co-Pilot UI.

## Install Notes

Dependencies are not installed by this scaffold. Once Python and Node are available:

```powershell
cd copilot/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```powershell
cd copilot/web
npm install
npm run dev
```

If Docker is not available in a fresh PowerShell session, prepend Docker Desktop's CLI folders:

```powershell
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Docker\Docker\resources;C:\Program Files\Docker\cli-plugins;' + $env:Path
```

Verified scaffold commands:

```powershell
cd copilot/api
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app
```

```powershell
cd copilot/web
npm audit --audit-level=moderate
npm run build
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:3001'
npm run test:e2e -- --project=chromium
```

Optional live OpenEMR smoke test:

```powershell
cd copilot/api
$env:RUN_LIVE_OPENEMR='1'
$env:OPENEMR_BASE_URL='http://localhost:8300'
$env:OPENEMR_FHIR_BASE_URL='http://localhost:8300/apis/default/fhir'
$env:OPENEMR_CLIENT_ID='<printed by register-openemr-dev-client.ps1>'
$env:OPENEMR_CLIENT_SECRET='<printed by register-openemr-dev-client.ps1>'
$env:OPENEMR_DEV_USERNAME='admin'
$env:OPENEMR_DEV_PASSWORD='pass'
$env:OPENEMR_TLS_VERIFY='false'
.\.venv\Scripts\python.exe -m pytest tests\test_live_openemr_smoke.py -q
```

Latest local verification:

```text
api pytest: 37 passed, 5 skipped
api ruff: all checks passed
api mypy: success
web build: success
web npm audit: 0 vulnerabilities
Playwright smoke: 1 passed
previous live OpenEMR smoke: 5 passed
```

Current verified demo URLs:

```text
API: http://127.0.0.1:8001
Web: http://127.0.0.1:3001
```
