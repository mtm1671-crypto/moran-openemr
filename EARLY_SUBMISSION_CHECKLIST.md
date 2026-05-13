# Early Submission Checklist

This checklist tracks what must be true before sending the early AgentForge submission.

## Current Local State

Implemented locally:

- OpenEMR SMART/OAuth launch remains intact.
- Patient dropdown and source-backed chat remain intact.
- Synthetic lab/intake document upload exists in the Co-Pilot UI.
- Document extraction returns strict typed facts with source citations and bounding boxes.
- The committed synthetic scanned intake/lab images extract offline through SHA-256-pinned OCR fixtures, while configured OpenAI/OpenRouter OCR paths still run when enabled.
- Human review can approve extracted facts.
- Approved lab facts write real FHIR `Observation` resources through the write adapter when a SMART bearer token is present; successful creates must round-trip by read and retain the deterministic document identifier.
- Approved intake facts become chat evidence and vector-index seed evidence.
- Safety/access check verifies the selected OpenEMR patient before document attach/review/write when FHIR is configured.
- Week 2 evals are executable from committed fixtures and baseline with `python -m app.w2_eval --enforce`, explicit pass thresholds, and a 5% regression bound.
- GitHub Actions has a Week 2 PR gate for lint, mypy, pytest, and the 50-case eval; `.github/branch-protection-week2.json` records the required protected-branch status check.
- Production-mode document workflow persistence is available through encrypted Postgres when explicitly enabled.
- `/readyz` and `/api/capabilities` expose document workflow persistence readiness for deployed proof.

Latest local verification:

```text
API tests: 178 passed, 6 skipped
Ruff: all checks passed
Mypy: success
Week 2 eval: 50 passed, 0 failed
Web lint: passed
Web build: passed
Playwright: 13 passed
pip-audit: no known vulnerabilities found
npm audit: 0 vulnerabilities
git diff --check: passed
```

## Early Submission Blockers

| Blocker | Status | Owner | Done When |
|---|---|---|---|
| Commit Week 2 implementation | Done | Repo | Commit `6e7a3ef5f` contains document workflow, tests, docs, and diagram |
| Push to GitHub/GitLab | Done | Repo | GitHub and GitLab `master` contain commit `6e7a3ef5f` |
| Redeploy Railway API/web | Done | Railway | API deployment `a63dc595-f653-44a1-8585-dca3dbf4ebe8` and web deployment `ae344f94-7939-4a07-ba07-6afd5af77ecc` were deployed from clean service packages on 2026-05-08 |
| Production smoke test | Done | Demo | API `/readyz` is 200, document workflow persistence readiness is true, web root is 200, and no-token production document access returns 401; full OpenEMR browser capture is still manual video work |
| Week 2 document smoke test | Done | Demo | Local tests cover scanned intake/lab extraction and Observation round-trip; deployed bearer-token upload/review/approved-evidence/chat path passed on job `w2doc-a77e9b6b-f6ac-4d1f-9cee-ca5e9c2d7b4a` |
| Screenshot/video evidence update | Done | Submission | Screenshots/video segment captured for document extraction, review, bbox preview, and evidence-backed chat |
| Eval doc refresh | Done | Repo | `EVAL_DATASET.md` records latest local eval gate, pass thresholds, hybrid RAG metadata, and deployed checks |

Post-redeploy endpoint checks:

```text
Co-Pilot API /readyz: 200
Co-Pilot API document_workflow_persistence_enabled: true
Co-Pilot API document_workflow_storage: true
Co-Pilot API document_workflow_persistence_ready: true
Co-Pilot API /api/documents/patients/demo-diabetes-001/approved-evidence without auth: 401
Co-Pilot API bearer upload/review/approved-evidence/chat: passed
Co-Pilot API patient/guideline bundle separation in live chat: passed
Co-Pilot web /: 200
Co-Pilot web contains document panel markup: yes
```

## Demo Script Delta

Add this Week 2 section after the existing chat/source-link walkthrough:

1. Select an authorized synthetic patient.
2. Upload a synthetic intake form.
3. Click `Extract`.
4. Show extracted facts, source preview, bounding-box highlight, and trace.
5. Click `Approve all`.
6. Ask `What social barriers are documented?`.
7. Show the answer citing approved document evidence.
8. Upload a synthetic lab document.
9. Click `Extract`, `Approve all`, and `Write labs`; show the write result from OpenEMR FHIR `Observation.create`.
10. Explain that only approved lab facts are eligible for `Observation` writes, and missing SMART write scope produces a retryable re-authorization message.

## Production Caveats To State Clearly

- Local/default Week 2 document workflow uses in-memory storage for demo and tests. Production-mode workflow persistence now exists through encrypted Postgres and is enabled/ready on the Railway demo.
- Synthetic text/PDF extraction is deterministic. The committed synthetic scan images now have offline OCR fixtures; arbitrary scanned PDF/image OCR still requires the provider-backed OCR path and is not broad real-world production OCR.
- OpenEMR `DocumentReference` source-document round trip is not complete yet; the current source preview proves citation/bounding-box plumbing inside Co-Pilot.
- The executable Week 2 eval gate now has 50 deterministic committed cases, a passing baseline, explicit thresholds, a 5% regression bound, and a GitHub Actions workflow. Apply `.github/branch-protection-week2.json` in GitHub branch protection after push; mirror the same command into GitLab only if the final submission must use GitLab status checks.

## Remaining Manual Submission Work

- Add the uploaded demo video link to the submission form.
- Mention the production caveats above clearly.

Optional final local rerun:

```powershell
cd copilot/api
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m app.w2_eval --enforce

cd ..\web
npm run lint
npm run build
$env:PLAYWRIGHT_API_PORT='8126'; $env:PLAYWRIGHT_WEB_PORT='3126'; $env:PLAYWRIGHT_OPENEMR_MOCK_PORT='9926'; npm run test:e2e
```
