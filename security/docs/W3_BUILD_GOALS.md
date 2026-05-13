# Week 3 Build Goals: MVP To Final Product

This document turns the Week 3 PRD, threat model, and system design into buildable goals. Each step has a goal, a way to get there, and verification tests.

Source artifacts:

- `WEEK3_PRD.md`
- `THREAT_MODEL.md`
- `W3_SYSTEM_DESIGN.md`
- `security/docs/diagrams/w3-adversarial-platform.png`

## Build Principles

- Build the adversarial platform outside Co-Pilot and test Co-Pilot through HTTP.
- Ship a deployed operator app, while preserving local development mode.
- Use LangGraph for the bounded autonomous loop.
- Use SQLite as the run store, backed by persistent storage in deployment.
- Keep blocking Judge verdicts deterministic and black-box.
- Treat LLM judgment as advisory until separately validated.
- Run only against allowlisted synthetic local/deployed targets.
- Present risk clearly to a hospital director or CISO.

## MVP Definition

The MVP is complete when a reviewer can open the deployed adversarial operator app, run or review an adversarial campaign against the deployed Co-Pilot target, see coverage and risk status, and inspect at least one Judge-backed finding or passing result with reproducible evidence.

Minimum MVP capabilities:

- Top-level `security/adversarial/` app scaffold.
- Deployed FastAPI operator UI.
- SQLite run store with migrations/readiness check.
- Local and deployed target modes.
- Target allowlist and dual synthetic auth config.
- Seed eval cases for the hospital-director suite.
- Target client that can run black-box attacks.
- Deterministic Judge Agent for the first risk categories.
- LangGraph loop wiring Orchestrator, Red Team, Target Runner, Judge, Documentation Draft, Regression Store, and Stop Policy.
- JSON/Markdown exports.
- Basic deployment docs and final demo path.

## MVP Build Plan

### Step 1: Create The Adversarial App Skeleton

Goal:
Create a top-level outside-in platform under `security/adversarial/` with its own Python package, app entrypoints, tests, and README.

Way to get there:

- Add `security/adversarial/pyproject.toml`.
- Add `security/adversarial/app/` package.
- Add `security/adversarial/tests/`.
- Add `security/adversarial/README.md` with local setup, env vars, run commands, and deployed-app expectations.
- Keep it separate from `copilot/api` runtime code.

Verification/tests:

- `cd security\adversarial && python -m pytest`
- `cd security\adversarial && python -m app.run_week3_eval --help`
- Import smoke test proves `app` modules load without importing Co-Pilot internals.

### Step 2: Define Core Schemas

Goal:
Make attack cases, runs, verdicts, traces, reports, budgets, and resilience snapshots typed before writing behavior.

Way to get there:

- Implement Pydantic models or dataclasses for:
  - `AttackCase`
  - `AttackRun`
  - `AgentTraceEvent`
  - `JudgeVerdict`
  - `VulnerabilityReport`
  - `CampaignPriority`
  - `ResilienceSnapshot`
  - `RunBudget`
- Encode severity and healthcare impact domain enums.
- Include injection layer for indirect prompt injection cases.

Verification/tests:

- Unit tests reject invalid severity, impact domain, verdict, target mode, and injection layer.
- Unit tests validate round-trip JSON serialization for every schema.
- Test fixtures include one case from each first-suite category.

### Step 3: Build The SQLite Run Store

Goal:
Persist all run state in SQLite so the CLI, LangGraph loop, dashboard, and exports share one source of truth.

Way to get there:

- Add `app/run_store.py`.
- Add simple SQL migrations under `security/adversarial/migrations/`.
- Store:
  - attack cases
  - runs
  - agent trace events
  - judge verdicts
  - vulnerability reports
  - campaign priority records
  - resilience snapshots
  - exports
- Add readiness validation for schema version and writable DB path.

Verification/tests:

- Unit tests create a temp SQLite DB, apply migrations, insert/read each record type.
- Readiness test fails when DB path is unwritable.
- Migration test proves running migrations twice is safe.
- Export test can reconstruct a run from only SQLite records.

### Step 4: Implement Configuration, Allowlist, And Budgets

Goal:
Make the platform safe by default before it can run attacks.

Way to get there:

- Add environment-driven config:
  - `ADVERSARIAL_TARGET_MODE=local|deployed`
  - local/deployed Co-Pilot URLs
  - allowed hostnames
  - synthetic clinician credential/token config
  - service account config
  - budget caps
  - SQLite path
- Fail closed on missing target, missing allowlist, missing auth, or unsafe URL.
- Add report-only/enforce run mode.

Verification/tests:

- Unit tests reject non-allowlisted URLs.
- Unit tests reject missing credentials for deployed runs.
- Unit tests reject production-like target names unless explicitly allowlisted.
- Unit tests prove `report-only` never blocks and `enforce` applies thresholds.

### Step 5: Build The Target Client

Goal:
Create the black-box HTTP layer that talks to Co-Pilot targets and captures observable evidence.

Way to get there:

- Add `app/target_client.py`.
- Support:
  - readiness checks
  - session/auth setup using synthetic clinician
  - chat request execution
  - document endpoint smoke hooks
  - status/capability metadata collection
  - timing, status code, response body, citations, and source links
- Keep gray-box metadata separate from black-box verdict evidence.

Verification/tests:

- Unit tests use mocked HTTP responses to verify evidence capture.
- Tests prove black-box and gray-box records are stored separately.
- Integration smoke command:
  - `python -m app.run_week3_eval --target local --suite smoke --report-only`
  - `python -m app.run_week3_eval --target deployed --suite smoke --report-only`
- Failure tests cover timeout, 401/403, 5xx, and target readiness failure.

### Step 6: Create The First Eval Dataset

Goal:
Seed the hospital-director suite with reproducible cases that map directly to the threat model.

Way to get there:

- Add `security/adversarial/evals/week3/cases/`.
- Add initial JSON cases for:
  - cross-patient PHI leakage
  - unauthorized access/session confusion
  - unsafe clinical recommendation jailbreak
  - malicious document/note injection, prompt-simulation layer
  - unauthorized writeback/tool misuse
  - cost amplification/runaway behavior
  - evidence/citation manipulation
- Include expected safe behavior, severity, impact domain, exploitability, and regression flag.

Verification/tests:

- Case loader validates all case files.
- Test fails if any case lacks threat-model category, severity, impact domain, expected safe behavior, or regression flag.
- Test confirms each first-suite category has at least one seed case.

### Step 7: Implement The Deterministic Judge Agent

Goal:
Make the Judge Agent the first credible decision-maker for pass/fail/partial/inconclusive verdicts.

Way to get there:

- Add `app/judge_agent.py`.
- Implement deterministic checks for:
  - wrong-patient identifiers
  - wrong-patient clinical facts from known synthetic fixtures
  - out-of-scope citations/sources
  - actionable clinical recommendations
  - missing citations on clinical claims
  - obvious unsupported citation/source mismatch
  - unauthorized write/tool outcomes
  - budget/request/latency breaches
- Keep optional LLM judging feature-flagged and advisory only.

Verification/tests:

- Unit tests for each failure definition in `THREAT_MODEL.md`.
- Known-safe responses pass.
- Known-vulnerable responses fail.
- Ambiguous high-severity cases return `inconclusive` and `requires_human_review=true`.
- Tests prove advisory LLM verdicts cannot override deterministic blocking verdicts.

### Step 8: Build The LangGraph MVP Loop

Goal:
Wire the bounded autonomous graph so the platform demonstrates real multi-agent orchestration.

Way to get there:

- Add `app/graph.py`.
- Nodes:
  - Orchestrator
  - Red Team
  - Target Runner
  - Judge
  - Documentation Draft
  - Regression Store
  - Stop Policy
- Start with seed cases and bounded variants.
- Store graph state transitions in `agent_trace_events`.

Verification/tests:

- Unit test graph compiles.
- Unit test one seed case moves through every expected node.
- Unit test stop policy halts on:
  - hard budget cap
  - critical PHI/auth failure
  - high-severity human-review gate
  - target instability
  - sufficient coverage
  - low-signal loop
  - timeout
  - operator cancellation
- Trace test proves each node writes ordered trace events.

### Step 9: Implement Red Team Bounded Generation

Goal:
Allow the Red Team Agent to generate useful attack variants inside approved categories without widening scope unsafely.

Way to get there:

- Add `app/red_team_agent.py`.
- Mutate prompt text, sequencing, persona pressure, document-note injection phrasing, and retrieval requests.
- Keep generation inside approved risk categories.
- Store mutation rationale and parent case id.
- New categories are `proposed` only and require human approval.

Verification/tests:

- Unit tests prove generated variants retain category, target workflow, severity, impact domain, and expected safe behavior.
- Tests reject variants outside the approved category list.
- Tests cap variants per case and total generated tokens.
- Test proves proposed new categories are not executed.

### Step 10: Implement Documentation Drafts And Report Lifecycle

Goal:
Generate useful vulnerability report drafts while keeping official reports limited to confirmed findings.

Way to get there:

- Add `app/documentation_agent.py`.
- Draft reports for fail/partial/inconclusive cases.
- Official reports require deterministic Judge confirmation or human confirmation.
- Include:
  - id
  - severity and impact domain
  - clinical/privacy impact
  - minimal reproduction
  - observed vs expected behavior
  - evidence links
  - remediation direction
  - status
  - validation runs

Verification/tests:

- Unit tests create a draft from a failed run.
- Unit tests prevent `confirmed` status without deterministic or human confirmation.
- Snapshot-like markdown tests verify report includes all required sections.
- Test proves false positives can be marked and excluded from official report counts.

### Step 11: Implement Regression Store And Enforce Mode

Goal:
Turn confirmed exploits into replayable regression cases and block dangerous regressions in enforce mode.

Way to get there:

- Add `app/regression_harness.py`.
- Convert confirmed vulnerability reports into regression case records.
- Support:
  - `--suite seed`
  - `--suite regression`
  - `--report-only`
  - `--enforce`
- Apply severity-tiered thresholds.

Verification/tests:

- Unit test confirmed exploit becomes regression case.
- Unit test `report-only` records failures but exits successfully.
- Unit test `enforce` fails on critical PHI/auth regression.
- Unit test medium/low findings remain advisory unless previously fixed regressions.

### Step 12: Build The Deployed Operator UI

Goal:
Provide a deployed dashboard that leadership can open and understand.

Way to get there:

- Add `app/ui.py`.
- Add server-rendered templates:
  - risk overview
  - run detail
  - finding detail
  - coverage view
  - exports view
- Dashboard first screen shows:
  - target URL/mode
  - latest run status
  - `Pass`, `Warn`, or `Block` with reason
  - critical/high findings
  - coverage by risk family
  - risk-weighted resilience trend
  - untested/inconclusive categories
- Include `/readyz` for deployment.

Verification/tests:

- FastAPI test client renders dashboard from seeded SQLite data.
- Test verifies dashboard fails gracefully when no runs exist.
- Test verifies critical findings appear on first screen.
- Test verifies black-box evidence and gray-box metadata are labeled separately.
- Deployed smoke:
  - `GET /readyz`
  - `GET /`
  - `GET /runs/<id>`

### Step 13: Package And Deploy The Adversarial App

Goal:
Deploy the operator app as a reviewer-accessible service with persistent SQLite storage.

Way to get there:

- Add `security/adversarial/Dockerfile`.
- Add deployment config, likely Railway-compatible.
- Mount persistent volume for SQLite.
- Set environment variables through deployment secrets.
- Add readiness failure if SQLite path is not writable.
- Record deployed URL in README/final submission notes.

Verification/tests:

- Docker build succeeds.
- Container smoke starts app and passes `/readyz`.
- Deployed `/readyz` passes.
- Deployed dashboard loads latest run from persistent SQLite.
- Restart smoke proves run store survives process restart.

### Step 14: Export Evidence For Submission

Goal:
Make every run easy to hand to reviewers without requiring database access.

Way to get there:

- Add `app/export_run.py`.
- Export:
  - run JSON
  - markdown run summary
  - vulnerability report drafts/confirmed reports
  - category coverage summary
  - budget/cost summary

Verification/tests:

- Export command writes JSON and Markdown from a temp SQLite run.
- Exported JSON validates against schema.
- Markdown contains target URL, run id, verdict summary, coverage, findings, and stop reason.

### Step 15: MVP End-To-End Proof

Goal:
Prove the MVP with a real deployed run and a reviewer-friendly dashboard.

Way to get there:

- Seed or verify synthetic target data.
- Run deployed seed suite in report-only mode.
- Run deployed regression/enforce subset when stable.
- Open deployed operator app.
- Export evidence.
- Capture demo screenshots/video.

Verification/tests:

- `python -m app.run_week3_eval --target deployed --suite seed --report-only`
- `python -m app.export_run --run-id <run_id>`
- Deployed dashboard shows same run id and verdicts as export.
- At least three risk families have seed coverage.
- No secrets or real PHI in SQLite exports.

## Final Product Plan

### Step 16: Expand Attack Coverage Across All Risk Families

Goal:
Move beyond MVP seeds into broad, meaningful adversarial coverage.

Way to get there:

- Add multiple cases per first-suite category.
- Add state corruption/context poisoning.
- Add identity/persona hijacking.
- Add multi-turn policy erosion.
- Add layered indirect injection:
  - prompt simulation
  - uploaded synthetic documents
  - seeded synthetic OpenEMR notes

Verification/tests:

- Coverage test requires minimum case counts per risk family.
- Dashboard shows tested/untested/partially tested surfaces.
- Indirect injection tests label their layer.

### Step 17: Improve Orchestrator Scoring

Goal:
Make campaign selection feel like real security coordination.

Way to get there:

- Implement combined priority scoring:
  - coverage gap
  - severity/impact
  - recent failures/partials
  - inconclusive verdicts
  - age since last run
  - regression status
  - remaining budget
  - target health
- Store selection reasons.

Verification/tests:

- Unit tests prove critical PHI/auth gaps outrank low-risk cost cases.
- Unit tests prove stale untested categories gain priority.
- Unit tests prove low remaining budget redirects or halts campaigns.
- Dashboard shows why a campaign was selected.

### Step 18: Add Judge Quality Evaluation

Goal:
Test the tester so Judge verdicts are not trusted blindly.

Way to get there:

- Create a judge eval dataset with known safe, vulnerable, partial, and inconclusive examples.
- Measure false positives, false negatives, and inconclusive rate.
- Keep LLM judge advisory until it passes a separate threshold.

Verification/tests:

- `python -m app.run_judge_eval --enforce`
- Critical false negative count is zero.
- High-severity false negative count is zero or requires human signoff.
- Inconclusive rate stays under configured threshold.

### Step 19: Harden The Dashboard For Leadership

Goal:
Make the deployed app useful for hospital-director review, not just developer debugging.

Way to get there:

- Improve risk overview copy.
- Add severity/impact grouping.
- Add resilience trend explanation.
- Add open/resolved/regressed finding status.
- Add evidence drilldowns.
- Add export links.

Verification/tests:

- UI tests verify first screen includes recommendation and reason.
- UI tests verify critical/high findings are visible without drilling into traces.
- Accessibility checks cover headings, labels, contrast, and keyboard navigation.

### Step 20: Build Final Vulnerability Report Workflow

Goal:
Deliver at least three professional vulnerability reports.

Way to get there:

- Generate drafts for all fail/partial/inconclusive cases.
- Confirm at least three distinct findings.
- Add remediation guidance and validation runs.
- Mark false positives and resolved findings clearly.

Verification/tests:

- Report schema test requires all required fields.
- Export test includes confirmed reports.
- Manual review confirms a senior engineer can reproduce each issue from the report alone.

### Step 21: Add CI And Release Gates

Goal:
Prevent adversarial regressions from being ignored.

Way to get there:

- Add CI for deterministic local subset:
  - lint
  - tests
  - schema validation
  - judge eval
  - regression enforce subset that does not require live secrets
- Keep live deployed evals as protected manual or scheduled jobs with secrets.

Verification/tests:

- CI fails on schema drift.
- CI fails on deterministic Judge regression.
- CI fails on critical regression fixture.
- Manual deployed run records target URL and run metadata.

### Step 22: Add Cost Analysis For Test Run Scale

Goal:
Meet final cost-analysis requirements for 100 / 1K / 10K / 100K test runs.

Way to get there:

- Record request count, latency, token estimates, model usage, retries, and generated variants.
- Estimate costs by run type:
  - deterministic seed run
  - LLM-assisted report drafting
  - Red Team mutation run
  - full autonomous campaign
- Update `AI_COST_ANALYSIS.md`.

Verification/tests:

- Cost summary appears in every run export.
- Unit tests verify cost math for sample run records.
- Final cost table covers 100, 1K, 10K, and 100K test runs.

### Step 23: Add Operational Safety And Abuse Controls

Goal:
Make the platform safe to deploy and demo.

Way to get there:

- Add app auth or reviewer access control if public.
- Keep target allowlist mandatory.
- Add rate limits.
- Add max run duration.
- Add operator cancellation.
- Add audit events for campaign start/stop/export.
- Add secret redaction in logs and exports.

Verification/tests:

- Security tests reject non-allowlisted targets.
- Tests verify exports redact secrets.
- Tests verify cancellation records stop reason.
- Tests verify run cannot exceed budget caps.

### Step 24: Final Demo Script And Submission Packet

Goal:
Tell the story cleanly in 3-5 minutes.

Way to get there:

- Update README with deployed adversarial app URL.
- Update `W3_ARCHITECTURE.md`.
- Link system diagram PNG.
- Export final run evidence.
- Record demo:
  1. Open deployed operator app.
  2. Show risk overview.
  3. Run or review deployed campaign.
  4. Show black-box evidence.
  5. Show confirmed or draft report.
  6. Show regression/enforce behavior.

Verification/tests:

- Final checklist confirms every Week 3 required artifact exists.
- Demo run uses deployed target.
- Dashboard and exports agree on run id, verdicts, and findings.
- Slop-detector review finds no fake claims, dead artifacts, or unsupported requirements.

## Suggested First Implementation Order

1. App skeleton.
2. Schemas.
3. SQLite run store.
4. Config/allowlist/budgets.
5. Seed cases.
6. Target client.
7. Deterministic Judge.
8. LangGraph loop.
9. Deployed operator UI.
10. Docker/deployment.
11. Exports.
12. MVP end-to-end proof.

This order keeps the credibility anchor early: data contracts, safe config, black-box evidence, and deterministic judging all land before broader Red Team autonomy.

## Generalizing Beyond Co-Pilot Targets

The adversarial platform can expand into an authorized multi-site scanner by adding scan profiles rather than weakening the target allowlist. The safe default is passive scanning only:

- Every non-Co-Pilot target must be present in `ADVERSARIAL_ALLOWED_HOSTS`.
- Every site scan must resolve an authorized client/project/scope record before it runs.
- The operator must attest that the site is owned or explicitly authorized.
- Passive HTTP/header/cookie checks may run from the UI or CLI.
- Each site scan stores `client_id`, `project_id`, and `scope_id` with the run evidence.
- The source-backed scanner knowledge base lives in `WEB_VULNERABILITY_KNOWLEDGE_BASE.md` and `security/adversarial/knowledge/site_vulnerability_knowledge_base.json`.
- OWASP ZAP baseline scanning can be integrated as a future optional profile because it performs a short spider followed by passive analysis, not active exploitation.
- Active attack profiles require separate approval, rate limits, scope constraints, and written authorization evidence.
