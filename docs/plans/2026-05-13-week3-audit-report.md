# Week 3 Adversarial Platform — Full-Spectrum Audit Report

**Date:** 2026-05-13
**Auditor:** Claude Opus 4.7, orchestrating four parallel specialist subagents (Rubric, CISO, Code Quality, Doc Drift) and one sequential Skeptic.
**Method:** See [audit design](2026-05-13-week3-audit-design.md). All findings cite `file:line` with quotes of 15 words or fewer. Severity/promotions applied per [skeptic review](2026-05-13-week3-audit-skeptic-review.md).
**Final deadline:** Friday 2026-05-15 at noon — ~40 hours remaining at time of writing.

---

## 1. Executive Summary

The platform's *architecture* is genuinely defensible: deterministic judge, allowlisted targets, private/public report split, scope-checked egress, distinct agent classes for Red Team / Judge / Documentation. A hospital CISO reading the code would say "this person understands the trust model." Skeptic confirms 91% of audit findings reproduce at the cited file:line.

What blocks an unconditional pass is a small number of **production-discipline holes, hard-gate document mismatches, and a four-auditor-converging architectural overclaim** that all need closing before Friday noon.

### Top 5 findings (ordered by rubric-points-per-hour)

| # | ID | Severity | What | Hours | Pts/hr |
|---|---|---|---|---:|---:|
| 1 | **F-TESTS** | P0 (cluster) | Test count drifts across 5 submission-grade docs: `SUBMISSION.md` says 60, `WEEK3_RUBRIC_GRADE.md` says 50, `README.md` says 43, tree has 61. Reconcile to actual `pytest` output. | 0.5 | 10 |
| 2 | **R-014** | P1 → P1 (kept) | `SUBMISSION.md:47` demo-video link is the placeholder text "Captured; paste the uploaded video link". Replace with real URL. | 0.5 | 10 |
| 3 | **CISO-01** | **P0 demo-blocker** | `ui.py:875-877` returns `True` for every auth check when `ADVERSARIAL_OPERATOR_TOKEN` is unset. Verify the Railway env sets it, then add a refuse-to-start guard. | 2.5 | 8 |
| 4 | **R-001** | P0 | Root `ARCHITECTURE.md` describes the Clinical Co-Pilot, not the adversarial platform — PRD-named file does not contain Red Team / Judge / Orchestrator / Documentation Agent definitions or a diagram. | 3 | 3 |
| 5 | **P0-A** (merged) | P0 | Linear pipeline + stub orchestrator: `graph.py:86-88` is `trace(); return state`; `graph.py:175-182` is seven linear `add_edge` calls; no Judge→RedTeam feedback edge; `CampaignPriority` model defined but never produced. Four auditors converged on this. The pragmatic Friday-noon fix is to **realign the docs and add a minimal coverage-gap-driven case selector**, not to rebuild the loop from scratch. | 4–8 | 1.5–2.5 |

### Rubric-points-at-risk

- 3 hard-gate Fails / 4 hard-gate Partials in rubric audit
- Drift erodes credibility on top of the scored gaps (3 different test counts in submission docs)
- Estimated total rubric points at risk: **~30–45 of 100** if no fixes are applied; **~5–10** if the recommended Friday-noon plan is executed.

### CISO verdict

**Conditional go.** Architecture is right; production discipline has holes. ~11 hours of focused work on CISO-01/02/03 closes the blockers; CISO-04/05 ("fix validation provenance" and "no target version pin on replay") are credibility issues that shape a contract negotiation, not stop a pilot.

### Recommended Friday-noon plan (~22 hours of work)

Sorted by points-per-hour, must-do first:

| # | Finding | Hours |
|---|---|---:|
| 1 | F-TESTS — reconcile test counts across 5 docs to `pytest` output | 0.5 |
| 2 | R-014 — paste real demo-video URL in `SUBMISSION.md` | 0.5 |
| 3 | CISO-01 — verify `ADVERSARIAL_OPERATOR_TOKEN` set on Railway; add fail-closed startup check | 2.5 |
| 4 | R-001 — rewrite root `ARCHITECTURE.md` to be the adversarial-platform doc (move existing Co-Pilot content to `W2_ARCHITECTURE.md`; include agent diagram from `security/docs/W3_SYSTEM_DESIGN.md`) | 3 |
| 5 | R-004 — expand adversarial-platform section in `USERS.md` (workflows + automation justification) | 1.5 |
| 6 | DRIFT-REALIGN — edit `WEEK3_PRD.md`, `THREAT_MODEL.md` (root + security/docs), and `W3_ARCHITECTURE.md` so claims of "bounded autonomous loop with retries / 8 stop reasons / 95% pass-rate gate / LLM judge feature flag" match what the code does today (drop unsupported claims; cite the rubric grade's honest admissions) | 2 |
| 7 | R-003 — rewrite `AI_COST_ANALYSIS.md` "Architecture Changes By Scale" to be keyed to 100/1K/10K/100K **test runs** (not clinician users); include real architectural changes per scale (sharding, observation-table TTL, judge-as-service, batching, queue) | 3 |
| 8 | CISO-03 — enforce `max_wall_clock_seconds` in `run_week3_eval.run_suite` (single elapsed-time check in the for-loop) | 1 |
| 9 | CISO-02 (minimal) — redact `observed_responses.payload_json` at write time using the existing `public_report_view` redactor; or move the table to `private_sqlite_path`. Pick the cheaper. | 3 |
| 10 | P0-A (minimal) — add a real `orchestrator` node that reads `reporting.category_rollups` + open-FAIL queue and reorders cases by `(open_severity, coverage_gap)` before the Red Team. Document this as the loop's prioritization layer. | 4 |
| 11 | S1 — Demo-day Railway warm-up check: cold-start each of the 3 services 5 min before the demo, record `/healthz` responses in `SUBMISSION.md` evidence section | 1 |

Total: **~22 hours**. Leaves ~18 hours buffer for testing + recording + buffer.

**Explicitly excluded from the Friday-noon plan** (high cost vs marginal rubric impact at this deadline): rebuilding LangGraph into a true autonomous loop (Q11 demote; would risk regressions in 48h), SSO/OIDC (CISO-08), full async refactor of `start_run` (Q2), cross-category regression detection (R-008), CSP nonce migration (S2).

---

## 2. Scored Rubric

(From rubric auditor, severities adjusted per skeptic.)

### Hard gates

| Gate | Status | Evidence | Notes |
|---|---|---|---|
| Deployed target URL submitted | ✅ Pass | `SUBMISSION.md:13` `Co-Pilot API ... https://copilot-api-production-9f84.up.railway.app` | Plus `W3_ARCHITECTURE.md:18`. |
| `THREAT_MODEL.md` exists with ~500-word summary | ✅ Pass | `THREAT_MODEL.md:3-15` six-paragraph executive summary | ~500–650 words, explicit risk ranking. |
| `evals/` directory with ≥3 categories | ⚠ Partial | `security/adversarial/evals/week3/README.md:36-49` 13 categories | PRD says `./evals/`; adversarial evals live under `security/adversarial/evals/week3/`. Path is signposted from `SUBMISSION.md`. Skeptic demoted from P2 to P3. |
| ≥1 agent role running live against deployed target | ✅ Pass | `graph.py:167-182` 7 LangGraph nodes hit deployed Co-Pilot API; run IDs in `VULNERABILITY_REPORTS.md:18-33`. | |
| `ARCHITECTURE.md` ~500-word summary + agent diagram | ❌ **Fail** | `ARCHITECTURE.md:1` `# AgentForge Clinical Co-Pilot Architecture` | Wrong subject — describes target system, not platform. No Red Team / Judge / Orchestrator / Documentation named. **R-001 — P0**. |
| `USERS.md` with workflows + automation justification | ⚠ Partial | `USERS.md:176-184` adversarial section is 9 lines, bullets only | **R-004 — P1**. |
| ≥3 vulnerability reports following required format | ✅ Pass | `security/docs/VULNERABILITY_REPORTS.md:38,64,90,116` four `AF-W3-OEMR-00x` reports, all required fields | Skeptic blind-spot: all four are OpenEMR web-surface, none are confirmed AI-agent jailbreaks. See blind-spot **S6**. |
| `AI_COST_ANALYSIS.md` covers 100/1K/10K/100K runs with architectural changes per scale | ⚠ Partial | `AI_COST_ANALYSIS.md:164-178` table is `$0.25 × n`; lines 207-215 "Architecture Changes By Scale" is keyed to clinician *users*, not test runs | PRD explicitly forbids "cost-per-token × n". **R-003 — P0**. |
| Multi-agent architecture (not pipeline) | ⚠ Partial | `graph.py:175-182` linear edges; `WEEK3_RUBRIC_GRADE.md:27` admits "single-pass workflow per case" | Distinct classes exist, but execution is linear and orchestrator is a stub. **P0-A merged finding**. |
| Demo video plan + actual link | ⚠ Partial | `security/docs/FINAL_DEMO_SCRIPT.md:1-35` script present; `SUBMISSION.md:47` placeholder text in lieu of URL | **R-014 — P1 (promoted)**. |
| Eval dataset reproducible | ✅ Pass | `security/adversarial/evals/week3/README.md:13-19` command; deterministic regex judge | |
| Vuln report format complete | ✅ Pass | `security/docs/VULNERABILITY_REPORTS.md:38-62` AF-W3-OEMR-001 includes every required field | |

**Summary:** 7 Pass, 4 Partial, 1 Fail.

### Required agent capabilities

| Capability | Status | Evidence |
|---|---|---|
| Generates novel adversarial inputs | ⚠ Partial | `red_team_agent.py:17-33` three hard-coded `MutationTemplate`s; `WEEK3_RUBRIC_GRADE.md:28` admits deterministic templates. |
| Mutates partially-successful attacks | ❌ Fail | `red_team_agent.py:39-45` `generate_variants` runs unconditionally; no Judge→RedTeam feedback edge in `graph.py:175-182`. **R-005 — P1**. |
| Multi-turn attack sequences | ⚠ Partial | `red_team_agent.py:54-58` `multi_turn_pressure` adds one setup turn. |
| Consistent eval across runs/versions | ✅ Pass | Deterministic regex judge; `run_judge_eval.py` 0 FP / 0 FN on fixture set. |
| Prioritize by coverage gaps / open findings | ❌ Fail | `graph.py:86-88` orchestrator is trace-only no-op; `run_week3_eval.py:66-78` iterates `for case in cases` in load order. **R-006 — P1**. |
| Halt/redirect on no-signal cost | ⚠ Partial | Per-case budgets; no suite-level kill switch. |
| Trigger regression on target changes | ❌ Fail | `run_week3_eval.py:48-53` regression suite only via manual `--suite regression` CLI flag. **R-007 — P1**. |

### Required roles (Red Team, Judge, Orchestrator, Documentation)

- **Red Team** — Pass (class exists, typed I/O). `red_team_agent.py:36`.
- **Judge** — Pass (class exists, typed I/O, documented coordination). `judge_agent.py:29`.
- **Orchestrator** — **Fail.** `graph.py:86-88` is a trace-only function, not a class. No trust-level doc. No priority signals enumerated. Implementation contradicts its `W3_SYSTEM_DESIGN.md:77` documented loop.
- **Documentation** — Pass (class exists). `documentation_agent.py:8`.

### Observability layer (6 PRD questions)

3 Pass, 3 Partial, 0 Fail. Trend visibility weak: only latest resilience snapshot surfaced; no cross-version pass-rate diff; no cost-scaling trend.

### Regression & validation harness

| Bullet | Status |
|---|---|
| Store confirmed exploits versioned/queryable | ✅ Pass |
| Run regression suite when Orchestrator triggers | ❌ Fail (CLI only) |
| Detect previously-fixed vulnerability reappearing | ⚠ Partial |
| Flag cross-category regressions | ❌ Fail (no diff logic) |

### Documentation Agent format

5 Pass, 1 Partial. Auto-drafted remediation is generic boilerplate (`documentation_agent.py:37-41`); manual reports have substantive remediation.

---

## 3. CISO Defensibility Scorecard

(From CISO auditor, severities adjusted per skeptic; blind spots S1/S3/S4/S5/S7/S8 added below.)

| # | Trust dimension | Status | What a CISO would ask | Finding ID |
|---|---|---|---|---|
| 1 | **Judge independence** | **Strong** | Can judge see attacker's prompt context? | None — `judge_agent.py:29-177` pure regex, zero LLM. |
| 2 | **Audit trail** | Adequate | Tamper-evident, append-only? | **CISO-07** P1 — `run_store.py:223-239` uses `INSERT OR REPLACE`, no hash chain. |
| 3 | **Approval gates** | **Weak** | Two-person rule for "confirmed"? | **CISO-08** P1 — single shared `operator_token` (`config.py:33`); no per-user identity. |
| 4 | **Blast radius** | Adequate | What if allowlist misconfigured? | Allowlist is env-driven; **CISO-01** P0 if `operator_token` also unset (auth bypass chain). |
| 5 | **False-positive cost** | **Weak** | Calibration in prod? | **CISO-06** P1 — `judge_agent.py:17-21` `ACTIONABLE_CLINICAL_RE` matches `take.*test` broadly. |
| 6 | **Scope discipline** | Adequate | Subdomain/port anchoring? | **CISO-09** P2 — `config.py:104-105` compares hostname only, no port/scheme. |
| 7 | **PHI safety** | Adequate→**Weak** | Where does leaked PHI land? | **CISO-02** P0 — full target response persists in public `observed_responses` table (`run_store.py:241-255`). |
| 8 | **Cost containment** | Adequate→**Weak** | Suite wall-clock guard? | **CISO-03** P0 — `models.py:221` `max_wall_clock_seconds = 300` never enforced. Also **S8** P2 — `target_client.py:186-188` `len(text)//4` token estimate so coarse the token budget never fires. |
| 9 | **Regression integrity** | **Weak** | Replay proves fix? | **CISO-04** P1 — `models.py:277` `fix_validation_runs: list[str]` defined; never appended. **CISO-05** P1 — replay does not pin `target_version`. |
| 10 | **Reproducibility** | Adequate | Senior engineer can reproduce? | **CISO-11** P2 — bearer-token jti/exp not in `AttackRun.synthetic_principal`. **S4** P1 — target redeploys between MVP/Final may invalidate the 13 run IDs in `VULNERABILITY_REPORTS.md:18-32`. |

**Verdict:** Conditional go. ~11 hours on the three P0s closes the blockers a CISO would refuse a pilot over.

### CISO blind spots surfaced by skeptic

| ID | Severity | What | Evidence |
|---|---|---|---|
| **S1** | P1 | Demo-day Railway connectivity risk: 3 free-tier services may cold-start / rate-limit during the demo. | `SUBMISSION.md:79-96`; mitigation = warm-up + `/healthz` snapshot 5 min pre-demo. |
| **S2** | P2 | CSP `'unsafe-inline'` on script-src AND style-src, plus 5 `<pre>{escape(str(...))}</pre>` blocks dumping row dicts in `ui.py:521,591,599,603,607`. XSS chain if any DB row contains a Python repr with HTML. | `ui.py:842-843`. |
| **S3** | P1 | If CISO-01 fails (no operator token) AND `synthetic_clinician_password` is set in the deployed env, an unauthenticated dashboard reader can pivot to the synthetic-clinician account's grant. | `config.py:41-50`, `synthetic_auth.py:16-59`. |
| **S5** | P2 | `evidence_retention_days` applies only to reports/findings; `attack_runs`, `observed_responses`, `agent_trace_events`, `judge_verdicts` grow without bound. | `run_store.py:114-130`. |
| **S7** | P1 (doc) | `WEEK3_PRD.md:285` claims "LLM judging behind a feature flag" with no such flag in code; `WEEK3_RUBRIC_GRADE.md:29` honestly admits the gap. A reviewer reading both sees the platform contradicting itself. | Drop the PRD claim. |

---

## 4. Doc/Code Drift Summary

(From drift auditor + skeptic.)

281 claims checked across 27 docs. **235 Confirmed, 7 Contradicted, 11 Overstated, 1 Understated, 39 Unverified (live deployment).**

### Top 5 drift findings

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | **The "bounded autonomous loop" overclaim cluster** — F10/F11/F20/F75 + R-002 all describe the same defect through different lenses. PRD, root threat model, security/docs threat model all describe LangGraph-managed retries, orchestrator priority scoring, 8 stop reasons. Implementation is a 7-node linear DAG with a trace-only orchestrator, 4 stop reasons assigned. | P0-A | `graph.py:86-88,175-182,148-159`; `WEEK3_PRD.md:243-245`; `THREAT_MODEL.md:15` (security/docs). Skeptic note: present as ONE finding, not five. |
| 2 | **Test-count cluster** F1/F15/F29/F62/F63 — three different submission-grade docs disagree: `SUBMISSION.md:73` "60 passed", `WEEK3_RUBRIC_GRADE.md:85` "50 passed", `README.md:120` "43 passed". Actual tree: **61** test functions. | **P0 (promoted)** | Grep `^def test_` in `security/adversarial/tests/` returns 61. |
| 3 | **95% pass-rate + 10% inconclusive gates** F25 — PRD promises quantitative enforce thresholds. `run_week3_eval.py:123-132` only blocks on critical/high `FAIL`. | P1 | Doc fix: drop the numbers or implement them. |
| 4 | **PRD "Initial repo structure" stale** F16/F17/F18/F78 — references `case_models.py`, `orchestrator_agent.py`, `observability.py`, `cross_patient_exfiltration/`, `run_exports` table, `AttackRun.agent_trace` field. None exist. Real structure is different. | P2 | `migrations/001_initial.sql:1-164`; `models.py:166-189,247-262`. |
| 5 | **LLM judge feature flag** F72/X7 — `WEEK3_PRD.md:285` promises "LLM judging behind a feature flag"; no flag exists. `WEEK3_RUBRIC_GRADE.md:29` admits "No LLM advisory path is enabled." Internal contradiction. | P1 | Drop the PRD claim or wire the flag. |

### Cross-doc inconsistencies

| # | Topic | Severity |
|---|---|---|
| X1 | Test count: `60` (3 docs) vs `50` (2 docs) vs `43` (1 doc) vs **61** (tree) | P0 |
| X2 | Mypy "24 source files" vs 25–26 actual | P3 (demoted) |
| X3 | API tests `178 passed` (EVAL_DATASET) vs `192 passed` (README, SUBMISSION) | P2 |
| X4 | Identity hijacking priority: threat model "Medium" vs seed case "High" | P2 |
| X5 | Stop reasons: PRD 8 vs code 4 | P1 |
| X6 | Vuln-report count: "3+1" framing vs body lists 4 | P3 (internally consistent) |
| X7 | LLM judge feature flag claimed in PRD, denied in rubric grade | P1 |
| X8 | PRD initial-structure file names vs actual layout | P2 |
| X9 | EARLY_SUBMISSION_CHECKLIST vs SUBMISSION on API test count | P2 |

**Doc credibility verdict:** mixed. `SCHEMA_EVIDENCE.md`, target client / scanner / regression / resilience / migrations docs all match code. `WEEK3_PRD.md`, root + security/docs `THREAT_MODEL.md`, and submission-grade marketing docs overclaim agent autonomy and have stale numbers. Drift is concentrated in the planning artifacts.

---

## 5. Code Quality Summary

(From quality auditor + skeptic.)

40 smells total: **6 P1, 28 P2, 6 P3**. Skeptic demoted Q11 (LangGraph for linear DAG) and Q15 (hardcoded Railway defaults) to P3.

### Top 5 highest-impact refactors (NOT in the Friday-noon plan; for follow-up)

| # | ID | What | Evidence | Hours |
|---|---|---|---|---:|
| 1 | Q1 + Q17 + Q18 + Q19 | `RunStore.initialize()` runs schema ALTERs + redaction sweeps on every `/readyz` and every route call. Cache initialization once per process. | `run_store.py:80-168`, `170-181` (readiness triggers writes). | 3 |
| 2 | Q2 + Q31 | UI `start_run` is `async def` but calls sync `run_suite` which calls `asyncio.run` per case — blocks the event loop and the rate limiter for the whole suite. | `ui.py:382`, `graph.py:100`, `run_week3_eval.py:66`. | 5 |
| 3 | Q5 + Q6 + Q29 | Agent contact surface untested: `target_client.py` has 1 SSE happy-path test, `synthetic_auth.py` has 0, half of `JudgeAgent` branches uncovered. | `tests/test_target_client.py`, `tests/test_run_week3_eval.py`, `tests/test_judge_agent.py`. | 8 |
| 4 | Q7+Q8+Q9+Q10+Q39 (DEAD) | Speculative abstractions: `CampaignPriority` (zero callers), `service_account_token` (never read), three `ports.py` Protocols (single implementations), empty `app/templates/` dir, `RunBudget` defaults that duplicate `Settings` defaults, `scanner_factory` injection point. **User memory:** no speculative interface seams. | `models.py:449-460`, `config.py:51`, `ports.py:20-55`, `app/templates/`, `models.py:213-221`, `site_scan_workflow.py:37`. | 2 |
| 5 | Q3 + Q4 + Q12 + Q23 + Q24 + Q25 (SWALLOWED) | Five places silently swallow exceptions: `_record_audit` (`ui.py:969`), `update_report_status` row-missing (`sensitive_findings.py:115`), `costing.build_suite_summary` fallback (`costing.py:19`), `SiteScanWorkflow` (`site_scan_workflow.py:97`), `start_run` 502 wrap (`ui.py:395-415`), `site_scanner` candidate fetch (`site_scanner.py:786`). Each hides real failures. | (see file refs) | 4 |

### Dependency report

`langgraph` is the only meaningfully oversized dep for a 7-node linear DAG, but per skeptic, ripping it out two days before submission would *worsen* the multi-agent perception. Keep. Everything else earns its place.

### Concurrency / security smells in the platform itself

- `graph.py:100` `asyncio.run` inside a sync node — runtime trap if ever invoked from async caller.
- `ui.py:842` CSP `'unsafe-inline'` — see blind-spot S2.
- No SQL injection risk: all `conn.execute` parameterized.
- No shell-out / subprocess calls.
- No secrets in code; `SecretStr` env settings everywhere.

---

## 6. Prioritized Unified Backlog

Severity P0 first (by pts/hr within), then P1, then P2. Pts/hr is "estimated rubric points recovered / estimated hours" — proxy for CISO findings is trust-impact / hours.

### P0 — must do before Friday noon

| ID | Title | Files | Hours | Pts/hr | Source |
|---|---|---|---:|---:|---|
| F-TESTS | Reconcile test counts across 5 docs to actual `pytest` output | `SUBMISSION.md:71`, `WEEK3_SUBMISSION_CHECKLIST.md:44`, `WEEK3_RUBRIC_GRADE.md:85`, `README.md:120`, `FINAL_DEMO_SCRIPT.md:52` | 0.5 | 10 | Drift+Skeptic |
| R-014 | Replace demo-video placeholder with real URL | `SUBMISSION.md:47` | 0.5 | 10 | Rubric+Skeptic |
| CISO-01 | Verify `ADVERSARIAL_OPERATOR_TOKEN` set on Railway; add fail-closed startup check (`config.py` validator: if `operator_auth_enabled` mode is "required" and token is None, raise on import) | `ui.py:875-877`, `config.py:33` | 2.5 | 8 | CISO+Skeptic |
| R-001 | Rewrite root `ARCHITECTURE.md` to describe the adversarial platform; move existing Co-Pilot content to `W2_ARCHITECTURE.md`; embed agent-interaction diagram from `W3_SYSTEM_DESIGN.md` | `ARCHITECTURE.md`, `security/docs/W3_ARCHITECTURE.md`, `security/docs/W3_SYSTEM_DESIGN.md` | 3 | 3 | Rubric |
| R-003 | Rewrite `AI_COST_ANALYSIS.md` so "Architecture Changes By Scale" is keyed to 100/1K/10K/100K **test runs** (sharding, observation-TTL, judge-as-service, batching, queue) — not clinician users; replace `$0.25 × n` table with model that includes amortized infra costs per scale | `AI_COST_ANALYSIS.md:150-215` | 3 | 2.3 | Rubric |
| DRIFT-REALIGN | Edit `WEEK3_PRD.md`, root `THREAT_MODEL.md`, `security/docs/THREAT_MODEL.md`, `W3_ARCHITECTURE.md` to drop or qualify: "bounded autonomous loop with retries", "8 stop reasons", "95% pass-rate / 10% inconclusive gates", "LLM judge feature flag". Replace with what code actually does, citing the rubric grade doc's honest admissions. | (multiple) | 2 | 4 | Drift+Skeptic |
| CISO-03 | Enforce `max_wall_clock_seconds` in `run_suite`: single elapsed-time check in the for-loop; assign `StopReason.TIMEOUT` | `run_week3_eval.py:66-78`, `models.py:221` | 1 | 7 | CISO+Skeptic |
| CISO-02 | Redact `observed_responses.payload_json` at write time using existing `public_report_view` redactor (or move table to `private_sqlite_path`) | `run_store.py:241-255`, `sensitive_findings.py:187-204` | 3 | 6 | CISO |
| P0-A | Replace orchestrator no-op with a real prioritizer: read `reporting.category_rollups` + open-FAIL queue; reorder cases by `(open_high_severity, coverage_gap)` before the Red Team runs. Document the loop boundary in `W3_ARCHITECTURE.md`. | `security/adversarial/app/graph.py:86-88`, new `app/orchestrator.py`, `run_week3_eval.py:66-78` | 4 | 1.5 | Rubric+Drift+CISO+Quality (merged) |

**P0 subtotal:** 19.5 hours.

### P1 — high-leverage if time permits

| ID | Title | Hours | Source |
|---|---|---:|---|
| R-004 | Expand `USERS.md` adversarial-platform section to include workflows + automation justification | 1.5 | Rubric |
| S1 | Pre-demo Railway warm-up + `/healthz` snapshot recorded in `SUBMISSION.md` | 1 | Skeptic |
| S7 | Drop PRD's "LLM judging behind a feature flag" claim (or add the flag stub) | 0.5 | Skeptic |
| CISO-06 | Tighten `ACTIONABLE_CLINICAL_RE` to reduce false positives; add a labeled adversarial-fixture corpus | 4 | CISO |
| R-005 | Wire a Judge→RedTeam feedback edge: if verdict is INCONCLUSIVE or PARTIAL with `confidence < 0.6`, regenerate one variant from the same parent case | 5 | Rubric |
| R-007 | Add a "regression on deploy" trigger: `run_week3_eval.py` flag `--watch-target-version` that polls `/api/status.version` and runs `--suite regression` on change | 4 | Rubric |
| R-008 | Cross-category regression detection: for each promoted case, score the FAIL rate of *other* categories in the same run vs baseline; flag if any rises | 4 | Rubric |
| CISO-04 | Populate `fix_validation_runs` when `update_report_status` moves a report to `RESOLVED` after a passing replay | 3 | CISO |
| CISO-05 | Pin `target_version` on `regression_cases` row at promotion; refuse to record "PASS" verdict if replay target version ≠ pin (unless `--allow-version-drift`) | 4 | CISO |
| S4 | Capture target_version + commit SHA in `AttackRun.target_metadata` at every run; export in `VULNERABILITY_REPORTS.md` | 2 | Skeptic |
| S3 | Add an env-var sanity check at startup: if `synthetic_clinician_password` is set AND `operator_token` is unset, raise; force fail-closed | 1 | Skeptic |

**P1 subtotal:** 30 hours.

### P2 — polish

(28 P2 findings from quality + several from CISO/drift; see raw outputs. Not enumerated here. Skip for Friday.)

### P3 — deferred indefinitely

Q11 (LangGraph for linear DAG), Q15 (hardcoded Railway URLs), R-009 (eval path), R-011 (Orchestrator trust-level doc), F2 (mypy 24-vs-25), F4/F5 (PRD schema field omissions), Q35–Q40 (misc P3 polish), F16/F17/F18/F78 (PRD initial-structure drift — covered by DRIFT-REALIGN).

---

## 7. Skeptic Review Notes

Verbatim from `2026-05-13-week3-audit-skeptic-review.md`:

> Verdict counts across spot-checks: 38 CONFIRMED, 1 OVERSTATED, 0 WRONG, 0 MISSING-CONTEXT in this sample. The auditors are unusually accurate.

> Most rigorous auditor: CISO. Every CISO finding I sampled (10) was confirmed at the cited line.

> Auditors collectively over-index on architectural deficiency (linear pipeline / stub orchestrator) and under-index on demo-day operational risk (live Railway availability, CSP/XSS chain, secret exposure if CISO-01 misconfigured).

> The four converging "linear pipeline / stub orchestrator" findings should be presented as one issue, not four. — applied as **P0-A**.

> Quality is the weakest at producing rubric-actionable items. — applied: most Q-findings are P2 polish; only Q1/Q2/Q3/Q4/Q5/Q6 affect a CISO read; none move the rubric directly.

### Blind spots added to the backlog

S1, S3, S4, S7 (P1) and S2, S5, S6, S8 (P2) — all sourced from skeptic, none in the four original outputs.

---

## 8. Evidence Appendix (Top 25 findings)

Quotes verified at file:line. All quotes ≤15 words.

1. **R-001** `ARCHITECTURE.md:1` — `# AgentForge Clinical Co-Pilot Architecture`
2. **R-002 / P0-A** `graph.py:86-88` — `def orchestrator(state): trace(state, "orchestrator", "select", ...); return state`
3. **P0-A** `graph.py:175-182` — `graph.add_edge("orchestrator", "red_team"); ... graph.add_edge("stop_policy", END)`
4. **R-003** `AI_COST_ANALYSIS.md:209-215` — `## Architecture Changes By Scale ... At 100 users ... At 100,000 users`
5. **R-004** `USERS.md:176-184` — 9-line adversarial-platform bullet list
6. **R-005** `red_team_agent.py:39-45` — `def generate_variants(self, case, budget): return [...]` (unconditional)
7. **R-006** `graph.py:86-88` (same as P0-A) — orchestrator returns state unchanged
8. **R-007** `run_week3_eval.py:48-53` — `if suite == "regression": seed_cases.extend(...)` (manual only)
9. **R-014** `SUBMISSION.md:47` — `Captured; paste the uploaded video link`
10. **CISO-01** `ui.py:875-877` — `if not _operator_auth_enabled(settings): return True`
11. **CISO-02** `run_store.py:241-255` — `INSERT OR REPLACE INTO observed_responses ... _to_json(observed)`
12. **CISO-03** `models.py:221` — `max_wall_clock_seconds: float = 300` (defined, never enforced)
13. **CISO-04** `models.py:277` — `fix_validation_runs: list[str] = Field(default_factory=list)` (never appended)
14. **CISO-05** `regression_harness.py:25-31` — `case.model_copy(...)` only rewrites case_id
15. **CISO-06** `judge_agent.py:17-21` — `ACTIONABLE_CLINICAL_RE = re.compile(r"\b(...take)\b.*\b(...lab|test|...)\b", re.IGNORECASE | re.DOTALL)`
16. **CISO-07** `run_store.py:223-239` — `INSERT OR REPLACE INTO agent_trace_events`
17. **F1 / F-TESTS** `SUBMISSION.md:73` — `Week 3 adversarial tests: 60 passed`; `WEEK3_RUBRIC_GRADE.md:85` — `pytest: 50 passed`; `README.md:120` — `43 passed`; tree: 61 test functions
18. **F10** `WEEK3_PRD.md:243` — `LangGraph manages multi-agent state transitions, retries, stop conditions, and handoffs`
19. **F11** `WEEK3_PRD.md:244` — `Orchestrator either continues or stops based on coverage, budget, severity`
20. **F20** `security/docs/THREAT_MODEL.md:15` — `Coverage will be prioritized by a LangGraph Orchestrator using ...`
21. **F25** `WEEK3_PRD.md:348` — `Seed adversarial suite pass rate: 95% minimum`
22. **F35** `WEEK3_PRD.md:245` — 8 stop reasons listed; `graph.py:148-159` assigns 4
23. **F72** `WEEK3_PRD.md:285` — `Allows LLM judging only behind a feature flag` (no flag in `judge_agent.py`, `config.py`)
24. **Q1** `run_store.py:80-90` — `def initialize(self): self._run_migrations(); self._ensure_site_scan_scope_columns(); ...`
25. **Q3** `ui.py:981-982` — `except Exception: return`

---

## 9. Pointer to Raw Outputs

- Audit design: [docs/plans/2026-05-13-week3-audit-design.md](2026-05-13-week3-audit-design.md)
- Execution plan: [docs/plans/2026-05-13-week3-audit-execution.md](2026-05-13-week3-audit-execution.md)
- Rubric auditor (full): [docs/plans/2026-05-13-week3-audit-raw/rubric.md](2026-05-13-week3-audit-raw/rubric.md)
- CISO auditor (full): [docs/plans/2026-05-13-week3-audit-raw/ciso.md](2026-05-13-week3-audit-raw/ciso.md)
- Code quality auditor (full): [docs/plans/2026-05-13-week3-audit-raw/quality.md](2026-05-13-week3-audit-raw/quality.md)
- Doc/code drift auditor (full): [docs/plans/2026-05-13-week3-audit-raw/drift.md](2026-05-13-week3-audit-raw/drift.md)
- Skeptic review (full): [docs/plans/2026-05-13-week3-audit-skeptic-review.md](2026-05-13-week3-audit-skeptic-review.md)
