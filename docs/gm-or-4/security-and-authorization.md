# Security and authorization

The operational API checks active persisted session, CSRF for unsafe requests, base role and dependency-coherent capabilities. Domain services repeat authority checks after acquiring request/account fences. Supported account administration shares the User row lock. Student receipt mutation and preparation are forbidden; final issue requires COUNSELOR plus `good_moral.issue`. GSS may record/prepare and may inspect only with an explicit eligible grant. Head Guidance designation and IT access administration do not imply inspection/issuance authority.

## Newly executed real session matrix

`test_real_session_denials_leave_all_receipt_and_outcome_facts_unchanged` sends actual requests to Django with persisted opaque sessions and CSRF enforcement. It compares full request, identity, assignment, operation, verification and Audit rows, and notification/feedback counts before/after each refusal. Valid issuance payloads reach the role fence, rather than counting a schema error as proof of permission denial.

| Cases | Required outcome |
| --- | --- |
| Student correction / inspection / preparation / issuance | 403, no fact changes |
| Ungranted GSS; ungranted Counselor; Head Guidance without grant | 403 |
| Authorized GSS final issue | 403 |
| IT inspection/issue even with unusual overrides | 403 |
| Revoked, expired, missing dependent prepare capability | 403 |
| Inactive account / missing session | 401 |
| Forged verifier/time/fee-policy fields | 422 strict payload refusal |
| Other request's assignment UUID | 409; no reassignment |
| Missing/invalid CSRF | 403 |

The positive API F4/F6 tests also deny another Student's detail/PDF (404), assert Student-safe response omissions, and verify server-created actor/time and exact issuance references. These are authenticated API/PostgreSQL checks. Separate actual Chromium tests traverse Next→Django; no API response is fulfilled by the browser harness.

## Evidence and trust boundaries

Original verifier/time, method, exact claim and fee snapshot remain immutable; correction/cancellation invalidate eligibility, not historical attribution. One eligible inspection per assignment is enforced by database uniqueness/guards. A committed replay returns its original operation evidence; it cannot revive invalidated evidence. Issued retry returns committed issuance without duplicating Audit, notifications or feedback.

General Audit stores references and controlled classifications, not raw receipt facts or arbitrary payment narrative. Staff history is own-request bounded metadata, not a global receipt search. Student responses omit inspection/ledger/mutation/grant/policy internals while retaining the preexisting own certificate facts. UI source keeps protected state in memory under account/session/authority ownership; mocked browser tests exercise late responses and failed refresh.

Database guards protect ordinary application/SQL writers. Database owners/infrastructure administrators can drop tables, disable guards or restore incomplete snapshots; this is outside that guarantee. SQL snapshot shape is not independent proof of actor authority or institutional fee approval. Supported account-service locks do not cover arbitrary privileged override writes or uncontrolled mixed-policy deployments.

No complete password/MFA login, real account provisioning, external Cashier authentication or actual physical inspection is claimed: synthetic sessions are provisioned through the real session service. No real inspector matrix has been approved. Security assurance is PARTIAL across the full human/operational envelope; tested role/session boundaries pass.
