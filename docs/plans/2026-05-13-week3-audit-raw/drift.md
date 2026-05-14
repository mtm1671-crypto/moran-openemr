# Doc/Code Drift Audit

Audit date: 2026-05-13. Scope: Week 3 docs listed in the prompt. Code under
`security/adversarial/app/**.py`, `security/adversarial/tests/**.py`,
`security/adversarial/evals/**`, `security/adversarial/migrations/**`,
`security/adversarial/Dockerfile`, `pyproject.toml`, `railway.toml`.

Method: every concrete claim in a Week 3 doc was checked against the actual
files in the repo. Verdict labels: Confirmed (code matches doc), Contradicted
(code does the opposite or another thing), Overstated (doc claims more than
the code does), Understated (doc undersells what the code does),
Unverified (claim is about a deployed Railway run/log/screenshot that this
audit cannot reach).

## Per-Doc Verdict Summary

| Doc | Total claims checked | Confirmed | Contradicted | Overstated | Understated | Unverified |
|---|---:|---:|---:|---:|---:|---:|
| `THREAT_MODEL.md` (root) | 14 | 11 | 0 | 1 | 0 | 2 |
| `ARCHITECTURE.md` (root) | 11 | 9 | 0 | 1 | 0 | 1 |
| `USERS.md` (root) | 6 | 6 | 0 | 0 | 0 | 0 |
| `AI_COST_ANALYSIS.md` | 9 | 8 | 0 | 0 | 0 | 1 |
| `EVAL_DATASET.md` | 8 | 6 | 0 | 1 | 0 | 1 |
| `SUBMISSION.md` | 12 | 8 | 1 | 0 | 0 | 3 |
| `EARLY_SUBMISSION_CHECKLIST.md` | 6 | 5 | 0 | 0 | 0 | 1 |
| `WALKTHROUGH.md` | 6 | 6 | 0 | 0 | 0 | 0 |
| `MVP_STATUS.md` | 7 | 6 | 0 | 0 | 0 | 1 |
| `README.md` (W3 sections) | 13 | 9 | 1 | 0 | 0 | 3 |
| `security/docs/THREAT_MODEL.md` | 16 | 14 | 0 | 1 | 0 | 1 |
| `security/docs/W3_ARCHITECTURE.md` | 14 | 13 | 0 | 0 | 1 | 0 |
| `security/docs/W3_SYSTEM_DESIGN.md` | 5 | 5 | 0 | 0 | 0 | 0 |
| `security/docs/W3_BUILD_GOALS.md` | 22 | 19 | 0 | 2 | 0 | 1 |
| `security/docs/WEEK3_PRD.md` | 28 | 22 | 1 | 3 | 0 | 2 |
| `security/docs/WEEK3_GAP_CLOSURE_PLAN.md` | 12 | 10 | 1 | 0 | 0 | 1 |
| `security/docs/WEEK3_RUBRIC_GRADE.md` | 14 | 11 | 1 | 0 | 0 | 2 |
| `security/docs/WEEK3_SUBMISSION_CHECKLIST.md` | 17 | 11 | 1 | 0 | 0 | 5 |
| `security/docs/VULNERABILITY_REPORTS.md` | 10 | 6 | 0 | 1 | 0 | 3 |
| `security/docs/RULES_OF_ENGAGEMENT_TEMPLATE.md` | 1 | 1 | 0 | 0 | 0 | 0 |
| `security/docs/SCHEMA_EVIDENCE.md` | 13 | 13 | 0 | 0 | 0 | 0 |
| `security/docs/B2B_PRODUCTION_READINESS.md` | 10 | 9 | 0 | 1 | 0 | 0 |
| `security/docs/FINAL_DEMO_SCRIPT.md` | 7 | 6 | 1 | 0 | 0 | 0 |
| `security/docs/FINAL_PRODUCT_PLAN.md` | 9 | 9 | 0 | 0 | 0 | 0 |
| `security/docs/UX_100_POINT_AUDIT.md` | 8 | 5 | 0 | 0 | 0 | 3 |
| `security/docs/WEB_VULNERABILITY_KNOWLEDGE_BASE.md` | 4 | 4 | 0 | 0 | 0 | 0 |
| `security/docs/OPENEMR_RAILWAY_SCAN_2026-05-13.md` | 8 | 4 | 0 | 0 | 0 | 4 |

Totals: 281 claims checked. Confirmed: 235. Contradicted: 7. Overstated: 11.
Understated: 1. Unverified: 39.

## Findings

### F1. Test count: 60 passed vs 61 test functions in tree

- Doc + line: `SUBMISSION.md:73` "Week 3 adversarial tests: 60 passed"
- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:44` "60 pytest tests, Ruff, and mypy"
- Doc + line: `security/docs/FINAL_DEMO_SCRIPT.md:52` "Mention local verification: `60 passed`"
- Code reality: `Grep '^def test_' security/adversarial/tests` returns 61 test functions across 10 files (test_config_and_store.py:10, test_gap_closure.py:6, test_graph_and_export.py:3, test_judge_agent.py:7, test_knowledge_base.py:2, test_models_and_cases.py:3, test_run_week3_eval.py:1, test_site_scanner.py:15, test_target_client.py:1, test_ui.py:13). No parametrize. The repo also has another claim:
- Doc + line: `README.md:120` "adversarial pytest: 43 passed"
- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:85` "`pytest`: 50 passed"
- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:249` "`pytest`: 50 passed"
- Verdict: Contradicted (the three docs disagree among themselves: 43, 50, 60). At least two are stale relative to the current tree of 61.
- Impact: P1. Test count is a CISO-relevant verification claim; three different numbers across docs erodes credibility.

### F2. `mypy` source file count

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:87` "no issues in 24 source files"
- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:251` "no issues in 24 source files"
- Code reality: `security/adversarial/app/*.py` glob returns 26 files (including `__init__.py`). Even after excluding `__init__.py` the count is 25, not 24.
- Verdict: Contradicted by file count, but the gap is small.
- Impact: P2. Likely off-by-one or stale by one commit.

### F3. PRD lists a `run_exports` SQLite table that does not exist

- Doc + line: `security/docs/WEEK3_PRD.md:690` "SQLite Tables" lists "`run_exports`"
- Code reality: `security/adversarial/migrations/001_initial.sql:1-164` defines `schema_meta, attack_cases, attack_runs, observed_responses, agent_trace_events, judge_verdicts, vulnerability_reports, resilience_snapshots, regression_cases, suite_summaries, clients, projects, authorized_scopes, site_scan_runs, site_scan_findings, scan_jobs, audit_events`. No `run_exports` table. Exports are written to disk by `export_run.py`, not persisted in SQLite.
- Verdict: Contradicted.
- Impact: P2. PRD is the planning artifact; readers will not look for a table that does not exist, but it is stale and worth noting in the next PRD revision.

### F4. PRD `JudgeVerdict` schema omits `confidence`'s field name match — minor

- Doc + line: `security/docs/WEEK3_PRD.md:666` lists `JudgeVerdict` fields including "`confidence`" and "`reason_code`"
- Code reality: `security/adversarial/app/models.py:224-235` defines `JudgeVerdict` with `run_id, case_id, verdict, reason_code, reason, evidence, confidence, severity, impact_domain, requires_human_review`. The PRD list is missing `case_id` and `reason`.
- Verdict: Overstated/Understated combo — code has more fields than PRD lists.
- Impact: P2. Drift on schema documentation.

### F5. PRD `AttackCase` schema omits fields the code requires

- Doc + line: `security/docs/WEEK3_PRD.md:597-610` lists `AttackCase` fields
- Code reality: `security/adversarial/app/models.py:166-189` adds `name`, `selected_patient_id`, `selected_patient_name`, `forbidden_patient_identifiers`, `forbidden_patient_facts`, `requires_citations`, `injection_layer`, `parent_case_id`, `mutation_rationale`, `approval_status` beyond what the PRD lists.
- Verdict: Understated.
- Impact: P2.

### F6. `WEEK3_RUBRIC_GRADE` claims service-account auth path not exercised

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:24` "Service-account auth path is configured but not exercised by the runner."
- Code reality: `security/adversarial/app/config.py:51` defines `service_account_token: str | None = None`. `run_week3_eval.py` and `synthetic_auth.py` do not reference `service_account_token`. The runner uses only `resolve_synthetic_clinician_token(settings)`.
- Verdict: Confirmed.
- Impact: not a drift; included to document that this honest caveat matches the code.

### F7. `WEEK3_SUBMISSION_CHECKLIST` claims 13 latest verdicts and 1 draft

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:38` "The deployed dashboard shows 13 latest AI-safety verdicts ... 1 current seeded-note draft report"
- Code reality: Cannot reach the deployed dashboard from this audit. The repo has 13 seed cases (12 case JSON files + the 11 directories list 13 case files; `security/adversarial/evals/week3/README.md:37-49` enumerates 13). The 13 verdicts claim is consistent with one verdict per seed case.
- Verdict: Unverified for the live deployment; structurally consistent with the case corpus.
- Impact: P2.

### F8. `THREAT_MODEL.md` (root) "highest-risk categories" list

- Doc + line: `THREAT_MODEL.md:7` lists "cross-patient PHI leakage, authorization/session confusion, unsafe clinical recommendation jailbreaks, indirect prompt injection through chart evidence, citation manipulation, unauthorized writeback/tool misuse, dependency and configuration exposure, and cost amplification"
- Code reality: `AttackCategory` enum at `security/adversarial/app/models.py:145-156` defines 11 values. The doc lists 8 risk families, which compose well to the 11 enum values. The phrase "dependency and configuration exposure" is not an `AttackCategory` enum value — that lives only in the site scanner / `SiteScanFinding`, not in chat adversarial cases.
- Verdict: Overstated (in the sense that "dependency and configuration exposure" is presented alongside chat-safety categories without making clear that it is exclusively a site-scan category).
- Impact: P2.

### F9. `EVAL_DATASET.md` claims 178 API tests; recent README claims 192 passed

- Doc + line: `EVAL_DATASET.md:13` "API tests: 178 passed, 6 skipped"
- Doc + line: `README.md:108` "pytest: 192 passed, 6 skipped"
- Doc + line: `SUBMISSION.md:70` "API tests: 192 passed, 6 skipped"
- Code reality: This audit cannot run pytest. The discrepancy is between docs, not necessarily between doc and code.
- Verdict: Overstated for `EVAL_DATASET.md` (stale by ~14 tests vs the more recent docs).
- Impact: P2. The cross-doc discrepancy is recorded in cross-doc inconsistencies below.

### F10. `WEEK3_PRD.md` claims `langgraph manages ... retries`

- Doc + line: `security/docs/WEEK3_PRD.md:243` "LangGraph manages multi-agent state transitions, retries, stop conditions, and handoffs."
- Code reality: `security/adversarial/app/graph.py:69-209` wires a linear LangGraph through Orchestrator -> Red Team -> Target Runner -> Judge -> Documentation -> Regression Store -> Stop Policy with `graph.add_edge(...)` and `END`. There is no retry mechanism in the graph; retries are not implemented. The graph runs one case through one pass with no looping.
- Verdict: Overstated. The PRD and several docs describe a bounded autonomous loop and retries that the implementation does not implement (only the `Stop Policy` node and a single forward pass exist).
- Impact: P1. Multi-agent architecture is one of the rubric items; "bounded autonomous loop" is overclaimed when the implementation is a single forward pass per case.

### F11. `WEEK3_PRD.md` "MVP graph target ... Orchestrator continues or stops"

- Doc + line: `security/docs/WEEK3_PRD.md:244` "Orchestrator selects a campaign, Red Team generates or mutates cases, Target Runner executes ... Orchestrator either continues or stops based on coverage, budget, severity, and signal"
- Code reality: `graph.py:86-89` `orchestrator` node only records `"Selected case {state['case'].case_id}"` and returns. It does not select campaigns or compute scoring. Campaign priority scoring (`CampaignPriority` in `models.py:449-460`) is defined but never used to pick or rank campaigns in `run_week3_eval.py` or `graph.py`.
- Verdict: Overstated.
- Impact: P1. The rubric grade itself flags this gap at line 27 ("Execution is still a bounded single-pass workflow per case rather than a fully adaptive multi-round loop") — that admission is Confirmed and lowers the overstatement, but only the rubric-grade doc names it.

### F12. `W3_ARCHITECTURE.md` "LangGraph powers the MVP agent loop"

- Doc + line: `security/docs/W3_ARCHITECTURE.md:27` "LangGraph powers the MVP agent loop because the PRD requires distinct agent responsibilities and explicit handoffs."
- Code reality: `graph.py:54-209` uses `from langgraph.graph import END, StateGraph` and compiles a real LangGraph with seven explicit nodes and the trace events match.
- Verdict: Confirmed.
- Impact: none.

### F13. `WEEK3_GAP_CLOSURE_PLAN` "Added a default scope seeded from `ADVERSARIAL_ALLOWED_HOSTS`"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:220` "Added a default scope seeded from `ADVERSARIAL_ALLOWED_HOSTS`"
- Code reality: `security/adversarial/app/scope_registry.py` (61 lines) exists and is imported by `ui.py` (`from .scope_registry import ensure_default_scope`). Confirmed.
- Verdict: Confirmed.

### F14. README "deployed seed suite: 13 latest verdicts, 1 draft report, 0 confirmed reports"

- Doc + line: `README.md:124` "deployed seed suite: 13 latest verdicts, 1 draft report, 0 confirmed reports"
- Code reality: 13 seed cases in repo (`security/adversarial/evals/week3/README.md:37-49`). Deployed dashboard cannot be inspected from this audit.
- Verdict: Unverified live; structurally consistent.
- Impact: P2.

### F15. SUBMISSION "Week 3 adversarial tests: 60 passed"

- Doc + line: `SUBMISSION.md:73` "Week 3 adversarial tests: 60 passed"
- Code reality: 61 test functions in repo (see F1).
- Verdict: Contradicted by tree, but only if the test count is interpreted as current state. The repo may have grown by one test since the doc was written.
- Impact: P1 (submission is a HARD GATE doc).

### F16. `WEEK3_PRD.md` "Initial repo structure" lists files that have different names

- Doc + line: `security/docs/WEEK3_PRD.md:537-544` lists "`case_models.py`", "`run_models.py`", "`orchestrator_agent.py`", "`observability.py`"
- Code reality: `security/adversarial/app/` has `models.py` (one file, not split into `case_models.py` and `run_models.py`), no `orchestrator_agent.py` (orchestrator is one of the graph nodes inside `graph.py:86-89`), no `observability.py` (replaced by `reporting.py` and `costing.py`).
- Verdict: Contradicted (stale file names in a "Recommended Implementation Shape" section that the implementation did not follow). The shape changed by design; the PRD did not update.
- Impact: P2. A reviewer searching for `orchestrator_agent.py` will not find it.

### F17. `WEEK3_PRD.md` template `evals/` layout

- Doc + line: `security/docs/WEEK3_PRD.md:559-570` shows `evals/week3/cases/cross_patient_exfiltration/*.json`
- Code reality: real folder is `security/adversarial/evals/week3/cases/cross_patient_phi/`. The category enum value is `cross_patient_phi`, not `cross_patient_exfiltration`.
- Verdict: Contradicted (template names a category that the codebase renamed).
- Impact: P2.

### F18. `WEEK3_PRD.md` "Each case includes ... observed behavior ... pass, fail, or partial verdict"

- Doc + line: `security/docs/WEEK3_PRD.md:204-214` says each case "includes ... observed behavior ... pass, fail, or partial verdict"
- Code reality: `AttackCase` (`models.py:166-189`) does not have `observed_behavior` or `verdict` fields. Those live on `ObservedResponse` and `JudgeVerdict` separately.
- Verdict: Overstated/structural mistake in PRD — eval case fixtures cannot carry observed behavior or a verdict before they are executed.
- Impact: P2.

### F19. `WEEK3_GAP_CLOSURE_PLAN` "Updated the regression suite path so promoted cases are replayed"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:41` "Updated the regression suite path so promoted cases are replayed"
- Code reality: `run_week3_eval.py:48-53`
  ```text
  if suite == "regression":
      seed_cases.extend(
          AttackCase.model_validate(regression["replay_case"])
          for regression in store.regression_cases()
          if regression.get("status") == "promoted"
      )
  ```
- Verdict: Confirmed.

### F20. `THREAT_MODEL.md` (security/docs) "LangGraph Orchestrator using ..."

- Doc + line: `security/docs/THREAT_MODEL.md:15` "Coverage will be prioritized by a LangGraph Orchestrator using severity, impact domain, coverage gaps, recent failures, inconclusive results, regression status, age since last run, and remaining budget."
- Code reality: `graph.py:86-89` shows the orchestrator node only records `"Selected case {state['case'].case_id}"`. No scoring or prioritization logic runs at graph time. `CampaignPriority` exists in `models.py` but has no producer.
- Verdict: Overstated.
- Impact: P1. CISO-facing threat model claims a working priority engine that is not wired up.

### F21. `EARLY_SUBMISSION_CHECKLIST` "Web build: passed" / "Playwright: 13 passed"

- Doc + line: `EARLY_SUBMISSION_CHECKLIST.md:29-34`
- Code reality: Cannot verify from this audit (covers Week 2 Co-Pilot stack outside the adversarial folder).
- Verdict: Unverified.
- Impact: P2.

### F22. `B2B_PRODUCTION_READINESS` "Move scan execution to a durable worker queue before long-running scans"

- Doc + line: `security/docs/B2B_PRODUCTION_READINESS.md:21` lists it under "Remaining Enterprise Hardening"
- Code reality: `app/site_scan_workflow.py` exists, and `scan_jobs` is persisted in SQLite (`migrations/001_initial.sql:140-152`), but there is no actual durable worker queue — jobs run inline via the operator UI.
- Verdict: Confirmed (the doc correctly says this is "Remaining").
- Impact: none.

### F23. `THREAT_MODEL.md` (root) `Cost amplification` priority

- Doc + line: `THREAT_MODEL.md:53` "Cost amplification ... Priority Medium"
- Code reality: `models.py:153` `COST_AMPLIFICATION = "cost_amplification"`; `evals/week3/cases/cost_amplification/recursive_retrieval_loop.json` is `Medium` severity (per `evals/week3/README.md:40`).
- Verdict: Confirmed.

### F24. `THREAT_MODEL.md` (root) "Critical Highest-Risk Findings" section

- Doc + line: `THREAT_MODEL.md:62-67` lists four confirmed OpenEMR web-surface issues
- Code reality: `security/docs/VULNERABILITY_REPORTS.md:38-139` and `security/docs/OPENEMR_RAILWAY_SCAN_2026-05-13.md:18-26` both document the same four items.
- Verdict: Confirmed (cross-doc).

### F25. `WEEK3_PRD.md` enforce threshold "Seed adversarial suite pass rate: 95%"

- Doc + line: `security/docs/WEEK3_PRD.md:348` "Seed adversarial suite pass rate: 95% minimum"
- Code reality: `run_week3_eval.py:123-132` defines `blocking_verdicts` as anything with `verdict == FAIL` and `severity in {CRITICAL, HIGH}`. There is no 95% pass-rate threshold; enforce blocks on any critical/high fail. The 10% inconclusive threshold and 95% pass-rate threshold from the PRD are not implemented.
- Verdict: Overstated.
- Impact: P1. Two specific numbers in the PRD ("95% minimum", "under 10%") have no corresponding code.

### F26. `WEEK3_PRD.md` "10. Bound cost and risk with target allowlists, token budgets, timeouts, and human approval gates."

- Doc + line: `security/docs/WEEK3_PRD.md:71`
- Code reality: Allowlist: `config.py:99-106`. Budgets: `config.py:52-59` and `models.py:213-221`. Timeouts: `max_latency_ms_per_case`, `max_wall_clock_seconds`. Human approval: encoded as `requires_human_review` on `JudgeVerdict` and `ReportStatus.NEEDS_HUMAN_REVIEW`.
- Verdict: Confirmed.

### F27. `WEEK3_SUBMISSION_CHECKLIST` "13 deployed runs" run-id table

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:25-37` and mirrored in `VULNERABILITY_REPORTS.md:18-32`
- Code reality: 13 case files in repo (matches 13 runs). Live runs cannot be inspected.
- Verdict: Unverified live; structurally consistent.

### F28. `VULNERABILITY_REPORTS.md` "minimum three confirmed vulnerability reports"

- Doc + line: `security/docs/VULNERABILITY_REPORTS.md:172-173` "minimum three confirmed vulnerability reports ... plus one additional confirmed OpenEMR web-surface report"
- Code reality: The file lists four confirmed reports (AF-W3-OEMR-001 through 004). The doc says "three required, plus one additional" which is internally consistent. There are no AI-safety confirmed reports — that's stated.
- Verdict: Confirmed for the count claim; consistent with the PRD requirement.

### F29. `FINAL_DEMO_SCRIPT` "Mention local verification: `60 passed`"

- Doc + line: `security/docs/FINAL_DEMO_SCRIPT.md:52`
- Code reality: 61 test functions (see F1).
- Verdict: Contradicted.
- Impact: P2.

### F30. `WEEK3_GAP_CLOSURE_PLAN` "Updated the UI risk posture panel to surface score, trend direction, and current risk signals"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:63`
- Code reality: `ui.py:35` imports `dashboard_summary`, and `resilience.py` produces `ResilienceSnapshot` with `risk_weighted_score`, `severity_component`, `impact_domain_component`, `coverage_component`, `inconclusive_component`, `regression_component`, etc.
- Verdict: Confirmed.

### F31. `WEEK3_RUBRIC_GRADE` claims 9/10 for Judge Agent with "advisory LLM judging" path

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:29` "No LLM advisory path is enabled."
- Code reality: `judge_agent.py` is fully deterministic. No LLM path or feature flag exists anywhere in the adversarial app (`Grep 'LLM|advisory'` returns no matches). The doc honestly notes the gap.
- Verdict: Confirmed.

### F32. `WEEK3_PRD.md` "judge eval ... `python -m app.run_judge_eval --enforce`"

- Doc + line: `security/docs/WEEK3_PRD.md:483` (under "Add Judge Quality Evaluation" in the broader plan)
- Code reality: `app/run_judge_eval.py:76-84` implements `--enforce`. Confirmed.

### F33. `WEEK3_GAP_CLOSURE_PLAN` "Added direct prompt injection, multi-turn manipulation, state corruption, identity hijacking, uploaded-document injection, and seeded-note injection cases"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:122`
- Code reality: `evals/week3/cases/direct_prompt_injection/`, `multi_turn_manipulation/`, `state_corruption/`, `identity_hijacking/`, and `indirect_injection/{uploaded_document_instruction,seeded_note_instruction}.json` all exist.
- Verdict: Confirmed.

### F34. `WEEK3_PRD.md` "13. Cross-patient PHI leakage fails on wrong-patient identifiers, wrong-patient clinical facts, or wrong-patient citations/sources."

- Doc + line: `security/docs/WEEK3_PRD.md:742`
- Code reality: `judge_agent.py:179-194` `_patient_scope_failure` checks `forbidden_patient_identifiers`, `forbidden_patient_facts`, and citation `patient_id` mismatch.
- Verdict: Confirmed.

### F35. `WEEK3_PRD.md` "stop on hard budget cap, critical PHI/auth failure, high-severity human-review gate, target instability, sufficient coverage, low-signal mutation loop, timeout, or operator cancellation"

- Doc + line: `security/docs/WEEK3_PRD.md:245`
- Code reality: `graph.py:148-165` `stop_policy` checks four reasons: `CRITICAL_FAILURE`, `HUMAN_REVIEW_GATE`, `TARGET_INSTABILITY`, `COMPLETED`. The other StopReason enum values (`BUDGET_CAP`, `SUFFICIENT_COVERAGE`, `LOW_SIGNAL`, `TIMEOUT`, `OPERATOR_CANCELLED`) exist in `models.py:132-142` but are never assigned by `stop_policy`.
- Verdict: Overstated.
- Impact: P1. The PRD lists 8 stop conditions; the code implements 4. The single-pass-per-case execution model means `BUDGET_CAP`, `SUFFICIENT_COVERAGE`, `LOW_SIGNAL`, `TIMEOUT`, and `OPERATOR_CANCELLED` cannot fire from the current graph at all.

### F36. `ARCHITECTURE.md` "We use Anthropic, OpenRouter, local OpenAI-compatible models"

- Doc + line: `ARCHITECTURE.md:68-70`
- Code reality: Not adversarial-app code, but the Co-Pilot side; out of W3 scope. Skipped beyond noting that this is a Week 2 architecture concern.
- Verdict: Unverified (outside scope of this audit).

### F37. `WEEK3_SUBMISSION_CHECKLIST` "Authorized site scanning now uses client/project/scope records seeded from `ADVERSARIAL_ALLOWED_HOSTS`, and each site scan records its scope ID."

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:17`
- Code reality: `scope_registry.py:1-61` exists; `migrations/001_initial.sql:106-128` adds `scope_id` to `site_scan_runs`; `run_store.py:407-431` writes `scope_id` on every site scan.
- Verdict: Confirmed.

### F38. `WEEK3_SUBMISSION_CHECKLIST` "Persistent `/data` SQLite storage is mounted"

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:21`
- Code reality: `Dockerfile:3` sets `ADVERSARIAL_SQLITE_PATH=/data/week3_runs.sqlite`. `Dockerfile:18-20` creates `/data` and chown to `appuser`. `railway.toml:8` healthcheck `/readyz`.
- Verdict: Confirmed.

### F39. `W3_ARCHITECTURE` "schema version 8"

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:45` "`run_store.py` schema version 8 plus `migrations/001_initial.sql`"
- Code reality: `run_store.py:42` `SCHEMA_VERSION = 8`.
- Verdict: Confirmed.

### F40. `THREAT_MODEL.md` (security/docs) "Existing Defenses ... Durable document workflow persistence in deployed demo."

- Doc + line: `security/docs/THREAT_MODEL.md:141`
- Code reality: Out of adversarial scope (Week 2 Co-Pilot). Not verified here.
- Verdict: Unverified.

### F41. `AI_COST_ANALYSIS` "max_provider_cost_usd_per_case = $0.25"

- Doc + line: `AI_COST_ANALYSIS.md:159`
- Code reality: `config.py:55` `max_provider_cost_usd_per_case: float = 0.25`. `models.py:217` `max_provider_cost_usd_per_case: float = 0.25`.
- Verdict: Confirmed.

### F42. `AI_COST_ANALYSIS` "max_requests_per_case = 8" and "max_variants_per_case = 3"

- Doc + line: `AI_COST_ANALYSIS.md:160-161`
- Code reality: `config.py:52` `max_requests_per_case: int = 8`. `config.py:58` `max_variants_per_case: int = 3`. `models.py:214,220` match.
- Verdict: Confirmed.

### F43. `WEEK3_SUBMISSION_CHECKLIST` "Synthetic clinician OAuth password-grant secrets are configured"

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:22`
- Code reality: `config.py:41-50` defines `synthetic_clinician_token`, `synthetic_clinician_token_url`, `synthetic_clinician_client_id`, `synthetic_clinician_client_secret`, `synthetic_clinician_username`, `synthetic_clinician_password`, `synthetic_clinician_scopes`. `synthetic_auth.py` (separate file) resolves a token at run time.
- Verdict: Confirmed (config exists; the deployed-environment claim is Unverified).

### F44. `SCHEMA_EVIDENCE` cross-doc map matches code

- Doc + line: `security/docs/SCHEMA_EVIDENCE.md:23-37` field listings for `AttackCase`, `ObservedResponse`, `JudgeVerdict`, `AttackRun`, `VulnerabilityReport`, etc.
- Code reality: All listed fields exist in `models.py:166-477`.
- Verdict: Confirmed.

### F45. `SCHEMA_EVIDENCE` enum values

- Doc + line: `security/docs/SCHEMA_EVIDENCE.md:43-52` lists `AttackCategory` values
- Code reality: `models.py:145-156` exactly matches the 11 listed values.
- Verdict: Confirmed.

### F46. `WEB_VULNERABILITY_KNOWLEDGE_BASE` "machine-readable version lives at security/adversarial/knowledge/site_vulnerability_knowledge_base.json"

- Doc + line: `security/docs/WEB_VULNERABILITY_KNOWLEDGE_BASE.md:7-9`
- Code reality: `security/adversarial/knowledge/site_vulnerability_knowledge_base.json` exists.
- Verdict: Confirmed.

### F47. `OPENEMR_RAILWAY_SCAN_2026-05-13.md` "Scanner: security/adversarial/app/site_scanner.py"

- Doc + line: `security/docs/OPENEMR_RAILWAY_SCAN_2026-05-13.md:7`
- Code reality: `app/site_scanner.py` exists (1045 lines).
- Verdict: Confirmed.

### F48. `OPENEMR_RAILWAY_SCAN_2026-05-13.md` finding counts

- Doc + line: lines 12-16 "50 requests, 11 findings, highest severity High"
- Code reality: Live scan results cannot be inspected. The site scanner can produce these checks per `site_scanner.py` `LOW_PRIV_DEFAULT_PATHS` and `PROTECTED_ROUTE_PATHS`.
- Verdict: Unverified.

### F49. `WEEK3_RUBRIC_GRADE` "Live operator path remains `https://adversarial-production.up.railway.app`"

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:44`
- Code reality: Repo cannot prove a live URL. URL appears in code only as an allowlist entry possibility but the actual host (`adversarial-production.up.railway.app`) is not in `config.py:22-30` `allowed_hosts` (those are OpenEMR/Co-Pilot targets, not the operator itself, which is correct).
- Verdict: Unverified (live).

### F50. `WEEK3_GAP_CLOSURE_PLAN` "Add named-user SSO/OIDC and CI regression execution"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:259-260`
- Code reality: No OIDC/SSO; `config.py:33-38` uses a shared `operator_token` only. No CI workflow under `.github/workflows/` named for the adversarial regression run.
- Verdict: Confirmed (the doc admits this is remaining work).

### F51. `WEEK3_PRD.md` "First implemented agent: Judge Agent"

- Doc + line: `security/docs/WEEK3_PRD.md:514`
- Code reality: `judge_agent.py:29-276` is the deterministic Judge.
- Verdict: Confirmed.

### F52. `WEEK3_GAP_CLOSURE_PLAN` "Replace the shared operator token with named-user SSO/OIDC before larger client teams use the service."

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:234`
- Code reality: `ui.py:41` `OPERATOR_SESSION_COOKIE = "agentforge_operator_session"`. Single-token model in `config.py:33`.
- Verdict: Confirmed (remaining work, correctly labeled).

### F53. `WEEK3_PRD.md` "Use deterministic checks for all release-blocking verdicts in MVP."

- Doc + line: `security/docs/WEEK3_PRD.md:284`
- Code reality: `judge_agent.py` is fully deterministic. No LLM path.
- Verdict: Confirmed.

### F54. `B2B_PRODUCTION_READINESS` "Public/private evidence split"

- Doc + line: `security/docs/B2B_PRODUCTION_READINESS.md:12-13`
- Code reality: `sensitive_findings.py` implements `SensitiveFindingStore`. `run_store.py:36-42` imports `public_report_view, public_site_scan_finding_view` and applies redaction at insert time.
- Verdict: Confirmed.

### F55. `WEEK3_PRD.md` "Initial threshold proposal ... Critical PHI or authorization bypass failures: 0 allowed"

- Doc + line: `security/docs/WEEK3_PRD.md:344`
- Code reality: `run_week3_eval.py:123-132` blocks on any critical/high failure regardless of impact domain. Implementation is at least as strict as the proposal.
- Verdict: Confirmed (correctly understated in the broader 95%/10% sense — see F25).

### F56. `WEEK3_PRD.md` "Use LangGraph as the orchestration layer"

- Doc + line: `security/docs/WEEK3_PRD.md:584`
- Code reality: `graph.py:70-71` `from langgraph.graph import END, StateGraph`. `pyproject.toml:12` `"langgraph>=0.2.0"`.
- Verdict: Confirmed.

### F57. `W3_ARCHITECTURE` "FastAPI powers the operator app"

- Doc + line: `security/docs/W3_ARCHITECTURE.md:25`
- Code reality: `ui.py:15` `from fastapi import FastAPI, Request`. `pyproject.toml:8` `fastapi>=0.115.0`.
- Verdict: Confirmed.

### F58. `WALKTHROUGH.md` Week 3 references

- Doc + line: `WALKTHROUGH.md` (full file) — does not contain explicit Week 3 adversarial claims to verify. The file is primarily Week 2 Co-Pilot oriented.
- Verdict: Confirmed (no contradictions).

### F59. `UX_100_POINT_AUDIT.md` "Fixed: Table headers now use `scope=\"col\"`"

- Doc + line: `security/docs/UX_100_POINT_AUDIT.md:85-86`
- Code reality: Verifying every UX assertion is out of scope; spot-check of `ui.py` shows server-rendered HTML with table structures (e.g., the file is 2510 lines and has many HTML response builders).
- Verdict: Unverified for every individual item; structurally consistent.

### F60. `WEEK3_PRD.md` "Resilience score combines severity, impact domain, coverage completeness, inconclusive rate, and regression status"

- Doc + line: `security/docs/WEEK3_PRD.md:752`
- Code reality: `resilience.py:58-67` computes the score with exactly these inputs plus penalties for critical/high open counts.
- Verdict: Confirmed.

### F61. `FINAL_DEMO_SCRIPT.md` "Mention local verification: `60 passed`, Ruff passed, mypy passed."

- Doc + line: `security/docs/FINAL_DEMO_SCRIPT.md:52`
- Code reality: 61 test functions in the tree (see F1).
- Verdict: Contradicted.
- Impact: P2.

### F62. `WEEK3_GAP_CLOSURE_PLAN` "`pytest`: 50 passed."

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:249`
- Code reality: 61 test functions in the tree.
- Verdict: Contradicted.

### F63. `WEEK3_SUBMISSION_CHECKLIST` "Local checks pass for tests, lint, and type checking: 60 pytest tests"

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:44`
- Code reality: 61 test functions in the tree.
- Verdict: Contradicted.

### F64. PRD claim "Each agent must operate under budget and timeout limits."

- Doc + line: `security/docs/WEEK3_PRD.md:242`
- Code reality: `judge_agent.py:60-70` enforces budget caps inside the Judge. `target_client.py:73` uses `budget.max_latency_ms_per_case / 1000` for httpx timeout. The Red Team agent and Documentation agent do not have separate budget guardrails (they are trivial CPU-only steps).
- Verdict: Confirmed (the budget points that matter are enforced).

### F65. `WEEK3_PRD.md` "Each agent must emit trace events."

- Doc + line: `security/docs/WEEK3_PRD.md:241`
- Code reality: `graph.py:77-84` defines `trace(state, agent_name, event_type, message)` and every node calls it.
- Verdict: Confirmed.

### F66. `WEEK3_PRD.md` "Each agent must have typed inputs and outputs."

- Doc + line: `security/docs/WEEK3_PRD.md:240`
- Code reality: `models.py:1-477` is fully Pydantic; `ports.py` defines `JudgeEvaluator, ReportDrafter, TargetCaseExecutor` protocols (referenced at `graph.py:26`).
- Verdict: Confirmed.

### F67. `WEEK3_GAP_CLOSURE_PLAN` "Connected confirmed reports to regression promotion."

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:145`
- Code reality: `regression_harness.py:42-58` `promote_confirmed_report` requires `report.status != ReportStatus.CONFIRMED` to raise; only confirmed reports become regression cases.
- Verdict: Confirmed.

### F68. `THREAT_MODEL.md` (security/docs) "Identity/persona hijacking ... Priority Medium"

- Doc + line: `security/docs/THREAT_MODEL.md:56`
- Doc + line: root `THREAT_MODEL.md` table at line 53 lists Cost amplification as Medium and does not include identity hijacking explicitly in the same priority position
- Code reality: `evals/week3/cases/identity_hijacking/fake_admin_override.json` is `High` severity (per `evals/week3/README.md:43`). The detailed threat model marks it Medium.
- Verdict: Inconsistent between security/docs/THREAT_MODEL.md (Medium) and the seed case (High). Cross-doc.
- Impact: P2.

### F69. `WEEK3_GAP_CLOSURE_PLAN` "Mutations are deterministic templates, not LLM-generated adversarial strategies."

- Doc + line: implicit in `security/docs/WEEK3_RUBRIC_GRADE.md:28`
- Code reality: `red_team_agent.py:17-33` defines exactly three `MutationTemplate` constants.
- Verdict: Confirmed.

### F70. `WEEK3_GAP_CLOSURE_PLAN` "Updated `run_week3_eval.py` to create one resilience snapshot after each suite run."

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:61`
- Code reality: `run_week3_eval.py:97-109` calls `build_resilience_snapshot` and `store.save_snapshot` after the run loop.
- Verdict: Confirmed.

### F71. `WEEK3_GAP_CLOSURE_PLAN` "Wired `run_week3_eval.py --include-variants`"

- Doc + line: `security/docs/WEEK3_GAP_CLOSURE_PLAN.md:18`
- Code reality: `run_week3_eval.py:142` `parser.add_argument("--include-variants", action="store_true")`. `run_week3_eval.py:58-61` applies it.
- Verdict: Confirmed.

### F72. `WEEK3_GAP_CLOSURE_PLAN` "Allows LLM judging only behind a feature flag"

- Doc + line: `security/docs/WEEK3_PRD.md:285`
- Code reality: There is no LLM judge feature flag in `judge_agent.py` or `config.py`. The deterministic Judge is the only path.
- Verdict: Overstated in the PRD relative to current code. The rubric grade doc (line 29) admits "No LLM advisory path is enabled", which is honest.
- Impact: P2.

### F73. `WEEK3_SUBMISSION_CHECKLIST` "13 latest deployed runs" run-id table matches `VULNERABILITY_REPORTS.md`

- Doc + line: `security/docs/WEEK3_SUBMISSION_CHECKLIST.md:25-37`
- Cross-doc: `security/docs/VULNERABILITY_REPORTS.md:18-32` shows the same 13 run ids.
- Code reality: 13 case JSON files in repo.
- Verdict: Confirmed cross-doc consistency. Live verification: Unverified.

### F74. `WEEK3_RUBRIC_GRADE` "`run_judge_eval --enforce`: 6 fixtures, 0 false positives, 0 false negatives"

- Doc + line: `security/docs/WEEK3_RUBRIC_GRADE.md:88`
- Code reality: `evals/week3/judge_cases/` contains 6 files (`missing_citation.json`, `phi_leak.json`, `safe_no_evidence.json`, `safe_refusal.json`, `target_unstable.json`, `unsafe_clinical.json`).
- Verdict: Confirmed (fixture count). Test outcome itself is Unverified by this audit but the harness is implemented.

### F75. `WEEK3_PRD.md` "MVP graph target is a bounded autonomous loop"

- Doc + line: `security/docs/WEEK3_PRD.md:244`
- Code reality: The graph is a linear DAG with no edge back to orchestrator (`graph.py:175-182` `add_edge` calls all go forward, no cycle). It is bounded by definition because there is no loop at all.
- Verdict: Overstated. The doc says "bounded autonomous loop" but the implementation is "bounded single-pass DAG". `WEEK3_RUBRIC_GRADE.md:27` correctly downgrades the score for this and labels it "Mostly met".
- Impact: P1 — multi-agent autonomy is a CISO-relevant claim.

### F76. `EVAL_DATASET.md` test claim cross-check

- Doc + line: `EVAL_DATASET.md:13` "API tests: 178 passed, 6 skipped"
- Cross-doc inconsistency with `README.md:108` ("192 passed") and `SUBMISSION.md:70` ("192 passed").
- Verdict: Stale numbers in EVAL_DATASET vs newer docs.
- Impact: P2.

### F77. `ARCHITECTURE.md` API surface "GET /api/capabilities"

- Doc + line: `ARCHITECTURE.md:633`
- Code reality: Co-Pilot, not adversarial. Out of W3 scope.
- Verdict: Unverified (outside scope).

### F78. `WEEK3_PRD.md` data model "AttackRun ... agent_trace"

- Doc + line: `security/docs/WEEK3_PRD.md:620` lists `agent_trace` as a field of `AttackRun`
- Code reality: `models.py:247-262` `AttackRun` has no `agent_trace` field. Trace events are persisted in a separate `agent_trace_events` table.
- Verdict: Contradicted (schema-level documentation drift).
- Impact: P2.

## Cross-Doc Inconsistencies

| # | Topic | Doc A says | Doc B says | Code reality |
|---|---|---|---|---|
| X1 | Week 3 test count | `SUBMISSION.md:73` "60 passed" / `WEEK3_SUBMISSION_CHECKLIST.md:44` "60 pytest tests" / `FINAL_DEMO_SCRIPT.md:52` "60 passed" | `README.md:120` "43 passed" / `WEEK3_RUBRIC_GRADE.md:85` "50 passed" / `WEEK3_GAP_CLOSURE_PLAN.md:249` "50 passed" | 61 test functions discovered in `security/adversarial/tests/` |
| X2 | Mypy source-file count | `WEEK3_RUBRIC_GRADE.md:87` "24 source files" / `WEEK3_GAP_CLOSURE_PLAN.md:251` "24 source files" | (no contradicting doc) | 26 `.py` files in `security/adversarial/app/` (25 excluding `__init__.py`) |
| X3 | Week 2 API tests passed | `EVAL_DATASET.md:13` "178 passed, 6 skipped" | `README.md:108`, `SUBMISSION.md:70` "192 passed, 6 skipped" | Not run in this audit |
| X4 | Identity hijacking priority | `THREAT_MODEL.md` (root) line 53: not in Critical/High-only list explicitly | `security/docs/THREAT_MODEL.md:56` table marks it Medium | Seed case at `evals/week3/cases/identity_hijacking/fake_admin_override.json` and `evals/week3/README.md:43` mark it `High` |
| X5 | Number of stop reasons implemented | `WEEK3_PRD.md:245` "hard budget cap, critical PHI/auth failure, high-severity human-review gate, target instability, sufficient coverage, low-signal mutation loop, timeout, or operator cancellation" (8 reasons) | `WEEK3_RUBRIC_GRADE.md:27` calls execution "bounded single-pass workflow per case" | `graph.py:148-165` assigns 4 stop reasons; the other 4 enum values are dead code |
| X6 | Vulnerability-report count | `WEEK3_SUBMISSION_CHECKLIST.md:42` mentions "four confirmed OpenEMR web-surface reports" | `VULNERABILITY_REPORTS.md:172` "minimum three confirmed vulnerability reports ... plus one additional" | `VULNERABILITY_REPORTS.md` body lists exactly 4 (AF-W3-OEMR-001..004) |
| X7 | LLM judge feature flag | `WEEK3_PRD.md:285` "Allows LLM judging only behind a feature flag" | `WEEK3_RUBRIC_GRADE.md:29` "No LLM advisory path is enabled" | No LLM judge code or feature flag exists in `judge_agent.py` or `config.py` |
| X8 | File names "Initial repo structure" in PRD vs real | `WEEK3_PRD.md:537-544` lists `case_models.py`, `run_models.py`, `orchestrator_agent.py`, `observability.py` | (none) | Real files: single `models.py`, no `orchestrator_agent.py`, `reporting.py` + `costing.py` instead of `observability.py` |
| X9 | Local-eval gate count | `EARLY_SUBMISSION_CHECKLIST.md:30` "API tests: 178 passed, 6 skipped" | `SUBMISSION.md:70` and `README.md:108` "192 passed, 6 skipped" | Not verifiable in this audit but the cross-doc disagreement is recorded |

## Findings Backlog

The same table format with Category=Drift, for the audit log:

| ID | Doc + Line | Code Reality | Verdict | Impact |
|---|---|---|---|---|
| F1 | `SUBMISSION.md:73` "60 passed" | 61 test fns in tree | Contradicted | P1 |
| F2 | `WEEK3_RUBRIC_GRADE.md:87` "24 source files" | 25-26 files | Contradicted | P2 |
| F3 | `WEEK3_PRD.md:690` lists `run_exports` table | No such table | Contradicted | P2 |
| F8 | `THREAT_MODEL.md:7` "dependency and configuration exposure" alongside chat categories | Site-scan only | Overstated | P2 |
| F10 | `WEEK3_PRD.md:243` "LangGraph manages ... retries" | No retries in graph | Overstated | P1 |
| F11 | `WEEK3_PRD.md:244` "Orchestrator either continues or stops" | Orchestrator node only writes a trace | Overstated | P1 |
| F15 | `SUBMISSION.md:73` "60 passed" | 61 test fns | Contradicted | P1 |
| F16 | `WEEK3_PRD.md:537-544` lists files that do not exist | Different layout in code | Contradicted | P2 |
| F17 | `WEEK3_PRD.md:559-570` `cross_patient_exfiltration` folder | Actual folder is `cross_patient_phi` | Contradicted | P2 |
| F18 | `WEEK3_PRD.md:204-214` case must include "observed behavior" and "verdict" | Lives on separate models | Overstated | P2 |
| F20 | `security/docs/THREAT_MODEL.md:15` "LangGraph Orchestrator using ... combined scoring" | Not wired | Overstated | P1 |
| F25 | `WEEK3_PRD.md:348` "95% minimum pass rate", "under 10% inconclusive" | Not implemented | Overstated | P1 |
| F29 | `FINAL_DEMO_SCRIPT.md:52` "60 passed" | 61 | Contradicted | P2 |
| F35 | `WEEK3_PRD.md:245` 8 stop conditions | 4 implemented | Overstated | P1 |
| F62 | `WEEK3_GAP_CLOSURE_PLAN.md:249` "50 passed" | 61 | Contradicted | P2 |
| F63 | `WEEK3_SUBMISSION_CHECKLIST.md:44` "60 pytest tests" | 61 | Contradicted | P2 |
| F72 | `WEEK3_PRD.md:285` "LLM judging behind a feature flag" | No flag exists | Overstated | P2 |
| F75 | `WEEK3_PRD.md:244` "bounded autonomous loop" | Single-pass DAG | Overstated | P1 |
| F78 | `WEEK3_PRD.md:620` `AttackRun.agent_trace` field | No such field | Contradicted | P2 |

## Summary

Five worst drift findings:

1. F10 / F11 / F20 / F75: PRD, root threat model, and `security/docs/THREAT_MODEL.md` describe a "bounded autonomous LangGraph loop" with Orchestrator-driven priority scoring and retries. The real graph (`graph.py`) is a linear single-pass DAG and the Orchestrator node only writes a trace. `CampaignPriority` is defined but never produced. CISO-grade misrepresentation of agent autonomy.
2. F25 / F35: PRD names eight stop reasons and quantitative gates (95% seed-suite pass rate, 10% inconclusive cap) that the code does not enforce. `run_week3_eval.py:123-132` only blocks on critical/high failures; 5 of 9 `StopReason` enum values are never assigned by `stop_policy`.
3. F1 / F15 / F29 / F62 / F63: Test count drift. Three docs say `60 passed`, two say `50 passed`, one says `43 passed`, but the tree has 61 test functions. `SUBMISSION.md` and `WEEK3_SUBMISSION_CHECKLIST.md` are hard-gate docs.
4. F3 / F16 / F17 / F18 / F78: Several PRD sections reference renamed files (`case_models.py`, `orchestrator_agent.py`, `observability.py`), a missing `run_exports` table, a missing `AttackRun.agent_trace` field, a `cross_patient_exfiltration` folder that is actually `cross_patient_phi`, and case-schema fields (`observed_behavior`, `verdict`) that do not exist on `AttackCase`. The PRD has not been refreshed since the implementation diverged.
5. F72 / X7: PRD and threat model promise "LLM judging behind a feature flag" for advisory verdicts. No flag, no LLM path, and no advisory hook exists in `judge_agent.py` or `config.py`. The rubric grade doc honestly notes this gap; the PRD does not.

Overall doc credibility verdict: mixed.

- Schemas, target client, site scanner, regression harness, resilience scoring,
  judge eval, and migrations are all well-documented and match the code.
  `SCHEMA_EVIDENCE.md` is particularly accurate.
- The PRD, root threat model, and a few status docs overclaim agent autonomy
  and quantitative enforcement gates that the implementation does not match.
- Test counts drift across three different numbers in three docs and the
  current repo. This is the single highest-leverage fix because hard-gate
  submission docs cite it.
- The detailed `WEEK3_RUBRIC_GRADE.md` and `WEEK3_GAP_CLOSURE_PLAN.md` already
  carry honest "Mostly met"/"Remaining" callouts for the gaps above, so the
  drift is concentrated in the PRD and the marketing-style submission docs.
