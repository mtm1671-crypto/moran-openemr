# Clinical Co-Pilot Demo Plan

## Demo Goal

Show a serious, source-backed primary care workflow: a clinician authenticates from OpenEMR, selects one patient, asks concise chart questions, receives cited answers, sees the assistant refuse unsupported treatment recommendations, and uses the Week 2 document evidence flow for synthetic intake/lab documents.

Target length: 3-5 minutes.

For submission logistics, use [SUBMISSION.md](SUBMISSION.md). For deployed proof notes, use [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md).

## Demo Patient

Use the seeded serious synthetic primary-care patient:

```text
Name: Elena Morrison
OpenEMR public id: AF-MVP-001
Search term: mo
Problems: type 2 diabetes, hypertension, stage 3a chronic kidney disease
Recent labs: A1c, creatinine, eGFR
```

Seed or refresh it from the repo root with:

```powershell
.\copilot\scripts\seed-openemr-demo-patient.ps1
```

Do not use real PHI.

## Script

1. Open the Railway OpenEMR URL briefly and show that the EMR is accessible.
2. Explain the final placement: the Co-Pilot belongs as a top-level OpenEMR tab alongside Schedule/Calendar, with chart and schedule entry points that launch patient context.
3. Launch the deployed Co-Pilot from OpenEMR.
4. Complete SMART/OAuth if prompted.
5. Show the authenticated landing state as `doctor`.
6. Select the demo patient from the patient dropdown.
7. Ask: "What should I know before seeing this patient?"
8. Show streamed status:
   - checking access
   - retrieving demographics
   - retrieving active problems
   - retrieving recent labs
   - verifying sources
9. Show final answer with source labels.
10. Click one citation and open the source detail view.
11. Ask: "Summarize recent clinical notes for this patient."
12. Show cited unstructured note evidence.
13. Ask: "What medication changes should I make?"
14. Show refusal:
    - no treatment recommendations in MVP
    - offer to show active problems, recent labs, current meds, and allergies with sources.
15. Select Margaret Chen with search term `chen`.
16. Click `Open document workflow`.
17. Upload `example-documents/lab-results/p01-chen-lipid-panel.pdf` as a `Lab PDF`.
18. Click `Extract`.
19. Show the document workflow proof strip: durable storage readiness, patient assignment, source SHA-256, extraction count, persistence count, and write status.
20. Show extracted lipid facts with source quote and citation checks.
21. Click `Approve all`.
22. Show `Approved patient evidence` has retrievable evidence objects.
23. Reload the Co-Pilot page, reselect Margaret Chen, reopen `Open document workflow`, and click `Refresh evidence` to show the approved document evidence came back from durable storage.
24. Ask: "What changed and what should I pay attention to for diabetes or lipids?"
25. Show the answer citing approved document evidence and the audit route trace containing `approved_document_evidence`.
26. Reopen `Open document workflow` if the popup was closed, then upload a synthetic intake text file:

```text
Social History: Misses doses when work shifts change
```

27. Click `Extract`.
28. Show extracted fact, source preview, bounding-box highlight, and trace.
29. Click `Approve all`.
30. Ask: "What social barriers are documented?"
31. Show the answer citing approved document evidence.
32. Reopen `Open document workflow` if needed, then upload a synthetic lab text file:

```text
Collection Date: 2026-03-12
Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
LDL Cholesterol 142 mg/dL reference range 0-99 H
```

33. Click `Extract` and `Approve all`.
34. Point out the `Write` badge. In the current deployed OpenEMR, FHIR `Observation.create` is not exposed, so lab writeback is unavailable while approved evidence retrieval still works.

## Product Placement Talk Track

Use this line when transitioning from OpenEMR to the Co-Pilot demo:

```text
Long term, this belongs directly inside OpenEMR as a top-level Co-Pilot tab alongside Schedule/Calendar and the other daily workflow areas. The MVP is standalone so the agent, verifier, and retrieval services can be secured and tested independently, but the intended user experience is an embedded EMR workspace that opens with the current patient context when launched from a chart or schedule row.
```

## What The Demo Must Prove

- The app is not a general chatbot.
- The assistant is locked to one selected patient.
- The assistant retrieves evidence before answering.
- Every factual claim has a source.
- The assistant can answer follow-ups.
- The assistant refuses treatment recommendations.
- The UI exposes a concise audit trail without hidden chain-of-thought.
- The document workflow preserves source citations and bounding-box evidence.
- Chart writes are gated by explicit human approval.

## Failure Cases To Avoid

- No citation on a patient-specific claim.
- Citing a source that does not open.
- Saying a patient lacks data when the correct statement is "not found in retrieved records."
- Showing raw chain-of-thought.
- Showing PHI in logs, browser console output, or error messages.
- Letting the user ask about another patient inside the same conversation context.
- Presenting the synthetic document workflow as real-PHI-ready persistence.
