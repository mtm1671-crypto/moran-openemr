# Example Documents

These files are synthetic clinical examples for local development and submission testing. They
are not real patient records and should still be handled as PHI-shaped data.

## Current Coverage

- `intake-forms/*.pdf`: embedded-text intake forms used by the deterministic extraction tests.
- `lab-results/*.pdf`: embedded-text lab reports used by the deterministic extraction tests.
- `*.png`: scanned/image-style examples. The local deterministic pipeline intentionally fails
  closed for image files until an OCR or vision provider is configured.
- `p01-chen-*`: Margaret Chen synthetic examples used for the manual durable-storage
  demo and Week 2 golden cases.

## Verification

The API regression test `copilot/api/tests/test_example_documents.py` uploads these documents
through `/api/documents/attach-and-extract`, checks source-backed extracted facts, verifies image
fail-closed behavior, approves a sample PDF extraction, and confirms chat can answer from the
approved document evidence.

For deployed OCR verification, configure staging with either `OCR_PROVIDER=openai` plus the
required OpenAI/PHI approval variables, or `OCR_PROVIDER=openrouter` with a vision-capable
`OPENROUTER_OCR_MODEL` such as `baidu/qianfan-ocr-fast:free` for synthetic demo data. Then run:

```powershell
$env:RUN_STAGING_OCR="1"
$env:STAGING_COPILOT_API_BASE_URL="https://<copilot-api-domain>"
$env:STAGING_COPILOT_BEARER_TOKEN="<authorized-openemr-access-token>"
$env:STAGING_COPILOT_PATIENT_ID="<authorized-patient-id>"
.\.venv\Scripts\python.exe -m pytest tests\test_staging_ocr_smoke.py
```
