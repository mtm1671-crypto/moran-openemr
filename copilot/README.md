# Co-Pilot Services

The main AgentForge Clinical Co-Pilot documentation has been consolidated into the repository root [README.md](../README.md).

This folder contains the standalone Co-Pilot services:

```text
copilot/
  api/       FastAPI auth, FHIR retrieval, chat, provider adapters, verifier
  web/       Next.js SMART auth, proxy, patient dropdown, chat UI
  worker/    Future ETL, prefetch, reindex, and embedding jobs
  scripts/   Demo seeding and readiness utilities
```

Use the root README for:

- deployed URLs and final submission checklist
- demo patient list and seed commands
- local API/web setup
- Railway deployment commands and env vars
- PHI/demo model-provider guardrails
- verification commands
