# Patient Dashboard Migration Defense

## Summary

The surprise challenge asks for a modern-framework reimplementation of the OpenEMR patient dashboard without redesigning the clinical experience or changing OpenEMR's backend. This repository implements that as a new Next.js route at `/dashboard` inside the existing Co-Pilot web service. The dashboard uses the same SMART/OAuth session as Co-Pilot, calls OpenEMR's FHIR API as the data layer, and renders a deterministic patient summary view: patient header, allergies, problem list, medications, prescriptions, care team, and recent labs.

The framework choice is **Next.js + React + TypeScript**. We chose it because the existing Co-Pilot web app already runs on Next.js, already has SMART/OAuth login, already stores the OpenEMR bearer token in an encrypted HttpOnly cookie, and already deploys on Railway. Reusing that foundation lets the dashboard modernization stay focused on the presentation layer. React's component model maps naturally to patient dashboard cards, TypeScript gives safer parsing of loosely shaped FHIR JSON than ad hoc template code, and Playwright can test the full browser flow.

OpenEMR remains the clinical system of record. The dashboard does not write to the chart and does not introduce a new clinical backend. It reads FHIR resources through a narrowly scoped same-origin route handler that only allows the dashboard resources required for the challenge: `Patient`, `AllergyIntolerance`, `Condition`, `MedicationRequest`, `CareTeam`, `Observation`, and `Practitioner`. The route handler gets the access token from the encrypted SMART session cookie, forwards the request to OpenEMR FHIR, strips hop-by-hop headers, and rejects cross-site browser requests. This keeps the browser from owning the bearer token directly while still using OpenEMR's existing REST/FHIR APIs as the data layer.

## Feature Mapping

| Requirement | Implementation |
|---|---|
| OAuth2/OpenID Connect login | Existing SMART/OAuth start/callback routes in `copilot/web/app/api/auth/*`. |
| Patient header | `/dashboard` fetches `Patient/{id}` and renders name, DOB, sex, MRN, and active status. |
| Allergies | `AllergyIntolerance?patient={id}` card. |
| Problem List | `Condition?patient={id}` card. |
| Medications | `MedicationRequest?patient={id}` medication card. |
| Prescriptions | Same `MedicationRequest` bundle rendered through prescription/status/intent fields. |
| Care Team | `CareTeam?patient={id}` card, with empty state if OpenEMR exposes no rows. |
| Additional section | `Observation?patient={id}` recent labs card. |
| Existing API data layer | All dashboard clinical cards read through OpenEMR FHIR. |

## Why Next.js

Next.js gives us a modern presentation layer while preserving the OpenEMR backend boundary.

- **Component architecture.** Patient header and clinical cards are clean reusable React components.
- **TypeScript.** FHIR responses are flexible JSON; TypeScript forces explicit parsing and default states.
- **Secure session handling.** Next.js route handlers can read encrypted HttpOnly cookies server-side, so browser JavaScript never receives the OpenEMR bearer token.
- **Incremental migration.** The dashboard can live beside existing OpenEMR PHP screens while clinics keep using the rest of OpenEMR unchanged.
- **Testing.** Playwright can validate the browser dashboard, mocked FHIR data, and navigation from Co-Pilot.
- **Deployment fit.** The repo already deploys the Next.js web app on Railway, so this does not add a new service.

## What We Gained Moving Away From PHP Templates

- Faster UI iteration with small, typed components instead of server-rendered page fragments.
- Cleaner loading, empty, stale, and degraded states.
- A safer auth boundary where FHIR calls are same-origin and token handling stays server-side.
- Browser-level regression tests for the real user experience.
- A clear path to reusable cards across dashboard and Co-Pilot.
- Better separation between authoritative OpenEMR data and derived/read-only presentation state.

## Tradeoffs

- The dashboard adds a separate frontend runtime beside OpenEMR's PHP UI.
- FHIR coverage may be uneven. Some OpenEMR installs may expose sparse `CareTeam` or prescription detail, so the UI must show honest empty states.
- The React dashboard must track OpenEMR auth/session behavior carefully.
- Full feature parity with every historical dashboard widget would require additional resource mapping beyond the challenge's required cards.
- The route handler is presentation-layer infrastructure, but it is still another operational surface to secure, test, and monitor.

## Caching And Freshness

The dashboard is designed to display current FHIR-backed data first. It also keeps the last successfully loaded dashboard state in memory while refreshing. If an OpenEMR refresh fails, the page can keep the previous session data visible with a stale/cached badge and an explicit warning. This is intentionally not a durable clinical cache and not a final-answer cache. Production-grade caching should use the Co-Pilot evidence/read-model layer with freshness metadata such as source timestamp, index timestamp, source hash, and verification state.

The rule is: cached dashboard data may improve perceived latency, but OpenEMR remains the source of truth.

## Files Added Or Changed

| File | Purpose |
|---|---|
| `copilot/web/app/dashboard/page.tsx` | Modern patient dashboard route and FHIR parsing/rendering. |
| `copilot/web/app/api/dashboard/fhir/[...resource]/route.ts` | Read-only same-origin FHIR proxy using the encrypted SMART session. |
| `copilot/web/app/globals.css` | Dashboard layout, patient header, cards, status badges, responsive behavior. |
| `copilot/web/app/page.tsx` | Adds a link from Co-Pilot chat to the selected patient's dashboard. |
| `copilot/web/tests/clinical-copilot.spec.ts` | Adds dashboard smoke coverage. |
| `PATIENT_DASHBOARD_MIGRATION.md` | This defense document required by the challenge. |

## Demo Path

1. Open the deployed Co-Pilot web app or launch from OpenEMR.
2. Complete SMART/OAuth authorization.
3. Open `/dashboard`.
4. Select an authorized patient from the patient dropdown.
5. Show the persistent patient header.
6. Show the clinical cards loading from FHIR.
7. Refresh the dashboard.
8. Click "Ask Co-Pilot" to move from deterministic dashboard view to the AI assistant for the same selected patient.
