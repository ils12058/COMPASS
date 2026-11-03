# SAR-1 — Shadow Student Academic Profile

**Status:** Backend-only, additive implementation slice. **Not activated.**
**Base:** `integration/ux15-modernization` at `5a147bb1dd64d10837eeed905c6db68dfd2b716b` (SAR-0 merge, PR #353).
**Branch:** `codex/sar-1-academic-profile`.
**Date:** 2026-11-03.
**Activation gate:** `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED`, default `False`. It is not enabled in
the repository, tests, Compose, CI or documentation examples. Every gate-on test uses Django
`override_settings` only.

## 1. Scope delivered

1. New Django app `be/compass/student_academics/` containing only `StudentAcademicProfile`.
2. One schema-only migration (`0001_initial`). No data rows are created by the migration.
3. A sync service that is the only runtime writer of the profile.
4. Gated dual-write from `set_student_affiliation` and `remove_student_affiliation` inside the
   existing affiliation transaction.
5. `backfill_student_academic_profiles` and `reconcile_student_academic_profiles` management
   commands with aggregate-only output.
6. Focused tests in `be/tests/test_student_academic_profiles.py` and CI bundle/domain mapping.
7. This documentation package.

## 2. Explicit non-goals

Not implemented by this slice:

- `StudentAcademicPeriodRecord` or `StudentGraduationRecord`.
- Any API endpoint, OpenAPI contract change, frontend route or component.
- Any `student_academics.*` capability or change to `be/compass/accounts/policy.py`.
- Any change to account creation, CSV provisioning or seed data.
- Any change to `StudentAffiliation`'s model, API contract or behavior while the gate is off.
- Moving any consumer (reports, Inventory, Good Moral, Tracer, counseling, appointments, referrals,
  call slips, messages, follow-ups) to the profile.
- Backfilling Program, effective date, enrollment or graduation; marking any row `VERIFIED`;
  deleting or rewriting affiliation, Inventory, Good Moral or Tracer rows.
- A second audit system or duplicate audit events. Affiliation audit events remain the only
  affiliation audit trail.
- Enabling the gate, merging, deploying or migrating staging/production.

## 3. What changes with the gate off

Nothing observable changes:

- `StudentAcademicProfile` has no reads on any runtime path.
- `set_student_affiliation` and `remove_student_affiliation` return early in the sync service
  without touching the profile table.
- Affiliation responses, audit events, authorization, OpenAPI and frontend are unchanged.
- The only persistent change is the new table and Django app registration.

The profile is a **shadow projection**, not a source of truth. `StudentAffiliation` remains the sole
authoritative current College writer.

## 4. Decisions consumed

The SAR-0 decision register (`docs/sar-0/decisions.md`) records D-SAR-01 through D-SAR-20 as
**Open**. This slice applies the task's provisional engineering defaults (Option A for D-SAR-01
through D-SAR-08) so implementation can proceed without inventing institutional policy. These
defaults are reversible and the gate stays off. See [`decisions-consumed.md`](decisions-consumed.md).

## 5. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Model, gate, sync semantics, backfill and reconciliation logic |
| [`operations.md`](operations.md) | Backfill, activation, monitoring and rollback runbook |
| [`validation.md`](validation.md) | Exact commands and results, evidence limits |
| [`decisions-consumed.md`](decisions-consumed.md) | D-SAR-01..08 as applied; D-SAR-09..20 deferred |

## 6. Activation status

**Not activated.** Deploying this branch only adds an empty shadow table and dormant code. Before
the gate may be enabled, an approved operator must complete the runbook in
[`operations.md`](operations.md), including backfill, reconciliation to zero blocking mismatches,
and the D-SAR-08 activation approval. No such action was taken in this work.
