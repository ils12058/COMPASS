# SAR-2B + SAR-2C — Academic Periods, Graduation and the Student Academic Record workspace

**Status:** Implemented and validated on a feature branch. **Merged into
`integration/ux15-modernization` and pushed to `origin` without a PR; not deployed or run against any
shared environment.**
**Branch:** `integration/ux15-modernization`.
**Base:** `b1ccd59b8d8d45d5b80789eb908eac1a0586c0e1` (SAR-2A merge commit).
**Date:** 2026-11-04.

## 1. Scope delivered

- **SAR-2B** — `StudentAcademicPeriodRecord`: one record per Student, Academic Year and term, with
  College, optional year level and an enrollment classification.
- **SAR-2C** — `StudentGraduationRecord`: one confirmed graduation per Student, with the official
  date and a short verification-source note.
- `compass.student_academics.services` remains the **single writer**. `record_academic_period` and
  `record_graduation` are the only functions that create, update or delete these rows.
- Three API operations on the existing `/api/v1/student-academics` router:
  `studentAcademicsGetStudentRecord`, `studentAcademicsRecordPeriod`,
  `studentAcademicsRecordGraduation`.
- Two audit actions: `student_academics.period.recorded` and
  `student_academics.graduation.recorded`.
- The Organization workspace is renamed **Student Academic Records** in the navigation and command
  palette. Its directory rows link to a new detail route
  `/portal/organization/student-academics/{studentId}` built around the aggregate Student academic
  record.
- The directory adds an **Open record** action using the existing `PeoplePicker`, so cleared and
  graduated Students remain reachable after they leave the placements list.
- The staging dataset seeds canonical periods for every Student persona with recorded year levels
  and a graduation record for every persona whose lifecycle is `GRADUATED`.

## 2. Explicit non-goals

Not implemented by this slice:

- Program writer, Program field in any API, program-based policy or Program display.
- Enrollment import, roster reconciliation or automatic `NOT_ENROLLED`.
- Verification actions, effective-date semantics or corrections workflow beyond audited overwrite.
- Student self-view, academic-history export, CSV/import, reports or notifications.
- Multiple degrees, subsequent enrollment, un-graduation or revocation.
- Exit Interview or Good Moral gating. Recording graduation neither reads nor changes either.
- Retention/disposition policy for period or graduation rows.
- Any new capability, role or designation grant. `organization.manage` is reused; writes add recent
  MFA. D-SAR-05 remains open.
- Any change to `FacultyAffiliation`, Faculty code, `StudentAcademicProfile` fields or SAR-2A
  placement behavior beyond the two named residual fixes.
- Data migration or backfill. The product is not deployed; the database is rebuilt from the
  canonical baseline plus seeds.

## 3. One writer, one truth

Every `StudentAcademicPeriodRecord` and `StudentGraduationRecord` write goes through
`compass.student_academics.services`. No other module creates, updates or deletes these rows, and no
other module writes `StudentAcademicProfile` directly. Reads are allowed through the models'
relations and the aggregate reader.

Graduation is a consequential write: in the same transaction it upserts the one graduation record,
clears every current-placement fact with `cause="graduation"`, and moves the Student lifecycle to
`GRADUATED`. It does not emit `account.student_lifecycle.changed`; that action remains owned by
Account Management.

## 4. Decisions consumed

This slice applies provisional engineering defaults for D-SAR-09, D-SAR-10 and D-SAR-11. They are
engineering defaults, not UCN, GCO, Registrar, DPO, Records or IT approvals. D-SAR-12 through
D-SAR-20 remain deferred, including multiple degrees, retention, corrections, student visibility,
Year Level policy beyond 1–8, and reconciliation definitions. See [`decisions.md`](decisions.md).

## 5. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Models, migration, service semantics, API, audit, frontend, seeds and the 2A residual fixes |
| [`decisions.md`](decisions.md) | D-SAR-09/10/11 as applied; D-SAR-12..20 deferred; authorization boundary |
| [`validation.md`](validation.md) | Exact commands, results, zero-reference evidence, deviations and unvalidated items |

## 6. Historical records

`docs/sar-0/`, `docs/sar-1/` and `docs/sar-2a/` remain historical and are not rewritten. SAR-2A
established the canonical current-placement store this slice extends.
