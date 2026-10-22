# Findings and Disposition

## Finding register

| ID | Severity/status | Area | Reproduction and root cause | Disposition, evidence, and residual risk |
| --- | --- | --- | --- | --- |
| UX15-FINAL-01 | **No blocker / no confirmed production defect** | Integrated role Homes, forms, shell, access and submission recovery | Reviewed the fetched integration tree and ran the full frontend Node inventory plus 13 browser suites in both engines. | No production correction was warranted. Automated results pass; they do not replace backend runtime, screen-reader, browser-zoom, device, or institutional UAT. |
| UX15-FINAL-02 | **Low / fixed** | GSS account-switch browser regression | WebKit reported canceled Next route-prefetch fetches as page errors when the test reloaded immediately after receiving the initial Home. The assertion was checking test timing, not a leaked GSS projection. | Added the existing harness `settleFetches()` wait before the synthetic reload in `fe/tests/ux15-gss-home.browser.mjs`. The focused case passed in Chromium/WebKit; the full GSS suite passed 16/16 in both engines. No production source changed. |
| UX15-FINAL-03 | **Deferred / process limitation** | Hosted CI on integration-targeted PRs | `.github/workflows/frontend-targeted.yml` and backend filters target `staging` and `canon/compass-clean-baseline`; the UX15 integration branch is excluded. GitHub returned “Branch not protected” for the integration branch on 2026-10-22. | No filters or protection rules were modified. Local validation is comprehensive but is not hosted CI. If hosted checks are required before promotion, use a separately approved validation route. |
| UX15-FINAL-04 | **Manual / not run** | Assistive technology, actual browser zoom, and physical devices | The available browser suite models root-text enlargement and keyboard/focus behavior but does not exercise actual browser zoom, spoken screen-reader output, or physical devices. | Leave open for approved institutional UAT. Use the specific cases in [UAT matrix](uat-matrix.md); no conformance or acceptance claim is made. |
| UX15-FINAL-05 | **Manual / not run** | Deployed backend scope, live idempotency, and staging behavior | Browser APIs were synthetic. Backend source and existing backend negative tests were inspected, but no live staging or production service and no local PostgreSQL/Redis backend suite were exercised. | Require the normal backend checks and approved non-production account/scope UAT after a separately authorized staging deployment. No backend change was needed for this frontend-only baseline. |

## Severity summary

- **Blocker:** none demonstrated.
- **High:** none demonstrated.
- **Medium:** none demonstrated.
- **Low:** one browser-test timing correction, fixed in this consolidation PR.
- **Deferred/manual:** hosted CI trigger coverage, actual assistive-technology/device/zoom work, and
  live staging backend/UAT evidence.

## Decision

No confirmed product correctness, confidentiality, authorization, API compatibility, or critical
accessibility blocker remains in the inspected UX15 frontend baseline. The only source change in
this consolidation is a deterministic wait in a synthetic browser test. Remaining manual items are
release gates for later milestones, not stakeholder acceptance and not a basis to claim production
readiness. See [readiness assessment](readiness-assessment.md).
