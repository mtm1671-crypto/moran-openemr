# Clinical Co-Pilot Deployment Runbook

## Purpose

This runbook defines the MVP deployment shape for the standalone AgentForge Clinical Co-Pilot. OpenEMR is the identity and chart-data authority. The Co-Pilot runs as separate services and connects to OpenEMR through SMART/OAuth, FHIR, and narrowly scoped read-only fallback access only where needed.

## Local Prerequisites

Required:

- Docker Desktop or Docker CLI with Compose.
- Node.js 20+ for the Next.js app.
- Python 3.12+ for the FastAPI app and worker.
- Postgres 16 with `pgvector` and `pgcrypto`, or Railway Postgres for remote dev.

Current local Docker status:

- Docker Desktop is installed.
- Docker CLI works when Docker's `resources/bin` directory is on PATH.
- OpenEMR development-easy Compose has been verified healthy locally.

Important local workaround:

- Do not mount the full working repo into OpenEMR while Co-Pilot temp/dependency folders exist under `copilot/`.
- The OpenEMR dev image rsyncs the mounted repo and can fail on Windows-created Python temp/cache directories.
- Use the clean tracked-file runtime copy under `.runtime/openemr-clean` for OpenEMR Compose.

## Local OpenEMR

Expected command once Docker is available:

```powershell
cd docker/development-easy
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Docker\Docker\resources;C:\Program Files\Docker\cli-plugins;' + $env:Path
$env:OPENEMR_DIR = (Resolve-Path '..\..\.runtime\openemr-clean').Path
docker compose up --detach --wait
```

Expected local URLs from repo docs:

- OpenEMR HTTP: `http://localhost:8300/`
- OpenEMR HTTPS: `https://localhost:9300/`
- Login: `admin` / `pass`
- phpMyAdmin: `http://localhost:8310/`

FHIR and SMART checks:

```powershell
Invoke-WebRequest -Uri https://localhost:9300/apis/default/fhir/metadata -SkipCertificateCheck
Invoke-WebRequest -Uri https://localhost:9300/.well-known/smart-configuration -SkipCertificateCheck
```

The exact SMART metadata URL may vary by OpenEMR site path. If the well-known URL fails, check `Documentation/api/SMART_ON_FHIR.md` and the OAuth routes under `oauth2/`.

For local Co-Pilot API smoke tests, register and enable a dev OAuth client:

```powershell
cd copilot
.\scripts\register-openemr-dev-client.ps1
```

The script prints the environment variables needed by `copilot/api/.env`. This uses the OpenEMR password grant for local development only.

## Railway Services

MVP service shape:

```text
web
    Next.js chat UI

api
    FastAPI service

worker
    ETL, scheduled prefetch, on-demand reindex

postgres
    Railway Postgres with pgvector and pgcrypto
```

OpenEMR can be deployed separately or accessed from an existing reachable demo instance. The Co-Pilot does not modify OpenEMR for the MVP.

## Required Environment Variables

Shared:

```text
APP_ENV
PUBLIC_BASE_URL
DATABASE_URL
ENCRYPTION_KEY
```

OpenEMR:

```text
OPENEMR_BASE_URL
OPENEMR_SITE=default
OPENEMR_FHIR_BASE_URL
OPENEMR_OAUTH_AUTHORIZE_URL
OPENEMR_OAUTH_TOKEN_URL
OPENEMR_JWKS_URL
OPENEMR_CLIENT_ID
OPENEMR_CLIENT_SECRET
OPENEMR_REDIRECT_URI
```

Provider routing:

```text
LLM_PROVIDER
ANTHROPIC_API_KEY
OPENROUTER_API_KEY
LOCAL_MODEL_BASE_URL
ALLOW_PHI_TO_ANTHROPIC=false
ALLOW_PHI_TO_OPENROUTER=false
ALLOW_PHI_TO_LOCAL=true
```

Retention:

```text
CONVERSATION_RETENTION_DAYS=30
REINDEX_IDEMPOTENCY_SECONDS=120
```

## OpenEMR Configuration Requirements

Hard requirements:

- Enable OpenEMR Standard FHIR REST API.
- Register the Co-Pilot as a SMART/OAuth client.
- Keep OpenEMR API response logging at metadata/minimal level, not full body logging.
- Use HTTPS for any non-local demo.
- Use user-scoped bearer tokens for chat-time FHIR reads.
- Do not use a service token for user-scoped patient reads.

Recommended MVP scopes to validate:

```text
openid
profile
fhirUser
launch/patient
patient/*.read
user/Practitioner.read
user/Appointment.read
```

Final scopes should be narrowed after tool coverage is known.

## Health Checks

API:

```text
GET /healthz
GET /api/capabilities
```

Web:

```text
GET /
```

Worker:

```text
python -m copilot_worker.healthcheck
```

OpenEMR dependency:

```text
GET {OPENEMR_FHIR_BASE_URL}/metadata
GET {OPENEMR_JWKS_URL}
```

## Release Gate

Before calling the MVP deployable:

- A user can log in through OpenEMR SMART/OAuth.
- FastAPI validates the OpenEMR-issued token.
- A user can search/select an authorized patient.
- The assistant can answer at least three source-backed questions:
  - demographics/context
  - active problems
  - recent labs
- Every factual answer has inline citations.
- Unsupported treatment recommendation requests are refused.
- Logs do not contain raw PHI.
- Source links re-check authorization.
- Railway URL is recorded in `MVP_STATUS.md`.
