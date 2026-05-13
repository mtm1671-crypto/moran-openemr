# AgentForge Submission Packet

Use this file as the source of truth while filling out the AgentForge submission form.

## Repository And Deployments

| Item | Link |
|---|---|
| GitHub repository | https://github.com/mtm1671-crypto/moran-openemr |
| GitLab mirror | https://labs.gauntletai.com/michaelmoran/moran-openemr |
| OpenEMR deployment | https://openemr-production-f5ed.up.railway.app |
| Co-Pilot web deployment | https://copilot-web-production.up.railway.app |
| Co-Pilot API deployment | https://copilot-api-production-9f84.up.railway.app |
| API readiness | https://copilot-api-production-9f84.up.railway.app/readyz |
| Week 3 adversarial operator | https://adversarial-production.up.railway.app |

Latest submitted code:

```text
Current HEAD: Map example profiles to writable OpenEMR patients
81a85a6ae Record Week 2 redeploy status
6e7a3ef5f Implement Week 2 document evidence workflow
```

Current local working tree includes post-review Week 2 hardening for executable evals, durable document workflow persistence with source-key reuse, supervisor/guideline routing, stricter verification, a readable evidence viewer instead of raw JSON source pages, and an idempotent `Observation.create` write adapter that follows OpenEMR FHIR capability metadata.

## Required Artifacts

| Requirement | Artifact |
|---|---|
| GitHub repository forked from OpenEMR with setup guide, architecture overview, and deployed link | [README.md](README.md) |
| Audit document with one-page summary and findings | [AUDIT.md](AUDIT.md) |
| User doc with target user and use cases | [USER.md](USER.md) |
| Agent architecture doc with one-page overview, framework choices, verification strategy, and tradeoffs | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Week 2 multimodal/agent architecture | [W2_ARCHITECTURE.md](W2_ARCHITECTURE.md) |
| Week 3 adversarial platform architecture and evidence | [W3_ARCHITECTURE.md](W3_ARCHITECTURE.md), [WEEK3_SUBMISSION_CHECKLIST.md](WEEK3_SUBMISSION_CHECKLIST.md), and [VULNERABILITY_REPORTS.md](VULNERABILITY_REPORTS.md) |
| Eval dataset and results | [EVAL_DATASET.md](EVAL_DATASET.md) |
| AI cost analysis | [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md) |
| Demo plan and deployed proof notes | [DEMO_PLAN.md](DEMO_PLAN.md), [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md) |
| Final readiness checklist | [EARLY_SUBMISSION_CHECKLIST.md](EARLY_SUBMISSION_CHECKLIST.md) |

Demo video:

```text
Captured; paste the uploaded video link into the submission form.
```

## What The Product Demonstrates

- Clinician launches Co-Pilot from a deployed OpenEMR instance.
- SMART/OAuth authenticates against OpenEMR.
- Co-Pilot stores the OpenEMR bearer token in an encrypted HttpOnly session.
- The clinician selects an authorized patient from the patient dropdown.
- Chat retrieves patient-scoped FHIR evidence and source-backed unstructured notes.
- Answers include citations and a verification/audit trace.
- Source links re-check authorization before showing a readable evidence viewer, with raw JSON available behind an expandable details panel.
- Treatment, diagnosis, medication-change, dosing, order, and care-plan requests are refused.
- Week 2 document flow uploads synthetic lab/intake documents, extracts strict facts with bounding boxes, supports human approval, writes approved lab facts through the Observation adapter with round-trip read verification, and makes approved document facts available to chat/vector evidence.

## Verification Snapshot

Local checks:

```text
API tests: 192 passed, 6 skipped
Ruff: all checks passed
Mypy: success
Week 2 eval: 50 passed, 0 failed with python -m app.w2_eval --enforce
Web lint: passed
Web build: passed
git diff --check: passed
```

Deployed endpoint checks after Railway redeploy:

```text
Co-Pilot API /readyz: 200
Co-Pilot API document_workflow_persistence_enabled: true
Co-Pilot API document_workflow_storage: true
Co-Pilot API document_workflow_persistence_ready: true
Co-Pilot API /api/capabilities document_workflow_persistence_ready: true
Co-Pilot API document route without auth: 401
Co-Pilot API bearer upload/review/approved-evidence/chat: passed
Co-Pilot API patient/guideline bundle separation in live chat: passed
Co-Pilot API profile roster returns OpenEMR UUIDs for Margaret, James, Sofia, Robert, and Demo Patient
Co-Pilot API document bbox/citation/source roundtrip: passed
Co-Pilot API demo-bearer write reaches OpenEMR and returns 401 re-authorization instead of demo-profile block
OpenEMR /: 302 to login page
Co-Pilot web /: 200
Co-Pilot web document panel markup: present
```

## Final Manual Capture Checklist

Record or verify these in the final video with audible narration:

1. Open deployed OpenEMR.
2. Log in with the Railway demo clinician credentials.
3. Launch Co-Pilot from OpenEMR.
4. Complete SMART/OAuth if prompted.
5. Confirm `Authenticated as doctor`.
6. Select a seeded patient from the top dropdown.
7. Ask `What should I know before seeing this patient?`.
8. Ask `Summarize recent clinical notes for this patient.`.
9. Click a citation/source link.
10. Ask `What medication changes should I make?` and show refusal.
11. Upload a synthetic intake text file.
12. Click `Extract`, show extracted fact, source preview, bounding-box highlight, and trace.
13. Click `Approve all`.
14. Ask `What social barriers are documented?` and show approved document evidence in the answer.
15. Upload a synthetic lab text file.
16. Click `Extract`, `Approve all`, and `Write labs`; show the write result. If SMART write scope is missing, show the explicit re-authorization/write-scope failure.

Suggested synthetic intake file:

```text
Social History: Misses doses when work shifts change
```

Suggested synthetic lab file:

```text
Collection Date: 2026-03-12
Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
LDL Cholesterol 142 mg/dL reference range 0-99 H
```

## Caveats To State Clearly

- The submission uses synthetic data only.
- The OpenRouter free Nemotron path is for synthetic demo data, not real PHI.
- Retrieval includes PHI-local sparse evidence matching, hybrid sparse+dense guideline retrieval, patient/guideline answer-bundle separation, and an intent-aware reranker before model context; the regression suite covers newly approved document facts beating stale cholesterol-only evidence and demographic questions staying on demographics.
- Local/default Week 2 document workflow storage remains in-memory for demo speed. A production path now persists encrypted document sources, jobs, facts, and approved evidence in Postgres when `DOCUMENT_WORKFLOW_PERSISTENCE_ENABLED=true` with `DATABASE_URL` and `ENCRYPTION_KEY`; uploads first check durable storage by deterministic source key so a process restart does not create a duplicate workflow. The Railway demo now reports document workflow persistence enabled and ready.
- Synthetic text/PDF extraction is deterministic. The committed synthetic scanned intake/lab images have offline OCR fixtures; arbitrary real-world scanned PDF/image OCR still requires the configured provider-backed OCR path.
- `Observation.create` writeback requires an OpenEMR-launched SMART session so the web proxy can inject a real bearer token with `user/Observation.write`; successful creates must round-trip by read and retain the deterministic document-fact identifier. The seeded example profiles use real OpenEMR patient UUIDs for this path. Missing FHIR config, missing SMART token, or OpenEMR authorization failures fail closed and retain approved evidence.
- OpenEMR `DocumentReference` source-document round trip is not complete yet; current source preview proves citation and bounding-box plumbing inside Co-Pilot.
- The Week 2 eval gate now enforces at least 50 committed deterministic cases, explicit per-category thresholds, and a 5% regression bound with a passing 50-case baseline. GitHub Actions wires this as `.github/workflows/copilot-week2-gate.yml`; `.github/branch-protection-week2.json` records the required `API, Safety, and Eval Gate` protected-branch status check for GitHub settings.
