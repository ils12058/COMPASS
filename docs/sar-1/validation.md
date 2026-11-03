# SAR-1 validation

**Branch:** `codex/sar-1-academic-profile`
**Base:** `5a147bb1dd64d10837eeed905c6db68dfd2b716b`
**Date:** 2026-11-03
**Environment:** local macOS workspace, Django 6.1.1, `tests.settings`, local PostgreSQL test
database. No staging or production system was contacted.

## 1. Method

Validation combined:

- static checks (format, lint, migration drift, Django system check, OpenAPI drift);
- focused and regression pytest runs against the local test database;
- CI mapping checks that prove every test file is bundled exactly once;
- Git status/diff inspection to confirm the change set.

The gate remained `false` in every setting and environment file. Gate-on tests use
`override_settings` only.

## 2. Exact commands and results

| # | Command | Result |
|---|---|---|
| 1 | `cd be && uv run pytest tests/test_student_academic_profiles.py -q` | `11 passed in 15.19s` |
| 2 | `cd be && uv run ruff format --check .` | `887 files already formatted` |
| 3 | `cd be && uv run ruff check .` | `All checks passed!` |
| 4 | `cd be && uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` | `No changes detected` |
| 5 | `cd be && uv run python manage.py check --settings=tests.settings` | `System check identified no issues (0 silenced).` |
| 6 | `cd be && uv run python manage.py export_openapi --check --settings=tests.settings` | `OpenAPI contract is current: .../contracts/openapi.json` |
| 7 | `cd be && uv run python manage.py migrate --noinput --settings=tests.settings` | `student_academics.0001_initial... OK` on the first local run; a later run reports `No migrations to apply` |
| 8 | `cd be && uv run pytest tests/test_organization.py tests/test_account_management.py -q` | `43 passed in 52.00s` |
| 9 | `cd be && uv run pytest tests/test_catalog_concurrency.py tests/test_continuity_release_concurrency.py tests/test_faculty_referral_concurrency.py tests/test_referral_administration_concurrency.py -q` | `86 passed in 58.36s` |
| 10 | `python3 -m unittest discover -s .github/scripts` (repo root) | `Ran 60 tests ... OK` |
| 11 | `python3 .github/scripts/backend_ci.py verify` (repo root) | `OK: 211 test files bundled and each runs exactly once across 6 full-regression shards.` |
| 12 | `git diff --check` | Clean (no whitespace errors) |

The migration in command 7 was applied only to the local `tests.settings` database
(`compass_test`). No migration was executed against staging or production.

## 3. Focused test coverage

File: `be/tests/test_student_academic_profiles.py` — 11 tests.

| Test | Behavior proven |
|---|---|
| `test_profile_model_defaults_and_constraints` | UUID PK; nullable College/Program/effective/updater; default `UNVERIFIED`; `default_permissions == ()`; invalid status rejected by the check constraint; duplicate Student rejected by the one-to-one constraint |
| `test_gate_off_affiliation_writes_leave_profile_untouched` | Gate off: set, transfer and removal create no profile |
| `test_gate_on_set_creates_shadow_profile_with_actor` | Gate on: College copied, Program null, `UNVERIFIED`, effective null, actor recorded |
| `test_gate_on_transfer_updates_college_and_resets_verification` | Transfer overwrites College and resets Program/effective/verification |
| `test_gate_on_same_college_noop_creates_missing_profile_without_new_audit` | Same-College replay creates a missing profile, resets verification, and adds no affiliation audit event |
| `test_gate_on_removal_keeps_profile_and_clears_college` | Removal preserves the row, nulls College/Program/effective, keeps `UNVERIFIED`, records actor; affiliation is gone |
| `test_profile_write_failure_rolls_back_affiliation` | Profile exception propagates and the affiliation transaction rolls back fully |
| `test_backfill_is_dry_run_capable_batched_idempotent_and_excludes_non_students` | Dry-run counts; inactive Student included; non-Student excluded and reported; inactive College copied; existing profile never overwritten; real run creates only missing rows; rerun creates zero; invalid batch size rejected |
| `test_reconciliation_detects_every_blocking_mismatch` | All six blocking categories detected; `blocking_total == 6`; `--fail-on-mismatch` exits nonzero |
| `test_reconciliation_reports_non_student_and_inactive_profiles_separately` | Non-Student and inactive Student profiles reported separately with `blocking_total=0` |
| `test_student_without_affiliation_gets_no_profile` | Gate-on write path does not invent a profile for an unaffiliated Student |

## 4. CI mapping verification

`backend_ci.py verify` proves:

- `test_student_academic_profiles.py` is assigned to the `student-academics` bundle exactly once;
- the `student_academics` domain maps to `student-academics`, `organization` and `identity-access`;
- 211 test files are bundled and each runs in exactly one full-regression shard.

## 5. What was not validated

- **Population data quality.** No population counts were produced. `affiliations_total`,
  `non_student_role_rows`, `inactive_college_rows` and every reconciliation count remain Unknown
  until an approved operator runs the dry run against the target database.
- **Staging rehearsal.** No backfill, activation or rollback rehearsal was performed outside the
  local test database. Backup/restore evidence is still required.
- **Gate runtime configuration.** No deployment was performed, so no running process was inspected
  for the effective gate value. Activation is not claimed.
- **Full backend suite.** Only the focused suite and the listed affiliation/accounting/concurrency
  regressions were run locally. The full suite is delegated to CI.
- **Load, locking and duration.** Batch sizes were exercised for correctness, not performance. Lock
  behavior under production volume is unmeasured.
- **Consumer behavior.** No consumer reads the profile, so no consumer test was added or changed.
- **External systems.** No SIS/Registrar source, export or downstream office was contacted.

## 6. Definition-of-done status

| Requirement | Status |
|---|---|
| App, model, migration, services, commands added | Verified by source and migration check |
| Gate default false; not enabled anywhere | Verified by settings, `.env.example`, grep and tests |
| Dual-write transactional and failure-propagating | Verified by focused tests 3–7 |
| Backfill idempotent, batched, missing-only, non-Student excluded | Verified by focused test 8 |
| Reconciliation detects all specified blockers | Verified by focused tests 9–10 |
| No API/OpenAPI/frontend/capability/seed/consumer changes | Verified by `git status` and OpenAPI check |
| No data rows in migration | Verified by the migration file |
| Docs and CI mapping | Verified in this package and `backend_ci.py verify` |
| Gate activated / merge / deploy / staging migration | **Not done — explicitly out of scope** |
