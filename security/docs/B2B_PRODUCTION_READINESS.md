# B2B Production Readiness Controls

Status: implemented B2B foundation for the adversarial operator service.

## Implemented Controls

- Client, project, and authorized-scope administration.
- Global host allowlist plus per-scope host, mode, path, request-cap, expiry, contact, and authorization-note controls.
- Operator token auth, signed session cookies, CSRF protection for browser form actions, security headers, and per-path rate limiting.
- Audit log entries for login, suite runs, scope administration, scan jobs, and finding/report workflow changes.
- Scan job lifecycle records for queued, running, completed, failed, cancelled, and cancellation-requested states.
- Public/private evidence split: public SQLite stores redacted summaries; sensitive reproduction and remediation details live in the private findings database.
- Evidence retention metadata on vulnerability reports and site-scan findings.
- Finding lifecycle statuses: open, needs review, fixed, risk accepted, false positive.
- Client report exports by authorized scope in JSON and Markdown.
- Trust package endpoints for a security summary and rules-of-engagement template.

## Remaining Enterprise Hardening

- Replace single shared operator token with SSO/OIDC and named users.
- Move scan execution to a durable worker queue before long-running scans or concurrent client work.
- Add encrypted managed storage and backup/restore checks for the private findings vault.
- Add external monitoring and alerting for failed deployments, storage errors, and scan-job failures.
- Add signed rules-of-engagement upload/attachment support.
- Add CI deployment gates for the regression suite.

## Verification

Run from `security/adversarial/`:

```powershell
..\..\copilot\api\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
..\..\copilot\api\.venv\Scripts\python.exe -m ruff check app tests --no-cache
..\..\copilot\api\.venv\Scripts\python.exe -m mypy app --cache-dir <temp>
..\..\copilot\api\.venv\Scripts\python.exe -m app.run_judge_eval --enforce
```
