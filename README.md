# Moran OpenEMR

Hi Ken, not much of a healthcare guy but here it goes!

This is my fork of [OpenEMR](https://github.com/openemr/openemr) with an AI chart assistant bolted on properly: a clinician launches **Co-Pilot** from inside OpenEMR, picks a patient, asks questions about the chart, and gets short answers with citations that link back to the source record. It's read-only on purpose, it runs on synthetic data only, and there's a separate attack platform whose whole job is to try to break it.

## Why it's interesting

- **OpenEMR stays the boss.** Login goes through OpenEMR's own SMART/OAuth flow, tokens are checked against OpenEMR's JWKS, and the model only ever sees the one patient the clinician is authorized for.
- **No answer ships unverified.** The model has to cite evidence IDs; a deterministic verifier throws out unknown or cross-patient citations and anything that looks like a treatment, diagnosis, medication, or order recommendation.
- **Documents turn into evidence.** Upload a scanned lab or intake form, see extracted facts with bounding-box highlights, approve them, and only then can they be written back to OpenEMR (idempotently, with a read-back check).
- **It gets attacked on every push.** `security/adversarial/` runs prompt-injection, cross-patient PHI, identity-hijack, and cost-amplification cases against the deployed API and fails CI on regressions.
- **It's cheap by design.** Structured questions skip the LLM entirely; only broad note synthesis reaches a bigger model under token caps.

## Live demo

| Service | URL |
|---|---|
| OpenEMR fork | https://openemr-production-f5ed.up.railway.app |
| Co-Pilot web | https://copilot-web-production.up.railway.app |
| Co-Pilot API | https://copilot-api-production-9f84.up.railway.app/readyz |
| Adversarial operator | https://adversarial-production.up.railway.app |

Try: log in, open **Co-Pilot**, pick *Margaret Chen*, ask *"What should I know before seeing this patient?"*, click a citation, then ask *"What medication changes should I make?"* and watch it refuse.

## What's in the repo

```text
interface/agentforge/   OpenEMR -> Co-Pilot launch bridge + menu entries
copilot/api/            FastAPI: auth, FHIR retrieval, vector search, chat, verifier, document workflow
copilot/web/            Next.js: SMART auth, patient picker, chat + citations, document review
security/adversarial/   Attack corpus, target harness, judge, reports, operator UI
```

Everything else is upstream OpenEMR.

## Run it locally

```powershell
cd docker/development-easy && docker compose up --detach --wait   # OpenEMR at http://localhost:8300 (admin / pass)

cd copilot/api
python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001

cd copilot/web
npm install; npm run dev -- --port 3001
```

Checks: `pytest`, `ruff`, `mypy`, and `python -m app.w2_eval --enforce` (50-case eval gate) in `copilot/api`; `npm run build` in `copilot/web`. Latest run: 204 API tests, 73 adversarial tests, 50/50 eval cases passing.

## Digging deeper

[ARCHITECTURE.md](ARCHITECTURE.md) · [DOCUMENT_WORKFLOW_ARCHITECTURE.md](DOCUMENT_WORKFLOW_ARCHITECTURE.md) · [THREAT_MODEL.md](THREAT_MODEL.md) · [AUDIT.md](AUDIT.md) · [WALKTHROUGH.md](WALKTHROUGH.md) · [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) · [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md)

## License

GPL v3, same as upstream OpenEMR.
