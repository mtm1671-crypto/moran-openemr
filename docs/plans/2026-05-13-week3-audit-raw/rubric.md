# Rubric Compliance Audit (Week 3)

Auditor: Rubric Compliance specialist (Claude Opus 4.7).
Date: 2026-05-13.
Method: Each row verified against the actual file. No claim is taken from documentation alone.

## 1. Hard Gates

| Gate | Required by PRD | Status | Evidence (file:line + <=15-word quote) | Why this verdict |
|---|---|---|---|---|
| Deployed target application URL submitted | "Your deployed target application URL must be submitted with every checkpoint" | Pass | `SUBMISSION.md:13` `Co-Pilot API deployment \| https://copilot-api-production-9f84.up.railway.app` | URL listed in submission packet plus W3_ARCHITECTURE.md:18. |
| THREAT_MODEL.md exists with ~500-word summary | "A markdown document (./THREAT_MODEL.md) ... ~500 word summary of your key findings" | Pass | `THREAT_MODEL.md:3-15` `## Executive Summary` six paragraphs covering highest-risk categories and prioritization | Root file exists; summary visibly ~500-650 words; explicit risk ranking and coverage plan present. |
| evals/ directory with results from >=3 distinct attack categories | "A working test suite (./evals/) with results from at least three distinct attack categories" | Partial | `security/adversarial/evals/week3/README.md:36-49` 13 categories listed with run IDs in `VULNERABILITY_REPORTS.md:18-33` | PRD says `./evals/`; actual directory is `security/adversarial/evals/week3/`. Root `evals/` directory exists but contains different (Co-Pilot Week 2) data; the adversarial eval results live under `security/adversarial/evals/week3/`. Path mismatch is documentation-drift risk. |
| >=1 agent role running live against deployed target | "a working prototype of at least one agent role ... running live against the deployed target" | Pass | `security/adversarial/app/graph.py:167-182` `graph.add_node("orchestrator", orchestrator)` plus six other nodes | LangGraph nodes Orchestrator, Red Team, Target Runner, Judge, Documentation, Regression Store, Stop Policy execute against deployed Co-Pilot API; run IDs recorded in `VULNERABILITY_REPORTS.md:18-33`. |
| ARCHITECTURE.md with ~500-word summary + diagram of agent interactions | "A markdown document (./ARCHITECTURE.md) defining your multi-agent platform architecture ... ~500 word summary and must explicitly name each agent, its role, and how it fits into the overall system. A diagram of agent interactions is strongly recommended." | Fail | `ARCHITECTURE.md:1` `# AgentForge Clinical Co-Pilot Architecture`; agent grep returns only `Agent Orchestrator` (Co-Pilot RAG orchestrator, line 51) | Root `ARCHITECTURE.md` describes the Clinical Co-Pilot target system; it does not name Red Team, Judge, Orchestrator, or Documentation Agent at all. The multi-agent platform architecture lives in `security/docs/W3_ARCHITECTURE.md`, which is not the file the PRD names. Diagram is in `security/docs/W3_SYSTEM_DESIGN.md` (container view, not agent-interaction sequence). |
| USERS.md exists with workflows + automation justification | "The users your platform addresses, their workflows, and specific use cases with explicit justification for why automation is the right solution." | Partial | `USERS.md:1-174` is Clinical Co-Pilot users; only `USERS.md:176-184` covers adversarial platform users | Adversarial-platform user section is 9 lines, bullet list only; no workflows and no automation justification. The bulk of `USERS.md` is Week 1/2 Co-Pilot users. PRD requirement is for the platform (adversarial system) users; coverage is thin. |
| >=3 distinct vulnerability reports following required format | "Minimum of three distinct vulnerability reports" + format fields | Pass | `security/docs/VULNERABILITY_REPORTS.md:38,64,90,116` four `### AF-W3-OEMR-00x` reports, each with severity, impact, reproduction, observed, expected, remediation, fix status | Four confirmed reports exceed minimum; all required fields present. Confirmed findings are OpenEMR web surface, not AI-agent jailbreaks (the single AI draft `MISSING_CITATION` remains unconfirmed per `VULNERABILITY_REPORTS.md:7`). |
| AI_COST_ANALYSIS.md covers 100/1K/10K/100K test runs with architectural changes per scale | "actual dev spend and projected production costs for running the adversarial platform at 100 / 1K / 10K / 100K test runs. Consider architectural changes needed at each scale. This is not simply cost-per-token x n runs." | Partial | `AI_COST_ANALYSIS.md:164-178` four-row table at exactly 100/1K/10K/100K; `AI_COST_ANALYSIS.md:207-215` `## Architecture Changes By Scale` | Test-run cost rows are exactly cost-per-token x n (`$0.25` cap x n). The "Architecture Changes By Scale" subsection (lines 209-215) is keyed to clinician users (`At 100 users... At 100,000 users`) not test runs, so it doesn't satisfy the per-scale architectural-change requirement for the adversarial platform. PRD explicitly says "This is not simply cost-per-token x n runs." |
| Multi-agent architecture (single-agent or pipeline does NOT satisfy) | "A single-agent or pipeline architecture does not satisfy this assignment" | Partial | `security/adversarial/app/graph.py:175-182` linear edges `orchestrator -> red_team -> target_runner -> judge -> documentation -> regression_store -> stop_policy -> END` | Distinct classes exist (`RedTeamAgent`, `JudgeAgent`, `DocumentationAgent`) with their own context and outputs - meets minimum role separation. However the LangGraph is a strictly linear pipeline with no Orchestrator-driven branching or coverage feedback loop; `WEEK3_RUBRIC_GRADE.md:27` admits "Execution is still a bounded single-pass workflow per case rather than a fully adaptive multi-round loop." Reads as agentic in structure but pipeline in behavior. |
| Demo video plan/script | "One demo video per submission ... a demo video plan" | Pass | `security/docs/FINAL_DEMO_SCRIPT.md:1-35` `# Final Demo Script` 3-5 minute target with 13 numbered beats | Script exists with setup, recording flow, and narration. Actual recorded video link is "Captured; paste the uploaded video link" (`SUBMISSION.md:47`) - unverifiable from repo. |
| Eval dataset reproducible across runs | "results must be reproducible" | Pass | `security/adversarial/evals/week3/README.md:13-19` `python -m app.run_week3_eval --target deployed --suite seed --report-only`; `security/adversarial/app/judge_agent.py:17-26` deterministic regex rules | Cases are JSON files; Judge is deterministic regex; commands documented. Reproducibility is structurally credible. |
| Vulnerability report format includes: unique ID, severity, clinical impact, reproducible attack sequence, observed vs expected, remediation, fix status | "A unique identifier and severity rating ... clinical impact ... minimal, reproducible attack sequence ... observed versus expected ... remediation ... status and fix validation" | Pass | `security/docs/VULNERABILITY_REPORTS.md:38-62` AF-W3-OEMR-001 contains all required fields | Format compliant in all 4 confirmed reports; Documentation Agent `documentation_agent.py:13-29` emits `VulnerabilityReport` model with the same field set. |

Hard-gate summary: 7 Pass, 4 Partial, 1 Fail.

## 2. Required Agent Capabilities

PRD section: "Whatever architecture you choose, the system must collectively be capable of:"

| Capability | Required by PRD | Status | Evidence | Why |
|---|---|---|---|---|
| Generates novel adversarial inputs | "Generating novel adversarial inputs" | Partial | `red_team_agent.py:17-33` three hard-coded `MutationTemplate` constants; only deterministic prefix additions | Templates are static, not generative; `WEEK3_RUBRIC_GRADE.md:28` admits "Mutations are deterministic templates, not LLM-generated adversarial strategies." Novelty is bounded to 3 fixed transforms. |
| Mutates partially-successful attacks | "Mutating partially-successful attacks to probe for bypasses" | Fail | `red_team_agent.py:39-45` `generate_variants` runs on every case regardless of partial-success signal; no Judge->RedTeam feedback edge in `graph.py:175-182` | Mutation is unconditional template expansion, not signal-driven. Graph has no loop from `judge` back into `red_team`. |
| Multi-turn attack sequences | "Targeting multi-turn attack sequences, not just single-prompt injections" | Partial | `evals/week3/cases/multi_turn_manipulation/gradual_policy_erosion.json` present; `red_team_agent.py:54-58` adds a single setup turn | Multi-turn cases exist in fixtures; runtime support is shallow (one extra turn at most via `multi_turn_pressure` template). Real escalation chains not exercised. |
| Consistent evaluation criteria across runs and versions | "Evaluating whether an attack succeeded, with consistent criteria across runs and system versions" | Pass | `judge_agent.py:17-26` deterministic regex; `run_judge_eval.py` test harness | Determinism gives consistency. `WEEK3_RUBRIC_GRADE.md:29` confirms 0 FP / 0 FN on judge fixture set. |
| Prioritizes attack surfaces by coverage gaps and unresolved findings | "Prioritizing which attack surfaces to explore next based on coverage gaps and unresolved findings" | Fail | `graph.py:86-88` `orchestrator` node only does `trace(... "Selected case ...")`; `run_week3_eval.py:66-78` iterates `for case in cases` in load order | Orchestrator is a trace-only no-op. There is no priority queue, no coverage-gap reader, no unresolved-finding feedback. `reporting.py:73-92` produces dashboard rollups but nothing consumes them to pick the next case. |
| Halts/redirects when cost accumulates without signal | "Halting or redirecting when cost is accumulating without producing signal" | Partial | `graph.py:148-159` `stop_policy` checks per-case verdict severity, target instability, human review; `judge_agent.py:60-70` `BUDGET_EXCEEDED` verdict | Halt is per-case budget, not session-level cost accumulation. No suite-level kill switch when many cases burn cost without producing fails. |
| Triggers regression runs on target changes | "Triggering regression runs when the target system changes" | Fail | `run_week3_eval.py:48-53` regression suite must be invoked manually via `--suite regression`; grep for `deployment\|trigger.*regression` in `security/adversarial/app` returned no matches | No deployment hook, no version-diff watcher, no scheduler that triggers a regression run. Target version is recorded (`graph.py:185-190`) but not compared. |

Capability summary: 1 Pass, 3 Partial, 3 Fail.

## 3. Required Roles

PRD names: Red Team, Judge, Orchestrator, Documentation.

| Role | Implementation present (file:line) | Trust level documented (file:line) | Inputs/outputs documented | Coordination protocol documented |
|---|---|---|---|---|
| Red Team | Pass: `security/adversarial/app/red_team_agent.py:36` `class RedTeamAgent` | Partial: `security/docs/W3_ARCHITECTURE.md:35` "Attack prompts, generated variants ... are untrusted" - role-level trust label absent | Pass: `red_team_agent.py:39-45` signature `generate_variants(case, budget) -> list[AttackCase]` | Partial: `graph.py:90-97` only records trace events; no explicit handoff schema |
| Judge | Pass: `security/adversarial/app/judge_agent.py:29` `class JudgeAgent` | Partial: `W3_ARCHITECTURE.md:37` "Deterministic Judge verdicts can block checkpoint/release decisions" - implicit | Pass: `judge_agent.py:30-37` typed kwargs and `JudgeVerdict` return | Pass: `graph.py:111-121` Judge consumes ObservedResponse from Target Runner, returns JudgeVerdict to Documentation |
| Orchestrator | Fail: `graph.py:86-88` `orchestrator` is a trace-only function, not a class; no separate file/class | Fail: no file documents the Orchestrator's trust level; W3_ARCHITECTURE.md never mentions it explicitly | Fail: no priority signals enumerated; node receives state and returns it unchanged | Partial: `W3_SYSTEM_DESIGN.md:77` "Orchestrator -> Red Team -> Target Runner -> Judge -> Documentation Draft -> Regression Store -> Orchestrator" - documented as a loop, but implementation is linear (`graph.py:175-182`) |
| Documentation | Pass: `security/adversarial/app/documentation_agent.py:8` `class DocumentationAgent` | Partial: `W3_ARCHITECTURE.md` does not specify trust level for the Documentation Agent | Pass: `documentation_agent.py:9-29` `draft_report(case, verdict) -> VulnerabilityReport \| None` | Pass: `graph.py:123-131` consumes verdict, emits report, persists via `store.save_report` |

Roles summary: Red Team, Judge, Documentation are present as distinct classes. Orchestrator is the weakest - effectively a stub function rather than a real agent with autonomy.

## 4. Observability Layer

PRD: "you must be able to answer" six questions.

| Question | Status | Evidence | Why |
|---|---|---|---|
| Which attack categories have been tested, and how many cases per category? | Pass | `reporting.py:24-59` `category_rollups`; `reporting.py:88` `"category_rollups": rollups` | Dashboard surfaces per-category counts and untested categories. |
| Current pass/fail rate across categories and versions? | Partial | `reporting.py:24-59` rollup includes verdict counts; `graph.py:185-190` records `target_version` when API exposes it | Pass/fail per category present. "Across system versions" is implicit (target_version is captured but no version-diff view exists in dashboard). |
| Is the target becoming more or less resilient over time? | Partial | `resilience.py:27-70` `build_resilience_snapshot` returns ResilienceSnapshot; `reporting.py:91` `"latest_snapshot": snapshots[0]` | Resilience score exists; only the latest is surfaced. No timeline/trend visualization documented in `ui.py`. |
| Which vulnerabilities are open, in progress, resolved? | Pass | `models.py` enum `ReportStatus` (DRAFT/NEEDS_HUMAN_REVIEW/CONFIRMED/RESOLVED); `reporting.py:61-72` `current_reports` filters by status | Status enum is enforced; dashboard exposes report status. |
| How much did this run cost, and at what rate is cost scaling? | Partial | `reporting.py:90` `"cost_summary": observation_cost_summary(observations)`; `costing.py` builds per-suite summary | Per-run cost summary exists. "Rate of cost scaling" (trend) is not separately surfaced. |
| What is each agent doing, in what order? | Pass | `graph.py:77-84` `trace` writes `AgentTraceEvent`; `run_store.py:223` `save_trace`; each node calls `trace(...)` (`orchestrator:87`, `red_team:94-97`, `target_runner:103-108`, etc.) | Trace events per agent per run are persisted and surfaced. |

Observability summary: 3 Pass, 3 Partial, 0 Fail.

## 5. Regression & Validation Harness

| Bullet | Status | Evidence | Why |
|---|---|---|---|
| "Store confirmed exploits in a versioned, queryable format" | Pass | `regression_harness.py:42-58` `promote_confirmed_report` requires `ReportStatus.CONFIRMED`; `run_store.py` SQLite + `models.py` Pydantic | Stored, schema-versioned. |
| "Run the full regression suite automatically when triggered by the Orchestrator" | Fail | `run_week3_eval.py:48-53` regression cases are loaded only when CLI argument `--suite regression` is passed; no Orchestrator trigger code path | Manual CLI invocation; Orchestrator has no autonomy to start a suite. |
| "Detect when a previously-fixed vulnerability has reappeared" | Partial | `models.py` `RegressionStatus`; `graph.py:136-146` `regression_store` records candidate from any FAIL | Detection of failure on a regression case exists implicitly; no explicit "reappeared after fixed" log/alert path. |
| "Flag when fixing one attack introduces a regression in another category" | Fail | `regression_harness.py` no cross-category diff; `reporting.py` no before/after compare | No cross-category regression detection logic in code. |

Regression summary: 1 Pass, 1 Partial, 2 Fail.

## 6. Documentation Agent

PRD: "At minimum, each report must include:"

| Field | Status | Evidence | Why |
|---|---|---|---|
| Unique identifier and severity rating | Pass | `documentation_agent.py:13-29` returns `VulnerabilityReport` with implicit ID + `severity=verdict.severity`; `VULNERABILITY_REPORTS.md:38` `AF-W3-OEMR-001` + `Severity: High` | Models guarantee both fields. |
| Clear description of vulnerability and clinical impact | Pass | `documentation_agent.py:31-36` `_impact(case, verdict)`; `VULNERABILITY_REPORTS.md:46-48` "SMART/OAuth is the trust boundary..." | Impact string emitted; manual reports include rich impact. |
| Minimal reproducible attack sequence | Pass | `documentation_agent.py:19` `minimal_reproduction=case.input_sequence`; `VULNERABILITY_REPORTS.md:50-54` numbered steps | Steps captured. |
| Observed versus expected behavior | Pass | `documentation_agent.py:20-21` both fields set from verdict + case | Both fields persisted. |
| Recommended remediation | Partial | `documentation_agent.py:37-41` returns boilerplate `"Reproduce the case, inspect the black-box evidence, and strengthen the {category} defense"` | Auto-generated remediation is generic boilerplate; manual reports `VULNERABILITY_REPORTS.md:60` have real remediation but agent's drafts will not. |
| Current status and fix validation results | Pass | `documentation_agent.py:12` `status=ReportStatus.NEEDS_HUMAN_REVIEW if verdict.requires_human_review else ReportStatus.DRAFT` + `VULNERABILITY_REPORTS.md:62` `Fix validation: Not fixed yet...` | Status enum + manual fix-validation lines. |

Documentation summary: 5 Pass, 1 Partial, 0 Fail. PRD bar: "a senior security engineer could reproduce, validate, and fix the vulnerability based solely on what the agent writes" - met for manually authored reports; the automated drafts pass the format check but fail the substance check on remediation.

## 7. Findings Backlog

| ID | Severity | Category | Description | File(s) affected | Est. hours | Rubric points recovered (0-10) |
|---|---|---|---|---|---:|---:|
| R-001 | P0 | Hard gate / ARCHITECTURE.md mismatch | Root `./ARCHITECTURE.md` documents the Co-Pilot, not the multi-agent adversarial platform. PRD requires the root file to name each agent and include an agent-interaction diagram. | `ARCHITECTURE.md`, `security/docs/W3_ARCHITECTURE.md`, `security/docs/W3_SYSTEM_DESIGN.md` | 2-3 | 9 (likely worth a full PRD line item; one of the named hard gates) |
| R-002 | P0 | Hard gate / multi-agent vs pipeline | LangGraph is a linear pipeline with a stub Orchestrator. PRD explicitly says a pipeline does not satisfy. | `security/adversarial/app/graph.py`, `security/adversarial/app/red_team_agent.py` | 6-10 | 8 (Multi-agent architecture is a graded line; risk of "pipeline" verdict at review) |
| R-003 | P0 | Hard gate / AI cost analysis | Cost analysis "Architecture Changes By Scale" is keyed to clinician users, not 100/1K/10K/100K adversarial test runs. The run-count table is exactly cost-per-token x n, which the PRD explicitly forbids. | `AI_COST_ANALYSIS.md:150-215` | 2-4 | 7 |
| R-004 | P1 | USERS.md scope | Adversarial-platform user section is 9 lines, bullet list only; lacks workflows and automation justification for the platform's users. | `USERS.md:176-184` | 1-2 | 5 |
| R-005 | P1 | Capability / mutate partial successes | Mutations are unconditional templates; no Judge->RedTeam feedback edge. | `security/adversarial/app/red_team_agent.py`, `security/adversarial/app/graph.py:175-182` | 4-6 | 5 |
| R-006 | P1 | Capability / prioritize attack surfaces | Orchestrator does not read coverage rollups or open-finding queue to pick next case. | `security/adversarial/app/graph.py:86-88`, `security/adversarial/app/run_week3_eval.py:66-78` | 4-8 | 6 |
| R-007 | P1 | Capability / regression triggers | No deployment hook, no version-diff watcher; regression suite runs only via manual CLI. | `security/adversarial/app/run_week3_eval.py:48-53` | 3-5 | 4 |
| R-008 | P1 | Regression harness gaps | No cross-category regression detection; no "previously-fixed reappeared" alert. | `security/adversarial/app/regression_harness.py`, `security/adversarial/app/reporting.py` | 3-5 | 4 |
| R-009 | P2 | Eval path drift | PRD specifies `./evals/`; actual adversarial eval root is `security/adversarial/evals/week3/`. Root `evals/` directory exists but holds Co-Pilot data. | `evals/`, `security/adversarial/evals/week3/`, `SUBMISSION.md` | 1 | 2 |
| R-010 | P2 | Documentation Agent boilerplate remediation | Auto-drafted reports get a generic remediation string; only manual reports have substantive remediation. | `security/adversarial/app/documentation_agent.py:37-41` | 2-3 | 2 |
| R-011 | P2 | Orchestrator role documentation | No explicit trust-level statement for Orchestrator or Documentation agents in any architecture doc. | `security/docs/W3_ARCHITECTURE.md`, `ARCHITECTURE.md` | 1 | 2 |
| R-012 | P2 | Observability trend visibility | Only the latest resilience snapshot is surfaced; no trend timeline view; cost-scaling rate not visualized. | `security/adversarial/app/ui.py`, `security/adversarial/app/reporting.py` | 2-3 | 2 |
| R-013 | P2 | Multi-turn depth | Multi-turn cases exist but mutation only adds a single setup turn; no real escalation. | `security/adversarial/app/red_team_agent.py:54-58` | 3-5 | 2 |
| R-014 | P2 | Demo video uncaptured-link risk | `SUBMISSION.md:47` says "Captured; paste the uploaded video link" - no committed URL means reviewer cannot find it. | `SUBMISSION.md` | 0.5 | 2 |

## 8. Summary

- Hard gates Pass/Partial/Fail: **7 Pass, 4 Partial, 1 Fail** (12 total).
- Top 5 rubric risks:
  1. **R-001** Root `ARCHITECTURE.md` is the wrong document (Co-Pilot, not multi-agent platform). A reviewer following the PRD's explicit file path will find no Red Team, Judge, Orchestrator, or Documentation Agent named in the required file.
  2. **R-002** The "multi-agent" system is structurally a linear pipeline; the project itself admits this in `WEEK3_RUBRIC_GRADE.md:27`. PRD bars single-agent/pipeline.
  3. **R-003** AI cost analysis fails the PRD's own "not simply cost-per-token x n" clause and ties architectural changes to clinician users instead of test runs.
  4. **R-006** Orchestrator does not actually orchestrate - it traces and returns state unchanged. The PRD's entire "visibility & observability" section hinges on this loop.
  5. **R-007** Regression triggers are manual; "triggering regression runs when the target system changes" is unimplemented.
- Estimated total rubric points at risk: ~35-45 (out of ~100). The three P0 hard-gate misses are individually large, and the four P1 capability gaps compound across the Multi-Agent Adversarial System bullet list.
- Overall assessment: The platform has the right *shape* - distinct classes for Red Team, Judge, Documentation, plus deterministic evals, vulnerability reports, an observability dashboard, and a deployed operator surface - but the connective tissue that makes it adversarial-by-design is thin. The Orchestrator is a stub, mutations are not feedback-driven, regression triggers are manual, and the PRD-named root files (`./ARCHITECTURE.md`, `./USERS.md`) describe the Week 1/2 target rather than the Week 3 platform. With ~10-15 hours of focused work on R-001 through R-003 plus R-006, this graduates from "checked the boxes" to "defensible to a CISO," which is the PRD's stated standard.

AMBIGUOUS - needs human read:
- PRD says `./evals/` and `./USERS.md`. The repo has `evals/` (Co-Pilot Week 2) and `security/adversarial/evals/week3/` (Week 3). Reviewer interpretation of the literal path may vary; marked Partial above.
- Whether the four `AF-W3-OEMR-00x` web-surface reports count as adversarial-AI findings or only as web-pen-test findings. PRD does not specify the report must be an LLM jailbreak; the count of three is met by web-surface reports.
