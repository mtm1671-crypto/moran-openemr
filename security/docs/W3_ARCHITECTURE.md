# Week 3 Architecture: Adversarial AI Security Platform

## One-Page Overview

The Week 3 platform is an outside-in adversarial evaluation system for the AgentForge Clinical Co-Pilot. It is intentionally deployed and operated separately from the Co-Pilot runtime. Its job is to run bounded attacks against allowlisted local or deployed Co-Pilot HTTP targets, capture black-box evidence, judge whether the target behaved safely, and turn findings into repeatable regression artifacts.

The MVP architecture has five layers:

1. Design inputs: `THREAT_MODEL.md`, approved JSON attack cases, environment target config, budgets, and synthetic-only credentials.
2. Run controller: `security/adversarial/app/run_week3_eval.py` loads settings, validates target allowlists, opens SQLite, and runs a selected suite.
3. Agent graph: `security/adversarial/app/graph.py` uses LangGraph to move each case through Orchestrator, Red Team, Target Runner, Judge, Documentation Draft, Regression Store, and Stop Policy nodes.
4. Evidence and persistence: `security/adversarial/app/run_store.py` persists cases, runs, black-box observations, trace events, judge verdicts, draft reports, and resilience snapshots in SQLite.
5. Operator surface: `security/adversarial/app/ui.py` exposes `/readyz`, a risk overview dashboard, and run detail pages; `security/adversarial/app/export_run.py` exports JSON and Markdown evidence.

The target under test remains the deployed Clinical Co-Pilot API:

```text
https://copilot-api-production-9f84.up.railway.app
```

The OpenEMR and Co-Pilot web deployments stay in scope for demo context and future browser-level attacks, but the current Week 3 attack harness targets the API directly. The adversarial service can use either a short-lived `ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN` or environment-provided OpenEMR password-grant settings to mint a synthetic clinician bearer token at run time, avoiding committed secrets and avoiding dependence on browser cookies or Next.js proxy session state.

## Framework Choices

FastAPI powers the operator app because the rest of the Co-Pilot backend already uses Python/FastAPI patterns, and the Week 3 UI only needs a small operator dashboard rather than a full frontend app.

LangGraph powers the MVP agent loop because the PRD requires distinct agent responsibilities and explicit handoffs. The MVP graph is deliberately bounded: the Red Team node uses approved seed cases first, the Target Runner executes a single black-box HTTP request per case, the Judge uses deterministic rules for release-blocking verdicts, and Stop Policy terminates on critical failures, target instability, human-review gates, or completion.

SQLite is the run store because Week 3 needs durable evidence with low operational overhead. A mounted Railway volume is enough for checkpoint and demo history, while JSON/Markdown exports make evidence git-friendly.

Pydantic models in `security/adversarial/app/models.py` define the contracts for attack cases, runs, observed responses, judge verdicts, reports, budgets, traces, and resilience snapshots. These schemas keep eval cases and dashboard/export code aligned.

## Trust Boundaries

- Attack prompts, generated variants, uploaded synthetic documents, and seeded notes are untrusted.
- Co-Pilot responses are untrusted until the Judge checks black-box evidence.
- Deterministic Judge verdicts can block checkpoint/release decisions.
- Optional LLM judgment is advisory only until separately validated.
- Synthetic clinician and service credentials are environment-provided and must never enter git, logs, or exports.
- Non-allowlisted targets are rejected before any attack request is sent.

## Verification Strategy

Local verification:

```powershell
cd security\adversarial
..\..\copilot\api\.venv\Scripts\python.exe -m pytest
..\..\copilot\api\.venv\Scripts\python.exe -m ruff check app tests
..\..\copilot\api\.venv\Scripts\python.exe -m mypy app
```

Campaign verification:

```powershell
python -m app.run_week3_eval --target local --suite smoke --report-only
python -m app.run_week3_eval --target deployed --suite seed --report-only
python -m app.export_run --run-id <run_id> --out evals\week3\exports
```

Submission proof requires:

- A deployed operator app with `/readyz` passing.
- A deployed seed-suite run against the deployed Co-Pilot API.
- JSON and Markdown exports that include the run id, target URL, black-box observation, verdict, trace-backed report, and no secrets.
- A dashboard view that shows the same run id and recommendation as the exported evidence.

## Tradeoffs

The MVP targets the Co-Pilot API instead of driving a full browser session. This makes authentication and evidence capture reliable for checkpoint review, but it does not yet prove browser/session attacks through the deployed Next.js UI. Browser-level attacks are a final-product expansion.

The Red Team node starts with approved seeds rather than unconstrained generation. This reduces novelty, but it avoids unsafe scope expansion and makes the first suite reproducible.

The Judge is deterministic and conservative. It can miss semantic failures that require deeper clinical reasoning, but its blocking verdicts are stable, testable, and explainable. Ambiguous high-severity cases become human-review items rather than false passes.

SQLite is enough for checkpoint and demo evidence. A larger production platform would eventually move run history, reports, queues, and trend metrics into a managed database and job system.
