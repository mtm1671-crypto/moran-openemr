# Clinical Co-Pilot Walkthrough

This guide explains the Co-Pilot work we built around the OpenEMR fork. It is intentionally written as a learning map: what each important file does, why it exists, and where to look when something breaks.

The OpenEMR repository is large. This walkthrough focuses on the AgentForge Co-Pilot surfaces we created or heavily edited during the two-week build.

## Mental Model

The system has one clinical source of truth and several derived views.

```text
OpenEMR
  authoritative users, auth, patients, scopes, FHIR resources, documents

Co-Pilot API
  validates auth, checks patient access, retrieves evidence, calls models,
  verifies answers, stores encrypted product/audit/index data

Co-Pilot Web
  handles SMART launch/callback, stores encrypted session cookie,
  renders patient selector, chat, source links, document review UI

Worker / scheduled jobs
  reindex patients, prune expired rows, process long-running extraction/write work
```

The core safety rule is simple: **the model never owns patient identity or source truth**. The backend injects the selected patient into tools, retrieves evidence from OpenEMR or approved derived indexes, and verifies citations before the UI shows the final answer.

## Data-Intensive Patterns We Are Applying

| Pattern | How it appears here | Why it matters |
|---|---|---|
| System of record | OpenEMR remains authoritative for identity, patients, scopes, FHIR data, documents, and Observation writes. | Co-Pilot can scale and fail independently without becoming the clinical chart. |
| CQRS / read models | Postgres stores encrypted evidence cache, vector chunks, semantic relationships, retrieval telemetry, and conversation history. | Chat reads become fast without turning caches into truth. |
| Transactional outbox | Approved lab writes should become durable write commands before worker drain. | Prevents browser-request timeouts and makes retries/dead letters visible. |
| Bounded staleness | Evidence rows carry TTLs, hashes, source refs, model names, and indexed timestamps. | Lets the API decide whether cached evidence is still trustworthy. |
| Backpressure | Slow OCR, reindex, FHIR writes, and model calls move to worker/queue paths. | 1,000 concurrent users should not collapse the API request path. |
| Redis as coordination | Redis is planned for short-lived locks, rate limits, roster cache, idempotency, and SSE fanout. | It helps multi-replica coordination without storing clinical truth. |
| Partitioned telemetry | Audit, cost, retrieval, verification, and routing rows partition by time and tenant. | Keeps observability queryable as event volume grows. |
| Stable internal interfaces | Agent code calls retrieval/write/provider abstractions rather than raw provider code everywhere. | Lets us swap vector DB/model providers later without rewriting the agent loop. |

## Request Flow: Authentication

Start here when debugging login, invalid OAuth state, redirect loops, or `0.0.0.0` callback issues.

1. OpenEMR launches Co-Pilot from `interface/agentforge/copilot.php`.
2. The launch bridge sends `iss`, launch context, and optional patient context to the web app.
3. `copilot/web/app/api/auth/start/route.ts` validates issuer and creates OAuth state.
4. OpenEMR OAuth login/consent happens.
5. `copilot/web/app/api/auth/callback/route.ts` exchanges code for token and stores an encrypted HttpOnly `copilot_session`.
6. `copilot/web/app/api/auth/session/route.ts` lets the frontend check whether it is authenticated.
7. API requests go through `copilot/web/app/api/[...path]/route.ts`, which proxies to FastAPI and injects the bearer token.
8. FastAPI validates the token through `copilot/api/app/auth.py` and `copilot/api/app/openemr_auth.py`.

Important files:

| File | What it does | What to check when debugging |
|---|---|---|
| `interface/agentforge/copilot.php` | OpenEMR launch bridge that builds the Co-Pilot URL. | Wrong web URL, missing launch context, patient chart launch bugs. |
| `interface/main/tabs/menu/menus/standard.json` | Adds top-level Co-Pilot nav entry. | Co-Pilot missing from OpenEMR nav. |
| `interface/main/tabs/menu/menus/patient_menus/standard.json` | Adds patient-context Co-Pilot entry. | Co-Pilot missing from patient chart. |
| `library/globals.inc.php` | Adds connector/global setting for Co-Pilot URL. | Wrong deployed web URL in OpenEMR config. |
| `copilot/web/app/api/auth/start/route.ts` | Starts SMART/OAuth and validates issuer. | OAuth state errors, malicious/incorrect issuer, redirect target. |
| `copilot/web/app/api/auth/callback/route.ts` | Exchanges code, stores session cookie, redirects into app. | Token exchange errors, callback URL, cookie/session issues. |
| `copilot/web/app/lib/auth-session.ts` | Encrypts/decrypts the browser session cookie. | Bad session secret, expired token, cookie payload shape. |
| `copilot/api/app/auth.py` | FastAPI dependency that validates bearer token and builds `RequestUser`. | `/api/me` failures, role/scope parsing. |
| `copilot/api/app/openemr_auth.py` | Service-token and clinician-token helpers. | Reindex service account, backend jobs, token refresh style bugs. |

## Request Flow: Chat Answer

Start here when chat stalls, answers fail verification, citations are wrong, or the model behaves oddly.

1. `copilot/web/app/page.tsx` sends chat request with selected patient.
2. `copilot/api/app/api.py` starts `/api/chat` as an SSE stream.
3. The API checks read-only policy and role/patient access.
4. `copilot/api/app/evidence_tools.py` gathers structured FHIR evidence.
5. Approved document facts from `document_storage.py` are added when available.
6. If vector search is enabled, `vector_store.py` searches or lazily indexes patient evidence.
7. Provider adapter in `providers.py` / `openai_models.py` drafts an answer.
8. `verifier.py` checks citations, selected-patient scope, source URLs, and treatment-refusal policy.
9. `persistence.py` stores encrypted conversation/audit rows if configured.
10. The UI renders only the verified final event.

Important files:

| File | What it does | What to check when debugging |
|---|---|---|
| `copilot/web/app/page.tsx` | Main UI: patient dropdown, quick questions, chat stream, document review shell. | Disabled submit button, missing patients, stalled stream, bad error copy. |
| `copilot/api/app/api.py` | Main FastAPI router: health, patients, source links, chat SSE, model routing, vector/cache failover. | Most chat, source, cache, vector, and verification symptoms. |
| `copilot/api/app/models.py` | Shared Pydantic contracts for users, patients, chat, evidence, tools, jobs. | Shape mismatch between API, tests, and frontend. |
| `copilot/api/app/evidence_tools.py` | Converts OpenEMR FHIR resources into normalized evidence objects. | Missing labs/meds/problems/allergies/demographics. |
| `copilot/api/app/fhir_client.py` | Thin async client for OpenEMR FHIR. | FHIR URL, bearer token, timeout/retry behavior. |
| `copilot/api/app/providers.py` | Mock provider and provider protocol. | Local deterministic test behavior. |
| `copilot/api/app/openai_models.py` | OpenAI/OpenRouter-compatible model and embedding calls. | Real LLM path, OpenRouter model, retries, schema parse failures. |
| `copilot/api/app/verifier.py` | Final safety gate for answer/citation correctness. | "Could not generate verified answer" or unsupported-treatment refusals. |
| `copilot/api/tests/test_api_chat_evidence.py` | API chat evidence tests. | Regression coverage for source-backed answers. |
| `copilot/web/tests/clinical-copilot.spec.ts` | Playwright smoke tests for UI flows. | UI regression and stream behavior. |

## Request Flow: Vector Evidence

The vector path exists to search notes and unstructured evidence without sending full charts to the model.

1. Chat asks for broad note/history context.
2. API gathers source-backed evidence first.
3. `vector_store.py` embeds searchable text and writes vector records.
4. `persistence.py` stores encrypted evidence payloads and embedding metadata.
5. Search results are patient-filtered before ranking.
6. Vector hits are hydrated through source evidence before model context.

Important files:

| File | What it does | Notes |
|---|---|---|
| `copilot/api/app/vector_store.py` | Provider-neutral vector indexing/search service. | Hash embeddings are deterministic demo-safe; OpenAI embeddings require PHI approval flags. |
| `copilot/api/app/persistence.py` | Defines `evidence_vector_index`, pgvector schema, JSON fallback, encrypted payload storage. | This is where derived search data lives. |
| `copilot/api/tests/test_vector_store.py` | Tests indexing/search, patient scoping, and fallback behavior. | Run when changing vector behavior. |

Production rule: vector rows are **derived**. If the index is stale or unavailable, the API should use live FHIR evidence where safe or fail with an explicit limitation.

## Request Flow: Document Extraction And Review

Start here when PDF upload, OCR, review, approve-all, or lab write behavior breaks.

1. `DocumentUploadPanel.tsx` uploads a synthetic document.
2. `document_ingestion.py` creates a job and runs extraction.
3. `ocr_providers.py` chooses deterministic/demo OCR or configured vision/OCR provider.
4. `extraction_pipeline.py` converts OCR/layout into typed extracted facts.
5. `review.py` applies human approve/reject decisions.
6. `observation_writer.py` builds OpenEMR FHIR Observation resources for approved lab facts.
7. Failed writes keep per-fact error details so the UI can show why each lab failed.
8. Approved evidence becomes searchable/chat-available through `document_storage.py`.

Important files:

| File | What it does | What to check when debugging |
|---|---|---|
| `copilot/web/app/components/DocumentUploadPanel.tsx` | Upload UI. | File selection, upload error state, no patient selected flow. |
| `copilot/web/app/components/ExtractionReviewPanel.tsx` | Review/approve/retry UI for extracted facts. | Disabled approve button, failed writes, per-fact errors. |
| `copilot/web/app/components/PdfBoundingBoxPreview.tsx` | Shows source preview and bounding boxes. | Citation/source preview display. |
| `copilot/api/app/document_ingestion.py` | API routes for upload, job status, review, write approved facts. | Most document workflow bugs. |
| `copilot/api/app/document_models.py` | Pydantic schemas for jobs, facts, citations, statuses. | Schema/state drift. |
| `copilot/api/app/ocr_providers.py` | OCR provider adapters and settings. | Real OCR vs deterministic fixture behavior. |
| `copilot/api/app/extraction_pipeline.py` | Extracts typed facts from OCR/layout. | Bad parser output or missing facts. |
| `copilot/api/app/extraction_adapters.py` | Converts extraction output into domain facts. | Lab/intake field mapping issues. |
| `copilot/api/app/observation_writer.py` | Builds/writes FHIR Observations. | Observation.write scope, units, LOINC/code/value mapping. |
| `copilot/api/tests/test_document_api.py` | API-level document flow coverage. | Run after changing endpoints. |
| `copilot/api/tests/test_document_extraction.py` | Extraction/parser behavior. | Run after changing OCR/parser logic. |
| `example-documents/` | Synthetic lab/intake PDFs and PNGs. | Manual demo fixtures. |

## Production Readiness Files

These files are not the main product UI, but they prove the system can be defended.

| File | What it does |
|---|---|
| `ARCHITECTURE.md` | High-level architecture, safety model, data-intensive scaling patterns, provider strategy. |
| `W2_ARCHITECTURE.md` | Week 2 production-shape design: document ingestion, worker graph, RAG, evals, observability, scaling risks. |
| `AI_COST_ANALYSIS.md` | Dev spend, model-routing economics, cost projections at 100/1k/10k/100k users. |
| `AUDIT.md` | OpenEMR audit notes and key findings. |
| `USER.md` | Target user and use cases. |
| `EVAL_DATASET.md` | Eval dataset scope and results. |
| `DEMO_PLAN.md` | How to record or perform the live walkthrough. |
| `PRODUCTION_DEMO_EVIDENCE.md` | Evidence checklist for proving the deployed flow works. |
| `DEPLOYMENT_RUNBOOK.md` | Deployment and operational steps. |
| `EARLY_SUBMISSION_CHECKLIST.md` | Earlier readiness checklist and smoke path. |
| `SUBMISSION.md` | Final submission packet pointer. |

## Config And Guardrails

Start here when the app refuses to boot or `/readyz` is red.

| File | What it does |
|---|---|
| `copilot/api/app/config.py` | Central settings and runtime safety gates. PHI mode requires HTTPS, database, encryption, audit, OpenEMR URLs, and approved model egress. |
| `copilot/api/.env.production.example` | Production environment variable template. |
| `copilot/web/.env.production.example` | Web environment variable template. |
| `copilot/api/app/security.py` | Encryption and PHI-safe metadata helpers. |
| `copilot/api/app/telemetry.py` | PHI-safe telemetry emission. |
| `copilot/scripts/phi-readiness-check.ps1` | Local/ops check for PHI-related settings. |

The important idea: config is not just convenience. It is a safety boundary. If PHI controls are required, unsafe combinations fail during readiness/startup.

## Deployment And Data

| File | What it does |
|---|---|
| `copilot/api/railway.toml` | Railway API service definition. |
| `copilot/web/railway.toml` | Railway web service definition. |
| `copilot/api/railway.worker.toml` | Railway worker/cron definition. |
| `copilot/scripts/seed-openemr-railway-demo-patient.ps1` | Seeds deployed Railway OpenEMR demo patients/data. |
| `copilot/scripts/seed-openemr-demo-patient.ps1` | Seeds local OpenEMR demo data. |
| `copilot/scripts/seed-openemr-demo-population.sql` | Synthetic patient population. |
| `copilot/scripts/seed-openemr-demo-notes.sql` | Synthetic unstructured notes. |

When the UI works but no patients or facts appear, check seeding first, then OpenEMR auth scopes, then FHIR endpoints.

## Test Map

Use these when deciding what to run after changes.

| Change area | Tests to run |
|---|---|
| API auth, chat, source links | `pytest tests/test_api_chat_evidence.py tests/test_api_source.py tests/test_openemr_auth.py` |
| Patient dropdown/search | `pytest tests/test_api_patients.py` and Playwright. |
| Vector search/cache | `pytest tests/test_vector_store.py tests/test_phi_security.py` |
| Document extraction/review/write | `pytest tests/test_document_api.py tests/test_document_extraction.py tests/test_example_documents.py` |
| Provider/model behavior | `pytest tests/test_openai_models.py tests/test_providers.py tests/test_ocr_providers.py` |
| Full API safety regression | `pytest -q` from `copilot/api`. |
| Web UI regression | `npm run build` and `npx playwright test` from `copilot/web`. |

## Recommended Learning Path

Read in this order:

1. `README.md` for the product and demo path.
2. `ARCHITECTURE.md` for the main system design.
3. `copilot/web/app/page.tsx` to understand the user surface.
4. `copilot/api/app/api.py` to understand the live API routes and chat stream.
5. `copilot/api/app/evidence_tools.py` to see how FHIR becomes evidence.
6. `copilot/api/app/verifier.py` to see why answers pass or fail.
7. `copilot/api/app/persistence.py` to learn what gets stored and encrypted.
8. `copilot/api/app/vector_store.py` to learn how derived semantic search works.
9. `copilot/api/app/document_ingestion.py` and `observation_writer.py` for Week 2 document/lab write flow.
10. `AI_COST_ANALYSIS.md` and `W2_ARCHITECTURE.md` for production scaling and cost thinking.

## Debugging Heuristics

- If login fails, inspect web auth routes and OpenEMR OAuth client settings.
- If `/api/me` fails, inspect FastAPI auth/JWKS/token validation.
- If patient dropdown is empty, inspect OpenEMR seed data, patient FHIR search, and clinician scopes.
- If chat stalls, inspect SSE status events, web stream timeout, API logs, and provider timeout.
- If answer says it cannot verify, inspect evidence IDs, source URLs, verifier rules, and selected patient.
- If vector search returns nothing, inspect vector readiness, backend setting, patient id filter, and whether evidence was indexed.
- If document approve-all is disabled, inspect job status and whether any facts are still pending/reviewable.
- If lab writes fail, inspect `Observation.write` scope, OpenEMR FHIR response, and per-fact write diagnostics.

## How To Think About Future Changes

Before adding a feature, classify its data:

```text
Is this authoritative clinical truth?
Is this derived and rebuildable?
Is this ephemeral coordination state?
Does it need encryption?
Does it need audit?
What is its freshness rule?
What happens if it is missing or stale?
What test proves cross-patient leakage is impossible?
```

That one checklist prevents most scaling and safety mistakes in this codebase.
