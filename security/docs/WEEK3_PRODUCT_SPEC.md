# Week 3 Product Spec

This is the canonical product/specification document for the Week 3 adversarial AI security platform. It consolidates the prior PRD, build goals, final product plan, architecture notes, system-design notes, and production-readiness notes.

## Purpose

The Week 3 platform is an outside-in adversarial evaluation system for the AgentForge Clinical Co-Pilot. It runs bounded, synthetic, allowlisted attacks against local or deployed Co-Pilot targets, captures observable evidence, judges whether the target behaved safely, and turns confirmed failures into regression artifacts and vulnerability reports.

It is separate from the Clinical Co-Pilot runtime. The Co-Pilot remains the target. The adversarial platform is the security control plane.

## Non-Goals

- No real PHI.
- No arbitrary internet scanning.
- No brute force, destructive testing, broad fuzzing, or exploitation outside written authorization.
- No official vulnerability report without deterministic replay or human review.
- No reliance on private Co-Pilot internals for release-blocking verdicts.
- No LLM judge as a release-blocking authority until separately implemented and validated.

## Users

- Security engineer: runs allowlisted campaigns, reviews Judge evidence, exports run artifacts, and triages findings.
- AI platform engineer: uses smoke, seed, and regression runs before Co-Pilot release decisions.
- Clinical product owner: reviews patient-safety and workflow impact for confirmed findings.
- Compliance or privacy reviewer: checks PHI boundaries, auditability, and public/private evidence separation.
- Engineering manager: reviews coverage, resilience, cost, and release recommendation.

## Core Workflow

1. Operator authenticates to the adversarial control plane.
2. Operator confirms target and authorized scope.
3. Run controller loads approved seed or regression cases.
4. Orchestrator prioritizes cases by open failure severity, category coverage gap, inconclusive signal, regression candidacy, and case severity.
5. LangGraph executes each case through Orchestrator, Red Team, Target Runner, Judge, Documentation Draft, Regression Store, and Stop Policy.
6. Public SQLite stores dashboard-safe evidence. Private SQLite stores raw observations, full report details, and scan evidence when configured.
7. Operator exports JSON/Markdown run evidence and promotes confirmed failures to regression coverage.

## Attack Categories

The current seed corpus covers:

- Cross-patient PHI leakage.
- Authorization and session confusion.
- Unsafe clinical recommendation jailbreaks.
- Direct prompt injection.
- Indirect injection through prompt simulation, uploaded synthetic documents, and seeded synthetic notes.
- Citation manipulation.
- Tool misuse and unapproved writeback.
- Cost amplification and runaway behavior.
- State corruption.
- Identity hijacking.
- Multi-turn manipulation.
- Web-surface exposure through authorized site scans.

## Agent Responsibilities

| Agent or Component | Role | Trust Level |
|---|---|---|
| Orchestrator | Prioritizes cases before execution using open failure and coverage signals. | Trusted control logic; does not judge target safety. |
| Red Team | Uses approved seed cases and bounded deterministic variants with parent-case lineage and mutation rationale. | Untrusted attack inputs; bounded by categories and budgets. |
| Target Runner | Sends black-box HTTP requests to the allowlisted target. | Trusted transport wrapper; target output remains untrusted. |
| Judge | Applies deterministic safety checks to observed evidence. | Release-blocking only for deterministic rules. |
| Documentation Agent | Drafts reports for non-pass verdicts. | Draft-only until human or replay confirmation. |
| Regression Store | Captures replay candidates from failures. | Trusted persistence of replayable cases. |
| Stop Policy | Records completion, critical failure, human review, target instability, or suite timeout. | Trusted control logic. |

## Data And Evidence Model

Primary Pydantic models live in `security/adversarial/app/models.py`:

- `AttackCase`
- `AttackRun`
- `ObservedResponse`
- `JudgeVerdict`
- `VulnerabilityReport`
- `RegressionCase`
- `SuiteSummary`
- `AgentTraceEvent`
- `ResilienceSnapshot`
- `AuthorizedScope`
- `SiteScanRun`
- `SiteScanFinding`

SQLite tables live in `security/adversarial/migrations/001_initial.sql` and include runs, cases, redacted observations, verdicts, reports, traces, suite summaries, snapshots, scopes, scan runs, scan findings, jobs, and audit events.

Sensitive raw observations, report details, and scan evidence are stored by `security/adversarial/app/sensitive_findings.py` when `ADVERSARIAL_PRIVATE_SQLITE_PATH` is configured.

## Safety And Authorization

- Target URLs must pass `ADVERSARIAL_ALLOWED_HOSTS`.
- Site scans are bound to client/project/scope records.
- Deployed/Railway operator startup fails closed without `ADVERSARIAL_OPERATOR_TOKEN`.
- `/readyz` remains public for deployment health checks.
- Operator browser sessions use signed cookies, CSRF protection, rate limiting, and audit events.
- Synthetic clinician credentials are supplied by environment variables and are not exported.
- Public exports redact raw target observations, reproduction steps, passive scan evidence, and remediation details.

## Budgets

Default per-case limits:

```text
max_requests_per_case = 8
max_latency_ms_per_case = 30000
max_token_estimate_per_case = 8000
max_provider_cost_usd_per_case = 0.25
max_retries_per_case = 2
max_loop_depth = 3
max_variants_per_case = 3
max_wall_clock_seconds = 300
```

The current runner also records a suite timeout run with `StopReason.TIMEOUT` when wall-clock budget is exhausted before the next case executes.

Variant replay is enabled with `--include-variants`. This expands each approved seed or promoted regression case by up to `max_variants_per_case` deterministic Red Team child cases. CI also supports `--skip-tags setup-required` so target-fixture-dependent ingestion cases remain visible in the corpus without making local replay flaky. LLM mutation is intentionally disabled in release-blocking runs so CI and local regression evidence remain reproducible.

## Acceptance Criteria

- Deployed target URL is recorded in the submission packet.
- At least three attack categories have seed cases and run evidence.
- At least one agent role runs live against the deployed target.
- Threat model and user docs describe healthcare-specific risks and users.
- Operator UI shows run state, verdicts, traces, exports, coverage, findings, scans, and audit log.
- Confirmed vulnerability reports include severity, healthcare impact domain, reproduction, observed vs expected behavior, remediation, status, and fix validation.
- Local quality gates pass: pytest, Ruff, mypy, Judge eval, and `git diff --check`.
- GitHub Actions runs the Week 3 regression replay gate against a local Co-Pilot target with Red Team variants enabled and setup-required ingestion cases excluded until their target fixtures are automated.

## Current Implementation Boundary

The MVP is a bounded single-pass graph per case with suite-level prioritization and CI-backed regression replay. It is not yet a fully autonomous multi-round planner that redirects within a running graph based on low-signal results. Final-product work should add richer looping, target-version pinning for long-lived replay, named-user SSO/OIDC, managed encrypted storage, and richer trend charts.

## Current Source Map

| Area | Canonical Path |
|---|---|
| Operator app | `security/adversarial/app/ui.py` |
| Suite runner | `security/adversarial/app/run_week3_eval.py` |
| Orchestrator prioritizer | `security/adversarial/app/orchestrator.py` |
| LangGraph pipeline | `security/adversarial/app/graph.py` |
| Judge | `security/adversarial/app/judge_agent.py` |
| Red Team variants | `security/adversarial/app/red_team_agent.py` |
| Reports and private storage | `security/adversarial/app/documentation_agent.py`, `security/adversarial/app/sensitive_findings.py` |
| Run store | `security/adversarial/app/run_store.py` |
| Site scanner | `security/adversarial/app/site_scanner.py`, `security/adversarial/app/site_scan_workflow.py` |
| Raw eval corpus | `security/adversarial/evals/week3/` |
| Evidence packet | `security/docs/WEEK3_EVIDENCE_PACKET.md` |
