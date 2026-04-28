# OpenEMR Version Pin

## Planning Pin

The current MVP planning and audit were performed against this local checkout:

```text
OpenEMR version: 8.1.1-dev
Git branch: master
Git commit: 0baebc4137eb1a5c1baa41240977c99736234ffe
Database version: 538
ACL version: 13
```

The version values come from `version.php`.

## Why This Matters

The Co-Pilot relies on OpenEMR behavior for:

- SMART/OAuth authentication.
- FHIR authorization scopes.
- Patient search.
- Observation/lab retrieval.
- Condition/problem retrieval.
- Medication and allergy retrieval.
- API response logging behavior.

If the OpenEMR commit or release changes, re-run the audit checks in `AUDIT.md` before trusting the same integration assumptions.

## Upgrade Checklist

For each OpenEMR upgrade:

1. Confirm FHIR metadata endpoint still responds.
2. Confirm SMART/OAuth client registration and token flow.
3. Confirm JWKS URL and token validation behavior.
4. Confirm patient search pagination.
5. Confirm active problem and medication status mapping.
6. Confirm recent lab date and abnormal flags.
7. Confirm API response logging is not storing full PHI response bodies.
8. Confirm source links still open the intended chart record or document.
