# Co-Pilot Worker

The production worker uses the same Python package and settings contract as `copilot/api`.

Nightly maintenance entrypoint:

```powershell
cd ..\api
.\.venv\Scripts\python.exe -m app.jobs nightly-maintenance
```

Railway worker config lives at `copilot/api/railway.worker.toml`. It runs:

```text
python -m app.jobs nightly-maintenance
```

Manual patient reindex entrypoint:

```powershell
cd ..\api
.\.venv\Scripts\python.exe -m app.jobs patient-reindex --patient-id <openemr-fhir-patient-id>
```

The nightly job creates/repairs PHI storage tables, purges expired encrypted evidence cache rows, purges expired vector index rows, applies audit/conversation/job retention, and can run patient reindex when `NIGHTLY_REINDEX_ENABLED=true`. Patient reindex requires `OPENEMR_SERVICE_ACCOUNT_ENABLED=true` plus either a static backend bearer token or client-credentials settings. Do not use a clinician OAuth session in a background job.
