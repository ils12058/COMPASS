# SAR-2B + SAR-2C implementation

**Branch:** `integration/ux15-modernization`
**Base:** `b1ccd59b8d8d45d5b80789eb908eac1a0586c0e1`
**Date:** 2026-11-04.

## 1. Data model

Added to `be/compass/student_academics/models.py`:

- `AcademicTerm` — `FIRST_SEMESTER` (“First Semester”), `SECOND_SEMESTER` (“Second Semester”).
- `EnrollmentStatus` — `UNKNOWN` (“Unknown”, the default), `ENROLLED` (“Enrolled”),
  `NOT_ENROLLED` (“Not enrolled”).
- `StudentAcademicPeriodRecord` — UUID primary key; `student` (PROTECT, reverse
  `academic_period_records`); `academic_year` (PROTECT); `term`; `college` (PROTECT); a nullable
  `program` kept for the proposal shape and **never written**; nullable `year_level`; enrollment
  status; `created_by`/`updated_by` (SET_NULL); timestamps.
- `StudentGraduationRecord` — UUID primary key; one-to-one `student` (PROTECT, reverse
  `graduation_record`); `graduated_college` (PROTECT); a nullable `graduated_program` kept for the
  proposal shape and **never written**; `graduation_date`; `verification_source` (max 200);
  `verified_by` (SET_NULL); `verified_at`; timestamps.

Both models use `default_permissions = ()`. Period records are ordered
`("student_id", "-academic_year__label", "term")`; graduation records by `student_id`. Database
constraints:

| Constraint | Rule |
|---|---|
| `student_academics_period_uniq` | unique `(student, academic_year, term)` |
| `student_academics_period_term_valid` | `term` is an `AcademicTerm` value |
| `student_academics_period_enrollment_valid` | `enrollment_status` is an `EnrollmentStatus` value |
| `student_academics_period_year_level_positive` | `year_level` is null or at least 1 |

The service enforces the tighter 1–8 range; the check constraint protects the database from
zero/negative values. `StudentAcademicProfile` is unchanged.

## 2. Migration and canonical baseline

`be/compass/student_academics/migrations/0002_studentacademicperiodrecord_studentgraduationrecord.py`
is one ordinary migration depending on `organization/0005_delete_studentaffiliation` and
`student_academics/0001_initial`. Its path is in `be/compass/common/canonical_migrations.json` under
`additive_migrations`, so the reset-only canonical baseline replay includes it. No data migration or
backfill exists.

## 3. Service semantics

All writes live in `be/compass/student_academics/services.py`, run inside `transaction.atomic()`,
are decorated with `catalog_dependent_write`, lock the Student first (`select_for_update`), then the
College and its Campus, then the profile/period/graduation row, and are idempotent.

### 3.1 `record_academic_period(...)`

- Requires a Student-role account; allows inactive Students and any lifecycle status, because
  correcting history for former or graduated Students is valid.
- Requires the Academic Year to exist. College and Campus must both be active.
- Validates `term`, `enrollment_status`, and `year_level` (`None` or an integer 1–8).
- Never accepts a Program; `program` is stored null.
- Upserts by `(student, academic_year, term)`. Creating sets `created_by` and `updated_by`; updating
  sets `updated_by` through `save(update_fields=...)` including `updated_at`.
- A fully matching row returns unchanged without saving, touching `updated_at` or auditing.
- Emits exactly one `student_academics.period.recorded` event with target
  `student_academics.studentacademicperiodrecord` and flat metadata: `created`, `student_id`,
  `academic_year_id`, `term`, `previous_college_id`, `new_college_id`, `previous_year_level`,
  `new_year_level`, `previous_enrollment_status`, `new_enrollment_status`.
- Does not touch `StudentAcademicProfile` or `student_lifecycle_status`.

### 3.2 `record_graduation(...)`

- Requires a Student-role account; allows inactive Students and any lifecycle status.
- Requires an active College and Campus. Validates that `graduation_date` is a `date` (no
  future/past policy) and that `verification_source` strips to a non-empty string of at most 200
  characters.
- Never accepts a Program; `graduated_program` is stored null.
- Upserts the one-to-one record, setting `verified_by` to the acting User (null for a system
  context) and `verified_at` to `timezone.now()`.
- Clears every placement fact through the shared `_clear_placement_facts` helper (null College and
  Program, reset verification to `UNVERIFIED`, null effective date, set `updated_by`) and emits
  `student_academics.placement.cleared` with `previous_college_id` and `cause="graduation"`.
  `clear_current_placement` uses the same helper, so the two paths cannot drift.
- Sets `student_lifecycle_status = GRADUATED` when needed, saving
  `["student_lifecycle_status", "updated_at"]`. It does not emit the Accounts-owned
  `account.student_lifecycle.changed` event.
- Emits exactly one `student_academics.graduation.recorded` event with target
  `student_academics.studentgraduationrecord` and flat metadata: `created`, `student_id`,
  `previous_college_id`, `new_college_id`, `previous_graduation_date`, `new_graduation_date`
  (ISO dates), `previous_source`, `new_source`, `lifecycle_from`, `lifecycle_to`,
  `placement_cleared`.
- A fully matching record with lifecycle already `GRADUATED` and no placement facts returns without
  saving or auditing. If Accounts moved the lifecycle back to `CURRENT`, re-submitting graduation
  sets it to `GRADUATED` again and audits.
- There is no delete or un-graduation function.

### 3.3 Aggregate read

`get_student_academic_record(*, student_id)` returns a frozen dataclass with the Student,
`lifecycle_status`, the placement profile only when `current_college` is set, all period rows in
model order, and the graduation record or `None`. It locks nothing and validates the Student exists
with role `STUDENT`.

### 3.4 SAR-2A residual fixes

- `clear_current_placement` now calls `_clear_placement_facts`: a profile with no placement facts
  returns `False` without saving, touching `updated_at` or auditing.
- `list_current_placements` adds `student__role__code="STUDENT"` to the base queryset, so
  fixture-created non-Student profiles cannot appear in the directory.

## 4. API

`be/compass/student_academics/api.py` keeps the existing router, tag and session authentication.
Reads require `organization.manage`; writes require `organization.manage` and `recent_mfa=True`.
Errors reuse the existing mapping: 404 `student_academic_not_found`, 409
`student_academic_conflict`, 422 `invalid_student_academic_request`.

| Method/path | Operation ID | Response |
|---|---|---|
| `GET /api/v1/student-academics/students/{student_id}/record` | `studentAcademicsGetStudentRecord` | `StudentAcademicRecordResponse` |
| `PUT /api/v1/student-academics/students/{student_id}/periods` | `studentAcademicsRecordPeriod` | `AcademicPeriodRecordResponse` |
| `PUT /api/v1/student-academics/students/{student_id}/graduation` | `studentAcademicsRecordGraduation` | `GraduationRecordResponse` |

Schemas are `StrictSchema` (unknown keys rejected):

- `AcademicPeriodRecordRequest`: `academic_year_id`, `term`, `college_id`, optional `year_level`,
  `enrollment_status` defaulting to `UNKNOWN`.
- `AcademicPeriodRecordResponse`: `id`, `academic_year` (reusing `AcademicYearResponse`), `term`,
  `college` (`CollegeSummary`), `year_level`, `enrollment_status`, `created_at`, `updated_at`.
- `GraduationRecordRequest`: `graduated_college_id`, `graduation_date`, `verification_source`.
- `GraduationRecordResponse`: `id`, `graduated_college`, `graduation_date`, `verification_source`,
  `verified_by` (`OrganizationPersonSummary | None`), `verified_at`, `created_at`, `updated_at`.
- `StudentAcademicRecordResponse`: `student`, `lifecycle_status`, `placement | None`,
  `periods`, `graduation | None`.

The aggregate reuses the private `_person`, `_college`, `_context`, `_require` helpers from
`organization.api`. There is no DELETE route for periods or graduation. Django Ninja answers a
DELETE on those PUT-only paths with **405 Method Not Allowed**, not 404; the HTTP test asserts the
actual behavior and the deviation from the task text's “(404)” wording is recorded in
[`validation.md`](validation.md).

`uv run python manage.py export_openapi --output ../contracts/openapi.json` regenerated the
contract. The generated frontend client was produced by `pnpm api:generate`; neither file was
hand-edited.

## 5. Audit

`be/compass/audit/actions.py` adds and exports:

```python
STUDENT_ACADEMICS_PERIOD_RECORDED = "student_academics.period.recorded"
STUDENT_ACADEMICS_GRADUATION_RECORDED = "student_academics.graduation.recorded"
```

No audit migration was needed: the target-type regex already permits underscores. The actions are
intentionally absent from `compass/activity/domains.py`; My Activity is a closed evidence matrix.

## 6. Frontend

### 6.1 Directory

`fe/src/features/student-academics/student-academic-records/student-academic-records-page.tsx`:

- Student names are real links to `/portal/organization/student-academics/{student.id}`.
- A secondary **Open record** `PageAction` opens a Dialog with the existing `PeoplePicker`
  (`role="STUDENT"`). Selecting a Student and confirming navigates to the record. This is the only
  route to cleared or graduated Students after they leave the placements list.
- The Assign/Update/Clear placement flows are unchanged.

Navigation and command palette labels changed from “Student placements” to **Student Academic
Records** (`organization-navigation.tsx`, `portal-command-destinations.ts`). The results panel stays
titled “Student placements”, and every `student-academics` path and keyword is unchanged. The gate
copy is now “You don’t have access to Student academic records.”

### 6.2 Detail route and page

`fe/src/app/(portal)/portal/organization/student-academics/[studentId]/page.tsx` uses the Next.js
async `params` pattern, `pageSheetWidth`, `StudentAcademicRecordsGate` and a Suspense skeleton. The
component lives in
`fe/src/features/student-academics/student-academic-record/student-academic-record-page.tsx`:

1. **Page heading** — back link to Student placements, full name, institutional ID/email, lifecycle
   and active badges.
2. **Current placement** — read-only College, Campus, verification and a College-only Program note,
   or “No current College placement.” Placement changes stay in the directory.
3. **Academic periods** — table of Academic year, Term, College, Year level, Enrollment and Last
   updated, with a **Record period** panel action and a per-row **Update**. The Dialog edits Academic
   year, Term, College, optional year level (1–8) and enrollment status; saving is plain, shows
   `ActionStatus` and refetches the aggregate. Empty state: “No academic periods recorded.”
4. **Graduation** — College, Graduation date, Verification source, Verified by, Verified at and Last
   updated, or “No graduation recorded.” The Dialog (date, College, source) is followed by a
   `ConsequentialActionDialog` whose copy states that recording/updating graduation clears the
   current placement and sets the lifecycle to Graduated, and that Exit Interview and Good Moral are
   not checked or changed. The completed outcome appears in the same dialog; both the aggregate and
   the placements list are invalidated.

Data handling: one `useStudentAcademicsGetStudentRecord` aggregate read; College choices from
`useOrganizationListColleges` (requires `organization.structure.view`); Academic Year choices from
`useAcademicYearsList` (requires `academic_years.view`). Missing authority or a failed read disables
the affected forms with an explanatory notice while recorded facts stay visible. Only generated
hooks and query keys are used. Panel actions are ordinary Buttons per `fe/AGENTS.md`; page-level
actions use `PageAction`.

## 7. Staging seed

`be/compass/staging_seed/academic_history.py` adds `seed_academic_history(session)`, called from
`seed.py` as the **Student academic history** unit **after** “Background stories”, so every
lifecycle alignment has finished before a graduation record can move a Student to `GRADUATED`:

- For every Student persona with `year_levels`, each `(label, year_level)` is recorded as a
  `FIRST_SEMESTER` period with `ENROLLED`, the persona's `college_for(campus_code, college_code)`
  College and `session.system()` context. Labels absent from the seeded `AcademicYear` set are
  skipped; no Academic Year is invented.
- Every persona whose lifecycle is `GRADUATED` also gets a graduation record for its College, dated
  June 30 of the final listed Academic Year's end year, with
  `verification_source="Staging seed: Registrar confirmation"`.
- Existence checks run before each service call so `session.record(...)` reports `created`
  accurately and a rerun reports all rows as existing. The services remain idempotent.

`be/tests/test_staging_seed.py` gains
`test_canonical_academic_history_matches_each_personas_recorded_years`, which asserts the total
period count, every term/status/program, per-persona label/year-level and College sets, the exact
graduated Student set, June 30 dates, source constant, College, lifecycle `GRADUATED` and the
absence of a current placement. Existing seed assertions were not weakened; the full 51-test seed
suite passes.

## 8. File inventory

Backend:

- `be/compass/student_academics/models.py` — two models, two choice classes.
- `be/compass/student_academics/migrations/0002_studentacademicperiodrecord_studentgraduationrecord.py`.
- `be/compass/common/canonical_migrations.json` — additive migration entry.
- `be/compass/audit/actions.py` — two actions.
- `be/compass/student_academics/services.py` — two writers, aggregate reader, two residual fixes.
- `be/compass/student_academics/api.py` — three operations and five schemas.
- `be/tests/test_student_academic_records.py` — 16 new tests (32 total).
- `be/tests/test_openapi_contract.py` — the three new operation IDs added to the stable inventory.
- `be/compass/staging_seed/academic_history.py`, `be/compass/staging_seed/seed.py`,
  `be/tests/test_staging_seed.py`.

Frontend:

- `fe/src/app/(portal)/portal/organization/student-academics/[studentId]/page.tsx`.
- `fe/src/features/student-academics/student-academic-record/` — page and presentation helpers.
- `fe/src/features/student-academics/student-academic-records/student-academic-records-page.tsx`.
- `fe/src/features/organization/components/organization-action.tsx` — error copy.
- `fe/src/features/organization/components/organization-gate.tsx` — gate copy.
- `fe/src/features/organization/components/organization-navigation.tsx` — nav label.
- `fe/src/features/portal/components/portal-command-destinations.ts` — palette label.
- `fe/tests/student-academic-record.browser.mjs`, `fe/tests/student-academic-record.test.mjs`,
  `fe/tests/support/catalog-fixtures.mjs`, `fe/tests/organization-catalog.browser.mjs`.
- `contracts/openapi.json` (regenerated) and the gitignored generated client.
