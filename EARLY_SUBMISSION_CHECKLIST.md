# Early Submission Checklist

This checklist tracks what must be true before sending the early AgentForge submission.

## Current Local State

Implemented locally:

- OpenEMR SMART/OAuth launch remains intact.
- Patient dropdown and source-backed chat remain intact.
- Synthetic lab/intake document upload exists in the Co-Pilot UI.
- Document extraction returns strict typed facts with source citations and bounding boxes.
- Human review can approve extracted facts.
- Approved lab facts can write demo/FHIR `Observation` resources through the write adapter.
- Approved intake facts become chat evidence and vector-index seed evidence.
- Safety/access check verifies the selected OpenEMR patient before document attach/review/write when FHIR is configured.

Latest local verification:

```text
API tests: 114 passed, 5 skipped
Ruff: all checks passed
Mypy: success
Web build: passed
Playwright: 7 passed
git diff --check: passed
```

## Early Submission Blockers

| Blocker | Status | Owner | Done When |
|---|---|---|---|
| Commit Week 2 implementation | Done | Repo | Commit `6e7a3ef5f` contains document workflow, tests, docs, and diagram |
| Push to GitHub/GitLab | Done | Repo | GitHub and GitLab `master` contain commit `6e7a3ef5f` |
| Redeploy Railway API/web | Done | Railway | API and web were redeployed from clean service packages on 2026-05-04 |
| Production smoke test | Partial | Demo | API `/readyz` is 200 and web root is 200; full OpenEMR auth walkthrough still needs browser capture |
| Week 2 document smoke test | Partial | Demo | Deployed document API route is present and web panel is present; authenticated upload/review/chat path still needs browser capture |
| Screenshot/video evidence update | Not done | Submission | New screenshots or video segment show document extraction, review, bbox preview, and evidence-backed chat |
| Eval doc refresh | Local done, deployed pending | Repo | `EVAL_DATASET.md` records latest local and deployed checks |

Post-redeploy endpoint checks:

```text
Co-Pilot API /readyz: 200
Co-Pilot API /api/documents/patients/demo-diabetes-001/approved-evidence without auth: 401
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
9. Click `Extract`, `Approve all`, and `Write labs`.
10. Show write result and explain that only approved lab facts are eligible for `Observation` writes.

## Production Caveats To State Clearly

- Week 2 document workflow currently uses in-memory workflow storage in this slice. It is suitable for demo and automated smoke tests, but persistent encrypted Postgres storage is still required before real production use.
- Synthetic text/PDF extraction is deterministic. Scanned PDF OCR/VLM escalation is designed but not production-complete in this slice.
- OpenEMR `DocumentReference` source-document round trip is not complete yet; the current source preview proves citation/bounding-box plumbing inside Co-Pilot.
- The 50-case Week 2 eval gate has utility scaffolding and initial fixture shape, but the blocking GitLab CI gate is not activated yet.

## Recommended Next Commands

```powershell
git status --short
git add README.md PLANNING.md EARLY_SUBMISSION_CHECKLIST.md W2_ARCHITECTURE.md docs copilot
git commit -m "Implement Week 2 document evidence workflow"
git push origin master
git push gitlab master
```

Then trigger/review Railway deploys and run:

```powershell
cd copilot/api
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app

cd ..\web
npm run build
$env:PLAYWRIGHT_API_PORT='8126'; $env:PLAYWRIGHT_WEB_PORT='3126'; $env:PLAYWRIGHT_OPENEMR_MOCK_PORT='9926'; npm run test:e2e
```
