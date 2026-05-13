# Week 3 Rubric Checklist And Current-Code Grade

Audit date: 2026-05-12

Scope: current repository code after the Week 3 gap-closure pass. Plans and future-work text do not receive implementation credit unless the requirement is itself a document artifact.

Source requirements:

- `WEEK3_PRD.md`, especially sections 9.1 through 9.12 and MVP metrics.
- `W3_BUILD_GOALS.md`, especially the MVP definition and steps 1 through 15.
- `THREAT_MODEL.md`, especially the threat categories, evidence policy, and dashboard requirements.

## Summary Grade

| View | Grade | Meaning |
|---|---:|---|
| MVP readiness | 94 / 100 | Week 3 MVP is now implementation-ready: deployed operator path, expanded seed suite, deterministic Judge, judge eval, Red Team variants, regression promotion, resilience scoring, reporting/export evidence, and passing quality gates. |
| Full Week 3 PRD coverage | 84 / 100 | The major PRD mechanics are implemented. Remaining gaps are final-product hardening: deeper autonomous looping, real provider-cost accounting, CI wiring, reviewer auth/rate limiting, and confirmed vulnerability reports if deterministic failures are found. |

## Rubric Checklist

| Component | Weight | Current Score | Status | Current-code evidence | Remaining gap |
|---|---:|---:|---|---|---|
| 1. Live target harness | 12 | 11 | Met for MVP | `adversarial/app/config.py` supports local/deployed targets, allowlist, synthetic clinician auth, and budgets. `run_week3_eval.py` records `synthetic_principal`, target metadata, and target version hints when exposed. | Service-account auth path is configured but not exercised by the runner. |
| 2. Threat model artifact | 8 | 8 | Met | `THREAT_MODEL.md` covers required attack categories, failure definitions, trust boundaries, existing defenses, and evidence policy. | No implementation gap for this document requirement. |
| 3. Adversarial eval dataset | 10 | 9 | Met for MVP | `adversarial/evals/week3/cases/` now covers PHI, auth/session, clinical recommendation, indirect injection, direct prompt injection, multi-turn manipulation, state corruption, identity hijacking, tool misuse, cost amplification, and citation manipulation. Tests verify category and injection-layer coverage. | Uploaded-document and seeded-note cases are marked setup-aware until target fixture setup exists. |
| 4. Multi-agent architecture and LangGraph loop | 12 | 9 | Mostly met | `adversarial/app/graph.py` records Orchestrator, Red Team, Target Runner, Judge, Documentation, Regression Store, and Stop Policy trace events. It persists runs, observations, verdicts, reports, and regression candidates. | Execution is still a bounded single-pass workflow per case rather than a fully adaptive multi-round loop. |
| 5. Red Team Agent | 8 | 7 | Mostly met | `adversarial/app/red_team_agent.py` generates bounded variants with parent provenance, mutation rationale, and approval checks. `run_week3_eval.py` can include generated variants. | Mutations are deterministic templates, not LLM-generated adversarial strategies. |
| 6. Judge Agent | 10 | 9 | Met for MVP | `judge_agent.py` covers patient scope leaks, clinical recommendation failures, tool misuse, citation support, indirect injection, target instability, auth denial, direct prompt injection, identity hijacking, and budgets. `run_judge_eval.py --enforce` passes with zero false positives and zero false negatives on the fixture set. | Semantic citation validation is still heuristic. No LLM advisory path is enabled. |
| 7. Documentation Agent and vulnerability reports | 8 | 6 | Mostly met | `documentation_agent.py` drafts reports for non-pass verdicts with evidence and export links. Reports are stored and surfaced through the dashboard and exports. | There are no confirmed findings to package into three final vulnerability reports; the project should not invent them. |
| 8. Regression and validation harness | 8 | 7 | Mostly met | `regression_harness.py` promotes confirmed reports into replayable `RegressionCase` records. The graph persists regression candidates on failures, and the regression suite replays promoted cases. | CI integration is not wired yet. |
| 9. Observability and reporting | 8 | 7 | Mostly met | SQLite stores cases, runs, observations, traces, verdicts, reports, resilience snapshots, regression cases, and suite summaries. `reporting.py`, `costing.py`, and `export_run.py` add category rollups, dashboard summary, cost rollups, trace detail, and resilience exports. | Trending is available from stored snapshots, but richer historical visualizations can still improve the final product. |
| 10. Operator UI | 8 | 7 | Mostly met | `ui.py` shows target mode, recommendation, metrics, coverage, latest runs, findings, exports, black-box observations, trace detail, and a risk posture panel with resilience/cost signals. | Reviewer auth/rate limiting and deeper trend charts remain final hardening items. |
| 11. Cost and scale controls | 4 | 3 | Mostly met | `RunBudget`, Judge budget checks, per-run cost fields, and `costing.py` suite rollups are implemented. | Provider cost still depends on captured usage; token estimates are approximate when the target does not expose usage. |
| 12. Trust, safety, and authorization | 4 | 4 | Met for MVP | Allowlist checks reject arbitrary hosts. Synthetic clinician auth is environment-provided. Seed cases are synthetic. Credentials are not serialized in run metadata. | Public operator hardening should add reviewer auth/rate limiting before broader exposure. |

Total full-PRD score: 84 / 100.

## MVP Capability Checklist

| MVP capability from `W3_BUILD_GOALS.md` | Current status | Evidence |
|---|---|---|
| Top-level `adversarial/` app scaffold | Met | `adversarial/pyproject.toml`, `adversarial/app/`, `adversarial/tests/`, `adversarial/README.md`. |
| Deployed FastAPI operator UI | Met | Live operator path remains `https://adversarial-production.up.railway.app`; `/readyz` is part of the deployment verification. |
| SQLite run store with migrations/readiness | Met | `run_store.py` schema version 3 plus `migrations/001_initial.sql`. |
| Local and deployed target modes | Met | `TargetMode`, `Settings.target_url`, `run_week3_eval --target`. |
| Target allowlist and synthetic auth config | Met for MVP | Allowlist and synthetic clinician password-grant config are implemented; credentials are not exported. |
| Expanded eval cases for hospital-director suite | Met | Case corpus now covers all core PRD attack families and indirect-injection layers. |
| Target client for black-box attacks | Met | `TargetClient.execute_case` captures status, text, citations, timing, token estimate, headers, and safe target metadata. |
| Deterministic Judge Agent | Met | Judge rules plus `run_judge_eval --enforce` and fixture coverage. |
| LangGraph loop wiring required MVP nodes | Met for MVP | All node names exist, trace events are recorded, and failure paths produce reports/regression candidates. |
| JSON/Markdown exports | Met | `export_run.py` includes observations, traces, reports, and resilience snapshots. |
| Basic deployment docs and final demo path | Met | `adversarial/README.md`, root README/submission docs, Railway service path. |
| End-to-end proof | Met locally; deploy verification pending after this pass | Local tests, lint, typecheck, and judge eval are clean. |

MVP grade: 94 / 100.

## Remaining Important Gaps

1. Fully autonomous Red Team looping.
   The system now generates bounded variants, but the graph is not yet an adaptive multi-round planner that redirects budget based on low-signal results.

2. Final vulnerability report package.
   The reporting workflow is implemented, but confirmed reports should only be produced from deterministic failures or human review. If the expanded suite still finds no vulnerabilities, the correct final artifact is a clean evidence register, not invented findings.

3. Operational hardening.
   Add reviewer authentication, rate limiting, and CI regression execution before treating the public operator as a long-lived service.

4. Provider-grade cost accounting.
   Suite rollups exist, but exact provider cost requires usage data from the target or model provider.

## Verification Run

Commands run from `adversarial/`:

```powershell
..\copilot\api\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
..\copilot\api\.venv\Scripts\python.exe -m ruff check app tests --no-cache
..\copilot\api\.venv\Scripts\python.exe -m mypy app --cache-dir <temp>
..\copilot\api\.venv\Scripts\python.exe -m app.run_judge_eval --enforce
```

Results:

- `pytest`: 34 passed.
- `ruff`: all checks passed.
- `mypy`: success, no issues in 19 source files.
- `run_judge_eval --enforce`: 6 fixtures, 0 false positives, 0 false negatives, 0 critical/high false negatives.

## Bottom Line

The Week 3 MVP gaps identified in the first audit have been closed in code. The remaining work is final-product polish and operational rigor, not missing MVP substrate.
