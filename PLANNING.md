# AgentForge Planning Documents

The repository root [README.md](README.md) is the primary final-submission and setup guide. The planning artifacts below are supporting references for reviewers who want deeper context.

## Core Planning Set

| Document | Purpose |
|---|---|
| [PRESEARCH.md](PRESEARCH.md) | Pre-code planning, constraints, and discovery notes |
| [AUDIT.md](AUDIT.md) | OpenEMR security, performance, architecture, data quality, and compliance audit |
| [USERS.md](USERS.md) | Target users, workflow, roles, use cases, and demo scenario |
| [USER.md](USER.md) | Standalone primary-user and use-case document |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Co-Pilot architecture, OpenEMR placement, verification, and tradeoffs |
| [W2_ARCHITECTURE.md](W2_ARCHITECTURE.md) | Week 2 multimodal document, worker graph, RAG, eval gate, and risk design |
| [EARLY_SUBMISSION_CHECKLIST.md](EARLY_SUBMISSION_CHECKLIST.md) | Week 2 early submission blockers, smoke path, and deployment checklist |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | Local and Railway deployment plan |
| [DEMO_PLAN.md](DEMO_PLAN.md) | 3-5 minute demo script and talk track |
| [PRODUCTION_DEMO_EVIDENCE.md](PRODUCTION_DEMO_EVIDENCE.md) | Deployed walkthrough evidence, screenshots, and data-flow proof |
| [EVAL_PLAN.md](EVAL_PLAN.md) | Deterministic eval plan and fixture expectations |
| [MVP_AUTH_SCOPE.md](MVP_AUTH_SCOPE.md) | Local-demo auth scope and production-auth exclusions |
| [MVP_STATUS.md](MVP_STATUS.md) | Current build status and final-product roadmap |
| [OPENEMR_VERSION_PIN.md](OPENEMR_VERSION_PIN.md) | OpenEMR version and commit verified for planning |
| [eli5.md](eli5.md) | OpenEMR codebase orientation |

## Implementation Docs

Implementation-specific README files are intentionally short pointers back to the root README so setup and deployment instructions do not drift.

- [copilot/README.md](copilot/README.md) identifies the Co-Pilot service folders.
- [copilot/worker/README.md](copilot/worker/README.md) documents the worker placeholder.
- Existing upstream OpenEMR docs remain in their original directories.
