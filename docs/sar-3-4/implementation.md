# SAR-3 + SAR-4 implementation

**Status:** implemented, merged into `integration/ux15-modernization` and pushed to `origin` without
a PR; not deployed.

## 1. SAR-3 — canonical read boundary

### 1.1 Module

`be/compass/student_academics/reads.py` is read-only: no writes, audit, locks or policy resolution.

| Name | Shape | Behavior |
|---|---|---|
| `AcademicCollegeFacts` | frozen dataclass: `id`, `code`, `name`, `is_active`, `campus_id`, `campus_code`, `campus_name`, `campus_is_active` | `is_usable` is `is_active and campus_is_active` |
| `StudentPlacementFacts` | frozen dataclass: `student_id`, `profile_id`, `college`, `updated_at` | `revision` returns `f"student_academics:{self.profile_id}:{self.updated_at.isoformat()}"` |
| `get_current_placement(*, student_id, require_active_college=False)` | one profile via `select_related("current_college__campus")` | `None` when no profile or `current_college` is null; with `require_active_college=True`, also `None` when College or Campus is inactive |
| `student_is_placed_in_colleges(*, student_id, college_ids, require_active_college=True)` | `exists()` predicate | `False` for empty IDs; requires membership and, by default, active College and Campus ancestry |

Period and graduation read functions were deliberately **not** added. No cross-domain consumer reads
them today, so adding projections would invent an API without a caller. They remain future work when
a real consumer exists.

### 1.2 Migrated consumers — 13 call sites in 11 modules

Every site below now uses `compass.student_academics.reads`. Existing error classes, codes, reason
strings, HTTP messages and result shapes were preserved. No new consumer tests were added; the
existing domain suites are the regression evidence.

| Module | Site | Read used and preserved behavior |
|---|---|---|
| `organization/services.py` | `resolve_default_counselor_for_student` (94) | No active filter. `NO_AFFILIATION` when no placement; `INACTIVE_ORGANIZATION` when `not college.is_usable`; responsibility lookup by `facts.college.id`. |
| `organization/services.py` | `validate_role_transition` (121) | Any current placement blocks a Student role change; exact message unchanged. |
| `organization/services.py` | `validate_account_catalog_reactivation` (406) | A retained placement beneath inactive ancestry blocks reactivation; exact message unchanged. |
| `good_moral/services.py` | `_current_placement` (530) | `require_active_college=True`; same `GoodMoralPlacementRequired` message; caller uses `facts.college.name`. |
| `counseling/context_services.py` | `get_context_overview` (177) | No active filter; inactive placement is displayed exactly as before. |
| `guidance_messages/services.py` | `open_office_thread` first-thread routing (216) | No active filter; same counselor/capability/scope conditions and conflict message; thread uses `routing_college_id=facts.college.id`. |
| `guidance_followups/workspace.py` | `eligible_assignees` (94) | `require_active_college=True`; candidate routing uses `facts.college.id` or `None`. |
| `referrals/faculty_placement.py` | `resolve_student_placement` (20) | `require_active_college=True`; returns `college_id=facts.college.id` and `revision=facts.revision`. Guard and docstring intent unchanged. |
| `appointments/access.py` | `_student_in_organizational_scope` (39) | Scope helper after the empty-scope check. |
| `call_slips/services.py` | `_student_in_scope` (248) | Scope helper after the Head and empty-scope checks. |
| `guidance_followups/policy.py` | `in_operational_scope` (42) | Scope helper after the Head and empty-scope checks. |
| `referrals/services.py` | `_student_in_scope` (230) | Scope helper after the Head and empty-scope checks. |
| `student_support/services.py` | `_require_scoped_student` (61) | Scope helper after the Head and empty-scope checks; the same 404 message is preserved. |

The Faculty Referral revision token is byte-identical:
`student_academics:{profile_id}:{updated_at.isoformat()}`.

### 1.3 Residual direct couplings — intentional

These sites keep direct model or reverse-relation access. Converting a one-student fact helper into
a bulk predicate would either introduce N+1 queries or invent a queryset abstraction the domain does
not need.

| Group | Sites | Reason left direct |
|---|---|---|
| Bulk queryset / reverse-relation filters | `operational_students.py`, `assessment_records/services.py`, `call_slips/services.py::_scope_queryset`, `guidance_followups/policy.py` list filters, `guidance_followups/recovery.py`, `guidance_messages/services.py` list filters, `appointments/access.py` bulk predicates, `inventory/services.py`, `reports/services.py`, `good_moral/services.py` bulk eligibility, `good_moral/api.py`, `referrals/services.py` bulk | These filter whole `User`/record querysets. A per-student helper would degrade them to N+1 or force a new query-builder API. |
| Composite Counseling predicates | `counseling/continuity_services.py`, `continuity_access.py`, `coverage_selection.py`, `handoff_services.py` | Placement is combined with grant, encounter, coverage and handoff conditions in the same query. Extracting only the placement predicate would obscure a security-sensitive composite. |
| Bulk Organization catalog impact | `organization/catalog_services.py` | Counts and impact checks operate over all placements of many Colleges at once. |
| Seeds and seed verification | `staging_seed/organization.py`, `staging_seed/verify.py` | Seeds deliberately create canonical rows and verify the reset baseline directly; routing them through provisioning reads would couple seed reset to runtime policy. |
| Student academic domain aggregate | `student_academics/services.py` | The domain's own aggregate reader already owns these queries and is the canonical implementation the read module mirrors. |

## 2. SAR-4 — writer extension

`be/compass/student_academics/services.py:160` extends `set_current_placement` with keyword-only:

- `expected_campus_id: UUID | None = None` — after locking the active College, raises
  `InvalidStudentAcademicInput("The College must belong to the selected Campus.")` when the College
  belongs to another Campus. Nothing is written or audited.
- `allow_inactive_student: bool = False` — `_lock_student(..., require_active=not allow_inactive_student)`.

Everything else is unchanged: `UNVERIFIED`, Program null, effective date null, the existing no-op
check, audit action `student_academics.placement.set` and metadata
`{"previous_college_id", "new_college_id"}`. The existing API call omits the new arguments, so its
behavior and the existing inactive-Student rejection are unchanged.

## 3. Single account creation

`be/compass/account_management/services.py:679` accepts `student_campus_id` and
`student_college_id`. Inside the existing transaction:

1. Lock the management mutex and actor.
2. `_assert_manager`, `_assert_recent_mfa`.
3. `validate_faculty_college` (unchanged).
4. `validate_initial_student_placement` (shared rules below).
5. `_assert_academic_placement_authorized(locked_actor, requested=placement_college is not None)`.
6. Duplicate checks and `User.objects.create_user` (unchanged).
7. `ACCOUNT_CREATED` audit and `write_faculty_affiliation` (unchanged).
8. If a placement was supplied, call the canonical writer in the same transaction with
   `expected_campus_id=student_campus_id` and `allow_inactive_student=not user.is_active`; a
   `StudentAcademicError` becomes `InvalidManagementInput`.

Consequences enforced by tests:

- A placement failure rolls back the User and the `ACCOUNT_CREATED` audit.
- A placement adds a second audit event, `student_academics.placement.set`.
- No placement creates no `StudentAcademicProfile` row.
- `is_active=False` plus placement is allowed; placement does not enable the account.
- Behavior without the new fields is unchanged.

### 3.1 Shared validation

`be/compass/account_management/academic_placement.py` exposes:

- `validate_initial_student_placement(*, role, campus_id, college_id) -> College | None`
  - both `None` → `None`
  - exactly one supplied → `"Select both Campus and College, or neither."`
  - non-Student with either supplied → `"Only Student accounts accept an initial academic placement."`
  - invalid UUIDs → `"Campus and College must be catalog UUIDs."`
  - missing/inactive Campus → `"Select an active Campus."`
  - missing/inactive College or inactive Campus → `"Select an active College beneath an active Campus."`
  - College not beneath Campus → `"The College must belong to the selected Campus."`
- `resolve_csv_student_placement(*, role, campus_code, college_code) -> CsvStudentPlacement | None`
  - strips both; both blank → `None`
  - exactly one blank → `"Provide both campus_code and college_code, or leave both blank."`
  - non-Student with either supplied → the Student-only message
  - normalizes with `normalize_code` (`strip().upper()`)
  - resolves against active Campus and active College beneath it; returns catalog-normalized codes
  - unknown Campus → `"campus_code does not resolve to an active Campus."`
  - unknown/mismatched College → `"college_code does not resolve to an active College beneath that Campus."`
  - never reads `program_code`

## 4. CSV provisioning

`be/compass/account_management/csv_import.py`:

- `OPTIONAL_HEADERS` adds `campus_code` and `college_code`; `program_code` stays unsupported.
- Parsed rows carry `student_campus_id`, `student_college_id`, `campus_code`, `college_code`.
- Preview rows carry `campus_code` and `college_code`.
- Invalid placement pairs become `invalid_row` issues with the exact validation message.
- Classification loads `student_academic_profile__current_college`. Because the query joins a
  nullable relation, commit classification uses `select_for_update(of=("self",))`.
- Placement authorization is checked in **both** dry-run and commit authorization blocks.
- Commit writes placement after the account audit; a writer failure raises `CsvImportConflict` with
  one row result and rolls back the whole batch.

### 4.1 Classification matrix

| Existing account | Row codes | Action |
|---|---|---|
| No match | none or both | `CREATE` |
| Match; active; same role, identity, Faculty affiliation; no codes | none | `SKIP` |
| Match; active; same role, identity, Faculty affiliation; placement matches | both | `SKIP` |
| Match; active; same role/identity/Faculty, but placement differs or is absent | both | `CONFLICT` — `"existing account has a different academic placement"` |
| Match but disabled, different role, different identity or Faculty affiliation | any | `CONFLICT` as before |

Omitted codes mean "placement not specified", so re-importing a legacy file after commit remains
idempotent. Existing accounts are never updated; changing an existing Student's placement requires
the Student Academic Records workspace.

## 5. API and schema

- `AccountCreateRequest` adds optional `student_campus_id` and `student_college_id`.
- `CsvImportRowResponse` adds optional `campus_code` and `college_code`, emitted by `_csv_report`.
- `_raise_management_error` maps `AcademicPlacementNotAuthorized` to HTTP 403
  `academic_placement_permission_denied` before the generic `ManagementNotAuthorized` branch.
- The `accountsFacultyCollegeChoices` endpoint keeps its path and operation ID; only its summary
  changed to "List active catalog Colleges for account provisioning".
- No account response exposes placement. The Student Academic Records workspace remains the place to
  inspect it.
- `contracts/openapi.json` was regenerated; the frontend client was regenerated with
  `pnpm api:generate`. Generated files were not hand-edited.

## 6. Frontend

- **Create account:** an optional **Initial academic placement** section appears only for a Student
  role when the session holds `organization.manage`. It reuses the College choices query, derives
  unique Campus options, filters College by Campus, clears College when Campus changes, enforces
  both-or-neither before review, and posts both IDs. The review dialog shows
  `"<Campus> · <College>"` or "Not assigned" and states that placement is unverified and does not
  confirm enrollment.
- **CSV import:** the template adds `campus_code,college_code`; copy explains the Student-only,
  both-or-neither, new-accounts-only behavior and that `program_code` is unsupported; the reference
  summary is renamed **College references for CSV** and shows `campus_code`, `college_code`, College
  name and `faculty_college_id`; the preview adds a **Placement** column (`"<campus_code> · <college_code>"`
  or "—").
- `account-action.tsx` maps `academic_placement_permission_denied` to a placement-specific message
  instead of the generic account failure.
- No account-detail page change.

## 7. Audit, transaction and authorization

| Operation | Capability | MFA | Audit |
|---|---|---|---|
| Single create, no placement | `accounts.manage` | recent | `account.created` |
| Single create with placement | `accounts.manage` + `organization.manage` | recent | account event + `student_academics.placement.set` |
| CSV, no placement rows | `accounts.manage` | recent | per-row account events + batch event |
| CSV, any placement row (dry-run or commit) | `accounts.manage` + `organization.manage` | recent | same, plus per-row placement events on commit |

No `student_academics.*` capability, role grant or designation grant was introduced.
`organization.manage` is a deliberate temporary reuse; D-SAR-05 remains open. Campus is a validation
input only and is never stored or audited.
