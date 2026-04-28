# MVP Auth Scope For Tonight

Tonight's MVP uses local demo auth, not production SMART/JWT validation.

## In Scope

- FastAPI local auth bypass identifies the user as `dev-doctor`.
- The API uses the local OpenEMR password grant only to obtain a development FHIR bearer token.
- Patient access is read-only.
- Enabled chart reads are limited to:
  - `Patient.read`
  - `Condition.read`
  - `Observation.read`
  - `Practitioner.read`
- All LLM/provider output remains mock/local. No PHI is sent to Anthropic or OpenRouter.
- Source links re-read OpenEMR FHIR records and remain scoped to the selected patient when OpenEMR requires patient-scoped lookup.

## Out Of Scope Tonight

- Production SMART authorization-code login.
- OpenEMR JWT signature/JWKS validation.
- Persisted user sessions.
- Multi-patient chat.
- Write actions back to OpenEMR.
- Treatment recommendations.

## Demo Framing

Describe auth as:

> Local demo auth with OpenEMR-backed FHIR reads. Production SMART/JWT validation is the next security milestone before any real PHI deployment.

This is intentionally conservative: it proves patient-scoped chart retrieval, citations, and verification without presenting the MVP as production-authenticated.
