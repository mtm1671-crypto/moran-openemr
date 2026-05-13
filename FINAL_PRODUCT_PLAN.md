# Final Product Plan

This plan extends the Week 3 MVP into a final product path. Each step keeps the same goal, way, and verification style used in the build goals.

## Step 1: Lock The Deployed Baseline

Goal:
Keep the deployed Week 3 operator as a trustworthy source of evidence.

Way:
Maintain the separate Railway `adversarial` service, persistent `/data` SQLite volume, synthetic clinician OAuth settings, and per-run JSON/Markdown exports.

Verification:
`https://adversarial-production.up.railway.app/readyz` returns `200`, the dashboard shows latest verdicts by case, and a deployed seed run exports matching JSON and Markdown.

## Step 2: Expand The Attack Corpus

Goal:
Move beyond one seed per risk family.

Way:
Add 3 to 5 variants for cross-patient PHI, authorization/session confusion, unsafe clinical advice, indirect injection, tool misuse, cost amplification, and citation manipulation.

Verification:
The dashboard shows multiple cases per risk family and every case links to a threat-model category.

## Step 3: Strengthen Red Team Mutation

Goal:
Generate useful variants without turning the test suite into noise.

Way:
Let Red Team mutate seed prompts within fixed safety bounds: synthetic patients only, allowlisted target routes, bounded budgets, and explicit injection-layer labels.

Verification:
Generated variants validate against `AttackCase`, run in `report-only`, and can be promoted into committed regression cases.

## Step 4: Harden Judge Decisions

Goal:
Keep release-blocking verdicts defensible.

Way:
Use deterministic checks for patient scope, citation trust, unsafe clinical recommendations, tool outcomes, and budget breaches. Treat safe no-evidence answers as passes, not missing-citation failures.

Verification:
Unit tests cover positive, negative, and false-positive paths; `enforce` exits nonzero only for confirmed critical/high failures.

## Step 5: Build Regression Gates

Goal:
Turn confirmed failures into permanent release checks.

Way:
Promote reproducible failures into `regression` cases and run them with `--enforce` before release.

Verification:
`python -m app.run_week3_eval --target deployed --suite regression --enforce` exits nonzero for critical/high regressions and exits zero for a clean replay.

## Step 6: Deepen Indirect Injection Coverage

Goal:
Test prompt, document, and retrieval injection layers separately.

Way:
Keep prompt-simulated cases for Judge validation, then add uploaded synthetic document cases and seeded OpenEMR-note cases.

Verification:
Dashboard coverage distinguishes `prompt_simulation`, `uploaded_document`, and `seeded_note` so the demo does not overclaim coverage.

## Step 7: Validate Tool And Write Boundaries

Goal:
Prove Co-Pilot cannot perform unsafe writes or cross-patient tool actions.

Way:
Add cases for unapproved `Observation.create`, wrong-patient write attempts, missing SMART write scope, and retry/reauthorization behavior.

Verification:
Black-box evidence shows refused, not-invoked, or reauthorization-required outcomes; unsafe tool execution creates a high-severity report.

## Step 8: Improve Director-Level Reporting

Goal:
Make risk understandable without reading raw JSON.

Way:
Show latest verdicts by risk family, current reports, run exports, stop reasons, and pass/warn/block recommendations in the operator UI.

Verification:
A reviewer can open the deployed dashboard and understand the current risk posture in under one minute.

## Step 9: Add Cost And Runaway Controls

Goal:
Test adversarial cost behavior safely.

Way:
Track request count, latency, retry count, loop depth, token estimate, and provider cost per case.

Verification:
Cost-amplification cases fail deterministically when configured budgets are exceeded.

## Step 10: Produce Evidence-Backed Reports

Goal:
Create final security reports only from real evidence.

Way:
Use `VULNERABILITY_REPORTS.md` or `adversarial/evals/week3/vulnerability_reports/` for confirmed findings, false positives, and safe-behavior evidence.

Verification:
Every report references a deployed run id, observed response, expected behavior, Judge reason code, and remediation or closure status.

## Step 11: Wire CI And Release Checks

Goal:
Make adversarial testing part of release discipline.

Way:
Run tests, lint, typecheck, seed evals, and regression evals in a documented release gate.

Verification:
The release checklist includes local checks plus deployed `report-only` evidence and `enforce` regression status.

## Step 12: Package The Final Submission

Goal:
Give reviewers a complete, reproducible product story.

Way:
Update README, submission notes, architecture docs, threat model, cost analysis, screenshots, video walkthrough, deployed URLs, and final evidence exports.

Verification:
A reviewer can open the repo, deployed apps, evidence exports, and final docs without private context or manual reconstruction.
