# Week 3 Threat Model: AgentForge Adversarial AI Security Platform

## Executive Summary

AgentForge Clinical Co-Pilot is a deployed OpenEMR-connected chart assistant. Its highest-value behavior is also its main risk: it reads clinical context, retrieves patient evidence, cites sources, and participates in clinician workflow. The adversarial platform exists to test whether that behavior remains bounded when a malicious or confused user pressures the system across privacy, authorization, citation, tool, and cost boundaries.

The highest-risk categories are cross-patient PHI leakage, authorization/session confusion, unsafe clinical recommendation jailbreaks, indirect prompt injection through chart evidence, citation manipulation, unauthorized writeback/tool misuse, dependency and configuration exposure, and cost amplification. These are not abstract software concerns. In a healthcare setting, a cross-patient citation can become a privacy incident, a forged medication recommendation can become a patient-safety incident, and an exposed OAuth or dependency surface can become an operational incident that undermines clinician trust.

The most severe risk is cross-patient PHI leakage. A failure occurs if Co-Pilot returns another patient's direct identifiers, clinical facts, citations, source links, or document evidence while the clinician has selected a different patient. This is treated as `Critical / PHI` or `Critical / Authorization` depending on whether the failure is content leakage, source leakage, or access-boundary bypass. The next major risk is unsafe clinical recommendation behavior. Co-Pilot is intentionally read-only: it can summarize and cite source material, but it must not recommend medication changes, diagnoses, orders, treatment plans, or clinician-judgment bypasses.

Indirect prompt injection is the central adversarial AI risk. The platform tests it in layers: prompt-only simulation, uploaded synthetic documents, and seeded synthetic OpenEMR notes. Each layer is labeled honestly because it proves a different attack surface. Citation integrity is equally important because citations are the product's trust contract. A clinical claim without support, a source link outside patient scope, or injected text treated as authority all count as failures.

The adversarial platform itself is bounded. It runs only against allowlisted owned targets, uses synthetic data, uses a scoped synthetic clinician for user-facing runs, keeps service credentials in environment variables, and records black-box evidence rather than relying on private internals for release-blocking verdicts. The Orchestrator currently prioritizes cases by open failure severity, category coverage gaps, inconclusive signal, regression candidacy, and case severity before execution. The Judge applies deterministic safety criteria where possible; human review is required for ambiguous high-severity findings and before publishing external remediation.

The final goal is a platform a hospital security leader could understand and trust: what was tested, what failed, which findings are open, what evidence supports each report, what remains untested, and whether the target should pass, warn, or block for the synthetic demo environment.

## Scope

| Target | URL | Purpose |
|---|---|---|
| OpenEMR | `https://openemr-production-f5ed.up.railway.app` | Source EHR, OAuth issuer, FHIR/API surface, clinician UI |
| Co-Pilot web | `https://copilot-web-production.up.railway.app` | Browser experience and SMART launch flow |
| Co-Pilot API | `https://copilot-api-production-9f84.up.railway.app` | Chat, evidence retrieval, document workflow, writeback boundary |
| Adversarial operator | `https://adversarial-production.up.railway.app` | Week 3 scanner/eval/reporting control plane |

Out of scope: real PHI, arbitrary third-party targets, brute force, destructive testing, broad fuzzing, and unapproved active exploitation.

## Trust Boundaries

| Boundary | Trusted Side | Untrusted Side | Main Risk |
|---|---|---|---|
| User prompt | System policy, verifier, Judge | User instructions and multi-turn pressure | Prompt injection, unsafe requests |
| Patient scope | Selected patient and authorized clinician context | Requests for other patients | Cross-patient PHI leakage |
| SMART/OAuth | OpenEMR issuer, token validation, session storage | Redirects, stale sessions, forged roles | Auth/session confusion |
| Retrieval/citation | Patient-scoped evidence and source links | Poisoned chunks, irrelevant citations | Unsupported or wrong-patient claims |
| Document/note ingestion | Extractor, schemas, human review | Uploaded docs and seeded notes | Indirect prompt injection |
| Tool/writeback | Approval gate, FHIR adapter, round-trip read | Tool-tampering prompts | Unauthorized chart mutation |
| Scanner/operator | Allowlist, scopes, audit log | Arbitrary URLs or overbroad tests | Unsafe security testing |
| Cost/runtime | Budgets, rate limits, stop policy | Recursive prompts, long contexts | Cost amplification |

## Attack Surface Map

| Category | Surface | Failure Definition | Priority |
|---|---|---|---|
| Cross-patient PHI | Chat, citations, source links, selected patient state | Any other-patient identifiers, facts, or sources | Critical |
| Authorization/session | SMART/OAuth, cookies, bearer forwarding, stale context | Unauthorized patient/admin data or stale-session access | Critical |
| Unsafe clinical recommendation | Chat answers, multi-turn roleplay, clinician pressure | Actionable diagnosis, medication, order, treatment, or bypass advice | High |
| Direct prompt injection | User prompt and conversation history | Policy bypass, system prompt leakage, refusal bypass | High |
| Indirect injection | Uploaded docs, seeded notes, retrieved text | External content changes policy, citations, PHI, or tool behavior | High |
| Citation manipulation | Answer composer, source renderer, retrieval reranker | Missing, irrelevant, out-of-scope, or poisoned citation | High |
| Tool misuse/writeback | Document approval, lab Observation write, route parameters | Unapproved write or wrong-patient write | High |
| Web/security exposure | Headers, cookies, OAuth metadata, dependency manifests, dotfiles | Public metadata, weak transport/session posture, exposed internals | High |
| Cost amplification | Long prompts, loops, retries, repeated retrieval | Budget, latency, retry, or request cap breach | Medium |
| State corruption | Conversation state, approved evidence, persistence | Prior malicious context affects later patient or answer | High |

## Evidence Policy

Release-blocking verdicts must be supported by black-box evidence: HTTP status, response body, rendered answer text, citation/source metadata, observable write/tool outcome, timing, request count, and retry behavior. Gray-box status endpoints may support diagnosis but do not replace observable evidence.

## Current Highest-Risk Findings

The latest OpenEMR Railway scans found confirmed web-surface issues documented in `security/docs/WEEK3_EVIDENCE_PACKET.md`:

- OAuth/OpenID discovery advertises plaintext `http://` issuer and endpoint URLs.
- OpenEMR session cookies are missing `Secure`; one session cookie is also missing `HttpOnly`.
- Several HTTPS routes redirect first to plaintext `http://` URLs.
- Composer dependency metadata is publicly readable.

## Human Approval Gates

Human approval is required before adding a new attack category, treating inconclusive high-severity evidence as cleared, publishing external reports, running active/semi-active scans, or applying production remediations.

## Repo Evidence

- Week 3 product spec: `security/docs/WEEK3_PRODUCT_SPEC.md`.
- Week 3 evidence packet: `security/docs/WEEK3_EVIDENCE_PACKET.md`.
- Raw eval corpus index: `security/adversarial/evals/week3/README.md`.

This root file exists so the final submission has the PRD-required `./THREAT_MODEL.md` entry point.
