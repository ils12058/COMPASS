# SAR-3 + SAR-4 — Cross-domain reads and provisioning placement

**Status:** Implemented and validated, merged into `integration/ux15-modernization` and pushed to
`origin` without a PR; not deployed or run against staging or production.
**Branch:** `integration/ux15-modernization`.
**Base:** `ec083fda`.
**Date:** 2026-11-04.

## 1. Scope delivered

- **SAR-3** — one read-only boundary for canonical current Student placement at
  `be/compass/student_academics/reads.py`, and migration of the listed per-student consumers to it.
  Error codes, reason strings, messages and the Faculty Referral revision token are unchanged.
- **SAR-4** — optional initial Student placement during single account creation and CSV
  provisioning:
  - `set_current_placement` gains `expected_campus_id` and `allow_inactive_student`; it remains the
    only writer.
  - Single create accepts `student_campus_id` / `student_college_id` and calls the writer inside the
    same transaction.
  - CSV accepts optional Student-only `campus_code` / `college_code`, previews them, classifies
    existing placements, and writes them on commit.
  - Create-account and CSV-import UI expose the optional placement; the College reference summary
    and CSV preview were extended.
- No model or migration change was required or made.

## 2. Explicit non-goals

Not implemented or changed by this slice:

- Program anywhere: profile, API, CSV, UI or seeds. `program_code` remains an unsupported CSV header.
- Placement verification, effective dates, enrollment inference or Student lifecycle changes.
- Period or graduation read services, history views, corrections or retention.
- Good Moral, Exit Interview, Graduate Tracer or Inventory eligibility/prefill.
- Existing-account academic updates through CSV or account creation.
- Bulk consumer queryset migration, report reconciliation or Organization catalog impact counts.
- New capabilities, roles, designations, migrations or feature flags.
- Account-detail placement display, navigation changes or a new placement workspace.
- Changes to `FacultyAffiliation`, Faculty code, Graduate Tracer eligibility, Good Moral
  eligibility, Exit Interview policy, Inventory snapshots, Reports formulas or Group Sessions.

## 3. One writer, one read boundary

`compass.student_academics.services` remains the only module that creates, updates or clears
`StudentAcademicProfile`. `compass.student_academics.reads` is read-only: no writes, audit, locks or
policy resolution. Bulk querysets and composite Counseling predicates stay direct and are recorded
as intentional residual couplings in [`implementation.md`](implementation.md).

Placement remains College-only, always `UNVERIFIED`, with a null Program and a null effective date.
Campus is a validation input only; it is never stored on the profile, returned by the API or added
to audit metadata.

## 4. Decisions consumed

This slice applies D-SAR-01, D-SAR-02, D-SAR-04, D-SAR-05, D-SAR-06/07 and D-SAR-08, and records a
provisional engineering default for D-SAR-15 (initial placement is optional; omitting it creates no
profile row). D-SAR-05 and D-SAR-19/20 remain open. See [`decisions.md`](decisions.md).

## 5. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Read facts API, migrated consumers, residual couplings, writer and provisioning flows, CSV matrix, API/schema, frontend and authorization |
| [`decisions.md`](decisions.md) | Applied defaults, D-SAR-15 provisional default, `organization.manage` reuse, naming residues and open decisions |
| [`validation.md`](validation.md) | Exact commands and real results, failures and fixes, zero-reference checks and the explicit full-suite gap |

## 6. Relationship to earlier slices

`docs/sar-0/`, `docs/sar-1/`, `docs/sar-2a/` and `docs/sar-2b-2c/` remain historical and were not
rewritten. SAR-2A established the canonical current-placement store; SAR-2B/2C added periods and
graduation; this slice centralizes the read side and adds optional provisioning input on top of
those stores. The deliberate SAR-2A residues (`NO_AFFILIATION` and the report PDF label
`Applied — Student's current Guidance affiliation`) are untouched.
