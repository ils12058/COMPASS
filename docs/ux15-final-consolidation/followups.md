# Follow-ups

These follow-ups are not confirmed UX15 production defects and do not expand the final
consolidation scope. Keep separate implementation and institutional-policy proposals out of the
immediate promotion gate unless later evidence shows a dependency.

## Before or during staging UAT

1. Confirm any hosted-check requirement for PRs targeting the UX15 integration branch. Current
   Actions branch filters exclude that base; no workflow changes or manual dispatch were made.
2. After a separately approved staging deployment, run the account/capability/College/supervision
   cases in [UAT matrix](uat-matrix.md) with approved non-production records and current staging
   SHA.
3. Exercise actual browser zoom at 200%, institution-supported screen readers, keyboard navigation
   (including Safari Full Keyboard Access), and physical mobile/touch behavior.
4. Use the backend team's normal test environment for server-side scope, data privacy, database
   concurrency, and idempotency-store behavior. Do not use production records for fault injection.
5. Record real role-based stakeholder UAT, defects, evidence, and disposition. Proposal #15 remains
   experimental until institutional review/acceptance is completed.

## Monitoring notes

- Re-fetch staging before any promotion. If it advances independently, review overlapping files and
  use a separately approved reconciliation; do not merge automatically or rewrite shared history.
- Retain the distinct UX15 Home sources and form workflows. Do not introduce a generic dashboard,
  universal form engine, new global state manager, second authorization policy, or second work
  aggregator in a follow-up without a demonstrated need.
- No new role migration, Head override, Case Continuity feature, Group Session lifecycle, reporting
  subsystem, notification infrastructure, or other separately proposed feature is a dependency
  established by this audit.

## Completed in this consolidation

- Repaired the synthetic GSS account-switch browser test timing by waiting for Next route
  prefetches before reload. The test passes in both engines; application behavior and production
  code are unchanged.
- Indexed existing screenshots/geometry rather than copying the large image set.
- Preserved blank UAT fields; no stakeholder result was fabricated.
