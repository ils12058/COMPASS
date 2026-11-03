# SAR-2A implementation

**Base:** `9109aa83b761086337826d9d1404e0ba8c8c2be3` (SAR-1 commit).
**Branch:** `codex/sar-2a-canonical-placement`.
All statements below describe code in this branch. No migration, deployment or activation was run
against a shared environment.

## 1. Canonical model

**File:** `be/compass/student_academics/models.py`

`StudentAcademicProfile` is unchanged in schema from SAR-1; only the module and failure-path
docstrings were reworded. It remains the only model in the app.

| Field | Definition | SAR-2A behavior |
|---|---|---|
| `id` | UUID PK, `uuid.uuid4` | Generated |
| `student` | OneToOne `AUTH_USER_MODEL`, `PROTECT`, `related_name="student_academic_profile"` | One profile per Student |
| `current_college` | FK `organization.College`, `PROTECT`, `related_name="student_academic_profiles"`, nullable | The canonical current College; null when cleared |
| `current_program` | FK `organization.Program`, `PROTECT`, nullable | Always null; no writer |
| `placement_verification_status` | `UNVERIFIED` / `VERIFIED`, default `UNVERIFIED` | Always `UNVERIFIED`; no verify action |
| `placement_effective_at` | nullable datetime | Always null; no effective-date writer |
| `updated_by` | FK `AUTH_USER_MODEL`, `SET_NULL`, `related_name="+"`, nullable | Acting user when known |
| `created_at` / `updated_at` | automatic timestamps | Standard |

`Meta` keeps `default_permissions = ()`, `ordering = ("student_id",)` and the
`student_academics_verification_status_valid` check constraint. No capability, role or designation
grant references the model.

The app is registered as `compass.student_academics` in `be/config/settings.py:78`.

## 2. Migrations

| Migration | Contents |
|---|---|
| `be/compass/student_academics/migrations/0001_initial.py` | Creates `StudentAcademicProfile`; depends on `organization.0004_facultyaffiliation` |
| `be/compass/organization/migrations/0005_delete_studentaffiliation.py` | `DeleteModel` for `StudentAffiliation`; depends on `organization.0004_facultyaffiliation` |
| `be/compass/counseling/migrations/0005_student_placement_marker.py` | Renames the continuity grant field `student_affiliation_marker` to `student_placement_marker`; same value and semantics |
| `be/compass/audit/migrations/0002_alter_auditevent_target_type.py` | Updates the `target_type` validator to the underscore-permitting pattern |

`0005` is schema-only. There is no data migration, backfill or row rewrite. The repository uses a
reset-only canonical baseline, so no compatibility window or staged data transition is required.
`StudentAffiliation` survives only in the two historical migrations
(`0001_canonical_baseline.py`, `0005_delete_studentaffiliation.py`).

`FacultyAffiliation` is untouched: model, migration `0004`, services, API, serializers, audit
actions and frontend remain as they were.

## 3. Single writer

**File:** `be/compass/student_academics/services.py`

Only this module creates, updates or clears `StudentAcademicProfile`. Both writers lock the
canonical rows inside `transaction.atomic()` and are wrapped in `catalog_dependent_write` so a
catalog deactivation cannot race a placement write. The list function is read-only and takes no
locks.

### `set_current_placement(*, student_id, college_id, context)`

1. Locks the Student (`select_for_update(of=("self",))`) and requires role `STUDENT` and an active
   account.
2. Locks the College and its Campus and requires both to be active.
3. Locks the profile row when it exists.
4. Same canonical College with `current_program`, `placement_effective_at` null and status
   `UNVERIFIED`: return without saving or auditing.
5. Otherwise set `current_college`, null `current_program` and `placement_effective_at`, force
   `UNVERIFIED`, set `updated_by`, save, and append
   `student_academics.placement.set` with target type
   `student_academics.studentacademicprofile`, target ID `student.pk`, and metadata
   `previous_college_id` / `new_college_id`.
6. A transfer therefore cannot retain a stale Program, effective date or verification label.

### `clear_current_placement(*, student_id, context)`

1. Locks the Student; an inactive Student is allowed because clearing is a repair path. A
   non-Student still fails validation.
2. Locks the profile row. If no profile exists, return `False` without an audit event.
3. Null `current_college`, `current_program` and `placement_effective_at`, force `UNVERIFIED`, set
   `updated_by`, save and append `student_academics.placement.cleared` with metadata
   `previous_college_id`.
4. The row is retained. Clearing never deletes the profile and never touches the Student account.

### `list_current_placements(...)`

Read-only projection for the API. It filters `current_college__isnull=False`, selects
`student__role` and `current_college__campus`, supports Student, College, Campus and search filters,
orders by last name, first name and Student ID, and caps `page_size` at 50. A cleared profile is
therefore absent from the directory.

Domain errors are `StudentAcademicNotFound`, `StudentAcademicConflict`,
`InvalidStudentAcademicInput` and base `StudentAcademicError`.

## 4. API and contract

**File:** `be/compass/student_academics/api.py`; mounted at `/api/v1/student-academics` in
`be/compass/api/v1/router.py:259`.

| Method | Path | Operation ID | Authorization |
|---|---|---|---|
| GET | `/placements` | `studentAcademicsListPlacements` | `organization.manage` |
| PUT | `/students/{student_id}/placement` | `studentAcademicsSetPlacement` | `organization.manage` + recent MFA |
| DELETE | `/students/{student_id}/placement` | `studentAcademicsClearPlacement` | `organization.manage` + recent MFA |

Responses reuse the organization schemas `OrganizationPersonSummary`, `CollegeSummary` and
`RemovedResponse`. `PlacementResponse` adds `verification_status`. Errors map to `404`
`student_academic_not_found`, `409` `student_academic_conflict` and `422`
`invalid_student_academic_request`.

`be/compass/api/contract.py` adds the `student-academics` tag and the `studentAcademics` operation-ID
prefix. `contracts/openapi.json` was regenerated, not hand-edited. The retired organization routes
`/api/v1/organization/student-affiliations` and `/students/{id}/affiliation` no longer exist; a
regression test asserts both return 404.

## 5. Audit

**Files:** `be/compass/audit/actions.py`, `be/compass/audit/models.py`.

- Added `student_academics.placement.set` and `student_academics.placement.cleared`; removed the
  three `organization.student_affiliation.*` actions.
- `TARGET_TYPE_PATTERN` now permits underscores inside each dot-separated segment so
  `student_academics.studentacademicprofile` validates. `ACTION_PATTERN` already allowed them.
- Affiliation audit events are gone with the model. Placement writes append exactly one event per
  state change; no duplicate audit system was introduced.

## 6. Consumer source swap

Every consumer that previously resolved `StudentAffiliation` now resolves the profile through the
reverse OneToOne relation `student__student_academic_profile__current_college` (or a direct
`StudentAcademicProfile` query). Authorization, scoping and selection semantics are unchanged.

Swapped domains:

| Area | Files |
|---|---|
| Operational Student lists and scopes | `operational_students.py`, `appointments/access.py`, `assessment_records/services.py`, `call_slips/services.py`, `student_support/services.py` |
| Counseling context and continuity | `counseling/context_services.py`, `counseling/continuity_access.py`, `counseling/continuity_locks.py`, `counseling/continuity_models.py`, `counseling/continuity_services.py`, `counseling/coverage_selection.py`, `counseling/handoff_services.py` |
| Guidance work | `guidance_followups/policy.py`, `guidance_followups/recovery.py`, `guidance_followups/workspace.py`, `guidance_messages/services.py` |
| Good Moral and Inventory | `good_moral/api.py`, `good_moral/services.py`, `inventory/services.py` |
| Referrals | `referrals/services.py`, `referrals/faculty_placement.py` |
| Reports | `reports/services.py` |
| Organization routing | `organization/services.py` |

Deliberate behavior-preservation choices:

- `resolve_default_counselor_for_student` keeps the externally visible reason code
  `NO_AFFILIATION`; a missing profile and a profile without a current College both return it.
- `reports/pdf.py` keeps the existing label
  `Applied — Student's current Guidance affiliation` so report output is byte-identical. This is a
  wording deviation from the frontend "placement" terminology and is recorded in
  [`decisions.md`](decisions.md).
- `counseling/context_services.py` only renames a local variable from `affiliation` to `placement`.
- Good Moral keeps the same prerequisite (an active current College) but renames its exception and
  409 code from `good_moral_affiliation_required` to `good_moral_placement_required`. The frontend
  mapping and the assisted-request test were updated; the OpenAPI contract was regenerated.

## 7. Catalog impact

**Files:** `be/compass/organization/catalog_services.py`, `be/compass/organization/api.py`.

Counts, blockers and warnings now read placements:

| Old key | New key |
|---|---|
| `student_affiliations` | `student_placements` |
| `active_student_affiliations` | `active_student_placements` |
| `inactive_account_affiliations` | `inactive_student_placements` |
| preserved category `inactive_affiliations` | `inactive_placements` |

`pending_operational_followups` and the Good Moral student reference set now use placement Student
IDs. The blocker set for Campus/College deactivation is unchanged in meaning: active Student
placements still block. Counts are derived only from rows with a non-null `current_college`, because
the queryset filters `current_college_id__in=...`; a cleared profile has no College and cannot
block or inflate a catalog count.

## 8. Role transition guard

**File:** `be/compass/organization/services.py:145-153`.

Changing a Student's role is blocked while a profile with a non-null `current_college` exists. The
message is “Clear the student's current College placement before changing role.” A cleared or
missing profile does not block the transition. The guard is a read-only check; it never mutates the
profile.

## 9. Staging seeds

**Files:** `be/compass/staging_seed/organization.py`, `staging_seed/verify.py`,
`staging_seed/manifest.py`.

- `ensure_organization` calls `set_current_placement` and records `Student placements`.
- Conflict preflight reads the profile and fails when a seeded Student is placed in a different
  College than the dataset.
- Verification checks the profile's `current_college.campus.code` and `current_college.code` and
  requires non-affiliated personas to have no profile with a College.
- The manifest copy says “Review responsibilities and Student placements.”

No seed writes the profile directly; the seeder is an ordinary caller of the single writer.

## 10. SAR-1 machinery removed

- `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED` removed from `be/config/settings.py` and
  `be/.env.example`.
- `sync_profile_from_affiliation`, `clear_profile_for_removed_affiliation` and any gate helper
  deleted.
- `backfill_student_academic_profiles` and `reconcile_student_academic_profiles` commands and the
  `management/` package deleted.
- `be/tests/test_student_academic_profiles.py` deleted.
- No compatibility alias, proxy model, legacy related name or fallback route remains.

## 11. Frontend

| Change | Files |
|---|---|
| Feature moved | `fe/src/features/organization/student-affiliations/` → `fe/src/features/student-academics/student-academic-records/` |
| Route moved | `/portal/organization/student-affiliations` → `/portal/organization/student-academics` |
| Workspace gate | `StudentAcademicRecordsGate` in `organization-gate.tsx`, using `canManageOrganization`; unavailable message “Student Academic Records unavailable” |
| Page | Title “Student Academic Records”; panel “Student placements”; columns Student, Institutional ID, College, Campus, Verification, Action |
| Actions | Assign, Update and Clear placement through `ConsequentialActionDialog`; step-up via `useOrganizationAction` |
| Verification | Read-only “Unverified” / “Verified” badge; no verify action |
| Navigation and command palette | Link and destination `/portal/organization/student-academics`, label “Student placements”, keywords including “student academic records” |
| Catalog impact UI | New count and issue keys, placement explanations, link “Review Student placements” to the new route |
| Generated client | `pnpm api:generate` produced `student-academics/student-academics.ts` and `Placement*` models; old affiliation hooks removed |
| Tests | Static and browser suites updated for the new route, labels, API paths and count keys |

The page has no Program, effective-date, enrollment, graduation, verification, history or
Student-self-view control. It never displays the word “affiliation”.

## 12. CI mapping

**File:** `.github/scripts/backend_ci.py`

- Bundle `student-academics`: “Canonical Student placement: profile model, writer services, API,
  and listing.”, test file `test_student_academic_records.py`.
- Bundle `organization`: still owns `test_organization.py`.
- Domain `student_academics`: “Canonical Student placement writer read by every organization-scoped
  domain.”, bundles `student-academics`, `organization`, `identity-access`.

## 13. Compatibility summary

| Surface | Before | After |
|---|---|---|
| Model | `organization.StudentAffiliation` | `student_academics.StudentAcademicProfile` |
| Writer | `organization.services.set/remove_student_affiliation` | `student_academics.services.set/clear_current_placement` |
| Writer gate | SAR-1 feature flag, default off | None; live immediately |
| API | `/organization/student-affiliations`, `/organization/students/{id}/affiliation` | `/student-academics/placements`, `/student-academics/students/{id}/placement` |
| Audit | `organization.student_affiliation.*` | `student_academics.placement.set` / `.cleared` |
| Clear semantics | Row deleted | Row retained, placement fields reset |
| Read relation | `organization_student_affiliation` | `student_academic_profile` |
| Catalog keys | `*_student_affiliations`, `inactive_account_affiliations` | `*_student_placements` |
| Frontend route | `/portal/organization/student-affiliations` | `/portal/organization/student-academics` |
