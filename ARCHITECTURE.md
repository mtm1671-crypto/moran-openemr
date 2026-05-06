# AgentForge Clinical Co-Pilot Architecture

## Summary

The Clinical Co-Pilot is a read-only chart assistant deployed beside OpenEMR, not as a PHP-native OpenEMR module. OpenEMR remains the source of truth for clinician identity, patient records, ACLs, SMART/OAuth scopes, and FHIR data. The Co-Pilot adds an AI retrieval and verification layer without becoming a clinical system of record. The clinician launches the assistant from OpenEMR, completes SMART/OAuth authorization, selects an authorized patient, asks a chart question, and receives a concise answer with citations back to OpenEMR source records.

The main framework decision is to split the product into three deployable services: a Next.js web app, a FastAPI API service, and a background worker. Next.js owns the browser experience, SMART launch/callback handling, encrypted HttpOnly session cookies, and same-origin API proxying. FastAPI owns token validation, RBAC, patient access checks, deterministic evidence tools, vector search, model calls, claim verification, source-link authorization, audit persistence, and health/readiness gates. The worker owns scheduled maintenance: reindexing OpenEMR FHIR resources, chunking unstructured notes, refreshing embeddings, and pruning expired caches. This service boundary adds deployment complexity, but it keeps the agent loop testable, keeps OpenEMR modifications narrow, and lets the AI layer scale independently.

At request time, the API locks the conversation to a single selected `patient_id`; the model is never allowed to choose or override that identifier. The orchestrator gathers evidence with typed tools for demographics, problems, medications, allergies, labs, and clinical notes. Structured data is fetched through OpenEMR FHIR using the clinician's bearer token. Unstructured chart text is indexed in Postgres/pgvector and searched by patient scope, source type, and recency. The evidence assembler normalizes results into source-backed snippets, then the model provider adapter calls an LLM only after the context has been bounded. The current demo supports mock, OpenRouter, and OpenAI-compatible providers; real PHI requires a HIPAA-appropriate provider path, a BAA where applicable, or a self-hosted model deployment.

Verification is deliberately strict. The final answer must cite selected-patient evidence for every factual clinical claim. Source links re-check authorization before returning FHIR JSON. Unsupported diagnosis, treatment, prescribing, dosing, orders, or chart-write requests are refused. Prompt-injection defenses treat retrieved notes as untrusted data, reject cross-patient sources, reject model-emitted unknown evidence IDs, and use tool schemas so callable tools stay bounded as the system expands. If audit persistence is required and unavailable, the chat fails closed rather than returning an unverifiable answer.

The PHI posture is local-first and metadata-conscious. Conversations, message records, audit events, caches, and vector chunks live in Postgres with encryption controls and retention boundaries. Logs use allowlisted metadata rather than raw chart text. Cache and vector failures degrade to live FHIR evidence where safe; authorization, audit, verifier, and configuration failures stop the request. The verification strategy combines unit tests, API tests, Playwright smoke tests, PHI readiness checks, static typing/linting, dependency audits, and deterministic eval cases covering patient scoping, prompt injection, treatment-refusal behavior, stale evidence, cache failover, vector failover, and source-link authorization.

The known tradeoff is that the MVP favors reliability and auditability over maximal autonomy. It can summarize, retrieve, and cite evidence quickly, but it does not write to the chart, make clinical decisions, or replace clinician judgment. That constraint is intentional for the final AgentForge submission: the product demonstrates an agentic workflow that is useful in a live OpenEMR environment while keeping the clinical risk boundary narrow and testable.

## Architecture Diagram

```text
Clinician Browser
    |
    | HTTPS
    v
Next.js Chat App
    |
    | SMART/OAuth login redirect
    v
OpenEMR Auth Server
    |
    | OpenEMR JWT / scopes / practitioner identity
    v
Next.js App
    |
    | /api/chat SSE
    | /api/patients
    v
FastAPI Service
    |
    +--> Auth Middleware
    |       - validate OpenEMR JWT against JWKS
    |       - attach user, role, scopes, practitioner_id
    |
    +--> RBAC / Patient Access Policy
    |       - doctor, NP/PA, nurse, MA capability checks
    |       - selected patient locked per conversation
    |
    +--> Patient Search Service
    |       - OpenEMR FHIR Patient.search
    |       - optional schedule-based patient list
    |
    +--> Agent Orchestrator
    |       |
    |       +--> Verified Query Layer
    |       |       - deterministic structured queries
    |       |       - approved patient/problem/lab/med relationships
    |       |
    |       +--> Evidence Tools
    |       |       - FHIR reads
    |       |       - read-only OpenEMR MySQL fallback
    |       |       - pgvector chart/document search
    |       |
    |       +--> Evidence Assembler
    |       |       - normalized evidence objects
    |       |       - source links
    |       |
    |       +--> LLM Provider Adapter
    |       |       - Anthropic
    |       |       - OpenRouter
    |       |       - local OpenAI-compatible models
    |       |
    |       +--> Claim Verifier
    |               - every factual claim must cite evidence
    |               - selected-patient enforcement
    |               - no unsupported treatment recommendations
    |
    +--> Postgres 16
    |       - operational tables
    |       - encrypted conversations/messages
    |       - audit events
    |       - pgvector embeddings
    |       - semantic relationship model
    |
    +--> Structured Logs / Telemetry
            - PHI-safe allowlisted fields
            - latency, refusals, verifier failures

Railway Cron / ETL Worker
    |
    +--> OpenEMR FHIR APIs
    +--> optional read-only OpenEMR MySQL
    +--> chunking, embedding, relationship extraction
    +--> Postgres derived index
```

## Core Decisions

### Product Shape

The core product is a chat window. A clinician authenticates, selects one patient, asks natural-language questions, and receives cited chart information. The MVP stays read-only and informational. It should not generate treatment plans, diagnoses, orders, prescriptions, or care recommendations.

The first workflow is optimized for a primary care clinician with 1-2 minutes between rooms. Nurses, MAs, NPs, and PAs are supported through role-specific access rules, but the doctor/APP chart review workflow drives the first version.

### OpenEMR Product Placement

The intended final placement is a first-class OpenEMR workspace tab:

- Add a top-level `Co-Pilot` item near Schedule/Calendar and other daily workflow navigation.
- When opened from the global top nav, show the Co-Pilot patient selector and authorized patient search.
- When opened from a patient chart, load the Co-Pilot with that patient already selected.
- When opened from a schedule row, launch the same patient-scoped Co-Pilot view and optionally prefetch that patient's evidence.
- Keep all chart reads and source links tied back to OpenEMR authorization, FHIR records, and source views.

This is a product integration decision, not a reason to collapse the assistant into OpenEMR PHP internals. For the final product, OpenEMR should host the entry points and context handoff while the Co-Pilot web/API/worker services continue to own the agent workflow, verification, conversation storage, and retrieval infrastructure.

### Relationship To OpenEMR

OpenEMR is the source of truth for users, roles, patient records, and clinical documents. AgentForge is a separate application that connects to OpenEMR through:

- SMART/OAuth authentication.
- FHIR APIs for patient search and clinical data.
- Optional read-only MySQL access only when FHIR coverage is insufficient.

This keeps the MVP closer to an enterprise companion product: easier to scale independently, easier to test, and easier to deploy on Railway without deeply coupling the assistant loop to OpenEMR PHP internals.

### Frontend

Use Next.js only for the frontend.

The frontend owns:

- Login and callback flow.
- Patient search and patient selection.
- Chat transcript UI.
- SSE streaming display.
- Source-link rendering.
- Role-aware UI affordances.

The frontend should not make authorization decisions by itself. It can hide unavailable actions for clarity, but FastAPI remains the enforcement layer.

### Backend

Use Python 3.12+ with FastAPI and asyncio.

The backend owns:

- JWT validation and request context.
- RBAC and patient access checks.
- Patient search proxying.
- Agent orchestration.
- Evidence retrieval.
- Model-provider routing.
- Claim verification.
- Audit logging.
- Eval and test harness support.

Use `httpx.AsyncClient` for OpenEMR, LLM provider, and local-model calls. Use Pydantic v2 for request/response contracts and tool argument validation.

### Data Store

Use a single Postgres database for the MVP, with extensions for `pgvector` and `pgcrypto`.

Postgres contains three categories of data:

1. Operational data: conversations, messages, audit events, user/session metadata, provider config, job status.
2. Derived clinical index data: document chunks, embeddings, evidence metadata, source pointers, freshness state.
3. Verified semantic data: approved clinical entities and relationships used for deterministic structured queries.

OpenEMR remains the record of authority. Postgres is a search, evidence, audit, and product database.

## Patient And Auth Model

Authentication uses OpenEMR-issued identity. The preferred flow is SMART/OAuth login against OpenEMR. FastAPI validates JWTs against OpenEMR JWKS on every request and builds a request-scoped user object:

```text
RequestUser
    user_id
    role
    scopes
    practitioner_id
    organization_id
    raw_access_token
```

Patient access is checked before any patient data is returned or searched. The selected `patient_id` is locked into the conversation context. The model never supplies or changes the patient id directly; tools receive the patient id from the orchestrator.

This prevents cross-patient leakage from prompt injection, model mistakes, or crafted tool arguments.

## Role Model

The MVP should start conservative:

```text
Role        Default MVP Capability
----------  ---------------------------------------------------------
Doctor      Full read access to authorized patient summary evidence
NP/PA       Same as doctor when OpenEMR role/scope permits it
Nurse       Limited read access for prep-oriented chart questions
MA          Limited read access for demographics, schedule, prep data
Admin       Product/admin config only, no chart access by default
```

The role registry should be explicit and testable. Do not infer clinical permissions from display names alone. Use OpenEMR scopes and configured role mappings.

## Retrieval Pipeline

The assistant should use deterministic retrieval first, then vector retrieval when needed.

```text
User question
    |
    v
Intent / capability classification
    |
    +--> structured clinical question?
    |       |
    |       v
    |   Verified Query Layer
    |       - labs by date
    |       - active problems
    |       - medications
    |       - allergies
    |       - demographics
    |
    +--> document / note / broad history question?
            |
            v
        Vector Evidence Search
            - patient_id filtered
            - document type filtered
            - recency weighted
            - source-linked chunks

Evidence bundle
    |
    v
LLM answer draft
    |
    v
Claim verifier
    |
    +--> pass: stream final cited answer
    +--> fail: retrieve more evidence or refuse unsupported claims
```

### Verified Query Layer

The verified query layer is the deterministic part of the system, inspired by the relationship-style semantic modeling used by tools like Cortex Analyst. It defines what structured data exists, how entities relate, and which joins or filters are allowed.

Examples:

```text
Patient -> active Problems
Patient -> recent Lab Results
Patient -> current Medications
Patient -> Allergies
Patient -> Encounters
Encounter -> Notes
Lab Result -> LOINC / display name / value / unit / date
Problem -> ICD/SNOMED / display name / status / onset date
```

The goal is to reduce ambiguous model behavior. For common factual questions, the model should choose from approved query capabilities instead of improvising SQL, FHIR searches, or chart interpretations.

### Vector Search

Use pgvector for unstructured or semi-structured chart data:

- Clinical notes.
- Uploaded documents.
- Encounter narratives.
- Discharge summaries.
- Referral letters.
- Scanned-text extracts when available.

Every vector row must include:

- `patient_id`
- `source_type`
- `source_id`
- `document_id`
- `chunk_id`
- `chunk_hash`
- `source_updated_at`
- `indexed_at`
- embedding vector
- encrypted `chunk_text`

All vector searches must filter by selected patient before ranking.

## Evidence Object

Normalize every retrieved fact into an evidence object before it reaches the answer generator:

```json
{
  "evidence_id": "ev_01J...",
  "patient_id": "12345",
  "source_system": "openemr",
  "source_type": "lab_result",
  "source_id": "lab_987",
  "display_name": "Hemoglobin A1c",
  "fact": "A1c was 8.6% on 2026-03-12",
  "effective_at": "2026-03-12T00:00:00Z",
  "source_updated_at": "2026-03-12T14:08:00Z",
  "retrieved_at": "2026-04-28T16:30:00Z",
  "confidence": "source_record",
  "source_url": "/source/lab_987"
}
```

The answer may only make factual claims supported by evidence objects. Source links should open the underlying OpenEMR document, note, lab, or medication record when possible.

## Caching And Freshness

There are two caches:

1. Evidence/index cache: derived chart chunks, embeddings, and structured relationship rows.
2. Runtime retrieval cache: short-lived request/session cache for repeated questions.

The MVP should prioritize correctness over speed:

- Cache evidence only, not final answers.
- Revalidate evidence freshness before final answer generation.
- Store `source_updated_at`, `indexed_at`, and `chunk_hash`.
- Invalidate patient indexes when source records change.
- Use a 60-120 second idempotency window for reindex jobs.
- Allow manual reindex for a selected patient.

If freshness cannot be confirmed, the assistant should say so instead of presenting stale chart facts as current.

### Redis And Hot-Path Caching

Postgres remains the source of truth for encrypted evidence, audit records, vector chunks, job status, and conversation history. Redis is useful at scale, but only for short-lived operational state that can be safely rebuilt:

- SMART/JWKS validation cache keyed by token/JWKS hash, with a 30-60 second TTL.
- Patient roster and schedule prefetch cache scoped by clinician, organization, and OpenEMR scope set.
- Request idempotency keys for document uploads, reindex jobs, and Observation write retries.
- Distributed locks for per-patient reindex and per-document extraction so multiple API replicas do not duplicate expensive work.
- Rate-limit counters and per-tenant concurrency budgets.
- SSE progress fanout if the API moves document extraction and long-running jobs fully off-request.

Redis should not store final answers as the primary cache. Final-answer caching is risky because source freshness, authorization, and patient context can change quickly. Cache evidence and retrieval plans instead, then re-run source hydration and verification before showing the clinician an answer.

The MVP uses Postgres-backed encrypted evidence cache and in-process local caches where safe. Redis becomes a production scale add when either API replicas exceed one, queue depth becomes visible, or repeated evidence retrieval creates measurable OpenEMR/FHIR pressure.

## Latency, Cost, And Scale Strategy

The critical performance goal is that most chart questions feel interactive while still failing closed on safety gates. The target production budget is:

```text
Auth/session check            < 100 ms hot cache, < 600 ms cold JWKS/FHIR check
Patient roster                < 500 ms cached, < 2 s live OpenEMR FHIR
Structured evidence retrieval < 1.5 s p95
Vector search + hydration     < 2.5 s p95
LLM answer compose            < 3-8 s depending on model/provider
Verification                  < 500 ms for deterministic citation checks
```

The main latency levers are:

- Prefer deterministic source-backed answers for demographics, active problems, medications, allergies, and recent labs when no LLM is needed.
- Use vector search to narrow context before the LLM call; never send an entire chart or full document set to the model.
- Keep `MODEL_EVIDENCE_LIMIT`, `VECTOR_SEARCH_LIMIT`, and output token caps small unless evals prove quality requires more context.
- Stream status immediately so slow OpenEMR or model calls do not look like a dead UI.
- Run document OCR/extraction, patient reindex, and nightly maintenance through worker/queue paths instead of tying them to chat request latency.

The main cost levers are:

- Route trivial factual requests to the deterministic fallback instead of an LLM.
- Use a cheaper approved model for answer composition after it passes the same eval suite as the frontier model.
- Use expensive models only for hard cases: low confidence, broad summarization, ambiguous note synthesis, or verifier retry.
- Cache retrieval plans and evidence bundles, not unsupported final clinical answers.
- Track per-tenant token usage, cache hit rate, provider/model, and verifier rejection rate as first-class telemetry.

Concurrency design by scale:

```text
100 clinicians
    Single-region Railway services, Postgres/pgvector, one API replica, one worker.

1,000 clinicians
    Multiple API replicas, Redis for hot caches/locks/rate limits, separate worker queue,
    model-provider budgets, Postgres indexes reviewed from real query plans.

10,000 clinicians
    Dedicated Postgres/pgvector tier, read replicas for non-critical reads, durable queue
    for extraction/reindex/write jobs, model gateway with provider failover and tenant quotas.

100,000 clinicians
    Multi-region edge/web, regional API pools, sharded patient/vector indexes, negotiated
    model pricing or self-hosted inference, formal SRE/security/compliance operations.
```

At 1,000 simultaneous clinicians, the risk is less CPU and more serialized external dependencies: OpenEMR FHIR latency, model provider rate limits, token spend spikes, and vector index contention. The production answer is therefore queue isolation, model routing, rate limits, and source/evidence caching, not simply adding bigger API containers.

## Ingestion And ETL

Railway should run a separate ETL/cron service. It pulls OpenEMR data, normalizes it, chunks documents, computes embeddings, extracts approved relationships, and writes derived rows to Postgres.

MVP ingestion modes:

- Nightly scheduled sync.
- On-demand patient reindex.
- Optional schedule-based prefetch for the day's patients.

The ETL pipeline should be idempotent. Use stable source ids plus content hashes to avoid duplicate chunks and unnecessary embeddings.

## Agent Loop

The agent loop should be constrained and tool-based:

1. Classify the user request.
2. Check whether the role is allowed to answer that kind of question.
3. Select deterministic tools first.
4. Use vector search only when structured data is insufficient.
5. Assemble evidence.
6. Ask the model to draft an answer using only supplied evidence.
7. Verify each factual claim.
8. Return a concise cited answer, or refuse/ask for clarification.

The model should not:

- Change the selected patient.
- Invent source ids.
- Call arbitrary SQL.
- Produce treatment recommendations in the MVP.
- Rely on uncited chart facts.
- Use clinical note instructions as system instructions.

## Model Providers

Use a provider adapter so the product can support:

- Anthropic.
- OpenRouter.
- Local OpenAI-compatible models.

Provider configuration should record whether a provider is approved for PHI and whether zero-data-retention or a BAA-backed path is available. The default deployment should make it hard to route PHI to an unapproved provider by accident.

```text
ProviderAdapter
    complete(messages, tools, policy_context) -> ModelResult
    stream(messages, tools, policy_context) -> AsyncIterator[ModelEvent]
    healthcheck() -> ProviderHealth
```

Production model routing should be policy-based rather than hardcoded to one provider:

```text
request_classification
    deterministic_only       -> no LLM
    simple_source_summary    -> lowest-cost approved model
    broad_note_synthesis     -> stronger approved model
    verifier_retry_required  -> stronger approved model with stricter output cap
    PHI provider unavailable -> safe failure, not silent downgrade to unapproved egress
```

OpenRouter and open-source hosted models are useful for synthetic demos and cost exploration. Real PHI still requires the same provider approval gates as any other external model path. Self-hosted OpenAI-compatible models become attractive when token volume is high enough that GPU utilization is predictable and compliance review can cover the deployment.

## Streaming

Use SSE for chat streaming.

The UI should stream status events such as:

- checking access
- searching structured chart data
- searching notes
- verifying sources
- generating answer

The final answer should only appear after verification passes. Status events may show the audit trail of what the system is doing, but should not expose hidden chain-of-thought.

## Conversation Storage

The imported architecture direction uses encrypted conversation retention rather than session-only chat.

MVP default:

- Store conversations for 30 days.
- Encrypt prompt text and answer payloads.
- Store citation metadata in queryable JSONB.
- Support soft delete.
- Keep audit logs separately from visible chat history.

Suggested tables:

```text
conversations
    id uuid primary key
    user_id text not null
    patient_id text not null
    encrypted_title bytea
    created_at timestamptz
    last_message_at timestamptz
    soft_deleted_at timestamptz
    retention_days int default 30

messages
    id uuid primary key
    conversation_id uuid references conversations(id)
    role text
    encrypted_prompt_text bytea
    encrypted_answer_payload bytea
    citations jsonb
    verification_result jsonb
    turn_count int
    created_at timestamptz
```

Use `pgcrypto` for MVP encryption. Keep the key in Railway environment variables initially, with a migration path to KMS or envelope encryption for production.

## Security Controls

The main MVP risks are cross-patient leakage, unsupported medical claims, PHI exposure, and prompt injection from chart text.

Required controls:

- Validate OpenEMR JWTs on every backend request.
- Enforce role and patient access server-side.
- Lock one patient per conversation.
- Inject `patient_id` into tools from trusted context, not model output.
- Use typed Pydantic tool arguments.
- Treat chart text as untrusted data.
- Do not log prompts, answers, raw notes, lab values, or demographic PHI.
- Maintain a PHI-safe audit log using allowlisted fields.
- Add CI checks that fail on obvious PHI leakage in logs and audit samples.
- Track provider PHI approval status before routing requests.

## API Surface

Initial FastAPI endpoints:

```text
GET  /healthz
GET  /api/me
GET  /api/patients?query=
GET  /api/patients/today
POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{conversation_id}
POST /api/conversations/{conversation_id}/messages
GET  /api/conversations/{conversation_id}/events
POST /api/patients/{patient_id}/reindex
GET  /api/source/{source_id}
GET  /api/capabilities
```

Chat events should use SSE. Patient and source endpoints must re-check authorization.

## Tech Stack

```text
Frontend
    Next.js App Router
    TypeScript
    Tailwind
    shadcn/ui
    SSE client

Backend
    Python 3.12+
    FastAPI
    uvicorn
    asyncio
    httpx.AsyncClient
    Pydantic v2
    pydantic-settings

Database
    Postgres 16
    pgvector
    pgcrypto
    SQLAlchemy 2.x async
    asyncpg
    Alembic

OpenEMR Integration
    SMART/OAuth via authlib
    FHIR via thin httpx client
    optional read-only MySQL fallback via SQLAlchemy + asyncmy

LLM / Embeddings
    Anthropic SDK
    OpenRouter via OpenAI-compatible HTTP
    local OpenAI-compatible models
    default hosted embedding model
    local embedding option for restricted deployments

Testing
    pytest
    pytest-asyncio
    respx
    testcontainers
    Playwright
    ruff
    mypy --strict

Deployment
    Railway web service: Next.js
    Railway API service: FastAPI
    Railway cron/worker service: ETL
    Railway Postgres add-on
```

## Testing And Evals

Testing should prove that the assistant is safe before it is clever.

Required deterministic tests:

- A factual claim without a valid citation fails verification.
- A cited source from another patient fails verification.
- A nurse/MA cannot access doctor-only capability output.
- A prompt-injected note cannot override system rules.
- Treatment recommendation requests are refused or redirected to informational summaries.
- Stale evidence is detected.
- Patient id filters are applied before vector ranking.
- Source links re-check authorization.
- Logs and audit samples do not include obvious PHI.

Eval fixture patients:

- Complex adult primary care patient with T2D, HTN, HLD, recent A1c, lipid panel, eGFR.
- Pediatric wellness patient.
- Older adult with polypharmacy.
- Patient with no recent data.
- Patient with prompt injection inside a note.
- Patient note referencing another patient.

## Deployment Plan

Railway services:

```text
web
    Next.js app

api
    FastAPI app

worker
    ETL, reindex, scheduled prefetch

postgres
    Railway Postgres with pgvector and pgcrypto
```

Railway environment variables should cover:

- OpenEMR base URL.
- OpenEMR OAuth client id/secret.
- OpenEMR JWKS URL.
- Postgres URL.
- encryption key.
- provider keys.
- provider PHI approval flags.
- embedding provider config.
- retention defaults.

## MVP Tradeoffs

Standalone app over embedded OpenEMR module:

- Better product separation, easier iteration, cleaner FastAPI/Next.js stack.
- More integration work for auth, source linking, and deployment networking.

FHIR first over direct database reads:

- Cleaner security and compatibility story.
- May require read-only MySQL fallback for OpenEMR data not exposed well through FHIR.

Postgres plus pgvector over a separate vector database:

- Simpler Railway deployment and fewer moving parts.
- May need a dedicated vector service later if corpus size or retrieval complexity grows.

Verified query layer plus RAG over pure vector search:

- More upfront modeling work.
- Much better correctness for labs, medications, problems, demographics, and dates.

SSE over WebSockets:

- Simpler for one-way assistant progress streaming.
- Less flexible for future collaborative or bidirectional realtime features.

Encrypted 30-day conversations over session-only chat:

- Better product continuity and debugging/eval support.
- Higher PHI governance burden, so encryption, retention, deletion, and audit controls must be implemented from the start.

## Open Questions

- Which OpenEMR roles and scopes map to doctor, NP/PA, nurse, and MA in the test environment?
- Which OpenEMR FHIR resources are reliable enough for the first verified query layer?
- Which provider is allowed to process PHI in the first real deployment?
- Should on-demand patient reindex be available to nurses/MAs or only clinicians/admins?
- How should source links open when the user is authenticated in AgentForge but not currently inside OpenEMR?
