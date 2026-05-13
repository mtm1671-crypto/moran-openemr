# AgentForge Adversarial Platform

Outside-in adversarial evaluation platform for the AgentForge Clinical Co-Pilot.

The platform is intentionally separate from the Co-Pilot API runtime. It attacks only allowlisted local or deployed targets over HTTP, stores run evidence in SQLite, and presents results through a deployed FastAPI operator UI.

## Local Setup

```powershell
cd adversarial
..\copilot\api\.venv\Scripts\python.exe -m pip install -e ".[dev]"
..\copilot\api\.venv\Scripts\python.exe -m pytest
```

## Common Commands

```powershell
python -m app.run_week3_eval --target local --suite seed --report-only
python -m app.run_week3_eval --target deployed --suite seed --report-only
python -m app.run_week3_eval --target local --suite regression --enforce
python -m app.export_run --run-id <run_id> --out evals\week3\exports
python -m uvicorn app.ui:create_app --factory --host 0.0.0.0 --port 8080
```

`enforce` exits nonzero when a critical or high-severity deterministic failure is recorded. `report-only` always records evidence without failing the process.

## Deployed Operator

Current production operator:

```text
https://adversarial-production.up.railway.app
```

The dashboard shows the latest verdict per case, current risk-family coverage, and current vulnerability reports. Historical runs remain available in SQLite and through per-run export links:

```text
https://adversarial-production.up.railway.app/runs/<run_id>.json
https://adversarial-production.up.railway.app/runs/<run_id>.md
```

## Railway Deployment

Create a separate Railway service for the adversarial operator app and deploy this folder as the service root:

```powershell
railway up --service adversarial .\adversarial --path-as-root
```

Required variables:

- `ADVERSARIAL_SQLITE_PATH=/data/week3_runs.sqlite`
- `ADVERSARIAL_CASE_ROOT=/app/evals/week3/cases`
- `ADVERSARIAL_TARGET_MODE=deployed`
- `ADVERSARIAL_DEPLOYED_TARGET_URL=https://copilot-api-production-9f84.up.railway.app`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN_URL=https://openemr-production-f5ed.up.railway.app/oauth2/default/token`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_CLIENT_ID=<Railway secret>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_CLIENT_SECRET=<Railway secret, if client requires it>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_USERNAME=<Railway secret>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_PASSWORD=<Railway secret>`

For a short-lived manual run, `ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN` can be supplied instead of the password-grant settings.

Mount `/data` as a persistent volume so run history survives restarts.

## Safety Defaults

- Non-allowlisted targets are rejected.
- Real PHI is out of scope.
- Blocking Judge verdicts use deterministic black-box evidence.
- LLM judging is advisory until separately validated.
- SQLite must be writable or readiness fails.
