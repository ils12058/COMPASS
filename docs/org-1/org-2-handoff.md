# ORG-2 — Backend catalog CRUD handoff

ORG-1 supplies persisted Program policy, validation, active-chain helpers, a frozen additive backfill
and controlled initialization/adoption. Existing reads retain their wire shape. There is no Catalog
mutation API, editor, new capability or grant. Institution editing must remain unavailable until
ORG-2 safeguards and separate institutional authority decisions are complete.

Use [Program/receipt models](../../be/compass/organization/models.py),
[policy validator/accessor](../../be/compass/organization/program_policy.py),
[selection helpers](../../be/compass/organization/selection.py) and existing Organization services.
Do not use seed identity sets to authorize or classify new definitions.

ORG-2 responsibilities:

- Focused create Campus/College/Program; stable normalized code and UUID. Creation/activation needs
  valid active ancestry. New Program policy must use the shared validator and existing SQL guards.
- Official-name edits on the same UUID. Exclude code changes, parent moves, mergers, transfers,
  aliases, code reuse and generalized imports from ordinary update payloads.
- Explicit status operations with transactional dependency impact, current operational blockers and
  preserved historical references. Preview is advisory; recheck under the mutation transaction.
  Do not cascade child retirement or counselor/student reassignment.
- Explicit Program-policy mutation; current-only policy plus bounded Audit. Decide pending-request
  warnings/re-preparation and incomplete activation rules institutionally; do not add incidental
  F4 eligibility expansion or retroactive Inventory validation.
- Add positive integer resource_version to Campus/College/Program in the next additive migration
  (recheck graph; anticipated 0003). Require expected version, lock/re-read/compare and increment
  once. Preserve unique database keys and typed duplicate/stale/blocked conflicts.
- Introduce `organization.catalog.manage` with structure.view dependency and institutionally selected
  active-staff role fences. No automatic IT/Head/organization.manage grant. Apply recent MFA and
  capability checks in API and service entry points; preserve CSRF/session authentication.
- Reuse synchronous Audit: meaningful target/version/before/after evidence and bounded basis, same
  transaction. Failure rolls back entity/version. Restricted target-specific safe history only;
  catalog permission does not imply account/confidential-record or global Audit access.
- Use strict schema/operation IDs and generated OpenAPI/Orval for new contracts; no generic arbitrary
  model update endpoint or frontend-only safeguard.

Concurrency must cover duplicate creation, same-row edits, child creation versus parent retirement,
affiliation/responsibility/account reactivation versus retirement, policy versus Inventory submit/F4
creation, stale previews and Audit failure. ORG-1's initialization lock is not the ORG-2 operational
integrity barrier. Implement the reviewed shared/exclusive transaction gate/lock order across actual
participants before any editor activation; take it before existing user/domain locks, then parents
in stable order. Prove races with separate PostgreSQL connections/barriers, not sequential mocks.

Preserve StudentAffiliation, CounselorResponsibility, StaffSupervision, role transitions, Head/GSS
scope, provider-owned confidential access, saved Inventory/course/certificate facts and Tracer/report
history. Institution authority, pending/unknown policy tightening, retired historical choices,
historical names and workflow remediation remain explicit decisions, not assumptions.

ORG-3 consumes actual protected contracts in the existing Structure workspace; ORG-4 validates the
combined migration/consumer/history/access/browser result. Manual accessibility, institutional UAT,
actual cutover, recovery and grant assignment remain distinct release gates. Current migration
preflight still blocks unapproved deployed ORG-1 application; no ORG-2 source merge overrides it.
