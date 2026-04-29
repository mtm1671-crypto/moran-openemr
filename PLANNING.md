# AgentForge Planning Documents

The planning artifacts for the AgentForge Clinical Co-Pilot live at the repository root so reviewers can find them without digging through implementation folders.

## Core Planning Set

| Document | Purpose |
|---|---|
| [PRESEARCH.md](PRESEARCH.md) | Pre-code planning, constraints, and discovery notes |
| [AUDIT.md](AUDIT.md) | OpenEMR security, performance, architecture, data quality, and compliance audit |
| [USERS.md](USERS.md) | Target users, workflow, roles, use cases, and demo scenario |
| [USER.md](USER.md) | Compatibility pointer to `USERS.md` |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Co-Pilot architecture, OpenEMR placement, verification, and tradeoffs |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | Local and Railway deployment plan |
| [DEMO_PLAN.md](DEMO_PLAN.md) | 3-5 minute demo script and talk track |
| [EVAL_PLAN.md](EVAL_PLAN.md) | Deterministic eval plan and fixture expectations |
| [MVP_AUTH_SCOPE.md](MVP_AUTH_SCOPE.md) | Local-demo auth scope and production-auth exclusions |
| [MVP_STATUS.md](MVP_STATUS.md) | Current build status and final-product roadmap |
| [OPENEMR_VERSION_PIN.md](OPENEMR_VERSION_PIN.md) | OpenEMR version and commit verified for planning |
| [eli5.md](eli5.md) | OpenEMR codebase orientation |

## Implementation Docs

Implementation-specific Markdown stays near the code it describes, for example:

- [copilot/README.md](copilot/README.md) for local Co-Pilot API/web setup.
- [copilot/worker/README.md](copilot/worker/README.md) for the worker placeholder.
- Existing upstream OpenEMR docs remain in their original directories.
