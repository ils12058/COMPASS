# Preflight, contract and interaction decisions

## Integration preflight

Fetched origin and verified integration `1a8f9aa3` contains FAC-1 `1778359f` and
FAC-2 PR #349. Read FAC-1 documentation, FAC-2's README/handoff/privacy/architecture,
the published 2026-10-21 proposal booklet Chapter 10/Proposal #7, ADR-113's current
form mapping retained by FAC-2, `fe/AGENTS.md`, UX15/SIMPLIFY composition rules and
current Shell/Home/navigation, transport/CSRF, session/cache ownership, forms,
unsaved-navigation, Notifications and Profile implementations. Inspected generated
Referrals operations before implementing routes; Next's installed page convention
documentation confirms asynchronous route params.

The existing four Faculty APIs supply confirmation, submit, own list and detail.
They do not provide a combined permission to start a new form. Own-list success
cannot establish lookup approval, and a speculative confirmation would require a
Student identifier before the Home could know whether submission is available.

## Minimal domain availability addition

The necessary additive contract is `referralsFacultyAvailability`:
`GET /api/v1/faculty/referrals/availability`, authenticated with the existing session.
It returns only `can_confirm_student`, `can_submit_referral`,
`can_view_submissions`, and `valid_until` (nullable). It discloses no Student,
directory, policy reference, eligible-ID list or approval metadata.

The Referrals domain reloads/locks the Faculty account, actual session and managed
home under the existing catalog gate. It independently evaluates the current
lookup and submission/own-projection providers, scopes, capabilities, exact active
form, and the matching policy digest. Unusable home or absent approval yields false
availability; a non-Faculty/inactive actor or unavailable session is denied.
The deadline conservatively bounds positive facts by policy and session expiry.

This response is advisory, never an authorization token. Actual confirmation,
submission and reads keep all FAC-2 current-state checks. Both real providers are
unchanged and return `None`; the default projection is all false. No new model,
schema migration, activation endpoint, setting or environment flag is introduced.
The explicit FAC-3 request permits a genuinely necessary minimal domain projection;
this is the bounded backend-contract exception to frontend-only scope in AGENTS §59.

OpenAPI is regenerated at `contracts/openapi.json`; Orval generates all frontend
types, requests and query keys. Generated output remains ignored and unedited.

## Confidential form ownership and recovery

The form controller owns the exact ID, confirmation, declared course and reason in
component memory. They never enter URLs, persistent storage, query keys, logs or
analytics. Mutations call generated functions through TanStack Query with no
variables and no returned sensitive payload; confirmation never enters the shared
MutationCache. The existing transport owns session cookies and CSRF. No separate
client, sign-in token, signature, attestation, urgency field or academic verification
is added.

Review shows only the current form's Student display name, Course/Year/Block and
reason. Server expiry is scheduled through the existing deadline utility, bounded
by its Date header. Changed ID clears the confirmation; expiry requires a deliberate
new confirmation before a new submission. Referral information survives ordinary
confirmation/validation errors. Throttling honors Retry-After without guessing a
production limit or retrying automatically.

One intended submission owns an immutable request body plus a random idempotency
key. Pending UI and a synchronous guard prevent duplicate dispatch. Network/5xx
uncertainty locks editing and preserves that exact intent for **Retry same
submission**, including when the confirmation has since expired. The backend may
replay an existing committed result but cannot create a new record from an expired
confirmation. Editing a definitely refused submission drops the old intent and
requires another review/new key. A 409 never becomes assumed success. Discard is
explicit and warns about unresolved outcomes.

Only canonical 201/200 Submitted responses clear the draft and show success. The
result retains only the safe DTO. The existing unsaved-navigation guard covers
dirty internal navigation, Back and unload. Ordinary recoverable errors preserve
input; confirmed sign-out, account/role access loss or deliberately leaving/reloading
the page unmounts confidential state. There is no durable recovery across reload or
reauthentication and no automatic unsafe replay after either.

## Records, freshness and presentation

Home requests at most three actual own records only when own-read is available.
My Referrals uses the canonical items/page/page_size/has_next contract; it has no
invented totals, search or status filters. The pager stays on an empty later page.
Detail and list share allowlisted projections, never GCO DTOs or reason readback.
Unknown, foreign, GCO-only and omitted/voided records keep safe 404 handling without
alternative endpoint probing.

Query errors distinguish initial failure, policy denial and transient refresh with
last-confirmed data. Authorization errors conceal protected data. Availability
rechecks on focus, reconnect and its server deadline; failures cannot authorize
new work. Successful submission invalidates only the own-list query family. Existing
session revalidation and account-owned cache cancellation/removal remain in control.

The interface uses existing Panel/PageHeader/PageAction/Input/Textarea/Notice and
canonical paging/navigation primitives. Forms and records have no artwork, fake
counts, receipt/closure stages or clinical indicators. Outfit remains the functional
heading font and Plus Jakarta Sans the UI font. The product retains its intentional
light palette; OS light/dark preferences are tested without introducing a theme
switch or unrelated global restyling.
