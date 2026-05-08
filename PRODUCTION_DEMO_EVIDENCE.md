# Production Demo Evidence

Captured: 2026-04-29 22:39 America/Chicago / 2026-04-30T03:39Z

## Deployed Targets

| Service | URL |
|---|---|
| OpenEMR | https://openemr-production-f5ed.up.railway.app |
| Co-Pilot web | https://copilot-web-production.up.railway.app |
| Co-Pilot API | https://copilot-api-production-9f84.up.railway.app |

Latest deployed Co-Pilot web deployment checked for Week 2 visibility:
`dab3baaf-a3be-4864-8579-40f6600b78b5` on 2026-05-07.

Note: the original screenshot walkthrough below proves the Week 1 chat/source-link path.
As of 2026-05-07, the deployed web UI also exposes the Week 2 document workflow
proof panels. A fresh authenticated screenshot capture is still needed before
submission, but the production app now visibly surfaces storage readiness,
extraction details, approved patient evidence, and chat route trace.

## What The Live Walkthrough Proves

- OpenEMR is running on Railway and accepts clinician login.
- The OpenEMR Co-Pilot bridge launches the deployed Co-Pilot app.
- SMART/OAuth goes through OpenEMR provider login and scope authorization.
- Co-Pilot receives an authenticated OpenEMR session as `doctor`.
- Patient search returns the seeded OpenEMR patient `Elena Morrison`.
- Chat POSTs pass through the same-origin web proxy to the API.
- The API retrieves patient-scoped FHIR evidence from OpenEMR.
- The answer renders source labels, verification trace, and citations.
- A citation opens the Co-Pilot source endpoint, which re-reads the cited OpenEMR FHIR record.
- Treatment recommendation requests are refused by the read-only MVP policy.

## Screenshot Evidence

Artifacts live under:
`copilot/web/demo_artifacts/production-20260429-223912/`

| Step | Evidence |
|---|---|
| OpenEMR deployed login | [01-openemr-login.png](copilot/web/demo_artifacts/production-20260429-223912/01-openemr-login.png) |
| OpenEMR after login | [02-openemr-home.png](copilot/web/demo_artifacts/production-20260429-223912/02-openemr-home.png) |
| OpenEMR Co-Pilot bridge | [03-openemr-copilot-bridge.png](copilot/web/demo_artifacts/production-20260429-223912/03-openemr-copilot-bridge.png) |
| OpenEMR OAuth provider login | [04-openemr-oauth-login.png](copilot/web/demo_artifacts/production-20260429-223912/04-openemr-oauth-login.png) |
| SMART scope authorization | [05-openemr-oauth-authorize.png](copilot/web/demo_artifacts/production-20260429-223912/05-openemr-oauth-authorize.png) |
| Co-Pilot authenticated with patient search | [06-copilot-authenticated.png](copilot/web/demo_artifacts/production-20260429-223912/06-copilot-authenticated.png) |
| Agent pre-room brief with citations and trace | [08-agent-pre-room-brief.png](copilot/web/demo_artifacts/production-20260429-223912/08-agent-pre-room-brief.png) |
| Follow-up recent labs answer | [09-agent-recent-labs.png](copilot/web/demo_artifacts/production-20260429-223912/09-agent-recent-labs.png) |
| Treatment recommendation refusal | [10-agent-treatment-refusal.png](copilot/web/demo_artifacts/production-20260429-223912/10-agent-treatment-refusal.png) |
| Citation source endpoint | [11-openemr-source-record.png](copilot/web/demo_artifacts/production-20260429-223912/11-openemr-source-record.png) |

Machine-readable capture notes:
[notes.json](copilot/web/demo_artifacts/production-20260429-223912/notes.json).
Session tokens in captured URLs are redacted.

## Automated Checks From The Walkthrough

```text
authenticated_as_doctor: true
patient_search_has_elena: true
pre_room_mentions_patient_data: true
pre_room_has_evidence_labels: true
pre_room_has_verification_trace: true
pre_room_no_api_error: true
labs_query_mentions_labs: true
labs_no_api_error: true
treatment_refusal_visible: true
citation_count: 10
source_endpoint_opened: true
source_endpoint_has_fhir_json: true
```

## Data Flow To Narrate

```text
Clinician browser
  -> OpenEMR Railway app
  -> OpenEMR Co-Pilot bridge with SMART iss/aud
  -> Co-Pilot web /api/auth/start
  -> OpenEMR OAuth login and scope consent
  -> Co-Pilot web /api/auth/callback
  -> encrypted HttpOnly copilot_session cookie
  -> Co-Pilot same-origin /api/* proxy
  -> FastAPI validates OpenEMR bearer token
  -> OpenEMR FHIR patient/search/evidence reads
  -> deterministic agent response
  -> verifier checks selected-patient evidence
  -> UI renders answer, citations, and source links
```

## Live Demo Script

1. Open `https://openemr-production-f5ed.up.railway.app`.
2. Log in with the deployed OpenEMR demo clinician credentials from Railway variables.
3. Launch the top-level Co-Pilot entry or open `/interface/agentforge/copilot.php`.
4. Complete OpenEMR OAuth provider login and click `Authorize`.
5. In Co-Pilot, confirm `Authenticated as doctor`.
6. Search `mo` and select `Elena Morrison`.
7. Click `Pre-room brief`.
8. Point out the retrieval statuses, source labels, and verification trace.
9. Click `Recent labs`.
10. Click a citation and show the source endpoint returning FHIR JSON.
11. Ask `What medication changes should I make?`.
12. Show the read-only treatment recommendation refusal.

## Week 2 Manual Visibility Script

Use `https://copilot-web-production.up.railway.app` after launching/signing in from OpenEMR.

1. Confirm the main page shows a compact `Open document workflow` button below quick chart actions.
2. Click `Open document workflow` and confirm the `Document evidence` popup appears.
3. Point to the workflow proof strip:
   - `Storage` should show durable storage ready in production.
   - `Assignment` shows the selected patient or `unassigned`.
   - `Source` shows filename and source SHA-256 prefix after upload.
   - `Extraction` shows fact count and review count.
   - `Persistence` shows retrievable approved evidence count.
   - `Write` shows whether FHIR Observation writeback is available.
4. For the Margaret Chen scan demo, use [MARGARET_CHEN_DOCUMENT_DEMO.md](MARGARET_CHEN_DOCUMENT_DEMO.md) and upload `example-documents/lab-results/p01-chen-lipid-panel.pdf`.
5. For a short intake-only proof, upload a synthetic intake text file with `Social History: Misses doses when work shifts change`.
6. Click `Extract`.
7. Show the extracted fact card:
   - normalized value
   - schema/citation/bbox checks
   - source quote
   - fact id
   - selected bounding-box preview
   - supervisor trace
8. Click `Approve all`.
9. Show `Approved patient evidence` now has a retrievable evidence object and an `Open citation` link.
10. Ask `What social barriers are documented?` or `What changed and what should I pay attention to for diabetes or lipids?`.
11. Show the answer text, citation chip, retrieval chip containing `approved_document_evidence`, and `Agent route trace`.
12. Upload the synthetic lab text from `DEMO_PLAN.md` and approve it. The current deployed OpenEMR FHIR endpoint does not expose `Observation.create`, so the UI should show writeback as unavailable rather than returning raw 404 failures.

## Health And Security Smoke Checks

Latest deployed checks after the web proxy fix:

```text
API /readyz: 200
runtime_config: true
phi_controls: true
database: true
openemr_fhir_configured: true
openemr_tls_verify: true
llm_egress_disabled: true

Web /: 200
CSP frame-ancestors includes https://openemr-production-f5ed.up.railway.app
Untrusted SMART issuer rejected
Trusted OpenEMR issuer redirects with api:oemr, api:fhir, and FHIR read scopes
```

Local regression checks before redeploy:

```text
API pytest tests: 155 passed, 6 skipped
ruff: all checks passed
mypy: success
Week 2 eval gate: 4 passed, 0 failed
npm run lint: passed
npm run build: passed
npm run test:e2e: 9 passed
pip-audit: no known vulnerabilities found
npm audit: 0 vulnerabilities
```

## Week 2 Production Checks

Post-durable-persistence API checks on 2026-05-07:

```text
Co-Pilot API /readyz: 200
Co-Pilot API document_workflow_persistence_enabled: true
Co-Pilot API document_workflow_storage: true
Co-Pilot API document_workflow_persistence_ready: true
Co-Pilot API /api/capabilities document_workflow_persistence_ready: true
Co-Pilot API document route without auth: 401
Co-Pilot web /: 200
Co-Pilot web document panel markup: present
Co-Pilot web /api/capabilities document_workflow_persistence_ready: true
```

Capture these additional proof points in the authenticated browser walkthrough:

1. Co-Pilot document panel visible after OpenEMR launch.
2. Synthetic intake form upload and extraction.
3. Extracted facts with source preview and bounding-box highlight.
4. Supervisor trace entries for extraction/review/routing.
5. `Approve all` review action.
6. Chat answer to `What social barriers are documented?` showing approved document evidence.
7. Guideline-backed evidence in a lab/lipid question.
8. Synthetic lab upload, approval, and explicit `Observation.create` unavailable state.
9. Production persistence configuration if `DOCUMENT_WORKFLOW_PERSISTENCE_ENABLED=true` is enabled for the deployed API.
10. `/readyz` checks show `document_workflow_persistence_enabled=true`, `document_workflow_storage=true`, and `document_workflow_persistence_ready=true`.
11. `/api/capabilities` providers show `document_workflow_persistence_ready=true`.
