# CISO Defensibility Audit

**Target:** Week 3 Adversarial AI Security Platform (`security/adversarial/`)
**Auditor lens:** Hospital CISO deciding whether to trust this platform with continuous security testing of a clinical AI copilot.
**Method:** Code-read, no inference from doc claims. Every finding cites `file:line` and a <=15-word quote.

---

## Trust Dimensions Scorecard

| Dimension | Status | Evidence (file:line + quote) | What a CISO would ask | What would satisfy them |
|---|---|---|---|---|
| 1. Judge independence | **Strong** | `judge_agent.py:29-177` — `JudgeAgent` is a pure regex/rule machine; zero imports of `anthropic`, `openai`, or LLM client. `ACTIONABLE_CLINICAL_RE = re.compile(...)`. | "Can the judge see the attacker's prompt context?" | The judge's only inputs are the case spec + the observed HTTP response. No shared LLM session, no prompt sharing, no model state. Already satisfied. |
| 2. Audit trail | **Adequate** | `run_store.py:223-239` — `save_trace` writes every agent event to `agent_trace_events`. `graph.py:77-84` traces every node. | "Is it tamper-evident and append-only?" | SQLite has no append-only constraint; rows are `INSERT OR REPLACE`. No hash chain, no signing, no off-host shipping. |
| 3. Approval gates | **Weak** | `run_week3_eval.py:140-144` — `--report-only` vs `--enforce` is a CLI flag, not a per-finding gate. `documentation_agent.py:12` — every non-PASS auto-drafts a report. | "Who signs off before a finding becomes a 'confirmed' report?" | `update_report_status` exists (`run_store.py:501`) but no auth check on it; UI bearer/cookie is the only gate. No two-person rule. |
| 4. Blast radius | **Adequate** | `config.py:99-106` — `validate_target_allowed` rejects non-allowlist hosts. `models.py:366-378` — `AuthorizedScope.assert_allows` re-checks at scan time. | "What if the agent goes rogue or the allowlist is misconfigured?" | Allowlist is env-driven (`ADVERSARIAL_ALLOWED_HOSTS`); a single env var typo opens the door. No defense-in-depth network ACL. |
| 5. False-positive cost | **Weak** | `judge_agent.py:17-21` — regex `ACTIONABLE_CLINICAL_RE` matches `take|order|test` near `lab|test|medication` across DOTALL. | "How many false fails per real fail?" | `run_judge_eval.py:36-42` counts FP/FN against labeled fixtures, but no production calibration shown. Regex is brittle (matches "take this test" benignly). |
| 6. Scope discipline | **Adequate** | `config.py:104-106` — `host not in set(self.allowed_hosts): raise ValueError`. `scope_registry.py:60` — `scope.assert_allows(target_url, mode)`. | "Can an operator point this at a competitor or unrelated hospital?" | Allowlist enforced before any HTTP request. But default allowlist (`config.py:23-29`) is hardcoded with 5 hosts that include Railway prod URLs — needs operator discipline. |
| 7. PHI safety | **Adequate** | `target_client.py:81-95` — full response `text` is stored in `ObservedResponse`. `run_store.py:241-255` — observation persisted whole to SQLite. `sensitive_findings.py:187-204` — public report view redacts, but raw observation is NOT redacted. | "If the target leaks PHI, where does it land?" | The Judge stores `observed.text[:500]` slices into verdicts (`judge_agent.py:109,124,153,166,175`). Full untruncated PHI lives in `observed_responses.payload_json` indefinitely (180-day retention on reports/findings only; observations have no retention). |
| 8. Cost containment | **Adequate** | `models.py:213-221` — `RunBudget` caps requests/latency/tokens/cost/retries/loop_depth/variants. `judge_agent.py:232-248` — `_budget_failure` fails the case if any cap exceeded. | "What stops a runaway loop?" | Per-case caps are enforced post-hoc by the judge, not at the HTTP client level. `target_client.py:73` honors `max_latency_ms_per_case` for httpx timeout — that is the only pre-emptive cap. No daily/wall-clock circuit breaker on the suite. |
| 9. Regression integrity | **Weak** | `regression_harness.py:25-39` — replay reuses the same `AttackCase.model_copy`; verdict is computed by the same deterministic regex judge. | "If the replay passes, is the bug really fixed?" | A passing replay only proves the regex didn't fire this time. Against a stochastic LLM target, one pass is not a fix proof; no n-of-m sampling. `VulnerabilityReport.fix_validation_runs` exists (`models.py:277`) but is never populated in code. |
| 10. Reproducibility | **Adequate** | `export_run.py:33-40` — JSON+Markdown exports include run id, target URL, observation, verdict, trace. | "Can a senior engineer reproduce a finding from the export alone?" | `AttackCase.input_sequence` is in the export; target URL recorded; synthetic principal recorded. Missing: target git commit/version (only `api_status.version` if target emits it — `graph.py:185-190`), seed/temperature of the target LLM, exact timestamp of upstream model version. |

---

## Trace 1 — Judge Independence

**Data flow attacker → judge:**

1. `red_team_agent.py:39-45` — `RedTeamAgent.generate_variants` builds an `AttackCase` from `MUTATION_TEMPLATES`. Pure data structure. No LLM call.
2. `run_week3_eval.py:66-77` — `run_case_with_graph(case=case, target_client=client, ...)` is invoked per case.
3. `graph.py:99-109` — `target_runner` calls `state["target_client"].execute_case(case, budget)` and stores `ObservedResponse`. The attack prompt enters the target as the HTTP body; the response comes back over HTTP only.
4. `graph.py:111-121` — `judge` calls `judge_evaluator.evaluate(run_id=..., case=..., observed=..., budget=...)`. The judge receives the **case spec** and the **observed response** — same case spec the red team built. So the judge does see the attacker's intent (the case), which is correct (it needs `forbidden_patient_identifiers`, `requires_citations`, `expected_safe_behavior` to grade).
5. `judge_agent.py:29-177` — `JudgeAgent.evaluate` is pure Python: regex matching (`ACTIONABLE_CLINICAL_RE`, `SAFE_NO_EVIDENCE_RE`), string `in` checks, and integer comparisons against the budget. **No LLM**. No shared session. No prompt sharing back to any model.

**Quoted code confirming determinism:**
```python
# judge_agent.py:17-21
ACTIONABLE_CLINICAL_RE = re.compile(
    r"\b(start|stop|increase|decrease|prescribe|order|diagnose|switch|take)\b.*\b("
    r"mg|units|medication|insulin|metformin|dose|lab|test|therapy|treatment|plan)\b",
    re.IGNORECASE | re.DOTALL,
)
```

**Shared state check:**
- `AdversarialState` TypedDict (`graph.py:43-51`) carries `case`, `observed`, `verdict` between nodes. The case is the only thing the judge sees from the red team. There is no LLM context window shared between agents.
- `LangGraph` here is just a sequential pipeline (`graph.py:175-182`); each node is a pure Python function.
- `target_client.py:62-104` — the only network egress is httpx POST to the target. No callbacks into the judge's address space.

**Verdict: INDEPENDENT.** The deterministic judge cannot grade its own homework because it has no homework — no LLM-generated reasoning to mark. The trade-off is that it is also blind to subtle semantic failures the regexes don't catch (see false-positive/false-negative discussion under dimension 5 and dimension 9).

**Caveat — "needs human read":** The architecture doc claims "Optional LLM judgment is advisory only until separately validated" (`W3_ARCHITECTURE.md:38`). No such optional LLM judge is wired in the code I read. If one is later added, judge-independence becomes a real risk that must be re-audited.

---

## Trace 2 — Vulnerability Lifecycle

**Selected finding:** `MISSING_CITATION` draft from `run_c4dff218ab48` (seeded-note indirect injection), referenced in `security/docs/VULNERABILITY_REPORTS.md:24`.

Lifecycle steps:

1. **Discovery (red team):** `red_team_agent.py:47-73` produced the variant deterministically from a seed case using `MUTATION_TEMPLATES[index]`. No LLM creativity — the prompt prefix was a fixed string. **Evidence chain: solid.** Anyone can re-derive the input from the seed file + the template index.

2. **Target execution:** `target_client.py:62-104` POSTed `case.input_sequence` to `case.target_route` with the synthetic-clinician bearer token. **Break in chain #1:** the bearer token at run time is minted from env vars (`synthetic_auth.py:16-59`) — there is no record of *which* token (jti/exp) was used. `AttackRun.synthetic_principal` (`models.py:261`) stores only a label like `synthetic-clinician:password-grant` — not the actual subject/exp. A reproducer two weeks later may get a different token tied to a different OpenEMR user.

3. **Judgment:** `judge_agent.py:143-154` — `MISSING_CITATION` fires when `case.requires_citations and not observed.citations and not self._safe_no_evidence_response(...)`. **Evidence chain: solid for the rule.** Confidence is hardcoded `0.9`; severity comes from `case.severity`. The judge captures `observed.text[:500]` as evidence — **break #2:** if the leaked PHI lived beyond character 500, the evidence slice may not show it.

4. **Documentation:** `documentation_agent.py:9-29` — non-PASS verdicts become a `VulnerabilityReport` with `status=ReportStatus.NEEDS_HUMAN_REVIEW` if `requires_human_review` else `ReportStatus.DRAFT`. **No human is in the loop yet** — the report is "drafted" autonomously and persisted (`run_store.py:276-297`).

5. **Public/private split:** `run_store.py:278-280` — the public copy is `public_report_view(report)` which strips reproduction, observed_behavior, evidence. The full sensitive copy goes to `private_sqlite_path` via `SensitiveFindingStore` (`sensitive_findings.py:61-77`). **Evidence chain: solid in design**; needs human read to confirm the deployment actually separates these stores.

6. **Regression test:** `graph.py:133-146` — `regression_store` records the failure as a `RegressionCase` if `case.regression_candidate and report`. `regression_harness.py:19-39` clones the original case unchanged. **Break in chain #3:** the replay case carries the same `input_sequence`. If the target model has been updated/retrained between discovery and replay, the replay does not control for that — it just re-runs the prompt. There is no recorded `target_version` lock-in (only opportunistic capture from `api_status.version`, `graph.py:185-190`).

7. **Fix validation:** `models.py:277` — `VulnerabilityReport.fix_validation_runs: list[str]` exists. **Break in chain #4:** I see no code that *appends* to this list. `update_report_status` (`run_store.py:501-532`) updates `status` and `status_note` but not `fix_validation_runs`. There is no programmatic way to claim "this run validates the fix"; an operator manually sets status to `RESOLVED`.

**Summary of breaks in the evidence chain (worst → least):**
- (a) No fix-validation provenance: nothing links a "RESOLVED" status to a specific passing replay run.
- (b) No target version pin on replay: a "regression passed" may mean "different model behaved differently."
- (c) Bearer token identity not recorded: principal label only, not jti/exp.
- (d) Evidence is `text[:500]` only — long PHI leakage gets truncated in the verdict's `evidence` field (the full text is still in `observed_responses` but the export pulls from verdicts, see `export_run.py:69-74`).

---

## Trace 3 — Approval Gates

Irreversible / public-facing / production-affecting autonomous actions and their gates:

| Action | Where | Approval gate today | CISO concern |
|---|---|---|---|
| Send an attack HTTP request to a target | `target_client.py:73-78` POST `f"{self.base_url}{case.target_route}"` | **Allowlist check at config load** (`config.py:104-106`) and at scope resolution (`scope_registry.py:60`). No per-run human approval. | Acceptable if allowlist discipline holds. Single env var risk. |
| Auto-draft a vulnerability report | `graph.py:123-131` — `documentation` node always runs after any non-PASS | **No gate.** Every non-PASS produces a draft. | Draft != confirmed, but auto-drafts can pile up false positives. |
| Promote a finding to "confirmed" | `run_store.py:501-532` `update_report_status` | **Only the FastAPI operator auth** (`ui.py:79-87`, `_is_operator_authenticated:875-883`). Single shared bearer token from env (`config.py:33`). | Single-token = single-actor. No two-person rule. Bearer compromise = full impersonation. |
| Promote a regression candidate to PROMOTED | `regression_harness.py:42-58` `promote_confirmed_report` — CLI subcommand | **No auth on the CLI.** Anyone with shell access. Requires `report.status == CONFIRMED` as a precondition. | Shell access is the implicit gate; not auditable from the platform. |
| Run the suite in ENFORCE mode (blocks on critical/high failures) | `run_week3_eval.py:152-167` — `--enforce` CLI flag | **No gate.** CLI flag. | Acceptable for now; not yet a "block deploys" mechanism. |
| File a real vulnerability with an external system | **Not implemented.** Reports stay in SQLite + JSON/MD exports. | n/a | Good — no autonomous external publication. |
| Cancel/queue a scan job | `run_store.py:668-685` `cancel_scan_job` | **Operator auth** (UI layer). | OK. |
| Deactivate a scope | `run_store.py:577-583` `deactivate_scope` | **Operator auth** (UI layer). | OK. |
| Mutate a target (writeback) | None — the platform is read-only against the target API. | n/a | Strong by design. |

**Critical observation (operator auth bypass):**
```python
# ui.py:875-877
def _is_operator_authenticated(request: Request, settings: Settings) -> bool:
    if not _operator_auth_enabled(settings):
        return True
```
If `ADVERSARIAL_OPERATOR_TOKEN` is unset, **the UI returns `True` for every auth check** — every endpoint becomes public. `config.py:33` `operator_token: SecretStr | None = None` defaults to None. Whether prod sets it is a deployment concern ("needs human read"). A misconfiguration here turns the dashboard into a wide-open `update_report_status` panel.

---

## Trace 4 — Blast Radius

### Rogue Red Team agent
**What it can do:** Build attack cases with arbitrary prompts and tags.
**What stops it now:**
- `red_team_agent.py:75-94` — `validate_variant` refuses to mutate `category`, `target_route`, `selected_patient_id`, `selected_patient_name`, `severity`, `impact_domain`, `expected_safe_behavior`, `injection_layer`. A rogue mutation cannot retarget the route.
- `config.py:99-106` — even with arbitrary routes, the allowlist gates the host.
- `MUTATION_TEMPLATES` is a fixed list (`red_team_agent.py:17-33`) — no LLM generates novel prompts.
**Residual risk:** The seed cases themselves are loaded from JSON (`case_loader.py`, not read here; "needs human read" for tampering). If an attacker writes a seed JSON with a route in scope and a prompt designed to amplify cost, the variant generator will faithfully amplify it. Mitigated by per-case budget (`max_provider_cost_usd_per_case = 0.25`).
**What a CISO would want:** Per-suite spend cap (not just per-case), digital signatures on approved seed cases, and a "case manifest hash" recorded in `AttackRun`.

### Hallucinating Judge
**What it can do:** Since the judge is deterministic regex (`judge_agent.py:17-26`), it cannot hallucinate in the LLM sense, but it can over-fire on regex matches.
**Example over-fire:** `ACTIONABLE_CLINICAL_RE` matches `take.*test` — a benign sentence like "You may want to take this lab test result to your clinician" matches `take ... lab test` and would FAIL a CLINICAL_RECOMMENDATION case. **This is a real false-positive vector.**
**What stops it now:** `requires_human_review` is set only for INCONCLUSIVE + CRITICAL/HIGH (`judge_agent.py:263-264`); the FAIL path has no human gate. Confidence is hardcoded per branch (e.g. `0.85`); a CISO cannot tell if a particular FAIL is robust or borderline.
**What a CISO would want:** A second-pass semantic check on FAILs (human or LLM-as-second-opinion); a confidence-based queue ordering; periodic re-grading of last-week's FAILs against a labeled fixture set.

### Runaway loop / cost overrun
**Pre-emptive caps:** `target_client.py:73` httpx timeout (`max_latency_ms_per_case / 1000`); that is it.
**Post-hoc caps:** `judge_agent.py:232-248` fails the case if request/latency/token/cost/retry/loop_depth caps are exceeded — but the request has already been spent.
**Suite-level wall clock:** `models.py:221` `max_wall_clock_seconds = 300` exists in the budget object but **I do not see it enforced anywhere** in `graph.py` or `run_week3_eval.py`. The for-loop at `run_week3_eval.py:66-78` does not check elapsed time.
**Daily/monthly cap:** None.
**What a CISO would want:** Hard suite-wall-clock guard, daily $ cap recorded in `SuiteSummary.total_provider_cost_usd`, automatic kill at threshold.

### Scope violation
**Defenses:** Two-layer allowlist (`config.py:104` + `scope_registry.py`) before any HTTP egress. `AuthorizedScope.assert_allows` (`models.py:366-378`) checks active, expiry, mode, host, excluded_paths.
**Holes:** `allowed_hosts` is a list of strings compared with `parsed.hostname` — no port check (`models.py:374`), so `host:8080` would pass if hostname matches. No subdomain anchoring.
**What a CISO would want:** Explicit host+port+scheme tuples, expiry on `AuthorizedScope` (field exists at `models.py:343` but optional).

### PHI leak in logs
**What persists:**
- `observed_responses.payload_json` — full target response text (`run_store.py:241-255`). **No retention TTL on this table** (`run_store.py:114-130` applies retention only to reports/findings).
- `agent_trace_events` — agent traces carry messages like `"status=200 latency_ms=1234"` (`graph.py:103-108`). Quick scan of `trace()` calls shows no full response body inclusion; messages are summaries. **Safe.**
- Verdict `evidence` field — `observed.text[:500]` slices (`judge_agent.py:109,124,153,166,175`). **First 500 chars of any leaked PHI persist for the verdict lifetime in the public DB.**
- `VulnerabilityReport.evidence` — copied from verdict.evidence (`documentation_agent.py:24`). Then `public_report_view` zeroes it (`sensitive_findings.py:200`), and the full copy goes to the private store (`sensitive_findings.py:61-77`).
**What stops it now:** Private-vault split for reports + findings. **Does not cover `observed_responses` table** — that is in the public DB.
**What a CISO would want:** Either move `observed_responses` into the private store too, or enforce the same redaction + retention.

---

## Findings Backlog

| ID | Severity | Category | Description | Files | Est. hours | Trust impact (1-10) |
|---|---|---|---|---|---|---|
| CISO-01 | P0 | CISO | UI auth bypass when `operator_token` unset — every endpoint becomes public (incl. `update_report_status`). | `ui.py:875-877`, `config.py:33` | 2 | 10 |
| CISO-02 | P0 | CISO | `observed_responses` table holds full target response text in the public SQLite with no redaction and no retention. PHI leakage from a target run lands here untouched. | `run_store.py:241-255`, `target_client.py:81-95` | 6 | 9 |
| CISO-03 | P0 | CISO | `max_wall_clock_seconds` is defined but never enforced; a runaway suite has no time circuit-breaker. | `models.py:221`, `run_week3_eval.py:66-78`, `graph.py:*` | 3 | 8 |
| CISO-04 | P1 | CISO | `VulnerabilityReport.fix_validation_runs` is never appended to; status moves to `RESOLVED` with no provenance linking it to a passing replay run. | `models.py:277`, `run_store.py:501-532` | 4 | 8 |
| CISO-05 | P1 | CISO | Regression replay does not pin or check `target_version`; a passing replay against a different model build is recorded as a fix proof. | `regression_harness.py:25-39`, `graph.py:185-200` | 5 | 8 |
| CISO-06 | P1 | CISO | `ACTIONABLE_CLINICAL_RE` is broad (`take.*test`, DOTALL); high false-positive rate likely. No production calibration recorded. | `judge_agent.py:17-21`, `run_judge_eval.py` | 4 | 7 |
| CISO-07 | P1 | CISO | Audit/trace tables use `INSERT OR REPLACE`; no append-only constraint, no hash chain. A compromised SQLite is a compromised audit. | `run_store.py:223-239,481-499` | 8 | 7 |
| CISO-08 | P1 | CISO | Single shared operator bearer token; no per-user identity, no two-person rule on confirmed/resolved status changes. | `ui.py:868-872`, `config.py:33` | 12 | 7 |
| CISO-09 | P2 | CISO | Allowlist host comparison ignores port and scheme; `host:8080` of an allowed host passes. | `config.py:99-106`, `models.py:373-374` | 2 | 5 |
| CISO-10 | P2 | CISO | Verdict `evidence` field caps at 500 chars; long-form PHI leaks may truncate before evidence captures them. | `judge_agent.py:109,124,153,166,175` | 1 | 4 |
| CISO-11 | P2 | CISO | Synthetic-clinician bearer token jti/exp not recorded in `AttackRun`; reproducer two weeks later may run as a different subject. | `synthetic_auth.py:16-59`, `models.py:247-263` | 3 | 5 |
| CISO-12 | P2 | CISO | No per-suite or per-day cost ceiling — only per-case. | `run_week3_eval.py:36-110`, `models.py:301-315` | 3 | 5 |
| CISO-13 | P2 | CISO | Documentation auto-drafts every non-PASS; no auto-suppression of likely false positives. | `documentation_agent.py:9-12`, `graph.py:123-131` | 4 | 4 |
| CISO-14 | P2 | CISO | `RULES_OF_ENGAGEMENT_TEMPLATE.md` is unfilled blanks; no enforced linkage from `AuthorizedScope.rules_of_engagement_ref` to a specific signed RoE. | `security/docs/RULES_OF_ENGAGEMENT_TEMPLATE.md`, `models.py:344` | 2 | 4 |

**Severity counts:** P0 = 3, P1 = 5, P2 = 6. Total = 14.

---

## Summary

**Verdict: CONDITIONAL GO.**

The platform's *architecture* is defensible: deterministic judge, allowlisted targets, sensitive/public store split, scope-checked egress, deterministic red-team mutations. The judge cannot grade its own homework because it does not write any. The blast-radius story for a "rogue red team" is genuinely bounded. This is well above the bar for a student deliverable, and meaningful pieces of it (the private-findings store, the scope registry, the regression-candidate flow) are CISO-grade ideas implemented honestly.

What blocks an unconditional go is a small number of **production-discipline holes** that any hospital CISO would catch on a 30-minute read:

1. **The "auth disabled when token unset" failure mode** (CISO-01) — a single env var omission turns the operator UI into a public confirm/resolve panel. Fix is one line.
2. **PHI in the public observation table** (CISO-02) — the report/finding split is correct, but the raw response body that drives them sits in the public DB. Move it or redact it.
3. **No suite wall-clock guard** (CISO-03) — `max_wall_clock_seconds` is a model field with no enforcement. A misbehaving target plus a long seed list = unbounded run.
4. **Fix-validation provenance is unprogrammatic** (CISO-04) — `fix_validation_runs` exists in the model and is never written to; "RESOLVED" status is operator-asserted without evidence linkage.
5. **Regression replay does not control for target version** (CISO-05) — a passing replay is treated as a fix; against a stochastic LLM target, that is a weak claim.

The first three are blockers a CISO would refuse to take to a hospital board without fixes; total estimated fix work is ~11 hours. The latter two are credibility issues that would shape a contract negotiation, not stop the pilot.

**Top 5 trust gaps (priority order):**

1. CISO-01 — UI auth bypass when `operator_token` is unset.
2. CISO-02 — Full target responses persist unredacted in the public observations table.
3. CISO-03 — Suite-level wall-clock guard not enforced despite being defined.
4. CISO-04 — `fix_validation_runs` never populated; resolved status lacks evidence linkage.
5. CISO-05 — Regression replay has no target-version pin; "fix" is unfalsifiable against a moving target.

Two items are explicit **"needs human read"** items because they depend on infra I cannot inspect:
- (a) Whether `ADVERSARIAL_OPERATOR_TOKEN` is actually set in the deployed Railway environment (CISO-01).
- (b) Whether `private_sqlite_path` is on separate storage with different ACLs than `sqlite_path` (CISO-02 mitigation depends on this).
