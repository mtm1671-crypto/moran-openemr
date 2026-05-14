# Week 3 Adversarial Platform — Full-Spectrum Audit Design

**Date:** 2026-05-13
**Author:** Claude (Opus 4.7), brainstormed with project owner
**Status:** Approved — execution starting

## Goal

Produce the most thorough, evidence-backed audit of the Week 3 Adversarial AI Security Platform possible in the time available, covering three lenses simultaneously:

1. **Rubric / PRD compliance** — does the work hit every hard gate and scoring criterion in `Week 3 - AgentForge - Adversarial AI Security Platform PRD.pdf`?
2. **CISO defensibility** — would a hospital CISO trust this platform with continuous security testing of clinical AI? (The PRD's stated final-note standard.)
3. **Engineering quality** — is the code maintainable, the tests meaningful, the docs honest about what the code does?

Audit-only. No code is changed in this phase. The output is a prioritized backlog the owner can execute against before the Friday-noon deadline.

## Non-Goals

- Auditing the target system (`copilot/`) beyond *how* it is tested.
- Auditing OpenEMR PHP core or any Week 1/2 territory.
- Producing the fixes themselves. That is a separate phase.

## Methodology — Parallel Specialists + Adversarial Review

Five subagents. Four run in parallel; the fifth (skeptic) runs sequentially after, with access to the first four's outputs.

| # | Agent | Inputs | Output file |
|---|---|---|---|
| 1 | Rubric compliance | Week 3 PRD requirements + every claimed deliverable | `audit-raw/rubric.md` |
| 2 | CISO defensibility | All agent code + threat model + audit-trail code + approval gates | `audit-raw/ciso.md` |
| 3 | Code quality | All Python under `security/adversarial/{app,tests}` | `audit-raw/quality.md` |
| 4 | Doc/code drift | All Week 3 markdown vs the code it describes | `audit-raw/drift.md` |
| 5 | Skeptic (red-team the audit) | Outputs of 1–4 + spot-checks of cited files | `audit-skeptic-review.md` |

Synthesis is done by the main thread into the final report.

### Why this topology

- **Separation prevents conflict of interest.** The same lens that scores the rubric will rationalise weak code as "good enough for the rubric." Splitting forces explicit defenses.
- **Parallelism cuts wall-clock without losing depth.** Each specialist has its own context window.
- **Skeptic stops false positives from reaching the final report.** Most audits skip this. It is the single highest-value piece of the design.

### What was considered and rejected

- **Single deep sequential pass** by the main thread — coherent, but one context window for a 30-file Python platform plus 20+ docs is brittle.
- **Layered by architectural slice** (agents / harness / observability / docs, each scored on all three lenses) — clean structure but fragments cross-cutting concerns like judge independence.
- **Adding a performance/cost auditor** — cost analysis is already a PRD deliverable, so it is folded into rubric compliance instead of getting its own agent.

## Output Format

Single unified report at `docs/plans/2026-05-13-week3-audit-report.md`:

1. **Executive summary** — top 5 findings, rubric-points-at-risk, CISO go/no-go, total fix hours.
2. **Scored rubric** — every PRD line item: Pass / Partial / Fail / N/A with evidence and a one-line "why."
3. **CISO defensibility scorecard** — 6–8 trust dimensions each with status + evidence.
4. **Prioritized backlog** — each finding: severity, category, estimated hours, rubric-points-per-hour.
5. **Evidence appendix** — raw quotes for each finding so a reader does not have to trust the auditor.
6. **Skeptic review notes** — what the skeptic challenged and how it was resolved.

## Scope

**In:**
- `security/adversarial/**` — entire adversarial platform.
- All Week 3 docs: root `THREAT_MODEL.md`, `ARCHITECTURE.md`, `USERS.md`, `AI_COST_ANALYSIS.md`, `EVAL_DATASET.md`, `SUBMISSION.md`, `EARLY_SUBMISSION_CHECKLIST.md`, plus all of `security/docs/**`.
- Cross-checks against the Week 3 PRD.

**Out:**
- `copilot/` (target — audited only for how it is tested, not its own quality).
- OpenEMR PHP core, `interface/`, `library/`, Week 1/2 territory.

## Severity Levels

| Severity | Meaning |
|---|---|
| **P0 — Blocker** | Misses a PRD hard gate (deployed URL; multi-agent architecture; `THREAT_MODEL.md`; `ARCHITECTURE.md`; ≥3 attack categories with results; ≥3 vuln reports; AI cost analysis) OR a CISO-defensibility violation that breaks the platform's core premise (e.g., judge sharing context with red-team). |
| **P1 — Major** | Lowers rubric score significantly, OR an engineering defect that will visibly fail in the demo, OR a doc claim the code clearly contradicts. |
| **P2 — Polish** | Code smell, slop, minor doc drift, redundant abstraction, weak test. Won't move the rubric but degrades the "defensible to a CISO" quality bar. |

Backlog priority formula: `(rubric points recovered) / (estimated hours)`, descending. P0s come first regardless. The skeptic has veto power on any "high rubric points" claim that is not backed by evidence.

## Evidence Discipline

Every finding must include:
- A file path + line number (or doc heading).
- A direct quote of 15 words or fewer (longer quotes go in the evidence appendix).
- A mapped requirement: a specific PRD/rubric line for rubric findings, a CISO trust dimension for defensibility findings, or a code-smell category for quality findings.

No finding without evidence. No "feels wrong" findings. The skeptic agent enforces this.

## Deliverables

- `docs/plans/2026-05-13-week3-audit-design.md` — this doc.
- `docs/plans/2026-05-13-week3-audit-report.md` — final unified report.
- `docs/plans/2026-05-13-week3-audit-skeptic-review.md` — skeptic notes.
- `docs/plans/2026-05-13-week3-audit-raw/{rubric,ciso,quality,drift}.md` — raw per-specialist outputs.

Estimated wall-clock: 2–3 hours.
