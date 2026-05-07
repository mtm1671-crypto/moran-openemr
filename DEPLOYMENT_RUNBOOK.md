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

## OpenEMR Fork — Railway Deploy

The repository root ships with `Dockerfile`, `railway.toml`, `.dockerignore`, and `.railwayignore` so the OpenEMR fork itself can be deployed to Railway with one CLI flow. The Dockerfile inherits the official `openemr/openemr:flex` image at a pinned digest and identifies this build as the AgentForge fork via an `agentforge/` marker directory in the webroot. OpenEMR's PHP/Apache runtime is unchanged. The ignore files intentionally upload only the Dockerfile and fork-identifying docs because the full OpenEMR source tree is already inside the official base image.

The current Railway image also overlays the narrow Co-Pilot integration files that are required for the deployed app to show the Co-Pilot tab and bridge to the standalone web service:

- `interface/agentforge/copilot.php`
- Co-Pilot menu entries under `interface/main/tabs/menu/menus/`
- Flow Board launch wiring in `interface/patient_tracker/patient_tracker.php`
- The `AgentForge Clinical Co-Pilot URL` Connectors global in `library/globals.inc.php`
- `GlobalConnectorsEnum::AGENTFORGE_COPILOT_URL`

### One-time prerequisites

- A Railway account.
- Railway CLI installed locally: `npm install -g @railway/cli`.
- Authenticated: `railway login`.

### Deploy steps

```bash
# From the fork's repo root.
railway init                                         # create a new Railway project
railway add --database mariadb                        # provision managed MariaDB

# Set the env vars OpenEMR's official image consumes during first boot.
# Replace generated values with your own if you want stable known passwords.
OPENEMR_DB_PASS="$(openssl rand -hex 24)"
OPENEMR_OE_PASS="$(openssl rand -hex 24)"

railway variables \
  --set "MYSQL_HOST=\${{MariaDB.MARIADB_PRIVATE_HOST}}" \
  --set "MYSQL_ROOT_PASS=\${{MariaDB.MARIADB_ROOT_PASSWORD}}" \
  --set "MYSQL_USER=openemr" \
  --set "MYSQL_PASS=${OPENEMR_DB_PASS}" \
  --set "OE_USER=admin" \
  --set "OE_PASS=${OPENEMR_OE_PASS}" \
  --set "PORT=80"

railway up                                            # build the Dockerfile, deploy
railway domain                                        # generate a public URL
```

### First-boot expectations

- The official OpenEMR image runs `setup.php` against the empty MariaDB/MySQL service on first start and may compile assets. Expect several minutes before the app is ready.
- Readiness endpoint: `GET /meta/health/readyz` over HTTPS (set as the healthcheck path in `railway.toml`).
- Login at the generated URL with `admin` / `<OE_PASS value>`.

### After first deploy

- Record the public URL in the README "Deployed Application" table.
- Set OpenEMR's `api_log_option` global to `1` (Minimal Logging) before any non-synthetic data — see [AUDIT.md](AUDIT.md) finding S-1.
- Rotate `OE_PASS` from the demo value before any user-facing demo at scale.

For the synthetic Co-Pilot demo patient, seed Railway OpenEMR after first boot and after any database reset:

```powershell
.\copilot\scripts\seed-openemr-railway-demo-patient.ps1
```

Expected result: 15 synthetic patients are searchable. Start with `mo` for Elena Morrison, `chen` for Margaret Chen, `priya` for Priya Shah, then use `rosa`, `okafor`, `tanaka`, `andre`, `nadia`, `brooks`, `leah`, `jamal`, `owen`, `aisha`, `victor`, and `grace` for the expanded panel. Each seeded patient has 3 problems, 2 active medications, 1 allergy, 3 recent lab results, and 4 synthetic clinical notes exposed through FHIR `DocumentReference`. The script uses the Railway MySQL TCP proxy with injected database variables; it does not print database credentials.

### Why this Dockerfile shape

OpenEMR's official image is large but well-maintained and matches the local development setup. Building from scratch would re-implement Apache/PHP/MariaDB plumbing for no clinical benefit. The fork overlay is intentionally narrow: only the Co-Pilot launch/navigation files and fork-identifying docs are copied into the official runtime image.

## Railway Services (Co-Pilot stack — Thursday Early Submission)

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

OpenEMR can be deployed separately or accessed from an existing reachable demo instance. The Co-Pilot API and web services now have their own Dockerfile-based Railway configs:

- `copilot/api/railway.toml`
- `copilot/api/Dockerfile`
- `copilot/web/railway.toml`
- `copilot/web/Dockerfile`

### Synthetic-only demo deploy flow

The old Railway demo path used local-demo auth semantics: FastAPI identified the request as `dev-doctor` and used an OpenEMR password-grant OAuth client to read FHIR. That path is acceptable only for throwaway synthetic demos. It is not acceptable for PHI-mode, even if the current data set is mock data.

After `railway login`, create or select services:

```powershell
railway add --service copilot-api
railway add --service copilot-web
```

Set API variables on `copilot-api`:

```powershell
railway variable set --service copilot-api APP_ENV=local
railway variable set --service copilot-api PUBLIC_BASE_URL=https://<copilot-web-domain>
railway variable set --service copilot-api OPENEMR_BASE_URL=https://openemr-production-f5ed.up.railway.app
railway variable set --service copilot-api OPENEMR_SITE=default
railway variable set --service copilot-api OPENEMR_FHIR_BASE_URL=https://openemr-production-f5ed.up.railway.app/apis/default/fhir
railway variable set --service copilot-api OPENEMR_OAUTH_TOKEN_URL=https://openemr-production-f5ed.up.railway.app/oauth2/default/token
railway variable set --service copilot-api OPENEMR_TLS_VERIFY=true
railway variable set --service copilot-api OPENEMR_DEV_PASSWORD_GRANT=true
railway variable set --service copilot-api OPENEMR_DEV_USERNAME=admin
railway variable set --service copilot-api OPENEMR_DEV_PASSWORD=<deployed-openemr-admin-password>
railway variable set --service copilot-api OPENEMR_CLIENT_ID=<deployed-openemr-oauth-client-id>
railway variable set --service copilot-api OPENEMR_CLIENT_SECRET=<deployed-openemr-oauth-client-secret>
railway variable set --service copilot-api OPENEMR_DEV_SCOPES="openid offline_access api:oemr api:fhir user/Patient.read user/Practitioner.read user/Observation.read user/Condition.read user/MedicationRequest.read user/AllergyIntolerance.read user/DocumentReference.read"
railway variable set --service copilot-api LLM_PROVIDER=mock
railway variable set --service copilot-api ALLOW_PHI_TO_ANTHROPIC=false
railway variable set --service copilot-api ALLOW_PHI_TO_OPENROUTER=false
railway variable set --service copilot-api ALLOW_PHI_TO_LOCAL=true
```

Set web variables on `copilot-web`:

```powershell
railway variable set --service copilot-web COPILOT_API_BASE_URL=https://<copilot-api-domain>
railway variable set --service copilot-web PUBLIC_BASE_URL=https://<copilot-web-domain>
railway variable set --service copilot-web OPENEMR_BASE_URL=https://<openemr-domain>
railway variable set --service copilot-web OPENEMR_SITE=default
railway variable set --service copilot-web OPENEMR_CLIENT_ID=<deployed-openemr-smart-client-id>
railway variable set --service copilot-web OPENEMR_CLIENT_SECRET=<deployed-openemr-smart-client-secret-if-confidential>
railway variable set --service copilot-web OPENEMR_TOKEN_AUTH_METHOD=client_secret_basic
railway variable set --service copilot-web COPILOT_SESSION_SECRET=<at-least-32-random-bytes>
```

Deploy each service from its service folder:

```powershell
railway up --service copilot-api .\copilot\api --path-as-root
railway domain --service copilot-api

railway up --service copilot-web .\copilot\web --path-as-root
railway domain --service copilot-web
```

Enable and verify durable Week 2 document workflow persistence on `copilot-api`:

```powershell
railway login
.\copilot\scripts\enable-railway-document-workflow-persistence.ps1 -LinkProject
```

Expected proof after deploy:

```text
/readyz checks.document_workflow_persistence_enabled: true
/readyz checks.document_workflow_storage: true
/readyz checks.document_workflow_persistence_ready: true
/api/capabilities providers.document_workflow_persistence_ready: true
```

Finally point the deployed OpenEMR bridge to the hosted web app:

```powershell
railway variable set --service openemr AGENTFORGE_COPILOT_URL=https://<copilot-web-domain>
railway up --service openemr
```

If using the OpenEMR UI instead of an environment variable, set the Connectors global `AgentForge Clinical Co-Pilot URL` to `https://<copilot-web-domain>`.

### PHI-mode guardrails

For mock data that should be handled like PHI, set `PHI_MODE=true`. The API fails startup and `/readyz` fails unless every required control is configured. PHI-mode deployments must set:

```text
APP_ENV=production
PHI_MODE=true
DEV_AUTH_BYPASS=false
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
ENCRYPTION_KEY=<fernet-key>
ENCRYPTION_KEY_ID=primary
OPENEMR_DEV_PASSWORD_GRANT=false
OPENEMR_TLS_VERIFY=true
OPENEMR_API_LOG_OPTION=1
PUBLIC_BASE_URL=https://<copilot-web-domain>
OPENEMR_BASE_URL=https://<openemr-domain>
OPENEMR_FHIR_BASE_URL=https://<openemr-domain>/apis/default/fhir
OPENEMR_OAUTH_TOKEN_URL=https://<openemr-domain>/oauth2/default/token
OPENEMR_JWKS_URL=https://<openemr-domain>/oauth2/default/jwk
OPENEMR_JWT_ISSUER=<expected-openemr-token-issuer>
OPENEMR_JWT_AUDIENCE=<expected-openemr-token-audience>
LLM_PROVIDER=mock
ALLOW_PHI_TO_ANTHROPIC=false
ALLOW_PHI_TO_OPENROUTER=false
ALLOW_PHI_TO_LOCAL=false
```

Use `copilot/api/.env.production.example` and `copilot/web/.env.production.example` as the production variable checklist. The web service also requires `COPILOT_API_BASE_URL`, `OPENEMR_CLIENT_ID`, and `COPILOT_SESSION_SECRET` in production; without `COPILOT_API_BASE_URL`, same-origin `/api/*` proxy requests return a configuration error instead of attempting localhost.

Generate `ENCRYPTION_KEY` with:

```powershell
cd copilot/api
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Run the hard gate before deploy:

```powershell
.\copilot\scripts\phi-readiness-check.ps1
```

## Required Environment Variables

Shared:

```text
APP_ENV
PHI_MODE=true
PUBLIC_BASE_URL
DATABASE_URL
ENCRYPTION_KEY
ENCRYPTION_KEY_ID
DEV_AUTH_BYPASS=false
```

OpenEMR:

```text
OPENEMR_BASE_URL
OPENEMR_SITE=default
OPENEMR_FHIR_BASE_URL
OPENEMR_AUTHORIZATION_URL
OPENEMR_OAUTH_TOKEN_URL
OPENEMR_JWKS_URL=https://<openemr-domain>/oauth2/default/jwk
OPENEMR_JWT_ISSUER
OPENEMR_JWT_AUDIENCE
OPENEMR_TLS_VERIFY=true
OPENEMR_API_LOG_OPTION=1
OPENEMR_DEV_PASSWORD_GRANT=false
OPENEMR_CLIENT_ID
OPENEMR_CLIENT_SECRET
OPENEMR_TOKEN_AUTH_METHOD=client_secret_basic
OPENEMR_SCOPES
COPILOT_OAUTH_REDIRECT_URI=https://<copilot-web-domain>/api/auth/callback
COPILOT_SESSION_SECRET
COPILOT_COOKIE_SECURE=true
COPILOT_COOKIE_SAMESITE=none
```

Provider routing:

```text
LLM_PROVIDER
ANTHROPIC_API_KEY
OPENROUTER_API_KEY
LOCAL_MODEL_BASE_URL
ALLOW_PHI_TO_ANTHROPIC=false
ALLOW_PHI_TO_OPENROUTER=false
ALLOW_PHI_TO_LOCAL=false
```

Retention:

```text
CONVERSATION_RETENTION_DAYS=30
REINDEX_IDEMPOTENCY_SECONDS=120
JOB_STATUS_RETENTION_DAYS=30
CONVERSATION_PERSISTENCE_ENABLED=true
AUDIT_PERSISTENCE_REQUIRED=true
STRUCTURED_LOGGING_ENABLED=true
VECTOR_INDEX_BACKEND=pgvector
OPENEMR_SERVICE_ACCOUNT_ENABLED=false
NIGHTLY_REINDEX_ENABLED=false
OPENEMR_REQUEST_TIMEOUT_SECONDS=15
OPENEMR_RETRY_ATTEMPTS=3
OPENEMR_RETRY_BACKOFF_SECONDS=0.25
MODEL_RETRY_ATTEMPTS=2
MODEL_RETRY_BACKOFF_SECONDS=0.5
```

## OpenEMR Configuration Requirements

Hard requirements:

- Enable OpenEMR Standard FHIR REST API.
- Register the Co-Pilot as a SMART/OAuth client.
- Register `https://<copilot-web-domain>/api/auth/callback` as the Co-Pilot redirect URI.
- Keep OpenEMR API response logging at metadata/minimal level, not full body logging.
- Use HTTPS for any non-local demo.
- Use `COPILOT_COOKIE_SAMESITE=none` with `COPILOT_COOKIE_SECURE=true` when the Co-Pilot is embedded inside the OpenEMR tab/frame on a different origin. The web proxy rejects cross-site browser API requests before injecting the bearer token.
- Use user-scoped bearer tokens for chat-time FHIR reads.
- Do not use a service token for user-scoped patient reads.
- Use a backend OpenEMR service account only for worker/reindex jobs. Do not reuse a clinician OAuth token for background jobs.
- Keep `LLM_PROVIDER=mock` and every `ALLOW_PHI_TO_*` flag false until a signed BAA and no-retention provider path is approved.
- Store Co-Pilot audit metadata, encrypted conversations/messages, encrypted cache payloads, vector index payloads, job status, and semantic relationship rows with `ENCRYPTION_KEY`.

Recommended MVP scopes to validate:

```text
openid
api:oemr
api:fhir
fhirUser
launch
user/Patient.read
user/Practitioner.read
user/Observation.read
user/Condition.read
user/MedicationRequest.read
user/AllergyIntolerance.read
user/DocumentReference.read
```

Final scopes should be narrowed after tool coverage is known.

## Health Checks

API:

```text
GET /healthz
GET /readyz
GET /api/capabilities
GET /api/vector/status
GET /api/observability/status
GET /api/jobs/{job_id}
POST /api/patients/{patient_id}/reindex
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
- The web callback exchanges the authorization code server-side and stores the bearer token only in an encrypted HttpOnly cookie.
- The web same-origin proxy injects `Authorization: Bearer <OpenEMR token>` and does not forward browser cookies to the API service.
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
- `/readyz` reports green for operational storage, audit persistence, conversation persistence, job status storage, evidence cache, and vector store.
- `/api/vector/status` reports `backend=pgvector` for production.
- Transient OpenEMR, JWKS, token, OpenAI, and OpenRouter failures use bounded retry/backoff. Non-retryable authorization failures still fail closed.
- Evidence cache or vector-index outages degrade to live selected-patient OpenEMR FHIR evidence with an explicit audit limitation instead of stalling the chat.
- If audit persistence is required and unavailable, the API withholds the answer and returns an explicit `audit_persistence_failed` final event.
- A cold patient index can be built through `POST /api/patients/{patient_id}/reindex` using the backend service account.
- Chat evidence includes vector search and source hydration before the model context is built.
- A chat completion writes encrypted conversation/message rows and a PHI-safe audit event.
- Railway URL is recorded in `MVP_STATUS.md`.
