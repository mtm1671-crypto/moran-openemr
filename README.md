# AgentForge Clinical Co-Pilot

AgentForge Clinical Co-Pilot is an OpenEMR-integrated clinical chart assistant. This repository is an OpenEMR fork plus a standalone Co-Pilot stack built with Next.js and FastAPI.

The product goal is narrow and practical: a clinician launches Co-Pilot from OpenEMR, authenticates through SMART/OAuth, selects an authorized patient, asks chart questions, and receives concise source-backed answers with citations. The MVP is read-only and refuses treatment, diagnosis, medication-change, order, or care-plan recommendations.

This is a synthetic-data demo. Do not use the current OpenRouter demo model path with real PHI.

## Live Demo

| Service | URL |
|---|---|
| OpenEMR fork | https://openemr-production-f5ed.up.railway.app |
| Co-Pilot web | https://copilot-web-production.up.railway.app |
| Co-Pilot API | https://copilot-api-production-9f84.up.railway.app |
| API readiness | https://copilot-api-production-9f84.up.railway.app/readyz |

Use the deployed OpenEMR demo clinician credentials from Railway variables. Do not commit credentials or API keys to the repo.

## Submission Artifacts

| Requirement | Artifact |
|---|---|
| Final submission packet | [SUBMISSION.md](SUBMISSION.md) |
| Forked OpenEMR repo with setup guide, architecture overview, and deployed link | This [README.md](README.md) |
| Audit document with one-page summary and findings | [AUDIT.md](AUDIT.md) |
| User document and use cases | [USER.md](USER.md) |
| Agent architecture document with one-page summary | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Week 2 architecture design | [W2_ARCHITECTURE.md](W2_ARCHITECTURE.md) |
| Early submission readiness checklist | [EARLY_SUBMISSION_CHECKLIST.md](EARLY_SUBMISSION_CHECKLIST.md) |
| Demo video plan and walkthrough checklist | [DEMO_PLAN.md](DEMO_PLAN.md) and [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md) |
| Eval dataset, test suite, and results | [EVAL_DATASET.md](EVAL_DATASET.md) |
| AI cost analysis | [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md) |

## What To Show In Final Submission

The final walkthrough should prove the complete product path, not just a standalone chat screen.

1. Open deployed OpenEMR.
2. Log in as the demo clinician.
3. Launch the top-level `Co-Pilot` entry.
4. Complete the OpenEMR SMART/OAuth authorization flow if prompted.
5. Confirm Co-Pilot shows an authenticated clinician session.
6. Select a seeded patient from the top patient dropdown.
7. Ask a broad chart question.
8. Ask an unstructured-note question.
9. Click citations/source links.
10. Ask a treatment recommendation question and show the read-only refusal.
11. Upload a synthetic intake/lab document.
12. Show extraction, bounding-box source preview, approval, and approved document evidence in chat.

Recommended demo prompts:

```text
What should I know before seeing this patient?
Summarize recent clinical notes for this patient.
What adherence or social barriers are documented?
Show current medications and allergies.
What medication changes should I make?
What social barriers are documented?
```

## Current Status

Working in the deployed demo:

- OpenEMR runs on Railway.
- OpenEMR contains top-level and patient-context Co-Pilot launch points.
- Co-Pilot web runs on Railway.
- Co-Pilot API runs on Railway.
- SMART/OAuth login and callback are wired through the web service.
- The web service stores the OpenEMR bearer token in an encrypted HttpOnly session cookie.
- Same-origin `/api/*` proxy requests inject the bearer token into API calls.
- FastAPI validates OpenEMR bearer tokens against OpenEMR JWKS.
- Patient dropdown lists seeded patients the clinician can access.
- Chat retrieves patient-scoped OpenEMR FHIR evidence.
- Answers include citations and source links.
- Unsupported treatment recommendation requests are refused.
- OpenRouter is enabled for synthetic demo data with `nvidia/nemotron-3-super-120b-a12b:free`.
- Local Week 2 document workflow supports synthetic lab/intake upload, extraction, bounding-box citation preview, human approval, lab write adapter, and approved document facts in chat evidence.

Latest API verification:

```text
pytest: 114 passed, 5 skipped
ruff: all checks passed
mypy: success
pip-audit: no known vulnerabilities found
npm audit: no known vulnerabilities found
web build: passed
Playwright: 7 passed
production /readyz: ok
openrouter_configured: true
pgvector_backend: true
```

## Demo Data

The Railway seed script refreshes 15 synthetic patients. Each has demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent lab results, and 4 unstructured clinical notes exposed through FHIR `DocumentReference`.

| Public ID | Patient | Search |
|---|---|---|
| AF-MVP-001 | Elena Morrison | `mo` |
| AF-MVP-002 | Marcus Chen | `chen` |
| AF-MVP-003 | Priya Shah | `priya` |
| AF-MVP-004 | Rosa Alvarez | `rosa` |
| AF-MVP-005 | Daniel Okafor | `okafor` |
| AF-MVP-006 | Mei Tanaka | `tanaka` |
| AF-MVP-007 | Andre Williams | `andre` |
| AF-MVP-008 | Nadia Petrova | `nadia` |
| AF-MVP-009 | Samuel Brooks | `brooks` |
| AF-MVP-010 | Leah Kim | `leah` |
| AF-MVP-011 | Jamal Price | `jamal` |
| AF-MVP-012 | Owen Gallagher | `owen` |
| AF-MVP-013 | Aisha Rahman | `aisha` |
| AF-MVP-014 | Victor Nguyen | `victor` |
| AF-MVP-015 | Grace Bennett | `grace` |

Refresh deployed Railway demo data:

```powershell
.\copilot\scripts\seed-openemr-railway-demo-patient.ps1
```

Refresh local demo data:

```powershell
.\copilot\scripts\seed-openemr-demo-patient.ps1
```

## System Architecture

```text
Clinician browser
  -> OpenEMR Railway app
  -> OpenEMR Co-Pilot bridge with SMART iss/aud/launch context
  -> Co-Pilot web /api/auth/start
  -> OpenEMR OAuth login and scope consent
  -> Co-Pilot web /api/auth/callback
  -> encrypted HttpOnly copilot_session cookie
  -> Co-Pilot same-origin /api/* proxy
  -> FastAPI validates OpenEMR bearer token
  -> OpenEMR FHIR patient and evidence reads
  -> selected-patient vector indexing/search in Postgres
  -> optional external embedding/evidence ranking
  -> LLM provider adapter
  -> verifier checks selected-patient citations and read-only policy
  -> UI renders cited answer, trace, and source links
```

Vector search is patient-scoped and lazy-indexed. On a chart question, the API searches the selected patient's vector index first. On a cold index, it fetches source evidence through OpenEMR FHIR, stores encrypted evidence payloads in Postgres, stores only hashed patient/resource references, embeds the searchable text, writes semantic relationship rows, and searches the selected patient's vector index. Vector hits are re-read from OpenEMR FHIR before entering the model context so stale index text does not become the final evidence source. Production should use `VECTOR_INDEX_BACKEND=pgvector`; the JSON backend remains a local/demo fallback. The demo deployment uses the local deterministic `hash` embedding provider so PHI does not leave the API for indexing. An OpenAI embedding provider is wired but requires the existing OpenAI PHI approval flags before real PHI can be sent out.

Agent execution is a bounded server-orchestrated loop: access check, schema-declared evidence tools, encrypted cache lookup/write, patient-scoped vector search, source hydration, model answer generation, fallback if model output fails schema/citation validation, and final verifier. Verified answers are persisted to encrypted conversation/message rows, and PHI-safe audit events are written for chat completions and source reads. Nightly maintenance repairs PHI storage schema and purges expired cache/vector/audit/conversation/job rows. It can run as a Railway cron worker from `copilot/api/railway.worker.toml`; on the current single-service demo it is also wired as a guarded in-process API scheduler. Background patient reindex uses a backend OpenEMR service-account path and must not borrow a clinician OAuth session.

Reliability behavior is intentionally bounded. OpenEMR FHIR, JWKS, token, OpenAI, and OpenRouter calls retry transient 408/409/425/429/5xx and network timeout failures with short exponential backoff. Authorization failures still fail closed. Evidence-cache and vector-index outages degrade to live selected-patient OpenEMR FHIR evidence with an audit limitation. If audit persistence is required and unavailable, the API withholds the answer and returns an explicit failure final event instead of leaking an unaudited answer.

Repository layout:

```text
.
  OpenEMR fork files
  interface/agentforge/copilot.php      OpenEMR launch bridge
  interface/main/tabs/menu/...          Co-Pilot menu entries
  library/globals.inc.php               Co-Pilot URL connector setting

  copilot/
    api/       FastAPI auth, FHIR retrieval, chat, provider adapters, verifier
    web/       Next.js SMART auth, proxy, patient dropdown, chat UI
    worker/    Future ETL, prefetch, reindex, and embedding jobs
    scripts/   Demo seeding and readiness utilities
```

## Agent Flow

The assistant is constrained to a selected patient and source-backed chart evidence.

1. The user chooses a patient from the authorized dropdown.
2. The API retrieves OpenEMR FHIR evidence for the question.
3. Evidence is normalized into `EvidenceObject` records with source URLs.
4. The model receives only the selected-patient evidence bundle.
5. The model returns an answer plus cited evidence IDs.
6. The verifier rejects unknown citations, cross-patient citations, source URL mismatches, and treatment recommendations.
7. The UI displays only verified final answers.

The model cannot choose a different patient ID, invent source IDs, call arbitrary SQL, or override system rules from clinical note text.

## Safety And PHI Guardrails

Current deployment is for synthetic data only.

Implemented controls:

- SMART/OAuth authorization through OpenEMR.
- OpenEMR bearer validation against JWKS.
- Server-side role/request user context.
- Patient-scoped FHIR retrieval.
- Source links re-read OpenEMR FHIR resources and re-check authorization.
- Read-only MVP policy blocks treatment, medication-change, order, diagnosis, and care-plan requests.
- API startup/readiness hard gates for PHI-mode configuration.
- Encrypted metadata/audit and evidence-cache primitives.
- Patient-scoped vector index with encrypted evidence payloads and hashed identifiers.
- Optional production `pgvector` backend with local JSON fallback.
- Vector hits are refreshed through OpenEMR FHIR before model context assembly.
- Encrypted evidence cache scoped to patient plus clinician/session context.
- Encrypted conversation/message retention with 30-day default cleanup.
- Durable PHI-safe audit events for chat completions and source reads.
- Job status and semantic relationship tables for reindex/ETL visibility.
- Nightly maintenance job for expired cache/vector/audit/conversation/job retention cleanup.
- Backend service-account reindex path for worker jobs.
- Bounded retry/backoff for OpenEMR, JWKS/token, and model-provider calls.
- Explicit degraded-mode audit limitations for cache/vector failures.
- Frontend chat stream timeout and malformed-event handling so requests do not appear stalled.
- Model/provider routing flags separate demo egress from PHI-approved egress.
- No API keys should be committed; provider keys belong only in Railway env vars.

Provider policy:

- `LLM_PROVIDER=openrouter` is currently allowed only with `OPENROUTER_DEMO_DATA_ONLY=true`.
- Real PHI requires a reviewed provider path with BAA/data-policy confirmation flags.
- OpenAI support is implemented but disabled unless `ALLOW_PHI_TO_OPENAI`, `OPENAI_BAA_CONFIRMED`, and `OPENAI_DATA_POLICY_CONFIRMED` are explicitly true.
- OpenRouter must not be used for real PHI unless `ALLOW_PHI_TO_OPENROUTER`, `OPENROUTER_BAA_CONFIRMED`, and `OPENROUTER_DATA_POLICY_CONFIRMED` are explicitly true.

## Local Development

### OpenEMR

Start the local OpenEMR development stack:

```powershell
cd docker/development-easy
$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Docker\Docker\resources;C:\Program Files\Docker\cli-plugins;' + $env:Path
docker compose up --detach --wait
```

Local OpenEMR:

```text
URL: http://localhost:8300/
Login: admin / pass
FHIR metadata: http://localhost:8300/apis/default/fhir/metadata
```

Register a local-only OpenEMR OAuth client for password-grant smoke tests:

```powershell
cd copilot
.\scripts\register-openemr-dev-client.ps1
```

Password grant is local development only. Production uses SMART authorization-code flow through the web service.

### API

```powershell
cd copilot/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

API checks:

```powershell
cd copilot/api
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app tests
```

Optional live OpenEMR smoke:

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

### Web

```powershell
cd copilot/web
npm install
npm run dev -- --port 3001
```

Web checks:

```powershell
cd copilot/web
npm audit --audit-level=moderate
npm run build
npm run test:e2e -- --project=chromium
```

## Railway Deployment

Deploy the OpenEMR fork from the repository root:

```powershell
railway up --service openemr
```

Deploy Co-Pilot services:

```powershell
railway up --service copilot-api .\copilot\api --path-as-root
railway up --service copilot-web .\copilot\web --path-as-root
```

If Windows file locks or ignored folders block `railway up`, stage only the service files into a temp directory and deploy that staged folder with `--no-gitignore --path-as-root`.

Key API variables:

```text
APP_ENV=production
PHI_MODE=true
PUBLIC_BASE_URL=https://<copilot-web-domain>
DATABASE_URL=postgresql://...
ENCRYPTION_KEY=<fernet-key>
DEV_AUTH_BYPASS=false
OPENEMR_BASE_URL=https://<openemr-domain>
OPENEMR_FHIR_BASE_URL=https://<openemr-domain>/apis/default/fhir
OPENEMR_OAUTH_TOKEN_URL=https://<openemr-domain>/oauth2/default/token
OPENEMR_JWKS_URL=https://<openemr-domain>/oauth2/default/jwk
OPENEMR_JWT_ISSUER=https://<openemr-domain>/oauth2/default
OPENEMR_JWT_AUDIENCE=<smart-client-id>
OPENEMR_TLS_VERIFY=true
OPENEMR_API_LOG_OPTION=1
OPENEMR_DEV_PASSWORD_GRANT=false
OPENEMR_CLIENT_ID=<smart-client-id>
OPENEMR_CLIENT_SECRET=<smart-client-secret>
LLM_PROVIDER=openrouter
EMBEDDING_PROVIDER=none
VECTOR_SEARCH_ENABLED=true
VECTOR_EMBEDDING_PROVIDER=hash
VECTOR_EMBEDDING_DIMENSIONS=256
VECTOR_SEARCH_LIMIT=6
VECTOR_CANDIDATE_LIMIT=200
EVIDENCE_CACHE_ENABLED=true
EVIDENCE_CACHE_TTL_SECONDS=300
AGENT_LOOP_MAX_STEPS=10
NIGHTLY_MAINTENANCE_ENABLED=true
NIGHTLY_MAINTENANCE_HOUR_UTC=8
OPENROUTER_API_KEY=<railway-secret>
OPENROUTER_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_DEMO_DATA_ONLY=true
ALLOW_PHI_TO_OPENROUTER=false
ALLOW_PHI_TO_LOCAL=false
```

Key web variables:

```text
PUBLIC_BASE_URL=https://<copilot-web-domain>
COPILOT_API_BASE_URL=https://<copilot-api-domain>
OPENEMR_BASE_URL=https://<openemr-domain>
OPENEMR_SITE=default
OPENEMR_CLIENT_ID=<smart-client-id>
OPENEMR_CLIENT_SECRET=<smart-client-secret-if-confidential>
OPENEMR_TOKEN_AUTH_METHOD=client_secret_basic
COPILOT_SESSION_SECRET=<at-least-32-random-bytes>
```

Run the PHI/readiness gate before production-style deploys:

```powershell
.\copilot\scripts\phi-readiness-check.ps1
```

Health checks:

```text
OpenEMR: GET /meta/health/readyz
API:     GET /readyz
Web:     GET /
```

## Final Submission Checklist

Before submitting:

- Rotate any provider key that was pasted into chat or logs.
- Confirm no secrets are committed.
- Confirm Railway variables, not files, hold provider keys and session secrets.
- Confirm `/readyz` is green.
- Confirm OpenEMR launch to Co-Pilot works from the deployed app.
- Confirm patient dropdown lists the seeded patients.
- Confirm a Nemotron/OpenRouter answer returns for synthetic data.
- Confirm unstructured notes are included in answers.
- Confirm source links open and show FHIR JSON.
- Confirm treatment recommendations are refused.
- Record the required 35-minute walkthrough video.
- Include repo URL, deployed URLs, and video URL in the AgentForge submission.

## Reference Documents

The root README is the source of truth for final submission. The remaining Markdown files are supporting references:

| Document | Purpose |
|---|---|
| [SUBMISSION.md](SUBMISSION.md) | Final submission links, artifact map, verification snapshot, demo checklist, and caveats |
| [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md) | Earlier deployed walkthrough screenshots and proof notes |
| [EARLY_SUBMISSION_CHECKLIST.md](EARLY_SUBMISSION_CHECKLIST.md) | Week 2 early submission blockers, smoke path, and deployment checklist |
| [DEMO_PLAN.md](DEMO_PLAN.md) | Demo script and talk track |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | Longer deployment notes and environment checklists |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deeper architecture plan and future-state design |
| [W2_ARCHITECTURE.md](W2_ARCHITECTURE.md) | Week 2 multimodal document, worker graph, RAG, eval gate, and risk design |
| [USER.md](USER.md) | Primary user, supporting users, use cases, and MVP non-goals |
| [MVP_STATUS.md](MVP_STATUS.md) | Historical MVP status and roadmap notes |
| [EVAL_PLAN.md](EVAL_PLAN.md) | Eval and fixture plan |
| [EVAL_DATASET.md](EVAL_DATASET.md) | Eval dataset, automated test coverage, and latest results |
| [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md) | Actual recorded dev AI spend and production cost projections |
| [AUDIT.md](AUDIT.md) | OpenEMR audit notes |
| [PLANNING.md](PLANNING.md) | Index of planning artifacts |

Upstream OpenEMR documentation remains in the original directories, including [DOCKER_README.md](DOCKER_README.md), [FHIR_README.md](FHIR_README.md), [API_README.md](API_README.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This fork preserves OpenEMR's [GNU GPL v3](LICENSE) license. AgentForge additions are released under the same terms.

OpenEMR upstream: https://github.com/openemr/openemr
