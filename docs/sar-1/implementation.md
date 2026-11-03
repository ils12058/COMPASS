# SAR-1 implementation

**Base:** `5a147bb1dd64d10837eeed905c6db68dfd2b716b`.
All statements below describe code in this branch. No consumer reads the profile.

## 1. App and model

**File:** `be/compass/student_academics/models.py`

`StudentAcademicProfile` (`models.py:18-68`) is the only model:

| Field | Definition | SAR-1 behavior |
|---|---|---|
| `id` | UUID PK, `uuid.uuid4` | Generated |
| `student` | OneToOne `AUTH_USER_MODEL`, `PROTECT`, `related_name="student_academic_profile"` | One profile per Student |
| `current_college` | FK `organization.College`, `PROTECT`, nullable | Mirrors the affiliation College, else null |
| `current_program` | FK `organization.Program`, `PROTECT`, nullable | Always null in SAR-1 |
| `placement_verification_status` | `UNVERIFIED` / `VERIFIED`, default `UNVERIFIED` | Always `UNVERIFIED` in SAR-1 |
| `placement_effective_at` | nullable datetime | Always null in SAR-1 |
| `updated_by` | FK `AUTH_USER_MODEL`, `SET_NULL`, `related_name="+"`, nullable | Acting user when known |
| `created_at` / `updated_at` | automatic timestamps | Standard |

`Meta` sets `default_permissions = ()`, `ordering = ("student_id",)` and a check constraint
`student_academics_verification_status_valid` limiting the status to the two declared values
(`models.py:55-65`).

The app is registered as `compass.student_academics` in `be/config/settings.py:78`. Applied
migration: `be/compass/student_academics/migrations/0001_initial.py`; it depends on
`organization.0004_facultyaffiliation` and the swappable User model, and creates schema only.

No capability, API, serializer or OpenAPI type references the model. There is no read path.

## 2. Activation gate

**File:** `be/config/settings.py:789`

```python
STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED = env_bool("STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED", False)
```

`be/.env.example:234` documents `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=false`. The gate is not set
true in any environment file, Compose file, CI workflow, seed or runtime default. Tests enable it
only through `override_settings`.

`sync_enabled()` in `be/compass/student_academics/services.py:20-21` reads the setting defensively
with a `False` default.

## 3. Dual-write behavior

**File:** `be/compass/student_academics/services.py:24-67`; call sites in
`be/compass/organization/services.py:285-302` and `:325`.

The write is inside the existing `catalog_dependent_write` + `transaction.atomic()` affiliation
operation, after the affiliation row is created/updated and before the affiliation audit event.

### Set or transfer

`sync_profile_from_affiliation(student, college, updated_by)`:

- Gate off: returns `None` immediately; no profile read or write.
- Gate on: `update_or_create` keyed by `student` with:
  - `current_college = college`
  - `current_program = None`
  - `placement_verification_status = UNVERIFIED`
  - `placement_effective_at = None`
  - `updated_by = actor` (`None` when the audit context has no user)

A transfer therefore resets any previously set Program, effective date or verification state. This
follows D-SAR-01/02/04 Option A and prevents a stale Program or verification label from surviving a
College change.

### Same-College no-op

`set_student_affiliation` returns early when the affiliation already points at the requested
College (`be/compass/organization/services.py:285-289`). The sync call runs before the return, so:

- a missing profile is created;
- an existing profile is refreshed to the same College and `UNVERIFIED`;
- no affiliation audit event is added, because this path never records one.

### Removal

`clear_profile_for_removed_affiliation(student_id, updated_by)`:

- Gate off: returns `False` immediately.
- Gate on: locks the profile row if present, then sets `current_college = None`,
  `current_program = None`, status `UNVERIFIED`, `placement_effective_at = None`, `updated_by =
  actor`, and saves only those fields plus `updated_at`. The row is preserved (D-SAR-07 Option A).
- If no profile exists, it returns `False` without creating one.

### Failure behavior

No exception is swallowed. A profile write failure propagates out of the affiliation service, so
the ambient `transaction.atomic()` rolls back both the affiliation write and the profile write. The
focused test `test_profile_write_failure_rolls_back_affiliation` monkeypatches
`update_or_create` to raise and asserts that neither row remains.

No new audit action is emitted by the profile layer. The existing
`organization.student_affiliation.*` event remains the only affiliation audit trail.

## 4. Backfill

**Command:** `python manage.py backfill_student_academic_profiles [--dry-run] [--batch-size N]`
(`be/compass/student_academics/management/commands/backfill_student_academic_profiles.py`).
`--batch-size` defaults to 200 and must be between 1 and 1000.

**Service:** `backfill_student_academic_profiles(dry_run, batch_size)` in
`services.py:86-153`.

Rules:

- Source is `StudentAffiliation`; no other model is read.
- Eligible rows are affiliations whose Student has role code `STUDENT`. **Inactive Student
  accounts are included** (D-SAR-03 Option A). Non-Student-role rows are excluded and counted.
- Existing profiles are never updated or overwritten. The dry run and real run both report
  `missing_profiles`; the real run creates only those.
- Every created row is `UNVERIFIED`, College-only, with null Program and null effective date.
- `updated_by` is the affiliation's `assigned_by` when present, otherwise null.
- Affiliations pointing at inactive College/Campus rows are copied as recorded and counted as a
  warning; no catalog state is changed.
- Real execution paginates by `student_id` (`student_id__gt`), checks existing profile IDs per
  batch, and inserts only missing rows with `bulk_create(..., ignore_conflicts=True)` inside a
  short `transaction.atomic()` per batch. Re-running is idempotent.
- Output is one aggregate line with tokens: `affiliations_total`, `eligible`, `missing_profiles`,
  `existing_profiles`, `inactive_student_accounts`, `non_student_role_rows`,
  `inactive_college_rows`, `created`, `dry_run`. No names, emails or Student IDs are printed.
- The backfill does not consult the activation gate; it is an operator action, not a runtime path.

## 5. Reconciliation

**Command:** `python manage.py reconcile_student_academic_profiles [--fail-on-mismatch]`
(`.../reconcile_student_academic_profiles.py`).

**Service:** `reconcile_student_academic_profiles()` in `services.py:179-205`.

Blocking mismatch counts (summed into `blocking_total`):

| Token | Definition |
|---|---|
| `affiliations_without_profile` | Student-role affiliation with no profile |
| `profile_college_drift` | Profile with an affiliation whose College is null or differs from the affiliation College |
| `profile_program_present` | `current_program` is not null |
| `profile_effective_at_present` | `placement_effective_at` is not null |
| `profile_verified` | Status is `VERIFIED` |
| `profiles_without_affiliation` | Profile whose Student has no affiliation |

Informational counts, reported separately and excluded from `blocking_total`:

- `non_student_profiles` — profile whose Student role is not `STUDENT`.
- `inactive_student_profiles` — Student-role profile with an inactive account.

`--fail-on-mismatch` raises `CommandError` when `blocking_total > 0`; otherwise the command warns
not to enable the gate. Output is aggregate-only.

## 6. CI mapping

`.github/scripts/backend_ci.py`:

- New bundle `student-academics` mapping `test_student_academic_profiles.py`
  (`.github/scripts/backend_ci.py:134-137`).
- New domain entry `student_academics` with bundles `student-academics`, `organization` and
  `identity-access` (`.github/scripts/backend_ci.py:763-767`).

`backend_ci.py verify` confirms every test file is bundled exactly once. No gate is enabled by CI.
