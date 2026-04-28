# AgentForge Clinical Co-Pilot Presearch

This document captures the pre-code planning pass for the AgentForge Clinical Co-Pilot MVP. It is based on the local project requirements PDFs, a focused OpenEMR codebase read, and a small set of official external references for healthcare/privacy and LLM security constraints.

## Source Material Reviewed

- `../Presearch.pdf`
- `../Week 1 - AgentForge.pdf`
- `eli5.md`
- `README.md`
- `CLAUDE.md`
- `API_README.md`
- `FHIR_README.md`
- `DOCKER_README.md`
- `docker/development-easy/docker-compose.yml`
- `docker/production/docker-compose.yml`
- `apis/routes/_rest_routes_standard.inc.php`
- `src/RestControllers/Config/RestConfig.php`
- `src/RestControllers/Subscriber/AuthorizationListener.php`
- `src/RestControllers/Subscriber/OAuth2AuthorizationListener.php`
- `src/RestControllers/Subscriber/ApiResponseLoggerListener.php`
- `src/RestControllers/Subscriber/TelemetryListener.php`
- `src/Services/PatientService.php`
- `src/Services/EncounterService.php`
- `src/Services/AppointmentService.php`
- `src/Services/ListService.php`
- `src/Services/VitalsService.php`
- `src/Services/ObservationLabService.php`
- HHS HIPAA Security Rule: https://www.hhs.gov/hipaa/for-professionals/security/index.html
- HHS Minimum Necessary guidance: https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html
- HHS Summary of the HIPAA Security Rule: https://www.hhs.gov/ocr/privacy/hipaa/understanding/srsummary.html
- HL7 SMART App Launch scopes and context: https://hl7.org/fhir/smart-app-launch/scopes-and-launch-context.html
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/

## MVP Interpretation

The MVP is not the agent build. The Tuesday MVP gate is the foundation for the agent:

1. Run OpenEMR locally with sample/demo patient data.
2. Deploy the standalone Co-Pilot services publicly on Railway, connected to OpenEMR for auth and chart data.
3. Produce `AUDIT.md` with security, performance, architecture, data quality, and compliance findings.
4. Produce `USERS.md` or `USER.md` with a narrow target user, workflow, and use cases.
5. Produce `ARCHITECTURE.md` with a codebase-informed plan for the Clinical Co-Pilot.

The strongest MVP story is: "I audited OpenEMR, chose a narrow clinical workflow, and designed an agent that never bypasses OpenEMR's permission boundary, only answers from retrieved patient records, and exposes source-backed uncertainty instead of unsupported conclusions."

## Phase 1: Constraints

### Domain

- Domain: healthcare, specifically EHR context support connected to OpenEMR.
- Primary target user: a primary care physician with a packed clinic day.
- Supporting user: a nurse or medical assistant preparing charts and rooming patients.
- Initial workflow: the 1-2 minute window between patient rooms.
- Agent shape: a chat-first standalone Next.js experience. The user authenticates through OpenEMR SMART/OAuth, the FastAPI backend derives role and data permissions from OpenEMR scopes/RBAC, the user searches/selects any patient they are authorized to access, and then asks patient-scoped questions in the chat window. Common quick-question context should be preloaded or cached when the schedule is set, while uncommon/custom questions should be answered on demand in the current patient context.
- Default response style: concise clinical brief. The first answer should be short, structured, and source-cited. More detail should be provided only when the user asks a follow-up.
- Citation style: inline source labels, such as `[Lab 2026-04-12]` or `[Problem List]`. Labels should be clickable and open the related OpenEMR source record, document, or source detail view when available.
- Product mode: read-only for MVP. The Co-Pilot retrieves and explains patient record information; it does not write, draft writebacks, place orders, create notes, or modify the chart.

### MVP Use Cases

1. Authenticated patient chat: the user opens the Co-Pilot, is recognized through OpenEMR session/RBAC, selects an allowed patient, and asks a question.
2. Pre-room patient brief: "What should I know before seeing this patient?"
3. Patient history and active problems: "Summarize active problems and relevant history."
4. Recent labs: "Show recent labs and abnormal results."
5. Source-backed follow-up and secondary context: citations first, then meds/allergies when relevant.

Out of scope for MVP and early agent:

- Diagnosis, triage, prescribing, medication dose recommendations, or treatment plans.
- Patient-facing agent behavior.
- Autonomous writes back into the chart.
- Drafted chart writebacks, orders, or note creation.
- Cross-patient comparison or population-style questions in chat.
- Real PHI. Use demo/sample data only.

Refusal style: short, direct, and useful. The agent should explain that it cannot perform the requested unsafe/out-of-role action and then offer source-backed patient information it can provide instead. Example: "I can't recommend treatment or medication changes. I can show the patient's active problems, recent labs, and current meds with sources."

### Verification Requirements

Every factual clinical claim needs a source reference. In practice, tool outputs should be normalized into evidence records with:

- `source_type`, such as `patient_data`, `form_encounter`, `lists`, `form_vitals`, `procedure_result`.
- `source_id`, such as `pid`, UUID, encounter id, list id, or procedure result id.
- `source_date`, if present.
- `field_path`, such as `medication.title` or `lab.result`.
- `value`.
- `display_label`, safe for user-facing citation.
- `source_link`, when OpenEMR can route to the source record, document, lab result, or chart section.

The verification layer should reject, hide, or rewrite claims that do not cite a retrieved evidence item. For the first implementation, prefer extractive summaries and tightly constrained templates for high-risk sections such as medications, allergies, and labs.

Caching decision: cache normalized evidence only, not LLM-written summaries. Final answers should be generated fresh from cached or newly retrieved evidence so the response can match the exact question and pass citation checks. Correctness takes priority over cache speed: cached evidence is a speed hint, not the source of truth.

### Data Sources

Codebase-informed first data sources:

- Primary: patient identity and demographics from `src/Services/PatientService.php`, table `patient_data`.
- Primary: active problems and relevant history from `src/Services/ListService.php`, table `lists`, and condition/problem-list services.
- Primary: recent labs from `src/Services/ObservationLabService.php`, tables `procedure_result`, `procedure_report`, `procedure_order`, `procedure_order_code`.
- Secondary: medications from `src/Services/ListService.php`, table `lists`, and medication-specific detail that may involve `lists_medication`.
- Secondary: allergies from `src/Services/AllergyIntoleranceService.php` and standard API allergy routes.
- MVP: today's schedule from `src/Services/AppointmentService.php`, table `openemr_postcalendar_events`, used for a lightweight schedule entry point and scheduled-patient prefetch.
- Future/near-next: encounters and recent visit reasons from `src/Services/EncounterService.php`, table `form_encounter`.
- Future/near-next: vitals from `src/Services/VitalsService.php`, table `form_vitals`.
- Future/near-next: document metadata from `src/Services/DocumentService.php`, table `documents`.

### Scale and Performance

MVP assumptions:

- Demo load: one clinician, one active patient, sequential requests.
- Response target: first useful answer in under 10 seconds; aspirational target under 5 seconds.
- Tool-call budget: one aggregate patient context fetch plus one LLM call for the first brief.
- LLM cost target: small enough for demo; exact model and cost analysis should be deferred until provider and model are selected.
- Common quick questions should use scheduled-patient prefetch or cache where possible; cache normalized evidence only, not prewritten model answers. Before producing a user-visible answer, cached evidence should be revalidated against OpenEMR source tables. If freshness cannot be proven, evidence should be refreshed. Uncommon questions can tolerate more on-demand retrieval latency as long as the UI communicates progress.

Production-minded assumptions for the architecture doc:

- Clinic-level use: 10-30 concurrent clinicians.
- Hospital-level discussion: hundreds of concurrent users requires caching, background prefetch for scheduled patients, rate limits, and strict observability.
- Expensive operations should be bounded by date windows and result counts.
- Revalidation is expected to add sub-second latency for the MVP evidence set and should be cheaper than the model call.

### Reliability

The cost of a wrong answer is high because clinical users may act on it. Non-negotiable requirements:

- No unsupported claims.
- Clear "not found in retrieved records" language.
- Source citations visible in the UI.
- No hidden writes.
- No raw PHI in normal observability logs.
- Fail closed on authorization and patient-context mismatch.

Human-in-the-loop requirement: the physician remains the decision maker. The agent is a retrieval and summarization aid, not clinical authority.

### HIPAA-Informed RBAC Model

HIPAA does not define a fixed permission matrix for doctors, nurses, NPs, PAs, or MAs. It requires covered entities to apply appropriate safeguards, authorize ePHI access according to the user's role, identify users uniquely, audit activity, and make reasonable efforts to limit unnecessary access/use/disclosure of PHI. The Co-Pilot should therefore use OpenEMR authentication and ACLs as the source of truth, then apply an agent-specific role policy that limits which evidence tools each role can use.

MVP role policy:

| Role | MVP Co-Pilot Access |
|---|---|
| Physician | Authorized patient search; demographics; active problems/history; recent labs; meds/allergies as secondary context; source-backed follow-up. |
| NP/PA | Same as physician for MVP if OpenEMR permissions identify them as a licensed clinician for the patient/workflow. This is intentional for MVP because the Co-Pilot is information-only. |
| RN/LPN | Authorized patient search; demographics; active problems summary; meds/allergies; recent labs when OpenEMR ACL permits; fewer broad chart-history tools by default. |
| MA | Authorized patient search; demographics; schedule/rooming context; meds/allergies and active problem names when OpenEMR ACL permits; no deep lab details by default unless explicitly allowed by site policy. |
| Admin/Billing | No clinical Co-Pilot access by default for MVP, unless a future nonclinical workflow is explicitly designed. |

Every role must still pass patient-level and data-category authorization. Chat text must never change role, patient access, or data access.

Decision: keep nurses and MAs conservative for MVP. Sites may relax access later through explicit policy and OpenEMR permissions, but the default agent policy should expose less clinical depth to supporting roles than to licensed diagnosing/treating clinicians.

### Team and Skill Constraints

Assumed constraints:

- One-week sprint.
- Existing codebase is large and mostly PHP.
- Fastest defensible path is to build a standalone Next.js + FastAPI app that relies on OpenEMR for SMART/OAuth identity and FHIR-backed clinical reads, rather than modifying OpenEMR internals during the MVP.

## Phase 2: Architecture Discovery

### Framework Selection

Recommendation for first agent build: use a custom single-agent orchestration layer in FastAPI rather than LangChain, LangGraph, CrewAI, or a multi-agent setup.

Reasoning:

- OpenEMR's permission boundary is already exposed through SMART/OAuth scopes and FHIR/API authorization.
- The agent needs a narrow set of deterministic tools, not open-ended autonomous planning.
- A general-purpose agent framework would add abstraction before the MVP has proven the workflow.
- Multi-agent architecture is unjustified for the initial use cases.

Possible later evolution: add a workflow framework only if the custom orchestrator becomes hard to evaluate, trace, or extend. The system should continue to call OpenEMR APIs with scoped user context rather than reading the clinical database directly at chat time.

### LLM Selection

Provider target: Anthropic, OpenRouter, or local OpenAI-compatible models. The architecture should keep this behind a provider adapter so provider choice can be configured without rewriting the agent.

The agent needs:

- Tool/function calling or equivalent structured tool invocation.
- Strict structured output support.
- Low-latency small/medium model for routine briefs.
- A stronger fallback model for difficult synthesis, if cost allows.
- Contractual posture compatible with PHI if real data is ever used. For this project, use demo data only.

MVP architecture decision: create a provider adapter interface so model, token accounting, retries, and PHI-cleared routing can change without rewriting retrieval tools.

### Tool Design

Initial tool allowlist:

- `get_patient_header(puuid|pid)`
- `get_today_schedule(user_id, date)`
- `preload_schedule_patient_context(user_id, date)`
- `get_recent_encounters(puuid|pid, limit, since)`
- `get_active_problems(puuid|pid)`
- `get_active_medications(pid)`
- `get_allergies(puuid|pid)`
- `get_recent_vitals(pid, limit, since)`
- `get_recent_labs(puuid|pid, limit, since)`
- `get_document_metadata(pid, limit, since)`

Each tool must:

- Require an explicit patient identifier or current patient context.
- Check ACL or run behind an already authorized internal endpoint.
- Return bounded, normalized evidence.
- Return structured errors, not raw exceptions.
- Include enough metadata for citation and audit.

No tool should accept arbitrary SQL, arbitrary file paths, arbitrary URLs, or free-form "search the database" instructions.

Multi-turn decision: support patient-scoped follow-up context within the current session. Follow-up references like "those labs" may resolve to the prior answer for the selected patient. When the selected patient changes, conversation context must reset.

Patient scope decision: one selected patient at a time. Cross-patient comparison and population-style questions are out of scope for MVP, even if the user has access to multiple patients.

### OpenEMR Integration Points

Likely UI location:

- Primary product surface: a Co-Pilot chat window with patient selector, quick questions, free-text prompts, and source-backed answers.
- Patient selector scope: all patients the user is authorized to access, with search. Today's schedule can provide shortcuts and prefetch but should not be the only patient list.
- Primary app surface: standalone Next.js chat application.
- Secondary MVP shortcut: today's schedule can open the chat for a scheduled patient and trigger scheduled-patient prefetch.
- The patient list must be permission-filtered. Doctors and nurses/MAs may see different patients or data categories based on OpenEMR role, scopes, and configured capability checks.

Likely backend path:

- Build a standalone FastAPI service for chat, retrieval, verification, patient search, and source links.
- Use OpenEMR FHIR APIs first for clinical data.
- Add optional read-only OpenEMR MySQL fallback only where FHIR coverage is insufficient.
- Store derived indexes, embeddings, evidence metadata, encrypted conversations, and audit events in Postgres.

Auth boundary:

- OpenEMR remains the identity and chart-data authority.
- FastAPI validates OpenEMR-issued JWTs against JWKS on every request.
- Backend tools inherit the selected patient id from trusted request context, not model output.
- Every patient search, source link, and retrieval tool must re-check role, scope, and selected-patient access.

### Observability

Strategy: use a provider-neutral telemetry adapter. Start with Co-Pilot-owned metadata logging in Postgres for MVP, and allow Langfuse, Braintrust, or another tracing backend later after PHI-handling rules are clear.

Minimum metadata to capture per request:

- Request id.
- User id or role id, not user name in normal logs.
- Patient id/UUID only when necessary for audit.
- Tool names invoked.
- Tool durations.
- Tool result counts.
- Verification result: pass/fail and rejected claim count.
- Model name.
- Prompt/completion token counts.
- Estimated cost.
- Error class.

Avoid logging raw prompt, raw response, free-text notes, lab text, or medication names by default. OpenEMR has existing API response logging, but an AI feature should not rely on full response logging for observability because that can capture PHI.

Conversation retention decision: store encrypted conversations for 30 days by default, with metadata retained separately for audit/observability. Prompt text and answer payloads must be encrypted; metadata such as tool names, durations, result counts, verification status, token counts, cost, and error class can remain queryable. Do not store raw unencrypted chat prompts or model responses.

### Eval Approach

First eval suite should be fixture-driven:

- Happy path: patient has demographics, recent encounter, meds, allergies, vitals, and labs.
- Missing data: no recent labs or stale vitals.
- Contradictory data: inactive medication appears in history but should not be stated as active.
- Unauthorized user: agent refuses or receives no data.
- Prompt injection in chart text: malicious note tells the agent to ignore instructions or reveal other patients.
- Ambiguous question: agent asks for clarification or scopes answer to current patient.
- Citation failure: answer with uncited claim fails verification.

Pass/fail should measure groundedness, source coverage, refusal correctness, and latency. Human review can score clinical usefulness later, but the first automated gate should catch unsupported claims and authorization failures.

Eval strategy decision: use both deterministic and LLM-judged evals, but deterministic tests are the required first gate. LLM-judged evals can be added later for usefulness and answer quality after source coverage, role access, refusal behavior, and missing-data behavior are stable.

### Verification Design

Proposed response flow:

1. Resolve current user, site, patient, and optional encounter context.
2. Run permission checks before any data retrieval.
3. Retrieve bounded evidence through allowlisted tools.
4. Ask the model for a structured response that cites evidence ids.
5. Validate that every claim cites an available evidence id.
6. Strip or rewrite unsupported claims.
7. Return answer plus source list and uncertainty flags.
8. Log metadata and verification outcome.

Known limitation: source citation verifies that a statement points to retrieved data, not that the statement is clinically complete or medically wise. The architecture should state this explicitly.

Streaming decision: stream status updates only, such as "Checking demographics," "Checking labs," and "Verifying sources." Do not stream factual answer text before verification completes. The final answer appears only after source verification passes.

Reasoning transparency decision: do not expose hidden chain-of-thought. Instead, show a user-facing reasoning summary/audit trail by default under each answer, with the tools checked, source categories used, verification result, and limitations. This should answer "how did you get this?" without displaying private model reasoning.

## Phase 3: Post-Stack Refinement

### Failure Modes

- Tool failure: return partial answer with "unable to retrieve X" and no fabricated substitute.
- Missing records: state absence in retrieved record set, not absence in reality.
- Ambiguous patient context: refuse to answer until patient context is selected.
- Unauthorized data: fail closed and avoid confirming whether data exists.
- LLM timeout/rate limit: return retrieval-only brief if safe, or ask user to retry.
- Prompt injection from chart content: treat record text as untrusted data; never let retrieved text change system instructions or tool rules.
- Conflicting records: show both records with dates and sources instead of choosing silently.

### Security Considerations

- Prompt injection, sensitive information disclosure, insecure plugin/tool design, excessive agency, and overreliance are first-class LLM risks per OWASP's LLM Top 10.
- HIPAA Security Rule framing: ePHI requires appropriate administrative, physical, and technical safeguards.
- Minimum necessary framing: retrieve and disclose only the data needed for the user task where applicable.
- API keys must live in environment variables or secrets, not committed files.
- Development compose files contain demo credentials and token-like values; do not reuse them for public deployment.
- Audit logs should record access and behavior without turning logs into a PHI dump.

### Testing Strategy

MVP docs:

- `AUDIT.md`: document findings, risks, and mitigations.
- `USERS.md` or `USER.md`: narrow user and use cases.
- `ARCHITECTURE.md`: planned integration, verification, observability, eval, and deployment.

Early implementation:

- Unit tests for evidence objects and verifier behavior.
- Service tests for each patient context tool.
- API tests for auth, patient binding, and route behavior.
- Eval tests for groundedness and refusal cases.
- Manual browser test in local OpenEMR.

### Open Source Planning

- Keep all new code GPL-compatible with OpenEMR.
- Do not commit API keys, private deployment URLs with credentials, or real PHI.
- Document setup, env vars, demo data assumptions, and model-provider configuration.
- Any demo video should use seeded demo patients only.

### Deployment and Operations

Local run path:

```powershell
cd docker/development-easy
docker compose up --detach --wait
```

Expected local URLs from repo docs:

- OpenEMR HTTP: `http://localhost:8300/`
- OpenEMR HTTPS: `https://localhost:9300/`
- Login: `admin` / `pass`
- phpMyAdmin: `http://localhost:8310/`

Public deployment path needs a short proof before finalizing. The new architecture deploys the Co-Pilot as separate Railway services and connects to OpenEMR rather than embedding the assistant inside the PHP app. OpenEMR still needs to be reachable for SMART/OAuth and FHIR during the demo.

Railway is the starting deployment target. The likely Railway shape is:

- `web`: Next.js chat app.
- `api`: FastAPI app.
- `worker`: ETL, scheduled prefetch, and on-demand patient reindex.
- `postgres`: Railway Postgres with `pgvector` and `pgcrypto`.
- OpenEMR: separate reachable auth/FHIR source for the MVP demo.

### Iteration Planning

Feedback loop:

1. Run local OpenEMR.
2. Complete audit and identify integration risks.
3. Choose the user and write use cases.
4. Draft architecture.
5. Build minimal data tools.
6. Add verification.
7. Add LLM synthesis.
8. Add observability and eval.
9. Deploy and record demo.

Feature priority:

1. Source-backed pre-room brief.
2. Follow-up questions over retrieved evidence.
3. Schedule-driven patient prefetch and lightweight schedule entry point.
4. More clinical domains only after verification and eval are solid.

## Immediate MVP Work Plan

1. Run OpenEMR locally with `docker/development-easy`.
2. Confirm sample patient data and API settings.
3. Create `AUDIT.md` with a one-page summary plus detailed security, performance, architecture, data quality, and compliance sections.
4. Create `USERS.md` with the primary care physician workflow and 3-4 concrete use cases.
5. Create `ARCHITECTURE.md` with the integration plan above, refined by audit findings.
6. Validate public deployment path and record deployed URL.
7. Prepare a 3-5 minute demo video focused on the completed foundation.

## Open Questions To Close Next

- Do we want the MVP user doc to be named `USERS.md` from the stage gate or `USER.md` from the submission table? Safest answer: create both, with one redirecting to the other.
- Which Anthropic/OpenRouter model should be used for the early/final agent build?
- How much UI polish is required for the schedule entry point versus simply using it to launch the patient-scoped Co-Pilot?

## Demo Scenario

Use OpenEMR sample/demo data plus a serious synthetic primary-care scenario:

- Adult patient presenting for type 2 diabetes and hypertension follow-up.
- Active problems include type 2 diabetes, hypertension, and hyperlipidemia.
- Recent labs include A1c, creatinine/eGFR, lipid panel, and optionally urine microalbumin.
- The demo should show the agent answering information-only questions about demographics, active problems, and recent labs with sources.
- The demo should avoid diagnosis, treatment recommendations, prescribing, and chart writes.
