# Findings and disposition

Baseline: `f0b05dcf6a2a80e22193144891d23fee5865bdad`, audited October 23, 2026.
This matrix was recorded before production edits. Validation results are added as executed.

| ID / classification | Severity | Evidence and expected behavior | Disposition / residual risk |
| --- | --- | --- | --- |
| F01 Confirmed defect | P2 | `AuthFlowProvider` stores nextPath in memory; login routes to verify/setup without a next parameter; both reload restart links use plain `/login`. Refresh requires a fresh challenge but should preserve the validated record destination. | Focused regression first, then carry only the existing validated internal destination in the auth URL. Never persist challenge, credentials, codes or auth state. |
| F02 Test coverage gap | P2 | NOTIF-01 browser suite covers Appointment authentication only; no coordinated four-family Notification Center/read-failure/account-switch campaign. | Add synthetic browser journeys plus real backend API ownership tests. Intercepted UI fixtures do not prove a live backend/browser journey. |
| F03 Known architectural limitation | P3 | `notification-targets.ts` intentionally maps Inventory to `/portal/inventory/current`; historic reopened Inventory can differ from current year. | Document recipient-scoped destination. No Inventory lifecycle or new route in this slice. |
| F04 Institutional approval dependency | Gate | `email_disclosure.py` and NOTIF-03 central policy enable 15 events across four families. Code presence is not disclosure approval. | Complete-bundle GCO/UCN review required; no deployed configuration change. |
| F05 Environment-dependent/manual validation | Gate | Prior reports used locmem transport and local browser fixtures/previews. | SMTP acceptance, Gmail/Outlook, physical phones, screen readers and stakeholder UAT remain Not executed. |

No new queue, models, recipient expansion, email disclosures, Push enrichment or domain lifecycle is justified by this audit.

## F01 — resolved within the existing authentication architecture

Root cause: `AuthFlowProvider.nextPath` is intentionally memory-only. Login replaced
its URL with `/login/verify` or `/login/setup-authenticator`, so a document reload
lost the destination along with challenge state. Restart links then used `/login`
without the validated destination. This was a navigation defect, not an auth bypass.

Changed files: `fe/src/features/auth/login/login-screen.tsx`, the two login verify/
setup `page.tsx` files, `mfa-verification.tsx`, and `mandatory-totp-setup.tsx`.
Login carries only the validated internal next parameter; server pages revalidate
it with the existing helper, and restart links reuse `loginPathForPortal`. Normal
uninterrupted verification still uses the existing flow. A reload cannot recover
credentials, challenges, setup secrets or recovery codes. Fresh login is required.

Evidence: two pre-fix browser failures (`evidence/mfa-reload-before-fix.json`), then
21 distinct auth scenarios in each engine, including ordinary verification, setup,
reload, Back, expiry and malicious next. The expiry fixture was corrected to the
actual 400 `mfa_failed` API contract and rerun in both engines. New real backend
expiry cases assert no session and 401 record access for expired verification and
required setup. Results and iterations are in validation.

Residual risk: this preserves navigation, not a resumable authentication challenge.
Losing unsaved one-time setup/recovery-code display still requires the existing
secure restart/recovery process. No secret persistence or authentication rewrite.

## F02 — coverage added, with execution boundaries retained

New `be/tests/test_notification_cross_channel.py` has 49 cases: 30 event/policy joins,
nine actual Appointment actor policies, two Good Moral/Call Slip owner negatives,
three email-suppression/history cases, catalog/route checks, Group registration/
roster ownership and two real MFA-expiry cases. It imports established fixtures,
uses actual HTTP endpoints and locmem mail, and is registered in the existing CI
notification bundle. Frontend adds 22 Center journeys, expanded 21-case auth coverage,
22 shared route fixtures checked from both languages, and 100 email layout checks.
Existing realtime suite runs all 12 cases in each engine on CI's synthetic build.

These tests reduce the earlier cross-channel gap without replacing real UAT,
SMTP, physical devices or browser-to-live-backend proof. Broad hidden-button checks
are not treated as backend authorization evidence.

## F03/F04/F05 — accepted boundaries

F03 is the existing recipient-scoped Inventory current-year route. No protected
record access is granted, but a historic reopen may need a separately reviewed
historic route/lifecycle solution. F04 requires GCO/UCN approval of the exact complete
four-family bundle; no code or tests can grant it. F05 requires separately controlled
mail/client/accessibility/UAT execution. The UAT matrix keeps manual Not executed
states and the explicit Requires institutional approval gate.

## Validation environment finding — no production correction

The existing realtime browser suite assumes exact ready socket counts. Development
runs produced 9/12 Chromium and 11/12 WebKit despite passing many HTTP/polling cases.
The workflow's established dedicated synthetic production build passes 12/12 in
each engine. Earlier concurrent dev/build runs also timed out. These are recorded
execution failures, not waived passes or grounds for changing production socket,
privacy or authentication behavior. No timeout was raised and no workflow filter
was changed. No further development-mode root cause is claimed by this audit.
