# Week 3 Submission Checklist

This file tracks the adversarial AI security platform submission separately from the completed Week 2 Clinical Co-Pilot submission.

## Ready Now

- `THREAT_MODEL.md` covers the required healthcare risk families and failure definitions.
- `WEEK3_PRD.md` records goals, non-goals, acceptance criteria, and deliverables.
- `W3_SYSTEM_DESIGN.md` and `docs/diagrams/w3-adversarial-platform.png` provide the container-level system design.
- `W3_ARCHITECTURE.md` explains the implementation architecture, framework choices, verification strategy, and tradeoffs.
- `adversarial/` contains the outside-in FastAPI/LangGraph/SQLite platform.
- `adversarial/evals/week3/cases/` contains seed cases for the expanded Week 3 hospital-director risk families, including direct prompt injection, multi-turn manipulation, state corruption, identity hijacking, and three indirect-injection layers.
- Railway service `adversarial` is deployed at `https://adversarial-production.up.railway.app`.
- Persistent `/data` SQLite storage is mounted and `/readyz` returns `200`.
- Synthetic clinician OAuth password-grant secrets are configured; deployed Co-Pilot API accepts the minted token at `/api/me`.
- The deployed seed suite has run against `https://copilot-api-production-9f84.up.railway.app`.
- Latest deployed campaign evidence:
  - `run_689e5c9dac06` tool misuse
  - `run_1058e5a0ac0e` state corruption
  - `run_723d52931516` multi-turn manipulation
  - `run_f6ad95eff8f3` uploaded-document indirect injection
  - `run_c4dff218ab48` seeded-note indirect injection, draft `MISSING_CITATION` finding
  - `run_c2d34acb0b29` prompt-simulated indirect injection
  - `run_1eab122967fe` identity hijacking
  - `run_f442a164d420` direct prompt injection
  - `run_f72912c8ab54` cross-patient PHI
  - `run_c0e7340f28b1` cost amplification
  - `run_e1423a37744b` unsafe clinical recommendation
  - `run_7ca516d5a6a5` citation manipulation
  - `run_db74a32744c2` authorization/session confusion
- The deployed dashboard shows 13 latest verdicts, expanded risk-family coverage, and 1 current draft report. No official confirmed vulnerability report exists until deterministic replay or human review confirms it.
- Each deployed run has reviewer-accessible JSON and Markdown export links.
- Local checks pass for tests, lint, and type checking.

## Not Ready Yet

- Promote or dismiss the seeded-note draft finding after deterministic replay or human review.
- Extend final demo video/screenshots to show the adversarial operator app, risk overview, deployed campaign evidence, draft report, and export.
- Add target fixture setup for uploaded-document and seeded-note cases before treating those layers as full ingestion-path attacks.

## Final Commands

```powershell
cd adversarial
..\copilot\api\.venv\Scripts\python.exe -m pytest
..\copilot\api\.venv\Scripts\python.exe -m ruff check app tests
..\copilot\api\.venv\Scripts\python.exe -m mypy app
python -m app.run_week3_eval --target deployed --suite seed --report-only
python -m app.export_run --run-id <run_id> --out evals\week3\exports
```

For deployed evidence, open the operator and use per-run export links:

```text
https://adversarial-production.up.railway.app
https://adversarial-production.up.railway.app/runs/run_c4dff218ab48.json
https://adversarial-production.up.railway.app/runs/run_c4dff218ab48.md
```
