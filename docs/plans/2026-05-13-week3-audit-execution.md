# Week 3 Adversarial Platform Audit — Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Execute the full-spectrum audit defined in `2026-05-13-week3-audit-design.md` and deliver one prioritized backlog report.

**Architecture:** Four specialist auditor subagents run in parallel (rubric / CISO / code-quality / doc-drift), then a skeptic subagent red-teams their findings, then the main thread synthesizes into a single report with executive summary, scored rubric, CISO scorecard, prioritized backlog, and evidence appendix.

**Tech Stack:** Claude Code Agent tool (subagent_type=general-purpose for the auditors, subagent_type=Explore for read-only spot checks if needed), markdown outputs committed to `docs/plans/`.

---

## Pre-flight

**Working directory:** `C:/Users/mtm16/New folder (3)/moran-openemr`

**Reference docs the subagents will need to know exist:**
- Week 3 PRD: `C:/Users/mtm16/New folder (3)/Week 3 - AgentForge - Adversarial AI Security Platform PRD.pdf`
- Design doc: `docs/plans/2026-05-13-week3-audit-design.md`
- Adversarial platform code: `security/adversarial/app/**` (24 Python files), `security/adversarial/tests/**` (10 test files)
- Adversarial platform docs: `security/docs/**` (19 markdown files) and root: `THREAT_MODEL.md`, `ARCHITECTURE.md`, `USERS.md`, `AI_COST_ANALYSIS.md`, `EVAL_DATASET.md`, `SUBMISSION.md`, `EARLY_SUBMISSION_CHECKLIST.md`, `WALKTHROUGH.md`, `MVP_STATUS.md`

---

### Task 1: Create raw-output directory and skeleton files

**Files:**
- Create: `docs/plans/2026-05-13-week3-audit-raw/.gitkeep`

**Step 1: Create the directory**

Run: `mkdir -p "C:/Users/mtm16/New folder (3)/moran-openemr/docs/plans/2026-05-13-week3-audit-raw" && touch "C:/Users/mtm16/New folder (3)/moran-openemr/docs/plans/2026-05-13-week3-audit-raw/.gitkeep"`

Expected: directory created, .gitkeep file exists.

**Step 2: Verify**

Run: `ls "C:/Users/mtm16/New folder (3)/moran-openemr/docs/plans/2026-05-13-week3-audit-raw/"`
Expected: shows `.gitkeep`.

---

### Task 2: Dispatch four specialist auditors in parallel

All four Agent tool calls go in **one** assistant message so they execute concurrently. Each subagent writes its output to a file under `docs/plans/2026-05-13-week3-audit-raw/`. Each must include in its final summary message: the absolute path of the file it wrote, the count of findings by severity, and a 5-line top-of-mind list.

Each prompt below is self-contained: the subagent has none of this session's context.

---

#### Subagent A — Rubric compliance auditor

- `subagent_type`: `general-purpose`
- `description`: "Week 3 rubric audit"
- `prompt`:

```
You are the Rubric Compliance auditor for a Week 3 student deliverable. The
project is an adversarial AI security platform that red-teams a clinical AI
copilot (OpenEMR Clinical Co-Pilot).

WORKING DIRECTORY: C:/Users/mtm16/New folder (3)/moran-openemr

YOUR JOB
Score the project against every requirement in the Week 3 PRD. Cite evidence
for every claim. Do NOT trust documentation that claims something exists;
verify by reading the file or running a grep.

INPUTS
1. PRD: "C:/Users/mtm16/New folder (3)/Week 3 - AgentForge - Adversarial AI
   Security Platform PRD.pdf" — read it first. Extract every hard gate, every
   "must include," and every line in the Submission Requirements table.
2. Audit design doc: docs/plans/2026-05-13-week3-audit-design.md (read it for
   scope and severity definitions).
3. Codebase to verify against:
   - security/adversarial/** (adversarial platform code, tests, evals, docs)
   - Root docs: THREAT_MODEL.md, ARCHITECTURE.md, USERS.md,
     AI_COST_ANALYSIS.md, EVAL_DATASET.md, SUBMISSION.md,
     EARLY_SUBMISSION_CHECKLIST.md
   - security/docs/** (all 19 files; especially W3_*, WEEK3_*, THREAT_MODEL.md,
     VULNERABILITY_REPORTS.md, RULES_OF_ENGAGEMENT_TEMPLATE.md)

OUT OF SCOPE
- copilot/ target system itself (we only check that the platform tests against it).
- OpenEMR core PHP code.

OUTPUT
Write a single markdown file to:
docs/plans/2026-05-13-week3-audit-raw/rubric.md

Structure:
# Rubric Compliance Audit (Week 3)
## 1. Hard Gates
Table with columns: Gate | Required by PRD | Status (Pass/Partial/Fail) |
Evidence (file:line + ≤15-word quote) | Why this verdict.

Hard gates to score (extract from PRD; this is the floor — add any I missed):
- Deployed target application URL submitted
- THREAT_MODEL.md exists with ~500-word summary
- evals/ directory with results from ≥3 distinct attack categories
- ≥1 agent role running live against deployed target
- ARCHITECTURE.md with ~500-word summary + diagram of agent interactions
- USERS.md exists with workflows + automation justification
- ≥3 distinct vulnerability reports following required format
- AI_COST_ANALYSIS.md covers 100 / 1K / 10K / 100K test runs with
  architectural changes per scale (NOT just cost × n)
- Multi-agent architecture (single-agent or pipeline does NOT satisfy)
- Demo video plan/script
- Eval dataset reproducible across runs
- Vulnerability report format includes: unique ID, severity, clinical impact,
  reproducible attack sequence, observed vs expected, remediation, fix status

## 2. Required Agent Capabilities (Platform Requirements section)
For each capability in the PRD's "Multi-Agent Adversarial System" bullet list,
score whether the platform actually does it:
- Generates novel adversarial inputs
- Mutates partially-successful attacks
- Multi-turn attack sequences
- Consistent evaluation criteria across runs and system versions
- Prioritizes attack surfaces by coverage gaps and unresolved findings
- Halts/redirects when cost accumulates without signal
- Triggers regression runs on target changes

Same table format as section 1.

## 3. Required Roles
For each named agent role in the PRD (Red Team, Judge, Orchestrator,
Documentation), verify the role exists as a distinct agent with its own
context, and score:
- Implementation present (file:line)
- Trust level documented (file:line)
- Inputs/outputs documented
- Coordination protocol documented

## 4. Observability Layer
PRD lists 6 questions the observability layer must answer. For each, score
whether the platform can answer it, and cite where.

## 5. Regression & Validation Harness
Score each PRD bullet point under "Regression & Validation Harness."

## 6. Documentation Agent
Score each PRD bullet point under "Documentation Agent" minimum-fields list.

## 7. Findings Backlog
Every Fail/Partial above becomes a backlog row:
ID | Severity (P0/P1/P2 per the design doc) | Category | Description |
File(s) affected | Est. hours to fix | Rubric points recovered (your estimate
on a 0–10 scale, with reasoning).

## 8. Summary
- Hard gates Pass / Partial / Fail counts
- Top 5 rubric risks
- Estimated total rubric points at risk
- 3-sentence overall assessment

CONSTRAINTS
- Every finding needs a file path + line/heading + ≤15-word direct quote.
- No claim without evidence. If you cannot find evidence, mark as "unverified"
  and note what you searched for.
- Word budget: 4000 words. Prefer tables over prose.
- Do NOT propose fixes in detail — the backlog row's description is enough.
- Mark anything ambiguous in the PRD as "AMBIGUOUS — needs human read."

When done, output to the main thread:
1. Absolute path of the file you wrote.
2. Count by severity: P0=__ P1=__ P2=__.
3. Top 5 findings, one line each.
```

---

#### Subagent B — CISO defensibility auditor

- `subagent_type`: `general-purpose`
- `description`: "Week 3 CISO defensibility audit"
- `prompt`:

```
You are the CISO Defensibility auditor for a Week 3 student deliverable: an
adversarial AI security platform that red-teams a clinical AI copilot.

WORKING DIRECTORY: C:/Users/mtm16/New folder (3)/moran-openemr

THE STANDARD
The PRD's final note: "The deliverable that matters is not the one that finds
the most impressive jailbreak in a demo. It's the one you could defend in
front of a hospital CISO who is deciding whether to trust this platform with
continuous security testing of systems their physicians depend on."

Score against THAT standard. A hospital CISO cares about:
1. Judge independence — the eval agent cannot share context with the attack
   agent or it grades its own homework.
2. Audit trail — every action taken by every agent is replayable, attributable,
   and tamper-evident.
3. Approval gates — autonomous actions that affect production (filing reports,
   recommending patches, triggering regressions) have explicit human approval
   where appropriate.
4. Blast radius — what is the worst case if the Red Team Agent goes rogue or
   the Judge starts hallucinating?
5. False-positive cost — what stops the platform from drowning real findings
   in noise?
6. Scope discipline — can the platform attack systems it should not be
   attacking? Is there an enforced target allowlist?
7. PHI safety — when the Red Team probes PHI extraction, where does that data
   land? Is it logged, redacted, persisted?
8. Cost containment — can a runaway agent loop drain a budget? Are there
   circuit breakers?
9. Regression integrity — does a passing regression test prove the vuln is
   fixed, or just that the model behaved differently this time?
10. Reproducibility — can a senior engineer who was not present reproduce any
    documented finding from the artifacts alone?

INPUTS
- All adversarial platform code: security/adversarial/app/**
- All tests: security/adversarial/tests/**
- Threat model: THREAT_MODEL.md (root) and security/docs/THREAT_MODEL.md
- Architecture: ARCHITECTURE.md (root) and security/docs/W3_ARCHITECTURE.md,
  W3_SYSTEM_DESIGN.md
- Rules of engagement: security/docs/RULES_OF_ENGAGEMENT_TEMPLATE.md
- Vuln reports: security/docs/VULNERABILITY_REPORTS.md
- Audit design doc (for severity defs): docs/plans/2026-05-13-week3-audit-design.md

KEY FILES TO TRACE (read these in full):
- security/adversarial/app/red_team_agent.py
- security/adversarial/app/judge_agent.py
- security/adversarial/app/documentation_agent.py
- security/adversarial/app/graph.py (the orchestrator)
- security/adversarial/app/regression_harness.py
- security/adversarial/app/sensitive_findings.py
- security/adversarial/app/synthetic_auth.py
- security/adversarial/app/scope_registry.py
- security/adversarial/app/run_store.py
- security/adversarial/app/costing.py
- security/adversarial/app/resilience.py

OUTPUT
Write to: docs/plans/2026-05-13-week3-audit-raw/ciso.md

Structure:
# CISO Defensibility Audit
## Trust Dimensions Scorecard
Table with one row per trust dimension above:
Dimension | Status (Strong/Adequate/Weak/Missing) | Evidence (file:line +
quote) | What a CISO would ask | What would satisfy them.

## Trace 1 — Judge Independence
Show the data flow from attack generation to judgment. Identify any shared
prompt context, shared model, shared state, or shared LLM session. Quote the
code. Verdict: independent / contaminated / unverifiable.

## Trace 2 — Vulnerability Lifecycle
For one documented vulnerability, trace it from discovery → judgment →
documentation → regression test → fix validation. Identify every breakage in
the evidence chain.

## Trace 3 — Approval Gates
List every irreversible / public-facing / production-affecting action the
platform can take autonomously. For each, identify the approval gate (or its
absence).

## Trace 4 — Blast Radius
Worst-case scenario for: rogue Red Team agent, hallucinating Judge, runaway
loop, scope violation, PHI leak in logs. For each, what stops it now? What
would a CISO want?

## Findings Backlog
Same row format as the rubric auditor: ID | Severity | Category=CISO |
Description | Files | Est. hours | Trust impact (1–10).

## Summary
- CISO go / conditional-go / no-go verdict, with reasoning.
- Top 5 trust gaps in priority order.

CONSTRAINTS
- Read the code, do not infer behavior from doc claims.
- Every finding needs file:line + ≤15-word quote.
- Word budget: 4000 words.
- Mark "needs human read" if a trust dimension depends on infra you cannot see
  (e.g., deployed env vars).

When done, output to the main thread:
1. Absolute path of the file you wrote.
2. Severity counts.
3. Your go / conditional-go / no-go verdict, one sentence.
```

---

#### Subagent C — Code quality auditor

- `subagent_type`: `general-purpose`
- `description`: "Week 3 code quality audit"
- `prompt`:

```
You are the Code Quality auditor for a Week 3 adversarial-AI-security-platform
student deliverable, written in Python.

WORKING DIRECTORY: C:/Users/mtm16/New folder (3)/moran-openemr

SCOPE
Read every Python file under:
- security/adversarial/app/**.py (24 files)
- security/adversarial/tests/**.py (10 files)

Also read:
- security/adversarial/pyproject.toml (deps)
- security/adversarial/Dockerfile

OUT OF SCOPE
- security/adversarial/.mypy_cache, .ruff_cache, __pycache__
- copilot/ and any non-Python file (audited by others)
- OpenEMR core code

CHECK FOR
1. Dead code — modules / functions / parameters never called or referenced.
2. Weak abstractions — ports/adapters that exist for no reason; speculative
   interface seams; "ship X now, swap Y later" hedges with no second
   implementation in sight.
3. Unhandled error paths — try/except that swallows everything, or paths that
   silently fail (return None where the caller expects data).
4. Magic numbers / hardcoded strings that should be config.
5. Test quality — tests that assert nothing meaningful, tests that mock the
   system under test, tests that pass regardless of implementation, missing
   tests for the agent code paths.
6. Dependency bloat — packages in pyproject.toml that are not imported, or are
   imported once for a trivial use.
7. Type/lint debt — places where types are clearly wrong, or where # noqa /
   # type: ignore is used to silence a real issue.
8. Coupling — files that import too many other files, circular import risk.
9. Documentation in code — module docstrings that lie about what the module
   does; comments that contradict the code below them.
10. Concurrency / async gotchas if the platform uses asyncio.
11. Security smells in the platform itself (separate from what it tests for):
    SQL injection in any local DB code, command injection in shell-outs,
    secrets in code, broad file paths.

OUTPUT
Write to: docs/plans/2026-05-13-week3-audit-raw/quality.md

Structure:
# Code Quality Audit (Python — security/adversarial/)
## File Inventory
Table: File | Purpose (one line) | LOC | Imports out / in | Has tests? | Smell
count.

## Findings By File
For each file with smells, list the smells with line numbers and ≤15-word
quotes.

## Cross-Cutting Findings
- Dead code map: full list of unused functions / classes / params.
- Dependency report: every package in pyproject.toml, where it is used, and
  whether it earns its place.
- Test gap map: per agent file, what behavior is and is not tested.
- Anti-patterns / over-engineering: speculative interfaces, "swap later" code,
  unjustified abstraction layers.

## Findings Backlog
Same row format: ID | Severity | Category=Quality | Description | File(s) |
Est. hours | Quality impact (1–10).

## Summary
- Total smells by severity.
- 5 highest-impact refactors.

CONSTRAINTS
- Cite file:line for every smell with a ≤15-word direct quote.
- Word budget: 5000 words.
- Mark P2 unless you can name a concrete failure mode for P1+.

When done, output to the main thread:
1. Absolute path of the file you wrote.
2. Severity counts.
3. Top 5 smells, one line each.
```

---

#### Subagent D — Doc/code drift auditor

- `subagent_type`: `general-purpose`
- `description`: "Week 3 doc/code drift audit"
- `prompt`:

```
You are the Doc/Code Drift auditor for a Week 3 student deliverable.

WORKING DIRECTORY: C:/Users/mtm16/New folder (3)/moran-openemr

YOUR JOB
For every concrete claim made in a Week 3 doc, verify that the code actually
does what the doc says. Catch:
- Claims the code contradicts.
- Claims that go beyond what the code does ("Production-grade circuit
  breakers" but no breaker code).
- Code behavior the docs do not mention ("Silently writes to /tmp/...").
- Stale references to renamed files, removed flags, retired models.
- Numbers in docs that do not match numbers in code (test counts, attack
  category counts, cost figures).

DOCS TO AUDIT
Root:
- THREAT_MODEL.md
- ARCHITECTURE.md
- USERS.md
- AI_COST_ANALYSIS.md
- EVAL_DATASET.md
- SUBMISSION.md
- EARLY_SUBMISSION_CHECKLIST.md
- WALKTHROUGH.md
- MVP_STATUS.md
- README.md (only the sections about Week 3 / the adversarial platform)

security/docs/:
- THREAT_MODEL.md
- W3_ARCHITECTURE.md
- W3_SYSTEM_DESIGN.md
- W3_BUILD_GOALS.md
- WEEK3_PRD.md
- WEEK3_GAP_CLOSURE_PLAN.md
- WEEK3_RUBRIC_GRADE.md
- WEEK3_SUBMISSION_CHECKLIST.md
- VULNERABILITY_REPORTS.md
- RULES_OF_ENGAGEMENT_TEMPLATE.md
- SCHEMA_EVIDENCE.md
- B2B_PRODUCTION_READINESS.md
- FINAL_DEMO_SCRIPT.md
- FINAL_PRODUCT_PLAN.md
- UX_100_POINT_AUDIT.md
- WEB_VULNERABILITY_KNOWLEDGE_BASE.md
- OPENEMR_RAILWAY_SCAN_2026-05-13.md

CODE TO VERIFY AGAINST
- security/adversarial/app/**.py and tests/**.py
- security/adversarial/evals/**
- security/adversarial/migrations/**
- security/adversarial/Dockerfile, pyproject.toml, railway.toml

PROCESS
For each doc:
1. List the concrete claims in it (skip pure prose; focus on "X does Y",
   "we use Z", "the agent calls W", numbers, lists).
2. For each claim, grep / read the relevant code.
3. Categorize: CONFIRMED / CONTRADICTED / UNVERIFIED / OVERSTATED /
   UNDERSTATED.

OUTPUT
Write to: docs/plans/2026-05-13-week3-audit-raw/drift.md

Structure:
# Doc/Code Drift Audit
## Per-Doc Verdict Summary
Table: Doc | Total claims checked | Confirmed | Contradicted | Overstated |
Understated | Unverified.

## Findings
For each Contradicted / Overstated / Understated claim:
- Doc + line: "<quote ≤15 words>"
- Code reality: file:line "<quote ≤15 words>"
- Verdict: Contradicted | Overstated | Understated
- Impact (P0 if a HARD GATE doc lies; P1 if a CISO-relevant claim lies; P2
  otherwise).

## Cross-Doc Inconsistencies
Where two Week 3 docs claim incompatible things, flag them.

## Findings Backlog
Same row format. Category=Drift.

## Summary
- 5 worst drift findings.
- Overall doc credibility verdict: high / mixed / low.

CONSTRAINTS
- Verify code by reading, not by trusting another doc.
- Every finding needs a doc quote AND a code quote (or "no matching code" with
  the searches you ran).
- Word budget: 5000 words.

When done, output to the main thread:
1. Absolute path of the file you wrote.
2. Counts of Contradicted / Overstated / Understated.
3. Top 5 drift findings, one line each.
```

---

**Step 1: Dispatch all four agents in a single message**

In the main thread, send one message with 4 Agent tool uses. After they return, save each result message to memory (not file — the agents wrote their own files).

**Step 2: Verify all four files exist**

Run: `ls -la "C:/Users/mtm16/New folder (3)/moran-openemr/docs/plans/2026-05-13-week3-audit-raw/"`
Expected: `rubric.md`, `ciso.md`, `quality.md`, `drift.md` all present, all non-empty.

If any file is missing, re-dispatch only that one agent with the same prompt.

**Step 3: Skim each output**

Open each file. Confirm it follows the required structure. If structure is wildly off (no findings backlog, no evidence quotes), re-dispatch with a stricter prompt note. Otherwise proceed.

---

### Task 3: Dispatch the skeptic subagent

- `subagent_type`: `general-purpose`
- `description`: "Week 3 audit skeptic review"
- `prompt`:

```
You are the Skeptic for an audit of a Week 3 student deliverable. Four
specialist auditors (rubric, CISO, code quality, doc drift) have written
findings. Your job is to red-team their findings — catch false positives,
overstatements, and blind spots.

WORKING DIRECTORY: C:/Users/mtm16/New folder (3)/moran-openemr

INPUTS
Read the four auditor outputs in full:
- docs/plans/2026-05-13-week3-audit-raw/rubric.md
- docs/plans/2026-05-13-week3-audit-raw/ciso.md
- docs/plans/2026-05-13-week3-audit-raw/quality.md
- docs/plans/2026-05-13-week3-audit-raw/drift.md

Also have access to the codebase to spot-check any cited file:line.

Reference:
- Audit design: docs/plans/2026-05-13-week3-audit-design.md
- Week 3 PRD: "C:/Users/mtm16/New folder (3)/Week 3 - AgentForge -
  Adversarial AI Security Platform PRD.pdf"

PROCESS
1. For each auditor's output, pick the top 5 highest-severity findings.
   For each, open the cited file and verify the quote and context. Verdict:
   CONFIRMED / OVERSTATED / WRONG / MISSING-CONTEXT.
2. Pick 5 additional findings at random per auditor and verify the same way.
3. Look for BLIND SPOTS — things none of the four auditors covered. Think
   about: demo readiness, what happens between MVP and Final submission,
   risks to the rubric that are situational (e.g., live target down at demo
   time), and anything in the PRD that fell between auditor lanes.
4. Identify FALSE POSITIVES — findings that sound bad but are not actually
   defects (e.g., "no orchestrator agent" when graph.py is the orchestrator).
5. Identify OVERSTATEMENTS — findings whose severity is too high given the
   evidence.

OUTPUT
Write to: docs/plans/2026-05-13-week3-audit-skeptic-review.md

Structure:
# Skeptic Review
## Per-Auditor Spot-Check Results
For each auditor, a table of finding IDs you verified and your verdict
(CONFIRMED / OVERSTATED / WRONG / MISSING-CONTEXT) with one-line reasoning.

## Findings to Demote
List of finding IDs whose severity should drop, with the new severity and
why.

## Findings to Promote
List of findings whose severity should rise, with new severity and why.

## Findings to Drop
List of false positives. Cite why each is wrong.

## Blind Spots
Things none of the four auditors caught. For each: description, severity,
evidence pointer, what auditor should have caught it.

## Meta-Observations
- Which auditor was most rigorous?
- Where did the auditors overlap or contradict each other?
- Where did the audit collectively over-index vs under-index?

## Final Verdict
- Of the four outputs, percentage of findings you trust.
- Top 5 corrections the synthesizer must apply.

CONSTRAINTS
- You must open at least 20 cited files in total to verify.
- For every CONFIRMED / OVERSTATED / WRONG verdict, quote the actual code or
  doc (≤15 words) as proof, not just the auditor's quote.
- Word budget: 4000 words.
- It is OK to confirm that an auditor is right — say so.

When done, output to the main thread:
1. Absolute path of the file you wrote.
2. Count of confirmed / overstated / wrong / missing-context verdicts.
3. Number of blind spots found.
4. One-sentence overall trust level in the audit.
```

**Step 1: Dispatch the skeptic.** Single Agent tool call.

**Step 2: Verify output file exists and is non-empty.**

Run: `ls -la "C:/Users/mtm16/New folder (3)/moran-openemr/docs/plans/2026-05-13-week3-audit-skeptic-review.md"`

**Step 3: Read the skeptic's report fully** into the main thread. This is the input to synthesis.

---

### Task 4: Synthesize the final report

This is the only main-thread-only task. Done by Claude, not by a subagent.

**Files:**
- Create: `docs/plans/2026-05-13-week3-audit-report.md`

**Step 1: Read all five raw outputs**

Read all of:
- `audit-raw/rubric.md`
- `audit-raw/ciso.md`
- `audit-raw/quality.md`
- `audit-raw/drift.md`
- `audit-skeptic-review.md`

**Step 2: Apply skeptic corrections**

- Drop findings the skeptic ruled WRONG / false-positive.
- Adjust severities per skeptic's promote/demote list.
- Add blind-spot findings as new backlog rows, attributed to "Skeptic."

**Step 3: Compute the unified backlog**

Merge all surviving findings into one table. For each, compute
`rubric_points_per_hour = points_recovered / est_hours`. Sort P0s first
(by points_per_hour within P0), then P1s, then P2s.

**Step 4: Write the report**

Required sections, in this order:

1. **Executive Summary** (≤1 page)
   - One-paragraph state-of-the-platform.
   - Top 5 findings (one line each, with severity badge and points/hr).
   - Total rubric points at risk.
   - CISO go / conditional-go / no-go verdict.
   - Total estimated fix hours to clear all P0s, all P0+P1s, everything.
   - Recommended Friday-noon plan (which P0s + P1s realistically fit the
     remaining time).

2. **Scored Rubric** (table from rubric auditor, with skeptic adjustments).

3. **CISO Defensibility Scorecard** (table from CISO auditor, with
   skeptic adjustments).

4. **Doc/Code Drift Summary** (top mismatches, with skeptic adjustments).

5. **Code Quality Summary** (top smells, with skeptic adjustments).

6. **Prioritized Backlog** — single unified table:
   ID | Severity | Category | Title | Files | Est. hours | Rubric pts/hr |
   Source auditor | Status (Open).

7. **Skeptic Review Notes** — quote the skeptic's meta-observations
   verbatim and any blind spots, so the reader understands which findings
   were softened.

8. **Evidence Appendix** — for the top 25 findings, the raw quote(s) from
   the cited file(s).

9. **Pointer to Raw Outputs** — link each of the five raw files for anyone
   who wants the full detail.

**Step 5: Verify the report has every section, every backlog row has
file:line evidence, and no P0 lacks a quote.** Re-open the report and grep
yourself.

---

### Task 5: Commit everything and report back

**Step 1: Stage all new files**

```bash
cd "C:/Users/mtm16/New folder (3)/moran-openemr"
git add docs/plans/2026-05-13-week3-audit-raw/
git add docs/plans/2026-05-13-week3-audit-skeptic-review.md
git add docs/plans/2026-05-13-week3-audit-report.md
git add docs/plans/2026-05-13-week3-audit-execution.md
```

**Step 2: Commit**

```bash
git commit -m "docs(audit): execute Week 3 full-spectrum audit

Four parallel specialist auditors (rubric, CISO, code quality, doc drift)
plus a sequential skeptic, synthesized into a single prioritized backlog
report. Output is read-only — no code changes in this commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Step 3: Verify commit**

Run: `git log --oneline -1`
Expected: most recent commit is the audit commit.

**Step 4: Report to user**

Summarize in the assistant message:
- Path to the final report.
- Top 5 findings, one line each.
- Total rubric points at risk.
- CISO verdict.
- Estimated hours to clear all P0s.
- Recommended next-action set for the Friday-noon deadline.
