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

The intended final product placement is a top-level OpenEMR `Co-Pilot` tab alongside daily workflow areas such as Schedule/Calendar. Opening the tab globally should show authorized patient search and schedule context. Opening it from a patient chart or schedule row should launch the same Co-Pilot workspace with that patient already selected. The standalone Next.js/FastAPI services remain the implementation boundary, while OpenEMR owns navigation, identity, permissions, and source-of-truth chart records.

The first standalone scaffold has been started under `copilot/`:

- `copilot/api`: FastAPI app with health, capabilities, OpenEMR FHIR patient search, JWKS-backed bearer validation, deterministic evidence tools, chat SSE endpoint, source-link endpoint, mock provider, and verifier tests.
- `copilot/web`: Next.js chat shell with SMART auth start/callback routes, encrypted HttpOnly session cookies, same-origin bearer-token proxying, patient search/select, quick questions, message composer, SSE stream parsing, citations, trace display, and Playwright smoke coverage.
- `copilot/worker`: worker placeholder for ETL, prefetch, and reindex jobs.

Step 1 of the final-product roadmap has started in OpenEMR itself:

- Main menu roles now expose a top-level `Co-Pilot` tab.
- The patient chart menu includes a patient-scoped `Co-Pilot` launch.
- Flow Board schedule rows include a `Co-Pilot` action that passes patient and appointment context.
- `interface/agentforge/copilot.php` bridges OpenEMR navigation to the standalone Co-Pilot web app, using the `AgentForge Clinical Co-Pilot URL` Connectors global or `AGENTFORGE_COPILOT_URL`.
- Patient and schedule launches include SMART `iss`, `aud`, and `launch` parameters when patient context is available.
- The Co-Pilot web/API can accept an incoming `patient_id` launch context and preselect that patient.

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

Seeded serious demo patients:

```text
Name: Elena Morrison
OpenEMR public id: AF-MVP-001
Search term: mo
FHIR patient id: c3888c9f-432d-11f1-a700-7a0f44501ceb
Data: demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent labs, 4 clinical notes

Name: Marcus Chen
OpenEMR public id: AF-MVP-002
Search term: chen
FHIR patient id: 5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02
Data: demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent labs, 4 clinical notes

Name: Priya Shah
OpenEMR public id: AF-MVP-003
Search term: priya
FHIR patient id: f0d8bb04-8d8f-4e66-8f59-ecf2d8d98f34
Data: demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent labs, 4 clinical notes

Additional expanded synthetic test panel:
AF-MVP-004 Rosa Alvarez, search rosa
AF-MVP-005 Daniel Okafor, search okafor
AF-MVP-006 Mei Tanaka, search tanaka
AF-MVP-007 Andre Williams, search andre
AF-MVP-008 Nadia Petrova, search nadia
AF-MVP-009 Samuel Brooks, search brooks
AF-MVP-010 Leah Kim, search leah
AF-MVP-011 Jamal Price, search jamal
AF-MVP-012 Owen Gallagher, search owen
AF-MVP-013 Aisha Rahman, search aisha
AF-MVP-014 Victor Nguyen, search victor
AF-MVP-015 Grace Bennett, search grace

Each expanded patient has demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent labs, and 4 clinical notes exposed through FHIR `DocumentReference`.
```

Recreate or refresh the seed with:

```powershell
.\copilot\scripts\seed-openemr-demo-patient.ps1
```

Refresh the same synthetic patient in the deployed Railway OpenEMR service after `railway login`:

```powershell
.\copilot\scripts\seed-openemr-railway-demo-patient.ps1
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

The patient search, chat evidence, and source endpoints now support real OpenEMR FHIR calls with either a user bearer token or a local-only dev password-grant token. Production-style bearer validation against OpenEMR JWKS is implemented on the API side. The browser SMART authorization-code flow is now wired in the web service: `/api/auth/start` redirects to OpenEMR, `/api/auth/callback` exchanges the code server-side, and the same-origin proxy injects the OpenEMR bearer token into API requests without forwarding browser cookies. Chat currently uses deterministic FHIR retrieval plus a mock provider, not an external LLM. The retrieval layer supports patient demographics, active problems, recent labs, active medications, and allergies, then verifies that final citations belong to the selected patient. Treatment recommendation requests are refused by policy before answer generation.

Local-demo mode still exists only for development:

- FastAPI identifies the request as `dev-doctor` only when `APP_ENV=local` and `DEV_AUTH_BYPASS=true`.
- The API can use OpenEMR's local password grant only when `OPENEMR_DEV_PASSWORD_GRANT=true`.
- PHI mode rejects both local auth shortcuts.
- All chart access remains read-only.

Current verification:

```text
pytest: 54 passed, 5 skipped
ruff: all checks passed
mypy: success
pip-audit: no known vulnerabilities
web build: success
web npm audit: 0 vulnerabilities
Playwright smoke: 5 passed
Docker builds: api, web, OpenEMR overlay passed
Container smoke: API /readyz, web /, web /api/me proxy passed
previous live OpenEMR smoke: 5 passed
```

## Open Questions To Close

1. Which OpenEMR roles and SMART scopes map to doctor, NP/PA, nurse, and MA in the test environment?
2. Which provider is PHI-approved after the first PHI-mode mock deployment? Current gate is `LLM_PROVIDER=mock` and all `ALLOW_PHI_TO_*` flags false.
3. Should on-demand patient reindex be available to nurses/MAs, or only clinicians/admins?
4. What exact OpenEMR role claim/role mapping should be used for the deployed SMART tokens?

## Final Product Roadmap

There are 8 major steps from the current MVP scaffold to the final product:

1. Initial implementation complete: add the OpenEMR product entry points with a top-level `Co-Pilot` tab, chart launch, and schedule-row launch.
2. Production SMART/OAuth authorization-code login is wired in the frontend; next is live OpenEMR client registration and deployed callback verification.
3. Finalize OpenEMR role, scope, and patient-access mapping for doctor, NP/PA, nurse, MA, and admin users.
4. Deploy the full Co-Pilot stack on Railway: `web`, `api`, `worker`, and `postgres`, connected to the deployed OpenEMR service.
5. Add Postgres persistence: encrypted metadata/audit and evidence cache primitives are in place; full encrypted conversations/messages and vector indexes remain next.
6. Expand retrieval coverage beyond the current demo set: schedule context, encounters, vitals, notes/documents, source links, and on-demand patient reindex.
7. Add real model provider adapters behind PHI gates, then keep deterministic claim verification, treatment-refusal behavior, and citation checks as release blockers.
8. Harden for release: CI eval suite, PHI-safe logging, retention/deletion controls, monitoring, backup/restore, deployment runbooks, and final demo walkthrough.
