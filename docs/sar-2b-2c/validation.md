# SAR-2B + SAR-2C validation

**Branch:** `integration/ux15-modernization`
**Base:** `b1ccd59b8d8d45d5b80789eb908eac1a0586c0e1`
**Environment:** macOS arm64; Python/Django via `uv`; PostgreSQL test database; Node.js 24; pnpm;
Playwright Chromium and WebKit.
**Date:** 2026-11-04.

No command contacted staging, production, a real mailbox, an SMS provider, a payment provider or any
other external system. Backend tests use the local test database; browser suites intercept every API
call with synthetic fixtures and run against a local Next server.

## 1. Backend

Commands were run from `be/` unless stated otherwise.

| Command | Result |
|---|---|
| `uv run ruff format --check .` | PASS — 885 files already formatted |
| `uv run ruff check .` | PASS — all checks passed |
| `uv run python manage.py check --settings=tests.settings` | PASS — no issues |
| `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` | PASS — no changes detected |
| `uv run python manage.py export_openapi --output ../contracts/openapi.json --settings=tests.settings` | PASS — exported; the contract diff is +538 lines and is stable on rerun |
| `uv run pytest -q tests/test_student_academic_records.py` | PASS — 32 passed |
| `python3 .github/scripts/backend_ci.py verify` (from the repository root) | PASS — 211 test files bundled, each runs exactly once across 6 shards |
| `uv run pytest -q tests/test_canonical_baseline.py tests/test_handoff_migrations.py tests/test_staging_deployment.py tests/test_staging_seed.py` | PASS — 102 passed |
| Lifecycle-reading files: `uv run pytest -q $(rg -l "student_lifecycle_status" tests \| grep -v -e test_student_academic_records.py -e test_staging_seed.py)` | PASS after one fix — 1526 passed, 1 failed, then the failed file rerun as 41 passed |

The single failure was `tests/test_openapi_contract.py::test_all_public_operations_have_stable_unique_ids_and_approved_tags`:
the test’s fixed `EXPECTED_OPERATION_IDS` inventory did not yet include the three new operations
(446 generated IDs versus 443 expected). The three IDs were added to the inventory; the entire file
then passed (41 passed) and `ruff check` / `ruff format --check` stayed clean. No production code
changed.

The lifecycle-reading list covers 41 test files. Two (`test_student_academic_records.py`,
`test_staging_seed.py`) are reported above; the remaining 39 are the suite in the last row. No other
file required a change.

### 1.1 Full-suite gap

The complete backend suite was **not** re-run on the final tree. This is explicit: the evidence is
the focused suite, the four migration/seed suites and every file that reads
`student_lifecycle_status`, plus `backend_ci.py verify` for the CI mapping. This result must not be
described as a full-suite or CI-green validation.

## 2. Frontend

Commands were run from `fe/`.

| Command | Result |
|---|---|
| `pnpm api:generate` | PASS — Orval regenerated the client from the regenerated contract |
| `pnpm lint` | PASS — no output |
| `pnpm typecheck` | PASS — no output |
| `pnpm test` | PASS — 1033 tests, 0 failures |
| `pnpm build` | PASS — compiled; the route table contains `/portal/organization/student-academics/[studentId]` |
| `node tests/student-academic-record.browser.mjs` | PASS — 4/4 checks (Chromium) |
| `COMPASS_UI_BROWSER=webkit node tests/student-academic-record.browser.mjs` | PASS — 4/4 checks (WebKit) |
| `node tests/organization-catalog.browser.mjs` | PASS — 60/60 checks (Chromium) |

The two browser runs were executed headless against a local `pnpm exec next start -p 3107` server
after `pnpm build`. `fe/tests/student-academic-record.browser.mjs` is auto-discovered by
`tests/run-browser-regressions.mjs` (any `tests/**/*.browser.mjs`). The new suite covers: directory
Student link → aggregate record; period recording with the exact request body and refetch; the
graduation confirmation copy, completed outcome and post-refetch cleared placement/lifecycle; and a
missing `academic_years.view` authority disabling only the period form while facts stay visible.

The updated Organization catalog suite verifies the **Student Academic Records** navigation and
command-palette label; the results panel remains “Student placements”.

## 3. Zero-reference evidence

Commands were run from the repository root.

| Check | Command | Result |
|---|---|---|
| No direct period/graduation writes outside the service | `rg -n "StudentAcademicPeriodRecord.objects.create\|StudentGraduationRecord.objects.create\|StudentAcademicPeriodRecord.objects.update_or_create\|StudentGraduationRecord.objects.update_or_create" be/compass --glob '!**/migrations/**' --glob '!**/services.py'` | no matches |
| Retired affiliation model removed from runtime and tests | `rg -n "StudentAffiliation\|organization_student_affiliation" be/compass be/tests --glob '!**/migrations/**'` | no matches |
| New workspace contains no affiliation copy | `rg -in "affiliation" fe/src/features/student-academics "fe/src/app/(portal)/portal/organization/student-academics"` | no matches |
| No whitespace errors | `git diff --check` | clean |
| Contract contains the three new operations | `rg -o '"studentAcademicsGetStudentRecord"\|"studentAcademicsRecordPeriod"\|"studentAcademicsRecordGraduation"' contracts/openapi.json` | one match each |
| Contract contains no affiliation operations | `rg -n "StudentAffiliation\|studentAffiliation" contracts/openapi.json` | no matches |

`StudentAffiliation` remains only in the historical migrations
`be/compass/organization/migrations/0001_canonical_baseline.py` and
`0005_delete_studentaffiliation.py`.

## 4. Deviations

1. **DELETE routes return 405, not 404.** The task text asked for a 404 when deleting a period or
   graduation. Neither route exists, and Django Ninja answers a DELETE on those PUT-only paths with
   **405 Method Not Allowed**. The HTTP test `test_no_delete_routes_exist_for_periods_or_graduation`
   asserts the actual 405 behavior; adding a fake 404 handler would misrepresent the router.
2. **`backend_ci.py` location.** The task’s command block runs it from `be/`, but the script lives at
   the repository root `.github/scripts/backend_ci.py`; it was run from the repository root as in
   the SAR-2A validation.
3. **Seed placement in the sequence.** The academic-history unit is a new module called from
   `seed.py` after “Background stories”, not inside `organization.py`. Lifecycle alignment for
   action-ready and background Students finishes in the stories units; running earlier would move
   Graduated Students before their historical Inventory rows could be created. The final lifecycle
   is therefore not overwritten.
4. **Test inventory update.** `be/tests/test_openapi_contract.py` now lists the three new operation
   IDs. This is the expected consequence of adding operations, not a relaxation: the test still
   asserts the complete set and rejects duplicates/unknown tags.
5. **WebKit scope.** WebKit was run for the new suite only; the existing Organization catalog suite
   was run in Chromium. The full browser-regression matrix across every suite was not run.

## 5. Not validated

- The full backend suite was not re-run on the final tree (see §1.1); CI was not observed.
- No manual browser session; only the synthetic Playwright suites above.
- No deployment, staging seed run or production/staging contact.
- No data migration or backfill rehearsal, because neither exists in this slice.
- The temporary `organization.manage` authorization boundary and D-SAR-09/10/11 defaults were not
  reviewed by UCN, GCO, Registrar, DPO, Records or IT. D-SAR-05 and D-SAR-12..20 remain open.
- The four-commit split was merged into `integration/ux15-modernization` and pushed to `origin`;
  no PR, deployment, staging seed run or production/staging contact followed.
