# SAR-2A — Canonical Student Academic Placement Cutover

**Status:** Destructive backend and frontend cutover implemented. **Merged into
`integration/ux15-modernization` and pushed to `origin`; not deployed or activated against any
shared environment.**
**Branch:** `codex/sar-2a-canonical-placement`.
**Date:** 2026-11-03.
**Base:** `9109aa83b761086337826d9d1404e0ba8c8c2be3` (SAR-1 commit on
`integration/ux15-modernization`).

## 1. Scope delivered

1. `StudentAcademicProfile` is the single canonical store of a Student's current College placement.
2. `StudentAffiliation` is deleted, with its model, writer functions, API routes, schemas, audit
   actions, tests, seeds and frontend feature removed rather than shimmed.
3. `compass.student_academics.services` is the only writer:
   `set_current_placement` and `clear_current_placement`.
4. A new `/api/v1/student-academics` API exposes list, set and clear operations.
5. Every existing consumer now reads the profile through
   `student__student_academic_profile__current_college` (or an equivalent direct profile query).
6. Catalog impact terminology moved from affiliation to placement:
   `active_student_placements`, `student_placements`, `inactive_student_placements`.
7. The Organization workspace now has a **Student Academic Records** page at
   `/portal/organization/student-academics` listing the directory as **Student placements**.
8. SAR-1 transitional machinery is deleted: the gate setting and environment variable, the
   dual-write sync/clear functions, `backfill_student_academic_profiles`,
   `reconcile_student_academic_profiles` and their shadow-only tests.

## 2. Explicit non-goals

Not implemented by this slice:

- Program editing, effective-date editing, enrollment status, period records or graduation records.
- Verification actions or any `student_academics.*` capability.
- Student self-view, academic history or corrections.
- Data migration or backfill. The product is not deployed; local data may be dropped and seeds
  create placements from scratch.
- A new feature flag. The new path is live immediately.
- Any change to `FacultyAffiliation` or Faculty code.
- Any production or staging contact, deployment or gate activation. The cutover was merged into
  `integration/ux15-modernization` and pushed to `origin` without a PR.

`current_program` and `placement_effective_at` stay present in the model and remain null. They have
no writer in this slice.

## 3. One writer, one truth

Every current-placement write goes through `compass.student_academics.services`. No other domain
creates, updates or deletes `StudentAcademicProfile` rows. Reads are allowed through the model's
reverse relation and direct profile queries.

The placement row is never deleted by clearing. Clearing nulls `current_college` and
`current_program`, resets `placement_verification_status` to `UNVERIFIED`, nulls
`placement_effective_at`, records the actor and keeps the row and its timestamps.

## 4. Temporary authorization boundary

Writes and reads reuse `organization.manage`; writes additionally require recent MFA. No
`student_academics.*` capability was introduced, and no role or designation grant changed. This is a
**deliberate temporary authorization boundary** for this slice, recorded in
[`decisions.md`](decisions.md). A future slice that introduces dedicated capabilities must revisit
the read and write boundary, MFA policy and designation grants explicitly.

## 5. Decisions consumed

SAR-2A applies provisional engineering defaults for SAR-0 decisions D-SAR-01 through D-SAR-08 and
explicitly supersedes the SAR-1 D-SAR-08 choice that kept `StudentAffiliation` as the sole writer.
These are engineering defaults, not UCN, GCO, Registrar, DPO, Records or IT approvals. D-SAR-09
through D-SAR-20 remain deferred. See [`decisions.md`](decisions.md).

## 6. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Model, migrations, writer semantics, API, audit, consumers and frontend |
| [`decisions.md`](decisions.md) | D-SAR-01..08 as applied; explicit supersession of SAR-1 D-SAR-08; D-SAR-09..20 deferred |
| [`validation.md`](validation.md) | Exact commands, results, zero-reference evidence and unvalidated items |

## 7. Historical records

`docs/sar-0/` and `docs/sar-1/` remain historical. SAR-1 described a gated shadow projection; this
slice replaces that design. The SAR-1 documents are not rewritten.
