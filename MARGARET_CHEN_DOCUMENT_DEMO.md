# Margaret Chen Document Persistence Demo

Last updated: 2026-05-07

This is the exact manual path for proving scan/upload -> extract -> approve -> durable storage -> retrieve -> grounded response using the synthetic Margaret Chen example.

## Demo Patient

| Field | Value |
|---|---|
| Name | Margaret Chen |
| OpenEMR public id | `AF-MVP-002` |
| Search term | `chen` |
| Source document | `example-documents/lab-results/p01-chen-lipid-panel.pdf` |
| Document MRN | `MRN-2026-04481` |
| Document date | `2026-04-23` |

Refresh deployed OpenEMR demo data after `railway login`:

```powershell
.\copilot\scripts\seed-openemr-railway-demo-patient.ps1
```

## Manual Walkthrough

1. Open OpenEMR and launch Co-Pilot from the OpenEMR Co-Pilot tab or patient context.
2. In Co-Pilot, search `chen` and select `Margaret Chen`.
3. Click `Open document workflow`.
4. In the `Document evidence` popup, choose `Lab PDF`.
5. Upload `example-documents/lab-results/p01-chen-lipid-panel.pdf`.
6. Click `Extract`.
7. Verify the proof strip:
   - `Storage` says durable storage is ready in production.
   - `Assignment` shows Margaret's selected patient id.
   - `Source` shows the uploaded filename and SHA-256 prefix.
   - `Extraction` shows extracted lipid facts.
8. Verify the extracted fact cards show:
   - `Total Cholesterol`
   - `HDL Cholesterol`
   - `LDL Cholesterol`
   - `Triglycerides`
   - schema/citation/bbox checks
   - quoted source values from the scanned PDF
9. Click `Approve all`.
10. Verify `Approved patient evidence` shows retrievable evidence objects.
11. Reload the Co-Pilot page, reselect Margaret Chen, reopen `Open document workflow`, and click `Refresh evidence`.
12. Verify approved evidence still appears. That is the browser-visible proof that it was not only in React state.
13. Ask: `What changed and what should I pay attention to for diabetes or lipids?`
14. Verify the answer cites approved document evidence and the audit trace includes `approved_document_evidence`.
15. If your OpenEMR authorization includes `user/Observation.write`, click `Write labs`; otherwise leave it disabled and call out that write-scope gating is working.

## Persistent Storage Proof

Use these public checks before the walkthrough:

```text
https://copilot-api-production-9f84.up.railway.app/readyz
checks.document_workflow_persistence_enabled = true
checks.document_workflow_storage = true
checks.document_workflow_persistence_ready = true

https://copilot-web-production.up.railway.app/api/capabilities
providers.document_workflow_persistence_enabled = true
providers.document_workflow_persistence_ready = true
```

After approval, use the same browser session to open the selected patient evidence endpoint through the web proxy:

```text
https://copilot-web-production.up.railway.app/api/documents/patients/<selected-patient-id>/approved-evidence
```

The selected patient id is visible in the patient switcher and in the document workflow `Assignment` proof badge. The response should include `evidence_count > 0` and evidence IDs like `document:w2fact-...`.

## What Is Expected To Work

- Margaret Chen is a seeded example patient after the seed script runs.
- The Chen lipid panel PDF has embedded text and should extract without OCR provider dependency.
- Approved facts should appear in `Approved patient evidence`.
- Reloading the page and refreshing evidence should still show approved facts when production durable storage is ready.
- Chat should retrieve approved document evidence and show it in the audit route trace.

## Current Limits To Say Out Loud

- Image-only scans need OCR configured. The production synthetic demo has OCR capability configured, but local deterministic mode fails closed for PNG/JPEG unless OCR is enabled.
- Writing labs into OpenEMR requires the clinician session to include `user/Observation.write`.
- The UI proves approved evidence retrieval; a full production proof should still capture screenshots after authentication.
