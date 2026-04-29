# Clinical Co-Pilot MVP Status

## Deployed URL (Stage 2 hard gate)

| Environment | URL |
|---|---|
| OpenEMR fork on Railway | https://openemr-production-f5ed.up.railway.app |

Login: `admin` / `<OE_PASS>` (set via `railway variables` on the openemr service; not committed). The first boot runs OpenEMR's `setup.php` against an empty MySQL and can take several minutes while assets are compiled; the readiness endpoint is `/meta/health/readyz`.

Latest verified Railway deployment:

```text
Service: openemr
Deployment: 2ef7363d-6a3d-40f5-bfc6-39c45ccec499
Status: SUCCESS
Verified: OpenEMR login page, admin login, and FHIR metadata return successfully.
```

## Current State

The MVP direction is now the standalone AgentForge Clinical Co-Pilot:

- Next.js chat UI.
- FastAPI backend.
- OpenEMR SMART/OAuth for authentication.
- OpenEMR FHIR as the primary chart data source.
- Optional read-only OpenEMR MySQL fallback for ETL gaps.
- Postgres with `pgvector` and `pgcrypto` for derived indexes, encrypted conversations, audit metadata, and eval support.
- Railway deployment target.

The first standalone scaffold has been started under `copilot/`:

- `copilot/api`: FastAPI app with health, capabilities, OpenEMR FHIR patient search, JWKS-backed bearer validation, deterministic evidence tools, chat SSE endpoint, source-link endpoint, mock provider, and verifier tests.
- `copilot/web`: Next.js chat shell with dev session display, patient search/select, quick questions, message composer, SSE stream parsing, citations, trace display, and Playwright smoke coverage.
- `copilot/worker`: worker placeholder for ETL, prefetch, and reindex jobs.

## Completed Planning Artifacts

- `PRESEARCH.md`: pre-code planning and constraints.
- `AUDIT.md`: OpenEMR security, performance, architecture, data quality, and compliance audit.
- `USERS.md`: target users, workflow, roles, use cases, and demo scenario.
- `USER.md`: compatibility pointer to `USERS.md`.
- `ARCHITECTURE.md`: standalone technical architecture.
- `MVP_AUTH_SCOPE.md`: tonight's local-demo auth scope and explicit production-auth exclusions.
- `DEPLOYMENT_RUNBOOK.md`: local and Railway deployment plan.
- `OPENEMR_VERSION_PIN.md`: OpenEMR version and commit verified for planning.
- `DEMO_PLAN.md`: 3-5 minute demo script.
- `EVAL_PLAN.md`: deterministic eval plan and fixtures.

## Environment Status

Docker Desktop is installed and the OpenEMR `docker/development-easy` stack is running.

Verified local OpenEMR:

```text
OpenEMR HTTP:  http://localhost:8300/
OpenEMR HTTPS: https://localhost:9300/
FHIR metadata: http://localhost:8300/apis/default/fhir/metadata
Login: admin / pass
```

The FHIR metadata endpoint returns a `CapabilityStatement`.

Seeded serious demo patient:

```text
Name: Elena Morrison
OpenEMR public id: AF-MVP-001
Search term: mo
FHIR patient id: c3888c9f-432d-11f1-a700-7a0f44501ceb
Data: demographics, 3 active problems, 3 recent labs
```

Recreate or refresh the seed with:

```powershell
.\copilot\scripts\seed-openemr-demo-patient.ps1
```

Because generated Co-Pilot dependency/temp folders under `copilot/` caused OpenEMR's dev rsync to fail, the local OpenEMR stack is mounted from a clean tracked-file copy:

```text
.runtime/openemr-clean
```

Rebuild that copy after OpenEMR source changes with:

```powershell
git checkout-index -a -f --prefix=.runtime/openemr-clean/
```

Current verified local Co-Pilot demo services:

```text
API: http://127.0.0.1:8001
Web: http://127.0.0.1:3001
```

Verified endpoints from the scaffold:

```text
GET  /healthz
GET  /api/capabilities
POST /api/chat
GET  /api/patients?query=
GET  /api/source/openemr/{resourceType}/{id}
```

The patient search, chat evidence, and source endpoints now support real OpenEMR FHIR calls with either a user bearer token or a local-only dev password-grant token. Production-style bearer validation against OpenEMR JWKS is implemented on the API side; the browser SMART authorization-code login still needs to be wired. Chat currently uses deterministic FHIR retrieval plus a mock provider, not an external LLM. The retrieval layer supports patient demographics, active problems, recent labs, active medications, and allergies, then verifies that final citations belong to the selected patient. Treatment recommendation requests are refused by policy before answer generation.

Tonight's auth scope is intentionally local-demo only:

- FastAPI identifies the request as `dev-doctor`.
- The API uses OpenEMR's local password grant to obtain a dev FHIR token.
- Full browser SMART login and deployed-role mapping are explicitly deferred.
- All chart access remains read-only.

Current verification:

```text
pytest: 37 passed, 5 skipped
ruff: all checks passed
mypy: success
web build: success
web npm audit: 0 vulnerabilities
Playwright smoke: 1 passed
previous live OpenEMR smoke: 5 passed
```

## Open Questions To Close

1. Which OpenEMR roles and SMART scopes map to doctor, NP/PA, nurse, and MA in the test environment?
2. Which provider is PHI-approved for the first real deployment: Anthropic, OpenRouter, or local model only?
3. Should on-demand patient reindex be available to nurses/MAs, or only clinicians/admins?
4. What exact OpenEMR role claim/role mapping should be used for the deployed SMART tokens?

## Next Build Milestones

1. Wire the frontend SMART/OAuth authorization-code login and callback flow.
2. Add Postgres schema for encrypted conversations, audit events, and evidence index.
3. Add Anthropic/OpenRouter/local provider adapters behind PHI gates.
4. Add deterministic eval fixtures for the serious demo patient scenario.
5. Deploy Railway `web`, `api`, `worker`, and `postgres` services.
