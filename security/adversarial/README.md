# AgentForge Adversarial Platform

Outside-in adversarial evaluation platform for the AgentForge Clinical Co-Pilot.

The platform is intentionally separate from the Co-Pilot API runtime. It attacks only allowlisted local or deployed targets over HTTP, stores run evidence in SQLite, and presents results through a deployed FastAPI operator UI.

## Local Setup

```powershell
cd security\adversarial
..\..\copilot\api\.venv\Scripts\python.exe -m pip install -e ".[dev]"
..\..\copilot\api\.venv\Scripts\python.exe -m pytest
```

## Common Commands

```powershell
python -m app.run_week3_eval --target local --suite seed --report-only
python -m app.run_week3_eval --target deployed --suite seed --report-only
python -m app.run_week3_eval --target local --suite regression --enforce
python -m app.run_site_scan --target-url https://owned.example --scope-id scope_agentforge_demo --authorization-note "Owned test target"
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
railway up --service adversarial .\security\adversarial --path-as-root
```

Required variables:

- `ADVERSARIAL_SQLITE_PATH=/data/week3_runs.sqlite`
- `ADVERSARIAL_PRIVATE_SQLITE_PATH=/data/private_findings.sqlite`
- `ADVERSARIAL_OPERATOR_TOKEN=<Railway secret used to access the operator UI/API>`
- `ADVERSARIAL_OPERATOR_SESSION_SECRET=<Railway secret for signed login cookies>`
- `ADVERSARIAL_OPERATOR_RATE_LIMIT_WINDOW_SECONDS=60`
- `ADVERSARIAL_OPERATOR_RATE_LIMIT_MAX_REQUESTS=120`
- `ADVERSARIAL_EVIDENCE_RETENTION_DAYS=180`
- `ADVERSARIAL_CASE_ROOT=/app/evals/week3/cases`
- `ADVERSARIAL_TARGET_MODE=deployed`
- `ADVERSARIAL_DEPLOYED_TARGET_URL=https://copilot-api-production-9f84.up.railway.app`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN_URL=https://openemr-production-f5ed.up.railway.app/oauth2/default/token`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_CLIENT_ID=<Railway secret>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_CLIENT_SECRET=<Railway secret, if client requires it>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_USERNAME=<Railway secret>`
- `ADVERSARIAL_SYNTHETIC_CLINICIAN_PASSWORD=<Railway secret>`
- `ADVERSARIAL_ALLOWED_HOSTS=adversarial-production.up.railway.app,copilot-api-production-9f84.up.railway.app,<owned client host>`
- `ADVERSARIAL_SITE_SCAN_BEARER_TOKEN=<optional low-privileged test-user bearer token>`
- `ADVERSARIAL_SITE_SCAN_COOKIE=<optional low-privileged test-user cookie>`
- `ADVERSARIAL_SITE_SCAN_MAX_URLS=12`

For a short-lived manual run, `ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN` can be supplied instead of the password-grant settings.

Mount `/data` as a persistent volume so run history survives restarts.

## Safety Defaults

- Non-allowlisted targets are rejected.
- The operator dashboard and exports require `ADVERSARIAL_OPERATOR_TOKEN` when deployed for client work; `/readyz` remains public for health checks.
- Browser form actions use signed-session CSRF tokens, operator requests are rate-limited, and mutating operator actions are recorded in the audit log.
- Generic site scanning is authorized-only: add only hosts you own or have written permission to test to `ADVERSARIAL_ALLOWED_HOSTS`.
- Site scans are bound to an authorized client/project/scope record. The default scope is seeded from `ADVERSARIAL_ALLOWED_HOSTS`, scan-mode limits, excluded paths, and request caps.
- The first generalized scanner mode is passive HTTP/header/cookie review. It does not fuzz, brute force, exploit, or crawl broadly.
- Low-privileged authenticated site scanning uses only configured test-user credentials, same-origin GET checks, and capped request counts.
- Public run exports redact vulnerability reproduction steps, passive scan evidence, and remediation specifics.
- Sensitive report and site-scan finding details are stored separately in `ADVERSARIAL_PRIVATE_SQLITE_PATH`.
- Real PHI is out of scope.
- Blocking Judge verdicts use deterministic black-box evidence.
- LLM judging is advisory until separately validated.
- SQLite must be writable or readiness fails.

## Authorized Scope Registry

The scanner keeps client, project, and authorized scope records in the adversarial SQLite database. Each site scan stores `client_id`, `project_id`, and `scope_id` so findings can be traced to the correct authorization boundary without mixing client evidence into the Co-Pilot app runtime.

By default, the app seeds:

- `client_agentforge_demo`
- `project_agentforge_security`
- `scope_agentforge_demo`

The seeded scope inherits allowlisted hosts from `ADVERSARIAL_ALLOWED_HOSTS`, permits passive and low-privileged scanning, and caps same-origin low-privileged checks with `ADVERSARIAL_SITE_SCAN_MAX_URLS`.

Operators can create additional clients, projects, and scopes from the dashboard. New scope hosts must also be present in `ADVERSARIAL_ALLOWED_HOSTS`, preserving a global deployment guardrail even when multiple client scopes exist.

## Generalized Site Scanning

The operator can run bounded passive checks against non-Co-Pilot sites when they are explicitly allowlisted and selected through an authorized scope. This is intended for owned apps, staging environments, and authorized demos.

Current checks include:

- HTTPS transport and response status.
- Security headers such as HSTS, CSP, frame protection, `X-Content-Type-Options`, and `Referrer-Policy`.
- Broad CORS wildcard detection.
- Cookie `Secure`, `HttpOnly`, and `SameSite` attributes.
- Informational server-header disclosure.
- Low-privileged authenticated checks for same-origin exposed `.env`, `.git`, debug/runtime endpoints, API schemas, backup artifacts, source maps, and privileged route responses.

Low-privileged mode is still bounded reconnaissance, not exploitation. It does not brute force, submit mutating forms, fuzz parameters, or attempt credential bypasses. It is intended for synthetic accounts on owned or explicitly authorized targets.

Future active or semi-active scanning should use an explicit scan profile and human approval. OWASP ZAP baseline mode is the right next integration point because it is designed around passive scanning rather than active exploitation.

## B2B Operations

Current client-grade controls:

- Scope-admin UI for clients, projects, hosts, modes, excluded paths, authorization notes, contacts, expiry dates, and rules-of-engagement references.
- Scan job lifecycle records for queued, running, completed, failed, and cancelled jobs.
- Finding workflow statuses for open, needs review, fixed, risk accepted, and false positive.
- Per-scope JSON/Markdown client reports.
- Private findings vault plus public redaction and evidence-retention metadata.
- Operator audit log for login, scope changes, scan jobs, suite runs, and finding/report status changes.
- Authenticated trust-package exports at `/trust/security-summary.md` and `/trust/rules-of-engagement.md`.
