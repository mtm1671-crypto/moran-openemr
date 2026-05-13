# UX 100-Point Audit

Audit date: 2026-05-12

Target: deployed Week 3 adversarial operator UI at `https://adversarial-production.up.railway.app`

Source base:

- Nielsen Norman Group, `10 Usability Heuristics for User Interface Design`
- W3C WCAG 2.2 Quick Reference, especially focus visibility, keyboard access, status messages, labels, contrast, resize/reflow, and error identification
- Baymard Institute form, feedback, and layout UX guidance where applicable

Legend:

- `Pass`: checked and acceptable for this MVP.
- `Fixed`: failed or was weak during this audit and was corrected.
- `Risk`: not a blocker, but worth improving.
- `N/A`: not applicable to this app surface.

## Summary

| Status | Count |
|---|---:|
| Pass | 80 |
| Fixed | 5 |
| Risk | 10 |
| N/A | 5 |

Overall: the MVP UI passes the broad UX checklist after the fixes in this audit. Remaining risks are mostly final-product polish: cancellation, progress granularity, gentler error copy, deeper trend visualization, and in-app help.

## Checklist

| # | Common UX Pitfall | Status | Evidence / Note |
|---:|---|---|---|
| 1 | No clear page purpose on first load | Pass | H1 states the current risk recommendation; target context is visible. |
| 2 | System status hidden during long actions | Pass | Run buttons now expose loading state and a live status strip. |
| 3 | Feedback arrives too late after clicking | Pass | Loading state appears immediately on submit. |
| 4 | Duplicate submissions are easy | Pass | Campaign buttons disable while a suite is submitting. |
| 5 | User cannot tell which action is running | Pass | Clicked button label changes to the specific running suite. |
| 6 | Status updates are visual-only | Pass | `role="status"` and `aria-live="assertive"` are present. |
| 7 | Spinner has no explanatory text | Pass | Status copy explains that the suite is executing. |
| 8 | Completion destination is unclear | Pass | Copy says the newest run opens when the suite finishes. |
| 9 | Loading state depends only on color | Pass | Text, disabled state, pulse, and spinner all change. |
| 10 | Long task has no cancellation | Risk | No operator cancel control yet; acceptable for MVP but important for final. |
| 11 | Navigation lacks a home path | Pass | Brand lockup and `Risk overview` return to dashboard. |
| 12 | Run detail page has no exports | Pass | JSON and Markdown export links are visible. |
| 13 | Important IDs are not clickable | Fixed | Draft report IDs now link to source run evidence. |
| 14 | Users cannot filter large run tables | Pass | Latest runs table includes a filter input and visible count. |
| 15 | Filter has no label | Pass | Filter input has a visible label. |
| 16 | Navigation labels are vague | Pass | Labels use task language: Risk overview, JSON export, Markdown export. |
| 17 | Back path hidden on error page | Fixed | Missing run page now links back to Risk overview. |
| 18 | Unknown routes masquerade as successful pages | Fixed | Missing run details now return HTTP 404. |
| 19 | App has no stable URL for evidence | Pass | `/runs/{run_id}`, `.json`, and `.md` are stable. |
| 20 | Current page context is missing | Pass | Run detail page repeats run id and evidence-packet context. |
| 21 | Interface uses unexplained internal jargon | Risk | Terms like resilience and regression are domain-appropriate but could use compact help text. |
| 22 | Critical copy is buried below decoration | Pass | Recommendation, target, posture, and controls appear before tables. |
| 23 | Content is too sparse to explain state | Pass | Dashboard shows recommendation, coverage, cost, reports, runs, and exports. |
| 24 | Content is too dense for scanning | Risk | Dense cyber style is stronger now, but novice reviewers may need slower narration. |
| 25 | Text hierarchy is flat | Pass | Header, hero, panel headings, status badges, and tables have clear hierarchy. |
| 26 | Acronyms appear without context | Pass | Section codes are decorative; main headings carry meaning. |
| 27 | Empty states are missing | Pass | No-runs and no-reports states are explicit. |
| 28 | Risk status lacks reasons | Pass | Posture panel shows resilience, untested, inconclusive, cost, and findings. |
| 29 | Findings are presented as confirmed when draft | Pass | Finding table shows `draft` status. |
| 30 | Copy overclaims safety | Pass | Resilience text says directional signal, not guarantee. |
| 31 | Primary action is visually indistinct | Pass | Seed suite button uses primary styling. |
| 32 | Dangerous actions lack clear mode | Pass | UI states report-only default; runs do not modify target state. |
| 33 | Forms submit with no visible controls | Pass | Campaign forms use visible buttons. |
| 34 | Form controls have no accessible name | Pass | Buttons have text labels; filter has label. |
| 35 | Error messages expose only codes | Risk | Run-failed page includes exception type; useful for dev, harsher for reviewers. |
| 36 | Errors do not suggest recovery | Pass | Run-failed page provides a path back. |
| 37 | Users can accidentally run expensive suites repeatedly | Pass | Buttons disable during submission. |
| 38 | No confirmation for high-cost actions | Risk | Report-only suite is bounded, but final should show estimated cost before run. |
| 39 | Required input is unclear | N/A | Dashboard actions have no user-entered required fields. |
| 40 | Validation happens only after submission | N/A | No complex form validation in this UI. |
| 41 | Search/filter has no visible result count | Pass | Visible row count updates. |
| 42 | Search/filter is case-sensitive unexpectedly | Pass | Filter lowercases query and row text. |
| 43 | Buttons move layout when state changes | Pass | Button dimensions and flex layout keep state stable. |
| 44 | Loading message disappears from assistive tech | Pass | Status region is live and not focus-dependent. |
| 45 | Multi-step workflow lacks next step | Pass | After suite completes, user lands on newest run. |
| 46 | Keyboard focus is invisible | Pass | `:focus-visible` outline exists. |
| 47 | Focus can be obscured by sticky header | Pass | Header becomes static on mobile; outline offset is visible. |
| 48 | Interactive elements are too small | Pass | Buttons and inputs use 38-40px minimum heights. |
| 49 | Links rely only on color | Pass | Export links and run links also use borders/shape/weight. |
| 50 | Status relies only on color | Pass | Status badges include text. |
| 51 | Tables lack programmatic column scope | Fixed | Table headers now use `scope="col"`. |
| 52 | Tables lack accessible descriptions | Fixed | Tables now include screen-reader captions. |
| 53 | Visual-only decorative mark is announced | Pass | Brand sigil and pulses use `aria-hidden`. |
| 54 | Input lacks accessible label | Pass | Run filter label uses `for="run-filter"`. |
| 55 | Page title is generic | Pass | Title names the risk overview. |
| 56 | Missing document language | Pass | `html lang="en"` is present. |
| 57 | Viewport is not responsive | Pass | Viewport meta is present. |
| 58 | Mobile layout cannot reflow | Pass | Media query stacks major regions and makes tables scroll. |
| 59 | Horizontal overflow traps content | Pass | Tables scroll horizontally on narrow viewports. |
| 60 | Text cannot wrap in data cells | Pass | `overflow-wrap: anywhere` is used. |
| 61 | Animations ignore reduced-motion preference | Fixed | Added `prefers-reduced-motion: reduce`. |
| 62 | Color contrast is likely weak | Pass | Main text uses high-contrast light-on-dark; red accents are not sole carriers. |
| 63 | Small text dominates critical decisions | Pass | Recommendation is H1; posture metrics are large. |
| 64 | Screen-reader status changes require focus | Pass | Live region avoids focus stealing. |
| 65 | Hidden content is accidentally exposed | Pass | `[hidden]` is CSS-enforced. |
| 66 | Layout lacks responsive breakpoints | Pass | Mobile breakpoint at 900px. |
| 67 | Cards nested inside cards create clutter | Pass | Panels are sections; cards are simple repeated metrics. |
| 68 | Primary visual style clashes with domain | Pass | Red/black control-plane style fits adversarial security demo. |
| 69 | Palette is one-note without hierarchy | Pass | Red, green, amber, cyan, bone, and muted values separate states. |
| 70 | Decorative effects overpower content | Risk | Strong aesthetic; still readable, but demo should zoom browser if recording small. |
| 71 | Tables are visually indistinct | Pass | Headers, badges, borders, and hover states aid scanning. |
| 72 | Hover is required for understanding | Pass | Hover only enhances, not required. |
| 73 | Font choice hurts readability | Pass | Chakra Petch is legible at current sizes; mono font suits data. |
| 74 | Long IDs break layout | Pass | Data cells wrap anywhere. |
| 75 | Sticky elements consume too much mobile space | Pass | Header unsticks on mobile. |
| 76 | Buttons use inconsistent shapes | Pass | Buttons share consistent geometry. |
| 77 | Hit targets are too close | Pass | Controls have gaps and padding. |
| 78 | Page has no clear visual grouping | Pass | Sections use headings and panels. |
| 79 | UI shifts after filtering | Pass | Row visibility changes only table contents. |
| 80 | Visual focus order conflicts with reading order | Pass | DOM order follows dashboard flow. |
| 81 | Dashboard lacks executive summary | Pass | Recommendation and posture appear before detailed tables. |
| 82 | Coverage is not visible by category | Pass | Coverage table groups by risk family. |
| 83 | Findings are disconnected from evidence | Fixed | Report IDs link to source run detail. |
| 84 | Evidence mixes black-box and gray-box data | Pass | Run detail separates black-box evidence from gray-box metadata. |
| 85 | Export paths are hidden | Pass | JSON and Markdown links are visible per run. |
| 86 | Current reports include superseded failures | Pass | Current-report helper filters by latest failing verdict. |
| 87 | Resilience score overclaims precision | Pass | Copy labels it directional, not proof. |
| 88 | Costs are not shown | Pass | Cost card shows tokens, requests, latency, and provider cost. |
| 89 | Zero-cost estimate may be misread as free | Risk | Provider cost is `$0.0000` when target does not expose usage; add tooltip later. |
| 90 | Latest run is hard to find | Pass | Runs are ordered by latest first. |
| 91 | App logs or displays secrets | Pass | Synthetic principal label is shown, not credentials. |
| 92 | App permits unsafe arbitrary targets | Pass | Backend allowlist rejects non-allowlisted hosts. |
| 93 | Real PHI risk is unclear | Pass | Copy and docs state synthetic target/auth. |
| 94 | Failure state blocks recovery | Pass | Failed run page has dashboard return path. |
| 95 | Deployed health is not checkable | Pass | `/readyz` exists and returns SQLite readiness. |
| 96 | Performance feels unpredictable | Risk | Suite duration is bounded and now shown as loading, but no progress percentage. |
| 97 | Browser back breaks workflow | Pass | Server-rendered pages are stable URLs. |
| 98 | No help/documentation path | Risk | README has docs, but UI lacks an inline help/documentation link. |
| 99 | No auditability for important actions | Pass | Runs, traces, observations, reports, and exports persist in SQLite. |
| 100 | No way to verify evidence outside UI | Pass | JSON/Markdown exports provide reviewable artifacts. |

## Remaining UX Risks To Address Later

1. Add a cancel/stop action for a running suite.
2. Add progress granularity during suite execution, such as `case 4 of 13`.
3. Make run-failed copy friendlier for reviewers while keeping diagnostic detail available.
4. Add a small help/docs link for terms like resilience, regression, and report-only.
5. Explain `$0.0000` provider cost when the target does not expose billable usage.
