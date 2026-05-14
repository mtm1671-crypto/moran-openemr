# Code Quality Audit (Python — security/adversarial/)

Scope: 25 modules under `security/adversarial/app/` plus 10 test modules under
`security/adversarial/tests/`. Dependency manifest (`pyproject.toml`) and
`Dockerfile` reviewed for dependency bloat and runtime hygiene.

## File Inventory

| File | Purpose (one line) | LOC | Imports out / in | Has tests? | Smell count |
|---|---|---:|---:|:---:|---:|
| app/__init__.py | Package marker; exports `__version__`. | 6 | 0 / 0 | n/a | 0 |
| app/case_loader.py | Load attack cases from JSON tree. | 52 | 1 / 2 | Yes | 1 |
| app/config.py | Pydantic settings + allowlist guard. | 140 | 1 / many | Yes | 4 |
| app/costing.py | Roll up cost/verdict counters. | 67 | 1 / 2 | Indirect | 1 |
| app/documentation_agent.py | Draft vulnerability report from verdict. | 42 | 1 / 2 | Indirect | 0 |
| app/export_run.py | Build run JSON/Markdown export. | 113 | 2 / 2 | Yes | 1 |
| app/graph.py | LangGraph orchestrator for one case run. | 214 | 6 / 2 | Yes | 4 |
| app/judge_agent.py | Deterministic verdict rules. | 277 | 1 / 3 | Yes | 3 |
| app/knowledge_base.py | Load static knowledge base JSON. | 35 | 0 / 1 | Yes | 1 |
| app/models.py | Pydantic models & enums. | 477 | 0 / many | Indirect | 3 |
| app/ports.py | Protocol contracts. | 55 | 1 / 2 | No | 1 |
| app/red_team_agent.py | Generate bounded case variants. | 95 | 1 / 2 | Yes | 1 |
| app/regression_harness.py | Promote reports to regression cases. | 91 | 3 / 2 | Yes | 1 |
| app/reporting.py | Verdict/coverage rollups for UI. | 93 | 2 / 2 | Indirect | 1 |
| app/resilience.py | Risk-weighted scoring. | 108 | 1 / 2 | Yes | 2 |
| app/run_judge_eval.py | Judge fixture evaluator (CLI). | 89 | 2 / 2 | Yes | 0 |
| app/run_site_scan.py | CLI for authorized passive scans. | 94 | 5 / 1 | Yes | 0 |
| app/run_store.py | SQLite persistence facade. | 774 | 3 / many | Yes | 5 |
| app/run_week3_eval.py | CLI entrypoint for suites. | 172 | 11 / 1 | Partial | 2 |
| app/scope_registry.py | Default client/project/scope seeder. | 62 | 3 / 2 | Yes | 1 |
| app/sensitive_findings.py | Private-store for redacted detail. | 229 | 1 / 1 | Yes | 2 |
| app/site_scan_workflow.py | Job lifecycle around scanner. | 108 | 6 / 2 | Indirect | 2 |
| app/site_scanner.py | Passive bounded scan checks. | 1046 | 3 / 3 | Yes | 5 |
| app/synthetic_auth.py | OAuth password-grant for clinician. | 71 | 2 / 1 | No | 2 |
| app/target_client.py | Black-box HTTP client for cases. | 189 | 1 / 2 | Partial | 2 |
| app/ui.py | FastAPI operator UI. | ~1980 | many / 2 | Yes | 8 |
| tests/test_config_and_store.py | Config + RunStore tests. | 277 | — | — | 1 |
| tests/test_gap_closure.py | Resilience/regression/judge eval. | 142 | — | — | 1 |
| tests/test_graph_and_export.py | Graph + export tests. | 162 | — | — | 1 |
| tests/test_judge_agent.py | Judge agent unit tests. | 116 | — | — | 0 |
| tests/test_knowledge_base.py | KB JSON shape tests. | 26 | — | — | 1 |
| tests/test_models_and_cases.py | Case JSON + enum coverage. | 53 | — | — | 0 |
| tests/test_run_week3_eval.py | `blocking_verdicts` only. | 44 | — | — | 1 |
| tests/test_site_scanner.py | Scanner unit tests with MockTransport. | 474 | — | — | 0 |
| tests/test_target_client.py | One SSE-parse test. | 33 | — | — | 1 |
| tests/test_ui.py | FastAPI route + helper tests. | 316 | — | — | 1 |

## Findings By File

### app/config.py
- `config.py:21` Hardcoded deployment URL outside env: `"https://copilot-api-production-9f84.up.railway.app"`. P2 — make this an env default.
- `config.py:24-29` `allowed_hosts` default factory inlines four production Railway hosts. Should come from env in non-dev. P2.
- `config.py:51` `service_account_token: str | None = None` — defined but never referenced anywhere in repo. Dead config. P2.
- `config.py:46-50` Magic OAuth scope string baked into code rather than env; identical content in `synthetic_auth.py` usage. P3.

### app/models.py
- `models.py:449-460` `CampaignPriority` model with 9 fields is defined but never imported, instantiated, persisted, or tested anywhere. Pure speculative type. P2 — dead code.
- `models.py:221` Default `max_wall_clock_seconds = 300` duplicates `config.Settings.max_wall_clock_seconds` (line 59) — divergence risk. P3.
- `models.py:213-221` `RunBudget` defaults duplicate all `Settings.max_*` defaults; `build_budget()` re-copies them — single source of truth lost. P3.

### app/ports.py
- `ports.py:20-54` Three `Protocol`s declared but only one (`SiteScanner`) is referenced via DI; `TargetCaseExecutor` and `JudgeEvaluator` are only used as type hints in `graph.py`. `ReportDrafter` has a single implementation (`DocumentationAgent`). Speculative seams with no second implementation. P2.

### app/case_loader.py
- `case_loader.py:39-51` `_default_case_root` tries three paths silently — a wrong env value falls through without warning. P3.

### app/costing.py
- `costing.py:19-28` Filter falls back to "use all observations" if metadata doesn't match — masks bugs where `run_id` keying is wrong. Quote: `"if not relevant_observations: relevant_observations = observations"`. P2.

### app/judge_agent.py
- `judge_agent.py:17-21` Regex hard-codes drug names (`metformin`, `insulin`). Brittle; should be config-driven. P2.
- `judge_agent.py:127-131` Magic strings for tool outcomes (`"refused"`, `"requires_review"`, `"not_invoked"`). Should be enum or shared constant. P2.
- `judge_agent.py:38, 49, 84, 100, 113, 126, 143, 156` Deep procedural if-chain with no early-exit table; many branches return identical verdict shape. P3 — refactor candidate.

### app/red_team_agent.py
- `red_team_agent.py:17-33` Three template `MutationTemplate`s baked into module; new templates require code change. P3.

### app/regression_harness.py
- `regression_harness.py:23-31` Mutation rationale is hardcoded string ("Regression replay generated from a non-pass verdict."). P3.

### app/knowledge_base.py
- `knowledge_base.py:31-33` `isinstance(entry, dict) or not isinstance(entry.get("id"), str)` — silently raises ValueError without surfacing which entry failed. P3.

### app/graph.py
- `graph.py:30-40` Catches `ImportError` and falls back to `PendingDeprecationWarning` — fine, but the warning suppression is global at module import. Quote: `"warnings.filterwarnings(\"ignore\", category=warning_category)"`. P2 — side-effect-on-import.
- `graph.py:69-72` Re-import of langgraph inside function with `RuntimeError` rewrap when missing. Module already imports `from langgraph.graph import END, StateGraph` lazily — split across two strategies. P3.
- `graph.py:100` `asyncio.run(...)` inside a sync graph node — will explode if graph is ever called from a running loop. No test exercises this. P2.
- `graph.py:43-51` `AdversarialState(TypedDict, total=False)` puts the store and target_client into the workflow state — couples state container to runtime collaborators. P2.

### app/reporting.py
- `reporting.py:53-55` `verdict_name in {verdict.value for verdict in Verdict}` iterates all values per loop iteration; minor perf nit. Also shadows outer name. P3.

### app/resilience.py
- `resilience.py:10-24` Magic scoring weights baked in (28/18/9/4/1 and 12/11/10/6/4/3) with no rationale in code. P2.
- `resilience.py:58-68` Final score blends 5 weighted components plus 2 absolute penalties. No test asserts these specific weights; weight changes are silent. P2.

### app/run_store.py
- `run_store.py:80-90` `initialize()` runs migration script then issues ad-hoc `ALTER TABLE` re-checks (`_ensure_site_scan_scope_columns`, `_ensure_site_scan_finding_columns`) — schema drift hack instead of versioned migrations. P2.
- `run_store.py:74-78` Every public method opens a new `sqlite3.connect`. No connection pool / shared cursor — high overhead in tight loops (e.g., `save_cases` opens N connections via the outer `with`, but other call sites open per call). P2.
- `run_store.py:132-168` `_redact_existing_public_reports` / `_redact_existing_site_scan_findings` run on every `initialize()` and re-redact already-public rows — wasteful and creates write churn. Quote: `"if report.sensitive_details_redacted: continue"`. P2.
- `run_store.py:170-181` `readiness()` catches `OSError, sqlite3.Error` and returns False — narrow enough — but it calls `initialize()` which has side effects (writes schema). Readiness probes shouldn't write. P1 — UI `/readyz` triggers DB writes on every poll.
- `run_store.py:42-49` `SCHEMA_VERSION = 8` increments are version-stamped but unused — code does not branch on the value beyond stamping it. P3.

### app/sensitive_findings.py
- `sensitive_findings.py:62, 80, 98, 106, 119, 154` Every method calls `self.initialize()` first — creates tables on every read. Same anti-pattern as `RunStore`. P2.
- `sensitive_findings.py:115-145` `update_report_status` silently returns when row missing (`if row is None: return`). Caller in `run_store.py:531` assumes update happened. P1 — silent partial failure between public and private stores.

### app/site_scan_workflow.py
- `site_scan_workflow.py:97` `except Exception as exc:` swallows everything (including `KeyboardInterrupt` in Python 3? No, `BaseException` not caught — okay). Still: catches `ValueError`, `httpx.HTTPError`, programming bugs alike, mapping all to `SiteScanWorkflowError`. P2 — loses original type.
- `site_scan_workflow.py:37` `scanner_factory: Callable[[Settings], SiteScanner] = PassiveSiteScanner` — factory parameter exists for tests; the only production caller passes the default, the only test caller is `test_site_scanner.test_run_site_scan_persists_scan_and_findings` which mocks via monkeypatch instead. Seam unused in practice. P2.

### app/site_scanner.py
- `site_scanner.py:35-68` 33-element `LOW_PRIV_DEFAULT_PATHS` tuple with no source citation in comments. Add reference URLs or move to knowledge base JSON. P2.
- `site_scanner.py:70-89` Two overlapping path-sets (`LOW_PRIV_DEFAULT_PATHS` and `PROTECTED_ROUTE_PATHS`) maintained separately. Drift risk. P3.
- `site_scanner.py:96-113` `OAUTH_DISCOVERY_PATHS` and `OAUTH_URL_FIELDS` are module constants but values mirror OIDC spec wording — keep, but add reference link. P3.
- `site_scanner.py:194-198` `ResponseCheck` Protocol with 9 implementations and a defaulted entry/candidate tuple — well-justified abstraction, but `_run_checks` discards return value typing through `Sequence[ResponseCheck]`. Minor. P3.
- `site_scanner.py:786` `except (ValueError, httpx.HTTPError): continue` — silent skip with no logged trace; failed candidate URLs vanish from the report. P2.

### app/synthetic_auth.py
- `synthetic_auth.py:22-25` Four `assert` statements re-check what `has_synthetic_clinician_auth` already enforced. With `-O` these become no-ops. P2.
- `synthetic_auth.py:31` `"user_role": "users"` magic string — OpenEMR-specific OAuth quirk, undocumented. P3.

### app/target_client.py
- `target_client.py:73` Timeout sourced from `budget.max_latency_ms_per_case / 1000` — couples HTTP timeout to verdict budget; if a user increases verdict budget they silently increase request timeout. P2.
- `target_client.py:186-188` Token estimate is `len(str(request_body) + response_text) // 4` — clearly wrong unit estimate; affects budget enforcement. Quote: `"return max(1, len(text) // 4)"`. P2.

### app/ui.py
- `ui.py:54-76` Three `@app.middleware("http")` stacked plus an `_is_rate_limited` per path keyed by raw client host — in-memory dict, no eviction, leaks memory under load. P1 — known DoS-by-memory.
- `ui.py:395-415` `except Exception as exc:` swallows everything during `run_suite`, then renders escaped exception type+message in HTML 502. Hides bugs as "Run failed". P2.
- `ui.py:521, 591, 599, 603, 607` `<pre>{escape(str(runs[0]))}</pre>` — dumps a dict via `str()` into HTML for run/site-scan details. Lazy display, leaks Python repr formatting to operator. P2.
- `ui.py:969-982` `_record_audit` catches bare `Exception` and silently returns — audit failures vanish. Quote: `"except Exception: return"`. P1 — audit silently broken on DB error.
- `ui.py:1091-1097` `_verdict_by_run_id` and `_latest_verdict_by_case` (line 1193) duplicate logic from `reporting.latest_verdict_by_case` (already imported). Drift risk. P2.
- `ui.py:1206-1215` `_current_reports` duplicates `reporting.current_reports`. Same drift risk. P2.
- `ui.py:1150-1151` `for case_id, verdict in latest_verdict_by_case.items(): case_id = str(verdict.get("case_id", ""))` — overwrites loop variable immediately. Suggests the dict key path is unused. P2.
- `ui.py:1653-1980` ~330 lines of inline CSS+JS inside Python f-strings; no template engine. Despite the empty `app/templates/` directory (dead). P2.

### app/run_week3_eval.py
- `run_week3_eval.py:113-120` `_synthetic_principal_label` returns string-typed label rather than a typed principal — only used in `AttackRun.synthetic_principal: str | None`. Fine, but tag the magic prefix `"synthetic-clinician:"` as a constant. P3.
- `run_week3_eval.py:48-53` `if suite == "regression": seed_cases.extend(...)` runs even when `include_variants` will then mutate the same list with `RedTeamAgent` — variant generation against promoted-regression replays is silent. P2.

### app/export_run.py
- `export_run.py:14-15` `[run for run in store.latest_runs(limit=500) if run["run_id"] == run_id]` — linear scan of 500 rows; should be a single-row SELECT. P3.

### Test files
- `tests/test_target_client.py` Only 1 test, exercises the SSE happy path and nothing else. No tests for `execute_case`, `metadata`, `readiness`, or any error path of the target HTTP layer. P1 — agent-critical code is uncovered.
- `tests/test_run_week3_eval.py` Tests only the `blocking_verdicts` helper. `run_suite()` (the actual entrypoint) has zero unit coverage; the only coverage is implicit through `test_ui` triggering "/site-scans/passive" and through e2e fixtures. P1 — entrypoint untested.
- `tests/test_knowledge_base.py:18-25` Test asserts each entry's fields are truthy without asserting any content shape. Quote: `"assert entry[\"source_refs\"]"`. P2 — passes if the file contains `["x"]` placeholders.
- `tests/test_config_and_store.py:38-42` "parse from env string" only validates list shape, not host-allowlist semantics. P3.
- `tests/test_gap_closure.py:138-141` `test_judge_eval_has_no_critical_or_high_false_negatives` asserts on the fixture suite itself — relies on the bundled fixtures being well-labeled; not a behavioral test of the judge. P2.
- `tests/test_graph_and_export.py:25-30` `FakeTargetClient` is local-only; nothing forces real `TargetClient` to satisfy the same Protocol. P2.
- `tests/test_ui.py:39-60` `test_dashboard_renders_no_runs` is mostly an HTML-substring smoke test (15 string asserts) — survives any markup rename. P2.

## Cross-Cutting Findings

### Dead Code Map
- `app/models.py:449-460` `CampaignPriority` — class, all 9 fields, never used.
- `app/config.py:51` `service_account_token` — never read.
- `app/ports.py:20-43` `TargetCaseExecutor`, `JudgeEvaluator`, `ReportDrafter` — protocols with single concrete implementations and no test-double substitutes outside `tests/test_graph_and_export.py` `FakeTargetClient`. Speculative.
- `app/templates/` — empty directory, no template engine wired; UI inlines HTML/CSS.
- `app/run_store.py:42` `SCHEMA_VERSION` — incremented to 8 but never checked at read time; only inserted as a stamp.
- `app/site_scan_workflow.py:37` `scanner_factory` parameter — defaulted to `PassiveSiteScanner`, no caller overrides it in production paths.
- `app/ui.py:886-889` `_is_bearer_authenticated` referenced only in `_csrf_failure_response` — duplicated logic from `_is_operator_authenticated`. Borderline; flag as candidate.
- `app/ui.py:1091-1097` `_verdict_by_run_id` and `_latest_verdict_by_case` (line 1193), `_current_reports` (line 1206) — duplicates of `reporting.py` helpers already imported.

### Dependency Report
| Package | Used in | Justification |
|---|---|---|
| fastapi | `ui.py` only | Single user, but core (operator UI). Earns its place. |
| uvicorn[standard] | Dockerfile CMD only | Runtime server; no import. Justified. |
| httpx | `target_client.py`, `synthetic_auth.py`, `site_scanner.py`, tests | Earns its place. |
| pydantic | `models.py`, `config.py`, `run_store.py` (BaseModel param) | Core schema layer. Justified. |
| pydantic-settings | `config.py` only | Single import; could be replaced by stdlib `os.environ` parsing given how thin `Settings` is. Marginal — keep. |
| langgraph | `graph.py` only (lazy import) | Single user, heavy dep. The graph nodes are linear (`orchestrator → red_team → target_runner → judge → documentation → regression_store → stop_policy`) — no branching, no parallelism, no conditional edges. A 40-line `for node in nodes: node(state)` would replace it. P2 — bloat candidate. |
| langchain_core | `graph.py` (try/except) | Optional sibling of langgraph; only used to silence one deprecation warning. P2 — drop together with langgraph. |
| pytest, ruff, mypy | dev | Earns place. |

Findings: **langgraph is a heavy dep for a linear pipeline; pydantic-settings is borderline.** Everything else is justified.

### Test Gap Map
Per agent / core module:

| Module | Tested behavior | Untested behavior |
|---|---|---|
| `judge_agent.py` | PATIENT_SCOPE_LEAK, citation-scope, UNSAFE_CLINICAL_RECOMMENDATION, MISSING_CITATION, TARGET_UNSTABLE, safe refusal. | Budget-exceed verdicts (request_count/latency/token/cost/retry/loop), DIRECT_PROMPT_INJECTION disclosure markers, IDENTITY_HIJACKING markers, TOOL_MISUSE unapproved tool_outcome, INDIRECT_INJECTION follower text. **Half of `JudgeAgent`'s branches uncovered.** |
| `red_team_agent.py` | Variant count, parent_case_id preserved, category/route preserved. | `validate_variant` failure paths; multi_turn_pressure two-prompt construction; `max_variants_per_case` upper bound. |
| `documentation_agent.py` | Implicit via `test_graph_and_export.py`. | No direct test of `_impact` / `_remediation` text or `NEEDS_HUMAN_REVIEW` branch. |
| `target_client.py` | One SSE-final happy path. | All error paths (httpx.HTTPError → status 0 fallback), JSON parsing variants, citation flattening from `sources` vs `citations`, `_estimate_tokens`, `metadata()`, `readiness()`. |
| `synthetic_auth.py` | None. | Entire OAuth password-grant flow; error message extraction. |
| `graph.py` | Linear path execution, critical-failure stop reason. | Inconclusive/human-review branches, regression-store skip path, `langgraph` import error path. |
| `site_scanner.py` | Strong: headers, cookies, B2B, OAuth, redirects, env exposure, scope limits. | Auth header construction precedence (`bearer+cookie`), `_unique_urls` ordering. |
| `run_store.py` | Save/load roundtrips for cases, scans, reports, scopes. | `cancel_scan_job` running→cancelled flow; `deactivate_scope` audit; retention expiry behavior. |
| `run_week3_eval.py` | `blocking_verdicts` helper. | The actual `run_suite` entrypoint (loads cases, calls graph, builds summary). |
| `ui.py` | Routes return 200/303/404; CSRF/auth happy path; rate-limit not exercised. | Rate-limit eviction (none — memory leak); audit-write failure path; `_record_audit` swallowing. |
| `costing.py` | Indirectly via graph. | No direct unit test of fallback-to-all-observations behavior. |
| `resilience.py` | Coverage component, basic penalty. | No test pinning the specific weight constants. |

### Anti-Patterns / Over-Engineering
- **Speculative Protocol layer in `ports.py`** with no second implementations in sight (memory says: don't ship interface seams without a second user).
- **Empty `app/templates/` directory** — looks like a planned Jinja swap that never landed; UI inlines all HTML/CSS/JS in `ui.py`.
- **`scanner_factory` injection point** in `SiteScanWorkflow` — defaulted to one implementation, not overridden in any production caller; tests monkeypatch instead.
- **`CampaignPriority` model** — speculative scoring schema with 9 fields, zero callers.
- **Duplicate verdict-rollup helpers** in `ui.py` re-implement what `reporting.py` already exports.
- **`SCHEMA_VERSION` stamp** that is written but never read for branching.
- **LangGraph for a linear 7-node DAG** with no conditional edges or parallelism.

### Concurrency Notes
- `graph.py:100` calls `asyncio.run` inside a sync node. Safe when invoked from `run_week3_eval.run_suite` (sync) but will raise `RuntimeError: cannot be called from a running event loop` if ever invoked from an async caller (e.g., a future FastAPI background task). P2.
- `ui.py:382` `start_run` is `async def` and calls sync `run_suite` which itself wraps `asyncio.run` for each case. That blocks the event loop and re-creates a fresh loop per case. P1 — UI thread freezes for the whole suite duration; rate-limit middleware can't fire.
- `ui.py:55-61` `rate_buckets` dict is mutated from multiple async middleware invocations without a lock. With uvicorn's single-loop default it's fine; with multiple workers it's per-worker (no shared state across workers). P2 — undocumented assumption.

### Security smells (in platform, separate from what it tests)
- `ui.py:1011` Renders `str(snapshot.get('score_explanation', ...))` directly into HTML; `escape()` is used everywhere else, but a few `<pre>{escape(str(...))}</pre>` blocks (lines 521, 591, 599, 603, 607) dump full row dicts which could include un-redacted strings from the DB.
- `ui.py:842` `'unsafe-inline'` in CSP `script-src` and `style-src` — needed for the inlined JS/CSS but defeats CSP's XSS goal. Templating + nonces would fix.
- `synthetic_auth.py:33` Password is sent via `data=` form-encoded POST. Correct for OAuth password grant, but log messages must not include the body (currently they do not — good).
- No SQL injection risk surveyed: every `conn.execute` uses parameterized placeholders. Clean.
- No shell-out / `subprocess` calls anywhere in scope. Clean.
- No secrets in code; tokens come from `SecretStr` env settings.

## Findings Backlog

| ID | Severity | Category | Description | File(s) | Est. hrs | Quality impact (1–10) |
|---|---|---|---|---|---:|---:|
| Q1 | P1 | Quality | `RunStore.initialize()` runs ALTERs + redaction sweeps on every readiness probe and every UI route call. | run_store.py:80–168 | 3 | 8 |
| Q2 | P1 | Quality | `ui.py` async route invokes sync `run_suite` containing `asyncio.run`; whole event loop blocks per suite. | ui.py:382, graph.py:100, run_week3_eval.py:66 | 5 | 8 |
| Q3 | P1 | Quality | `_record_audit` swallows all exceptions silently (`except Exception: return`); audit may be broken without operator notice. | ui.py:969–982 | 1 | 8 |
| Q4 | P1 | Quality | `SensitiveFindingStore.update_report_status` silently returns when row missing; called after public store update — leaves the two DBs divergent. | sensitive_findings.py:115–145 | 1 | 7 |
| Q5 | P1 | Quality | `target_client.py` has near-zero coverage (one SSE happy path) yet is the agent's only contact with the system under test. | tests/test_target_client.py | 4 | 9 |
| Q6 | P1 | Quality | `run_suite` entrypoint untested in isolation; only `blocking_verdicts` helper has a unit test. | tests/test_run_week3_eval.py | 4 | 8 |
| Q7 | P2 | Quality | Dead `CampaignPriority` model (9 fields, zero callers). | models.py:449–460 | 0.5 | 5 |
| Q8 | P2 | Quality | Dead `service_account_token` setting. | config.py:51 | 0.25 | 3 |
| Q9 | P2 | Quality | Speculative Protocols in `ports.py` with single implementations and no production substitution point. | ports.py:20–55 | 1.5 | 5 |
| Q10 | P2 | Quality | Empty `app/templates/` dir; UI inlines HTML/CSS/JS — splits intent across nowhere and `ui.py`. | app/templates/, ui.py | 8 | 5 |
| Q11 | P2 | Quality | LangGraph dep for a linear 7-node DAG; replace with explicit pipeline. | graph.py | 4 | 6 |
| Q12 | P2 | Quality | `costing.build_suite_summary` silently falls back to "use all observations" when run_id keying misses. | costing.py:19–28 | 1 | 5 |
| Q13 | P2 | Quality | Token estimate `len(text) // 4` drives budget enforcement — wrong unit; budget never fires realistically. | target_client.py:186–188 | 1.5 | 6 |
| Q14 | P2 | Quality | Hardcoded clinical regex (`metformin`, `insulin`) and magic tool-outcome strings. | judge_agent.py:17–21, 127–131 | 1 | 5 |
| Q15 | P2 | Quality | Hardcoded production Railway URLs in `Settings` defaults. | config.py:21, 26–28 | 0.5 | 4 |
| Q16 | P2 | Quality | Resilience weight constants undocumented and untested. | resilience.py:10–24, 58–68 | 1.5 | 5 |
| Q17 | P2 | Quality | `RunStore` opens a fresh sqlite connection per public method; `initialize()` triggers a write on every readiness call. | run_store.py | 3 | 5 |
| Q18 | P2 | Quality | Ad-hoc `ALTER TABLE` "ensure" methods substitute for versioned migrations despite SCHEMA_VERSION being 8. | run_store.py:92–112 | 3 | 6 |
| Q19 | P2 | Quality | Sweeping redaction pass runs on every `initialize()` rather than at write time only. | run_store.py:132–168 | 1.5 | 5 |
| Q20 | P2 | Quality | `ui.py` duplicates `_verdict_by_run_id`, `_latest_verdict_by_case`, `_current_reports` already in `reporting.py`. | ui.py:1091, 1193, 1206 | 1 | 5 |
| Q21 | P2 | Quality | Bare `<pre>{escape(str(...))}</pre>` dumps repr to operator HTML in 5 places. | ui.py:521, 591, 599, 603, 607 | 1.5 | 5 |
| Q22 | P2 | Quality | `_is_rate_limited` keeps unbounded in-memory dict keyed by host+path; no eviction. | ui.py:848–861 | 1 | 6 |
| Q23 | P2 | Quality | `SiteScanWorkflow` catches bare `Exception` and rewraps everything as `SiteScanWorkflowError`. | site_scan_workflow.py:97 | 0.5 | 4 |
| Q24 | P2 | Quality | `start_run` catches bare `Exception` and renders escaped exc str in HTML 502. | ui.py:395–415 | 0.5 | 4 |
| Q25 | P2 | Quality | `site_scanner.py` candidate-URL fetch silently swallows `(ValueError, httpx.HTTPError)`. | site_scanner.py:786 | 0.5 | 4 |
| Q26 | P2 | Quality | `judge_eval` test asserts on bundled fixtures only — tautological. | tests/test_gap_closure.py:138 | 2 | 5 |
| Q27 | P2 | Quality | `test_knowledge_base` tests check truthiness, not shape/content. | tests/test_knowledge_base.py:18 | 1 | 4 |
| Q28 | P2 | Quality | `test_dashboard_renders_no_runs` is a 15-substring smoke test that breaks on harmless renames. | tests/test_ui.py:39 | 1.5 | 4 |
| Q29 | P2 | Quality | Test untested branches of `JudgeAgent` (budget, identity, prompt-injection, tool-misuse, indirect-injection). | tests/test_judge_agent.py | 3 | 7 |
| Q30 | P2 | Quality | `graph.py` couples `RunStore` and `TargetCaseExecutor` into TypedDict state container. | graph.py:43–51 | 1.5 | 4 |
| Q31 | P2 | Quality | `graph.py` `asyncio.run` inside graph node — runtime trap if reused from async. | graph.py:100 | 1 | 5 |
| Q32 | P2 | Quality | `module import` side-effect: `warnings.filterwarnings(...)` at module load in `graph.py`. | graph.py:40 | 0.5 | 3 |
| Q33 | P2 | Quality | `synthetic_auth.py` re-asserts what `has_synthetic_clinician_auth` already checks — disappears under `-O`. | synthetic_auth.py:22–25 | 0.25 | 3 |
| Q34 | P2 | Quality | `target_client.py` couples HTTP timeout to verdict budget (`max_latency_ms_per_case / 1000`). | target_client.py:73 | 0.5 | 4 |
| Q35 | P3 | Quality | Default mutation rationale, OAuth scope string, "user_role: users" magic — move to constants/env. | red_team_agent.py, config.py, synthetic_auth.py | 1 | 3 |
| Q36 | P3 | Quality | `case_loader._default_case_root` silently falls through 3 candidates without logging. | case_loader.py:39–51 | 0.5 | 3 |
| Q37 | P3 | Quality | `reporting.category_rollups` shadows outer `verdict` name in set-comprehension. | reporting.py:54 | 0.25 | 2 |
| Q38 | P3 | Quality | `export_run.build_run_export` linear-scans 500 rows to fetch one run. | export_run.py:14–15 | 0.5 | 3 |
| Q39 | P3 | Quality | `RunBudget` defaults duplicate `Settings` defaults (single source of truth lost). | models.py:213–221, config.py:52–59 | 0.5 | 3 |
| Q40 | P3 | Quality | `LOW_PRIV_DEFAULT_PATHS` / `PROTECTED_ROUTE_PATHS` overlap maintained in two places. | site_scanner.py:35–89 | 0.5 | 3 |

## Summary

Total smells: **40**
- P1 (concrete failure modes named): **6**
- P2: **28**
- P3: **6**

### Top 5 highest-impact refactors
1. **Stop running schema/redaction sweeps on every read.** `RunStore.initialize()` is called from `/readyz`, every dashboard render, and every route — each triggers ALTERs and a public-report rewrite loop. Cache initialization once per process (Q1, Q17, Q18, Q19).
2. **Fix the async-blocking suite runner.** UI's `start_run` is async but calls sync `run_suite` which itself calls `asyncio.run` per case — blocks uvicorn's loop, breaks middleware, breaks the rate limiter for the duration of a run (Q2, Q31).
3. **Cover the agent surfaces that actually matter.** `target_client.py` has 1 happy-path test, `synthetic_auth.py` has 0, half of `JudgeAgent` branches are untested. These are the lines that decide whether the platform can produce a real verdict (Q5, Q6, Q29).
4. **Delete speculative abstraction.** Drop `CampaignPriority`, `service_account_token`, the three lonely Protocols in `ports.py`, the empty `templates/` directory, the unused `scanner_factory` seam, and the unread `SCHEMA_VERSION` (Q7, Q8, Q9, Q10).
5. **Stop swallowing errors silently.** `_record_audit` returns on bare `Exception`, `SensitiveFindingStore.update_report_status` returns on missing row, `SiteScanWorkflow` catches all Exception, `site_scanner` swallows candidate failures, `costing` falls back to "use everything". Each one hides real failures from the operator (Q3, Q4, Q23, Q24, Q25, Q12).
