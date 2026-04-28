# Clinical Co-Pilot Demo Plan

## Demo Goal

Show a serious, source-backed primary care workflow: a clinician authenticates, selects one patient, asks concise chart questions, receives cited answers, and sees the assistant refuse unsupported treatment recommendations.

Target length: 3-5 minutes.

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

1. Open the standalone Co-Pilot app.
2. State the auth scope: local demo auth with OpenEMR-backed FHIR reads.
3. Show the role-aware landing state as `dev-doctor`.
4. Search for or select the demo patient.
5. Ask: "What should I know before seeing this patient?"
6. Show streamed status:
   - checking access
   - retrieving demographics
   - retrieving active problems
   - retrieving recent labs
   - verifying sources
7. Show final answer with inline source labels.
8. Click one citation and open the underlying OpenEMR source or source detail view.
9. Ask: "Show recent labs and abnormal results."
10. Show cited lab answer.
11. Ask: "What medication changes should I make?"
12. Show refusal:
    - no treatment recommendations in MVP
    - offer to show active problems, recent labs, current meds, and allergies with sources.

## What The Demo Must Prove

- The app is not a general chatbot.
- The assistant is locked to one selected patient.
- The assistant retrieves evidence before answering.
- Every factual claim has a source.
- The assistant can answer follow-ups.
- The assistant refuses treatment recommendations.
- The UI exposes a concise audit trail without hidden chain-of-thought.

## Failure Cases To Avoid

- No citation on a patient-specific claim.
- Citing a source that does not open.
- Saying a patient lacks data when the correct statement is "not found in retrieved records."
- Showing raw chain-of-thought.
- Showing PHI in logs, browser console output, or error messages.
- Letting the user ask about another patient inside the same conversation context.
