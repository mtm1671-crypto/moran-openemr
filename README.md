# Moran OpenEMR

A fork of [OpenEMR](https://github.com/openemr/openemr) that adds **AgentForge Clinical Co-Pilot**: a read-only, source-backed chart assistant that clinicians launch from inside OpenEMR, plus a document-evidence workflow and a separate adversarial security platform that continuously attacks the assistant to prove it stays inside its guardrails.

Everything in this repository runs on synthetic data. Do not point the demo model path at real PHI.

## Why This Project Is Interesting

Most "AI in the EHR" demos are a chat box bolted onto a FHIR endpoint. This fork treats the assistant as a regulated clinical system and builds the surrounding engineering to match:

- **The EHR stays authoritative.** Patient identity, clinician identity, ACLs, and every FHIR resource remain inside OpenEMR. Co-Pilot authenticates through OpenEMR's own SMART/OAuth flow and validates bearer tokens against OpenEMR's JWKS. The model never sees a patient it is not authorized for and cannot choose one on its own.
- **Every answer is verifiable.** The model only receives a selected-patient evidence bundle and must return citation IDs. A deterministic verifier rejects unknown citations, cross-patient citations, source URL mismatches, and any treatment, diagnosis, medication-change, order, or care-plan recommendation before the UI ever renders the answer. Source links re-read the live FHIR resource and re-check authorization on click.
- **Documents become evidence, not just text.** Scanned lab reports and intake forms go through extraction with bounding-box citations, a side-by-side human review screen, and an explicit approval step. Only approved, high-confidence facts can be written back to OpenEMR, and that write path is idempotent with round-trip read verification.
- **Safety is tested adversarially, on purpose.** `security/adversarial/` is a standalone FastAPI/LangGraph operator platform that runs authenticated black-box attacks against the deployed Co-Pilot API: cross-patient PHI probes, prompt injection (direct, indirect, multi-turn), identity hijacking, tool misuse, cost amplification, citation manipulation. Verdicts, traces, and reports are persisted and replayed as a CI regression gate.
- **Cost and scale are designed in, not bolted on.** Structured questions are answered from verified FHIR objects without an LLM; simple summaries route to the cheapest eval-approved model; only broad note synthesis reaches a stronger model under strict token caps. Patient-scoped vector search uses hashed identifiers and encrypted payloads, and vector hits are re-hydrated from FHIR before they enter model context so stale index text never becomes the evidence of record.
- **It is deployed and measurable.** The full stack (OpenEMR fork, Co-Pilot web, Co-Pilot API, adversarial operator) runs on Railway with readiness gates, a 50-case deterministic eval suite that fails CI on regression, security-header and dependency-manifest checks on the OpenEMR surface, and a recorded cost analysis.

The thesis is simple: a clinical assistant is only useful if a clinician can trust it in the 90 seconds between rooms, and trust is an engineering property you can test.

## Live Demo

| Service | URL |
|---|---|
| OpenEMR fork | https://openemr-production-f5ed.up.railway.app |
| Co-Pilot web | https://copilot-web-production.up.railway.app |
| Co-Pilot API | https://copilot-api-production-9f84.up.railway.app |
| API readiness | https://copilot-api-production-9f84.up.railway.app/readyz |
| Adversarial operator | https://adversarial-production.up.railway.app |

Demo clinician credentials live in Railway variables. No credentials or API keys are committed to this repo.

A representative walkthrough: log in to OpenEMR, open the top-level `Co-Pilot` entry, complete the SMART authorization prompt, pick a seeded patient, ask *"What should I know before seeing this patient?"*, click through a citation to the source record, then ask *"What medication changes should I make?"* and watch the read-only refusal. From the same screen, `Open document workflow` uploads a synthetic lab or intake document and shows extraction, bounding-box source preview, approval, and the approved facts appearing as chat evidence.

Live working/limited/blocked capability status is available in the web app at `/status`.

## What The Fork Adds To OpenEMR

```text
interface/agentforge/copilot.php      OpenEMR -> Co-Pilot launch bridge (SMART iss/aud/launch context)
interface/main/tabs/menu/...          Top-level and patient-context Co-Pilot menu entries
library/globals.inc.php               Co-Pilot URL connector setting
src/Services/Globals/...              Connector enum entries
Dockerfile, railway.toml              Hardened Railway deployment of the fork

copilot/
  api/       FastAPI: auth, FHIR retrieval, vector search, chat, provider adapters, verifier,
             document ingestion/extraction/review/write, eval gate
  web/       Next.js: SMART auth, encrypted session cookie, same-origin API proxy,
             patient selector, chat + citation UI, document review, /dashboard
  worker/    ETL, prefetch, reindex, and embedding jobs
  scripts/   Demo seeding, readiness checks, deployment helpers

security/
  adversarial/   Operator platform: attack corpus, target harness, judge, reports, UI
  docs/          Product spec and evidence packet for the adversarial platform
```

The upstream OpenEMR tree is otherwise intact, including its own documentation ([DOCKER_README.md](DOCKER_README.md), [FHIR_README.md](FHIR_README.md), [API_README.md](API_README.md), [CONTRIBUTING.md](CONTRIBUTING.md)).

## How A Question Is Answered

```text
Clinician browser
  -> OpenEMR (Railway)
  -> Co-Pilot bridge with SMART iss/aud/launch context
  -> Co-Pilot web /api/auth/start
  -> OpenEMR OAuth login and scope consent
  -> Co-Pilot web /api/auth/callback -> encrypted HttpOnly copilot_session cookie
  -> Co-Pilot same-origin /api/* proxy injects the bearer token
  -> FastAPI validates the OpenEMR bearer token against JWKS
  -> patient-scoped OpenEMR FHIR reads
  -> selected-patient vector index/search in Postgres (encrypted payloads, hashed refs)
  -> vector hits re-hydrated from live FHIR
  -> LLM provider adapter (schema-declared tools, bounded loop)
  -> verifier: citations, patient scope, source URLs, read-only policy
  -> UI renders the verified answer, trace, and source links
```

Agent execution is a bounded server-orchestrated loop: access check, evidence tools, encrypted cache lookup, patient-scoped vector search, source hydration, model answer generation, fallback if output fails schema or citation validation, and a final verifier. Verified answers are persisted to encrypted conversation rows, and PHI-safe audit events are written for every completion and source read. If audit persistence is required and unavailable, the API withholds the answer rather than leaking an unaudited one.

Reliability is intentionally bounded: OpenEMR FHIR, JWKS, token, and model-provider calls retry transient failures with short exponential backoff; authorization failures always fail closed; cache and vector outages degrade to live FHIR evidence with an audit limitation.

Deeper design notes: [ARCHITECTURE.md](ARCHITECTURE.md), [DOCUMENT_WORKFLOW_ARCHITECTURE.md](DOCUMENT_WORKFLOW_ARCHITECTURE.md), [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md).

## Safety And PHI Guardrails

- SMART/OAuth authorization through OpenEMR; bearer validation against OpenEMR JWKS.
- Patient-scoped FHIR retrieval; the model cannot select a different patient, invent source IDs, run SQL, or override system rules from note text.
- Read-only policy blocks treatment, medication-change, order, diagnosis, and care-plan requests.
- Startup and readiness hard gates for PHI-mode configuration.
- Encrypted evidence cache, conversation retention (30-day default cleanup), and vector index with hashed identifiers.
- Durable PHI-safe audit events; nightly maintenance purges expired cache, vector, audit, conversation, and job rows.
- Backend service-account path for reindex jobs so worker tasks never borrow a clinician session.
- Provider routing flags separate demo egress from PHI-approved egress:
  - `LLM_PROVIDER=openrouter` is allowed only with `OPENROUTER_DEMO_DATA_ONLY=true`.
  - Real PHI to OpenAI or OpenRouter requires the explicit `ALLOW_PHI_TO_*`, `*_BAA_CONFIRMED`, and `*_DATA_POLICY_CONFIRMED` flags.

The full threat model is in [THREAT_MODEL.md](THREAT_MODEL.md).

## Verification

Latest local run (2026-05-14):

```text
pytest: 204 passed
ruff: all checks passed
mypy: success
document workflow eval gate: 50 passed, 0 failed  (python -m app.w2_eval --enforce)
web lint / build: passed
adversarial pytest: 73 passed; ruff and mypy clean
adversarial judge eval: 6 fixtures, 0 false positives, 0 false negatives
```

Deployed smoke checks after the same redeploy: `/readyz` green with pgvector and document-workflow persistence enabled; OpenEMR serving HSTS, CSP frame-ancestors, X-Frame-Options, nosniff, and Referrer-Policy headers with Secure/HttpOnly/SameSite login cookies; dependency manifests return 403; the adversarial site scan is down to a single Info-level Railway edge `Server` header disclosure.

CI runs the API/safety/eval gate (`.github/workflows/copilot-document-eval-gate.yml`) and the adversarial regression replay (`.github/workflows/adversarial-regression.yml`) on every push and pull request. `.github/branch-protection.json` records both as required checks.

## Demo Data

The seed scripts create 15 synthetic patients, each with demographics, 3 active problems, 2 active medications, 1 allergy, 3 recent lab results, and 4 unstructured clinical notes exposed through FHIR `DocumentReference`, plus the profile patients used by the example documents (Margaret Chen, James Whitaker, Sofia Reyes, Robert Kowalski, Demo Patient).

| Public ID | Patient | Search |
|---|---|---|
| AF-MVP-001 | Elena Morrison | `mo` |
| AF-MVP-002 | Margaret Chen | `chen` |
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

```powershell
.\copilot\scripts\seed-openemr-railway-demo-patient.ps1   # deployed Railway data
.\copilot\scripts\seed-openemr-demo-patient.ps1           # local data
```

## Local Development

### OpenEMR

```powershell
cd docker/development-easy
docker compose up --detach --wait
```

```text
URL:            http://localhost:8300/
Login:          admin / pass
FHIR metadata:  http://localhost:8300/apis/default/fhir/metadata
```

Register a local-only OAuth client for password-grant smoke tests (production uses the SMART authorization-code flow through the web service):

```powershell
cd copilot
.\scripts\register-openemr-dev-client.ps1
```

### API

```powershell
cd copilot/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -m app.w2_eval --enforce
```

Optional live-OpenEMR smoke: set `RUN_LIVE_OPENEMR=1` plus the `OPENEMR_*` variables printed by `register-openemr-dev-client.ps1`, then run `pytest tests\test_live_openemr_smoke.py -q`.

### Web

```powershell
cd copilot/web
npm install
npm run dev -- --port 3001
```

Checks: `npm audit --audit-level=moderate`, `npm run build`, `npm run test:e2e -- --project=chromium`.

### Adversarial platform

See [security/adversarial/README.md](security/adversarial/README.md) for running the operator locally and replaying the regression suite against a local Co-Pilot target.

## Railway Deployment

```powershell
railway up --service openemr                                   # OpenEMR fork, from repo root
railway up --service copilot-api .\copilot\api --path-as-root
railway up --service copilot-web .\copilot\web --path-as-root
.\copilot\scripts\enable-railway-document-workflow-persistence.ps1 -LinkProject
```

Run the PHI/readiness gate before any production-style deploy:

```powershell
.\copilot\scripts\phi-readiness-check.ps1
```

Health checks: OpenEMR `GET /meta/health/readyz`, API `GET /readyz`, web `GET /`.

Key API variables:

```text
APP_ENV=production
PHI_MODE=true
PUBLIC_BASE_URL=https://<copilot-web-domain>
DATABASE_URL=postgresql://...
ENCRYPTION_KEY=<fernet-key>
DEV_AUTH_BYPASS=false
DEMO_AUTH_BYPASS=false
OPENEMR_BASE_URL=https://<openemr-domain>
OPENEMR_FHIR_BASE_URL=https://<openemr-domain>/apis/default/fhir
OPENEMR_OAUTH_TOKEN_URL=https://<openemr-domain>/oauth2/default/token
OPENEMR_JWKS_URL=https://<openemr-domain>/oauth2/default/jwk
OPENEMR_JWT_ISSUER=https://<openemr-domain>/oauth2/default
OPENEMR_JWT_AUDIENCE=<smart-client-id>
OPENEMR_CLIENT_ID=<smart-client-id>
OPENEMR_CLIENT_SECRET=<smart-client-secret>
OPENEMR_TLS_VERIFY=true
LLM_PROVIDER=mock
VECTOR_SEARCH_ENABLED=true
VECTOR_INDEX_BACKEND=pgvector
VECTOR_EMBEDDING_PROVIDER=hash
EVIDENCE_CACHE_ENABLED=true
DOCUMENT_WORKFLOW_PERSISTENCE_ENABLED=true
AGENT_LOOP_MAX_STEPS=10
NIGHTLY_MAINTENANCE_ENABLED=true
OPENROUTER_API_KEY=
OPENROUTER_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_DEMO_DATA_ONLY=false
ALLOW_PHI_TO_OPENROUTER=false
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

The full variable list and operational notes are in [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md).

## Documentation

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Co-Pilot architecture, OpenEMR placement, data-intensive patterns, scaling plan |
| [DOCUMENT_WORKFLOW_ARCHITECTURE.md](DOCUMENT_WORKFLOW_ARCHITECTURE.md) | Multimodal document ingestion, worker graph, RAG, eval gate, and risk design |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threat model for the Co-Pilot and the adversarial platform |
| [security/docs/ADVERSARIAL_PRODUCT_SPEC.md](security/docs/ADVERSARIAL_PRODUCT_SPEC.md) | Adversarial security platform spec |
| [security/docs/ADVERSARIAL_EVIDENCE_PACKET.md](security/docs/ADVERSARIAL_EVIDENCE_PACKET.md) | Adversarial campaign evidence, findings, and remediation record |
| [AUDIT.md](AUDIT.md) | OpenEMR security, performance, architecture, and data-quality audit |
| [USERS.md](USERS.md) | Target users, use cases, non-goals, and operator workflows |
| [WALKTHROUGH.md](WALKTHROUGH.md) | Guided tour of the Co-Pilot code, request flows, and debugging paths |
| [PATIENT_DASHBOARD_MIGRATION.md](PATIENT_DASHBOARD_MIGRATION.md) | Next.js reimplementation of the OpenEMR patient dashboard on FHIR |
| [EVAL_PLAN.md](EVAL_PLAN.md) / [EVAL_DATASET.md](EVAL_DATASET.md) | Eval design, dataset, automated coverage, and latest results |
| [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md) | Recorded dev AI spend and production cost projections |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | Local and Railway deployment details |
| [MARGARET_CHEN_DOCUMENT_DEMO.md](MARGARET_CHEN_DOCUMENT_DEMO.md) | Manual scan/extract/approve/retrieve walkthrough |
| [MVP_AUTH_SCOPE.md](MVP_AUTH_SCOPE.md) | Local-demo auth scope and production-auth exclusions |
| [OPENEMR_VERSION_PIN.md](OPENEMR_VERSION_PIN.md) | Upstream OpenEMR version and commit this fork tracks |
| [eli5.md](eli5.md) | OpenEMR codebase orientation |

## License

This fork preserves OpenEMR's [GNU GPL v3](LICENSE) license. Additions in this repository are released under the same terms.

Upstream OpenEMR: https://github.com/openemr/openemr
