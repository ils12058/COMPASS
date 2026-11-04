# SAR-3 + SAR-4 validation

**Status:** implemented, merged into `integration/ux15-modernization` and pushed to `origin` without
a PR; not deployed.
**Date:** 2026-11-04.
**Branch:** `integration/ux15-modernization` at base `ec083fda`.

All commands below were run locally against the working tree. Results are copied from the actual
output; failures and fixes are recorded rather than omitted.

## 1. Backend — `be/`

| Command | Result |
|---|---|
| `uv run ruff format --check .` | **First run failed:** 3 files would be reformatted — `compass/appointments/access.py`, `compass/guidance_followups/workspace.py`, `compass/organization/services.py`. Fixed by running `uv run ruff format` on those files. Re-run: `888 files already formatted`. |
| `uv run ruff check .` | `All checks passed!` |
| `uv run python manage.py check --settings=tests.settings` | `System check identified no issues (0 silenced).` |
| `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` | `No changes detected` |
| `uv run python manage.py export_openapi --output ../contracts/openapi.json --settings=tests.settings` | `Exported OpenAPI contract: ../contracts/openapi.json` |
| `uv run pytest -q tests/test_student_academic_reads.py tests/test_student_academic_records.py tests/test_account_management.py tests/test_account_csv_import.py tests/test_openapi_contract.py` | `140 passed in 129.08s (0:02:09)` |
| `uv run pytest -q tests/test_organization.py tests/test_appointments.py tests/test_call_slips.py tests/test_guidance_followups.py tests/test_referrals.py tests/test_student_support.py tests/test_good_moral.py tests/test_counseling_context.py tests/test_guidance_messages.py tests/test_faculty_referrals.py` | `437 passed, 1 warning in 345.53s (0:05:45)`. The warning is a non-fatal teardown notice: another session held the test database (`database "test_compass_test" is being accessed by other users`). |

## 2. Backend bundle verification — repository root

| Command | Result |
|---|---|
| `python3 .github/scripts/backend_ci.py verify` | `OK: 212 test files are bundled and each runs exactly once across 6 full-regression shards.` |

## 3. Frontend — `fe/`

| Command | Result |
|---|---|
| `pnpm api:generate` | Orval `v8.29.0` generated the client from the regenerated contract; `src/lib/api/generated` stayed clean in `git status`. |
| `pnpm lint` | `eslint .` completed with no findings. |
| `pnpm typecheck` | `tsc --noEmit` completed with no findings. |
| `pnpm test` | `tests 1033`, `pass 1033`, `fail 0`, `cancelled 0`, `skipped 0`, duration `45.3s`. |
| `pnpm build` | Next.js `16.3.4` (Turbopack) compiled successfully and generated 99 static pages. |
| `node tests/student-placement-provisioning.browser.mjs` (production `pnpm start --port 3107`) | `4/4 browser checks passed`. |
| `COMPASS_UI_BROWSER=webkit node tests/student-placement-provisioning.browser.mjs` (production build) | `4/4 browser checks passed`. |
| `node tests/faculty-foundation.browser.mjs` (production build) | `11/11 browser checks passed`. |

Browser-suite history:

- The suites were first exercised against `pnpm dev --port 3107` and then re-run against the
  production `pnpm build` + `pnpm start --port 3107` output. The counts above are the production
  runs.
- The first chromium run of the new suite failed one check with a Playwright strict-mode violation:
  `getByRole('cell', { name: 'MAIN', exact: true })` matched two reference rows because two Colleges
  share the MAIN campus. Fixed by asserting both cells explicitly (`count() === 2` and `.first()`);
  the rerun passed on both engines.
- The renamed reference summary required the existing `faculty-foundation.browser.mjs` assertion to
  change from "Faculty College references for CSV" to "College references for CSV"; all existing
  Faculty assertions still pass.

## 4. Zero-reference checks

Commands run from the repository root:

- **No direct `StudentAcademicProfile` writes outside `student_academics`.** The write-pattern
  search returned only `student_academics/services.py:144` and `:196` (the canonical service) plus
  an unrelated `StudentSupportProfile.save(...)` in `inventory/services.py`. No other module calls
  `create`, `update`, `delete`, `bulk_*`, `get_or_create`, `update_or_create` or `save` on
  `StudentAcademicProfile`.
- **No live `StudentAffiliation` reference.** `rg -n "StudentAffiliation" be/compass` matches only
  the historical migrations `organization/migrations/0001_canonical_baseline.py` and
  `0005_delete_studentaffiliation.py`. No live module references it. Legacy ADR text under
  `be/docs/decisions/` still mentions the retired model and was not rewritten.
- **`program_code` is never read.** `rg -n "program_code" be/compass/account_management
  fe/src/features/accounts` returns only
  `fe/src/features/accounts/import/import-accounts.tsx` copy saying `program_code` is not supported.
  There is no backend reader, column or test fixture that accepts it; the CSV header list rejects it.
- **Whitespace:** `git diff --check` printed nothing (clean).

## 5. Explicitly not run

- The **full backend pytest suite** was not run. Only the two §9 groups plus the bundle verifier
  were executed; other domains and the complete six-shard regression were not.
- The **full browser regression inventory** (`pnpm test:ui`) was not run. Only
  `student-placement-provisioning.browser.mjs` (both engines) and `faculty-foundation.browser.mjs`
  were run.
- No staging or production environment was contacted; no deployment, migration, seed reset or
  external system (email, SMS, Daily/E-Counseling provider, push, webhook) was exercised.
- Repository state: the changes were merged into `integration/ux15-modernization` and pushed to
  `origin` without a PR. No deployment or shared-environment contact occurred.
