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

Latest submitted code:

```text
81a85a6ae Record Week 2 redeploy status
6e7a3ef5f Implement Week 2 document evidence workflow
```

## Required Artifacts

| Requirement | Artifact |
|---|---|
| GitHub repository forked from OpenEMR with setup guide, architecture overview, and deployed link | [README.md](README.md) |
| Audit document with one-page summary and findings | [AUDIT.md](AUDIT.md) |
| User doc with target user and use cases | [USER.md](USER.md) |
| Agent architecture doc with one-page overview, framework choices, verification strategy, and tradeoffs | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Week 2 multimodal/agent architecture | [W2_ARCHITECTURE.md](W2_ARCHITECTURE.md) |
| Eval dataset and results | [EVAL_DATASET.md](EVAL_DATASET.md) |
| AI cost analysis | [AI_COST_ANALYSIS.md](AI_COST_ANALYSIS.md) |
| Demo plan and deployed proof notes | [DEMO_PLAN.md](DEMO_PLAN.md), [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md) |
| Final readiness checklist | [EARLY_SUBMISSION_CHECKLIST.md](EARLY_SUBMISSION_CHECKLIST.md) |

Demo video:

```text
Paste the uploaded video link into the submission form.
```

## What The Product Demonstrates

- Clinician launches Co-Pilot from a deployed OpenEMR instance.
- SMART/OAuth authenticates against OpenEMR.
- Co-Pilot stores the OpenEMR bearer token in an encrypted HttpOnly session.
- The clinician selects an authorized patient from the patient dropdown.
- Chat retrieves patient-scoped FHIR evidence and source-backed unstructured notes.
- Answers include citations and a verification/audit trace.
- Source links re-check authorization before showing FHIR JSON.
- Treatment, diagnosis, medication-change, dosing, order, and care-plan requests are refused.
- Week 2 document flow uploads synthetic lab/intake documents, extracts strict facts with bounding boxes, supports human approval, writes approved lab facts through the Observation adapter, and makes approved document facts available to chat/vector evidence.

## Verification Snapshot

Local checks:

```text
API tests: 114 passed, 5 skipped
Ruff: all checks passed
Mypy: success
Web build: passed
Playwright: 7 passed
git diff --check: passed
```

Deployed endpoint checks after Railway redeploy:

```text
Co-Pilot API /readyz: 200
Co-Pilot API document route without auth: 401
Co-Pilot web /: 200
Co-Pilot web document panel markup: present
```

## Final Manual Capture Checklist

Record or verify these in the final video:

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
16. Click `Extract`, `Approve all`, and `Write labs`.

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
- Week 2 document workflow storage is in-memory in this slice; encrypted Postgres persistence is required before real production use.
- Synthetic text/PDF extraction is deterministic. Scanned PDF OCR/VLM escalation is designed but not production-complete.
- OpenEMR `DocumentReference` source-document round trip is not complete yet; current source preview proves citation and bounding-box plumbing inside Co-Pilot.
- The strict 50-case Week 2 eval gate has utilities and fixture shape, but the blocking GitLab CI gate is not activated yet.

