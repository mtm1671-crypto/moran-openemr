# Skeptic Review

**Date:** 2026-05-13.
**Auditor under review:** Rubric, CISO, Quality, Drift specialists.
**Method:** Opened 20+ cited files at the cited line ranges and confirmed the quoted code or text. Verdicts: CONFIRMED / OVERSTATED / WRONG / MISSING-CONTEXT.

## Per-Auditor Spot-Check Results

### Rubric (top 5 P0/P1 + 5 random)

| Finding | Verdict | One-line reasoning + my quote (<=15 words) |
|---|---|---|
| R-001 root `ARCHITECTURE.md` is Co-Pilot, not multi-agent | CONFIRMED | Grep for "Red Team|Judge|Documentation Agent" in `ARCHITECTURE.md` returns only `Agent Orchestrator` (Co-Pilot RAG sense). |
| R-002 LangGraph is linear pipeline w/ stub orchestrator | CONFIRMED | `graph.py:175-182` is seven `add_edge` calls, no conditional edges, no cycle back to orchestrator. |
| R-003 cost analysis is users not test-runs | CONFIRMED | `AI_COST_ANALYSIS.md:209-215` "At 100 users... At 100,000 users" — wrong axis. |
| R-006 Orchestrator does not prioritize | CONFIRMED | `graph.py:86-88` only `trace(..., f"Selected case {state['case'].case_id}")` and returns state. |
| R-007 regression triggers manual only | CONFIRMED | `run_week3_eval.py:48-53` regression cases only via `if suite == "regression":` CLI branch. |
| R-004 USERS.md adversarial section 9 lines | CONFIRMED | `USERS.md:176-184` = exactly 9 lines, bullet list, no workflows. |
| R-005 mutations unconditional | CONFIRMED | `red_team_agent.py:39-45` `generate_variants` iterates templates regardless of judge signal. |
| R-008 no cross-category regression detection | CONFIRMED | `regression_harness.py:42-58` only promotes single confirmed report; no cross-category diff. |
| R-009 eval path drift (`./evals/` vs `security/adversarial/evals/week3/`) | OVERSTATED | The PRD's `./evals/` is conventional; reviewers find the README via `SUBMISSION.md` and `W3_ARCHITECTURE.md`. P2 is fair but rubric won't necessarily ding for it. |
| R-013 multi-turn depth shallow | CONFIRMED | `red_team_agent.py:54-58` adds only one synthetic setup prompt for `multi_turn_pressure`. |

### CISO (top 5 + 5 random)

| Finding | Verdict | Reasoning |
|---|---|---|
| CISO-01 UI auth bypass when token unset | CONFIRMED | `ui.py:875-877` `if not _operator_auth_enabled(settings): return True`. Real, severe. |
| CISO-02 `observed_responses` holds full response | CONFIRMED | `run_store.py:241-255` `INSERT OR REPLACE INTO observed_responses ... _to_json(observed)` — full text persisted. |
| CISO-03 max_wall_clock_seconds never enforced | CONFIRMED | Field exists `models.py:221`, no enforcement in `graph.py` or `run_week3_eval.py` for-loop. |
| CISO-04 fix_validation_runs never appended | CONFIRMED | `models.py:277` defines list; `run_store.py:113-145` `update_report_status` does not touch the list. |
| CISO-05 regression replay no target_version pin | CONFIRMED | `regression_harness.py:25-31` `case.model_copy` only rewrites case_id; no version comparison. |
| CISO-06 ACTIONABLE_CLINICAL_RE over-fires on "take...test" | CONFIRMED | `judge_agent.py:17-21` regex with `\\b(...take)\\b.*\\b(...lab|test|...)\\b` + DOTALL — real false-positive surface. |
| CISO-07 audit tables `INSERT OR REPLACE` | CONFIRMED | `run_store.py:223-239` save_trace uses `INSERT OR REPLACE INTO agent_trace_events` — re-insertable. |
| CISO-09 allowlist ignores port | CONFIRMED | `config.py:104-105` compares only `parsed.hostname` not `parsed.port`/`parsed.scheme`. |
| CISO-11 bearer token jti/exp not recorded | CONFIRMED | `run_week3_eval.py:113-120` `_synthetic_principal_label` is a coarse string like `synthetic-clinician:password-grant`. |
| CISO-13 doc auto-drafts every non-PASS | CONFIRMED | `documentation_agent.py:9-12` only filters `Verdict.PASS`; INCONCLUSIVE drafts go through. |

### Quality (top 5 + 5 random)

| Finding | Verdict | Reasoning |
|---|---|---|
| Q1 `RunStore.initialize()` re-runs every readiness probe | CONFIRMED | `run_store.py:80-90` initialize runs `_redact_existing_public_reports` and ALTERs; `readiness():172` calls `self.initialize()`. |
| Q2 UI async route invokes sync run_suite with `asyncio.run` | CONFIRMED | `ui.py:382` async route → `run_suite` → `graph.py:100` `asyncio.run(...)`. Event loop blocks. |
| Q3 `_record_audit` swallows all exceptions | CONFIRMED | `ui.py:981-982` `except Exception: return`. |
| Q4 SensitiveFindingStore.update_report_status silent miss | CONFIRMED | `sensitive_findings.py:129-130` `if row is None: return`. |
| Q5 target_client.py near-zero coverage | CONFIRMED | `tests/test_target_client.py` has 1 test function (matches Grep count). |
| Q7 `CampaignPriority` dead | CONFIRMED | `models.py:449-460` defines class; no producer or consumer in `app/`. |
| Q9 speculative Protocols in ports.py | CONFIRMED | `ports.py:20-43` three Protocols each with one production implementation. |
| Q11 LangGraph for a 7-node linear DAG | CONFIRMED | `graph.py:175-182` linear edges; `pyproject.toml:12` `langgraph>=0.2.0`. Real bloat. |
| Q13 token estimate `len(text) // 4` | CONFIRMED | `target_client.py:186-188` `return max(1, len(text) // 4)`. Trivial heuristic. |
| Q22 unbounded in-memory rate-limit dict | CONFIRMED | `ui.py:848-861` keyed by `host:path` with no eviction. |

### Drift (top 5 + 5 random)

| Finding | Verdict | Reasoning |
|---|---|---|
| F1/F15/F29/F62/F63 test count drift (43/50/60 vs 61) | CONFIRMED | My grep shows 61 test functions across 10 files; multiple docs disagree. |
| F10 PRD "LangGraph manages retries" | CONFIRMED | `graph.py:54-209` has no retry node, no retry decorator, no loop. |
| F11 PRD "Orchestrator continues or stops based on coverage" | CONFIRMED | `graph.py:86-88` orchestrator is one-line trace. |
| F25 PRD "95% pass-rate, <10% inconclusive" not implemented | CONFIRMED | `run_week3_eval.py:123-132` only blocks on `verdict==FAIL and severity in {CRITICAL,HIGH}`. |
| F35 PRD lists 8 stop reasons, code implements 4 | CONFIRMED | `graph.py:148-159` assigns only CRITICAL_FAILURE/HUMAN_REVIEW_GATE/TARGET_INSTABILITY/COMPLETED. |
| F3 PRD lists `run_exports` table | CONFIRMED | `migrations/001_initial.sql` doesn't define `run_exports`; exports go to disk via `export_run.py`. |
| F17 `cross_patient_exfiltration` folder in PRD | CONFIRMED | Real folder is `cross_patient_phi/`; enum value matches the folder. |
| F20 threat model claims LangGraph priority engine | CONFIRMED | `graph.py:86-88` no scoring; `CampaignPriority` never produced. |
| F72 PRD "LLM judging behind a feature flag" | CONFIRMED | No feature flag in `judge_agent.py`/`config.py`. |
| F75 PRD "bounded autonomous loop" | CONFIRMED | Implementation is a single-pass DAG. |

**Verdict counts across spot-checks:** 38 CONFIRMED, 1 OVERSTATED (R-009 as a P2 with mitigations in `SUBMISSION.md`), 0 WRONG, 0 MISSING-CONTEXT in this sample. The auditors are unusually accurate.

## Findings to Demote

| Finding | Was | Now | Why |
|---|---|---|---|
| R-009 eval path drift | P2 | P3 | The PRD says `./evals/`; the repo has both a root `evals/` (Week 2) and `security/adversarial/evals/week3/`. `SUBMISSION.md` and `W3_ARCHITECTURE.md` link the right path. No reviewer who reads `SUBMISSION.md` will be confused. |
| R-011 Orchestrator trust-level doc | P2 | P3 | `W3_ARCHITECTURE.md:35-40` does label trust boundaries for prompts, responses, judge, credentials. The fact that an "Orchestrator trust level" is not separately enumerated is a doc gap, not a CISO blocker. |
| Q11 LangGraph for linear DAG | P2 | P3 | The rubric explicitly requires "use a multi-agent framework"; ripping out LangGraph in week-3-final could *worsen* the multi-agent perception even if engineering hygiene improves. Real but lowest-priority. |
| Q15 hardcoded Railway URLs in `Settings` defaults | P2 | P3 | `Settings` is env-overridable (`env_prefix="ADVERSARIAL_"`); the defaults are for local dev. Reviewer-friendly. |
| F2 mypy "24 source files" off-by-one | P2 | P3 | Cosmetic. 25 vs 24 will not move a rubric score. |
| F4/F5 schema-doc field omissions | P2 | P3 | Drift in PRD planning artifact, not in `SCHEMA_EVIDENCE.md` (which is the doc reviewers will read). Lower priority. |
| Q35–Q40 misc P3 polish | already P3 | hold | Confirmed but not worth surfacing in synthesis. |

## Findings to Promote

| Finding | Was | Now | Why |
|---|---|---|---|
| CISO-01 UI auth bypass when token unset | P0 (trust 10) | **P0+ (demo blocker)** | If the deployed Railway env does not set `ADVERSARIAL_OPERATOR_TOKEN`, the demo dashboard is wide open and the demo URL in `SUBMISSION.md:15` is the live evidence. Single env-var check before demo. |
| F1/F15/F29/F62/F63 test-count drift | P1 each | **P0 cluster** | These are *submission* hard-gate docs disagreeing with one another. A reviewer who runs `pytest` sees 61 while `SUBMISSION.md:71` says 60, `WEEK3_RUBRIC_GRADE.md:85` says 50, `README.md:120` says 43. Three different numbers in submission-grade docs is worse than one wrong number. |
| R-014 demo video link uncaptured | P2 | **P1** | Hard-gate. PRD requires a demo video per submission. `SUBMISSION.md:47` is a placeholder; if not replaced before submission this is an automatic miss. Trivial fix, large rubric impact. |
| CISO-02 PHI in `observed_responses` | P0 (trust 9) | **stay P0** | Just adding: this is also a rubric-CISO crossover — the platform claims a private/public store split but the table that drives them is in the public DB. |

## Findings to Drop

I do not find a clean false-positive in the four auditor outputs. The closest candidates and why they survive:

- **R-002 "linear pipeline does not satisfy multi-agent"** is *not* a false positive. Three distinct agent classes exist (`RedTeamAgent`, `JudgeAgent`, `DocumentationAgent`) — but the PRD bar is "must collectively be capable of … prioritizing attack surfaces … halting/redirecting when cost accumulates … triggering regression on target changes," all of which require a real orchestrator. The auditors are right to flag, and the project's own `WEEK3_RUBRIC_GRADE.md:27` admits it.
- **"No orchestrator agent" could be wrong if `graph.py` is the orchestrator**. I considered this. `graph.py` is *the wiring*, not an orchestrator. The orchestrator node at `graph.py:86-88` is a no-op (`trace(...); return state`). The convergence between auditors here is correct.
- **Q3 audit-swallow** is sometimes defended as "audit logging must never break the request path." Here the audit failure is silent — no log line, no metric, no exception. That's not graceful degradation; it's hidden failure.

Nothing to drop outright; everything I sampled was a real defect, with the demotions above adjusting severity.

## Blind Spots

Things none of the four auditors covered (or covered only obliquely):

1. **Demo-day connectivity risk.** Severity: P1. Evidence: `SUBMISSION.md:79-96` shows the demo flow depends on three live Railway services (`openemr-production-f5ed`, `copilot-api-production-9f84`, `adversarial-production`). If any one is rate-limited, cold-started, or evicted from a Railway free tier between submission and demo, the live runs in `VULNERABILITY_REPORTS.md:18-32` cannot be reproduced. Should have been caught by: CISO (operational risk) or Rubric (hard-gate verification).
2. **CSP `'unsafe-inline'` on both `script-src` and `style-src`.** Severity: P2. Evidence: `ui.py:842-843`. Quality flagged it in passing but did not call it out as a CISO concern. With the operator dashboard exposed on a public Railway URL, defeating CSP's XSS protection while the dashboard renders un-escaped report bodies (`ui.py:521,591,599,603,607`) is a real chain. Should have been caught by: CISO.
3. **Synthetic-clinician OAuth password-grant secrets in deployed env.** Severity: P1. Evidence: `config.py:41-50` defines `synthetic_clinician_password: SecretStr | None`. If the deployment provides real OpenEMR credentials (even synthetic-named), and the dashboard is unauthenticated (CISO-01), an attacker can read those values via a misconfigured `/debug` route. None of the auditors checked for stray debug routes; I did not find any, but the threat path is real. Should have been caught by: CISO.
4. **Reproducibility against a deployed target between MVP and Final.** Severity: P1. Evidence: `graph.py:185-190` captures `target_version` only opportunistically from `api_status`. If the Co-Pilot API redeploys between Wed (MVP) and Fri (Final), the 13 run IDs in `VULNERABILITY_REPORTS.md:18-32` may no longer be reproducible. None of the auditors connected target redeploys to demo-replay risk. Should have been caught by: Rubric (reproducibility hard gate) or CISO (regression integrity).
5. **`evidence_retention_days` applies to reports/findings only.** Severity: P2. Evidence: `run_store.py:114-130` applies retention only to reports and findings. `attack_runs`, `observed_responses`, `agent_trace_events`, and `judge_verdicts` grow without bound. The PRD says retention should be configurable; the code partially enforces. Drift auditor said the field exists; CISO listed PHI persistence but didn't connect the retention gap.
6. **"Multi-agent" rubric line and the `MISSING_CITATION` draft.** Severity: P2. Evidence: `VULNERABILITY_REPORTS.md:7,24`. The only AI-safety finding the platform has produced is a draft `MISSING_CITATION` that is still unconfirmed. None of the four explicitly noted: the platform was built to *find adversarial AI vulnerabilities*, and it has not yet confirmed one. The four confirmed reports are web-pen-test findings, which a strict reviewer of "adversarial AI platform" deliverables may discount. Rubric flagged it at the bottom of its summary; should have been a top-three finding.
7. **PRD claims an "advisory LLM judge behind a feature flag" but no such code exists.** Severity: P1. Evidence: F72/X7 + my own grep. Drift noted it but Rubric did not. The PRD line is `WEEK3_PRD.md:285`; the rubric grade `WEEK3_RUBRIC_GRADE.md:29` honestly admits the gap. The fact that the rubric grade openly contradicts the PRD on the same point is itself a credibility risk for a reviewer who reads both.
8. **Token estimate drives budget enforcement.** Severity: P2. `target_client.py:186-188` `len(text) // 4` is so coarse the token budget (`max_token_estimate_per_case=8_000`) will never fire on realistic responses. CISO listed cost containment as "Adequate" — it is not, because the only token signal entering the budget is meaningless. Quality flagged it at Q13 but did not connect it to CISO's cost-containment dimension.

## Meta-Observations

- **Most rigorous auditor: CISO.** Every CISO finding I sampled (10) was confirmed at the cited line, and the framing ("what would a CISO ask / what would satisfy them") forces evidence discipline. CISO also caught the most severe live-environment risk (`operator_token` unset).
- **Drift was the most surprising signal.** 235 of 281 claims confirmed is a high accuracy rate; the cross-doc contradictions (test counts, stop-reason counts, file names) are the most actionable findings because each one is a single-line fix that affects how a reviewer sees the project.
- **Rubric and Drift overlap most heavily** on the "linear pipeline / bounded autonomous loop" claim (R-002, F10, F11, F20, F75). Four converging signals at the cited line: this is the centerpiece of the audit, not a false positive.
- **Quality is the weakest at producing rubric-actionable items.** Q-findings are correct but the rubric only marginally cares about `len(text)//4` token estimates or async event-loop blocking. Synthesizer should weight Quality lower than Rubric/CISO for the "what to fix before Friday" backlog.
- **Auditors collectively over-index on architectural deficiency (the linear pipeline / stub orchestrator) and under-index on demo-day operational risk (live Railway availability, CSP/XSS chain, secret exposure if CISO-01 misconfigured).**
- **Contradiction:** Rubric R-002 marks the architecture "Partial" while Drift F75 marks the same as "Overstated/P1". These are consistent — Drift is grading the doc, Rubric is grading the system — but synthesis should not double-count.

## Final Verdict

**Trust level by auditor:**
- Rubric: 92% trust. R-001/R-002/R-003/R-006/R-007 are spot-on. Demote R-009; tighten R-014 (promote).
- CISO: 95% trust. Most rigorous output. Every spot-checked finding confirmed.
- Quality: 85% trust. Findings real; severity weighting overstates a few P2 items relative to rubric impact. Demote Q11, Q15.
- Drift: 90% trust. Test-count cluster is gold. Promote to P0. Some PRD-history items (F16, F18) are P3.

**Top 5 corrections the synthesizer must apply:**

1. **Verify `ADVERSARIAL_OPERATOR_TOKEN` is set on the Railway deployment before demo.** The single most important pre-demo check. CISO-01 is a one-line code defense; deployment env is "needs human read." Treat as a P0 demo blocker.
2. **Reconcile test count across `SUBMISSION.md:71`, `WEEK3_SUBMISSION_CHECKLIST.md:44`, `WEEK3_RUBRIC_GRADE.md:85`, `README.md:120`, `FINAL_DEMO_SCRIPT.md:52` to match the actual `pytest` output.** Three different numbers in submission-grade docs is worse than one wrong number. Promote from per-doc P1/P2 to a single P0 cluster.
3. **Replace the demo-video placeholder in `SUBMISSION.md:47` with an actual URL before submission.** Trivial, hard-gate.
4. **The four converging "linear pipeline / stub orchestrator" findings should be presented as one issue, not four.** R-002 + F10 + F11 + F20 + F75 are the same defect viewed by four lenses. Synthesizer should present a single P0 with all four lens labels, not stack severity.
5. **Add the blind-spot items above (demo connectivity, CSP/XSS, target redeploy reproducibility, "no confirmed adversarial AI finding") to the synthesized backlog.** These are not in any of the four raw outputs and the most "easy to miss in synthesis" risks.

**Overall trust in the audit:** ~91%. The four-auditor convergence on the orchestrator/linear-pipeline issue is real, not a shared blind spot — I confirmed it in `graph.py:86-88` and `graph.py:175-182`. Most findings reproduce at the cited line. The audit is unusually accurate; synthesis should focus on reweighting (demote a few P2s to P3, promote a few to P0) and on the eight blind spots above.
