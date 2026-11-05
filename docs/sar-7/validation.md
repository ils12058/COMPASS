# SAR-7 validation — real commands and results

All commands were run on 2026-11-05 on the local working tree at base `8931290e` plus the
uncommitted SAR-7 changes. No staging or production system was contacted; only local test databases
and local servers were used.

## 1. Focused backend regression

From `be/`:

```bash
uv run pytest \
  tests/test_student_academic_roster_import.py \
  tests/test_student_academic_records.py \
  tests/test_student_academic_reads.py \
  tests/test_capability_dependencies.py \
  tests/test_accounts.py \
  tests/test_account_management.py \
  tests/test_account_csv_import.py \
  tests/test_openapi_contract.py \
  -q
```

The first run failed one frozen expectation:

```text
FAILED tests/test_accounts.py::test_effective_capabilities_combine_role_designation_and_overrides
1 failed, 203 passed in 169.43s (0:02:49)
```

`HEAD_GUIDANCE_COUNSELOR`'s expected effective set did not yet contain
`student_academics.import`. The expectation was updated to match the deliberate designation grant;
no production gate was relaxed. The single test then passed (`1 passed in 10.28s`) and the full
command was rerun:

```text
204 passed in 181.21s (0:03:01)
```

## 2. Static and contract checks

| # | Command (directory) | Result |
|---|---|---|
| 1 | `python3 .github/scripts/backend_ci.py verify` (repository root) | `OK: 213 test files are bundled and each runs exactly once across 6 full-regression shards.` |
| 2 | `uv lock --check` (`be/`) | `Resolved 72 packages in 27ms` |
| 3 | `uv run ruff format --check .` (`be/`) | `890 files already formatted` |
| 4 | `uv run ruff check .` (`be/`) | `All checks passed!` |
| 5 | `uv run python -m compileall -q compass tests` (`be/`) | no output (exit 0) |
| 6 | `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` (`be/`) | `No changes detected` |
| 7 | `uv run python manage.py check --settings=tests.settings` (`be/`) | `System check identified no issues (0 silenced).` |
| 8 | `uv run python manage.py export_openapi --check --settings=tests.settings` (`be/`) | `OpenAPI contract is current: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |

The bundle count rose from 212 to 213 because SAR-7 adds exactly one backend test file,
`be/tests/test_student_academic_roster_import.py`, to the `student-academics` bundle. The first
format check on the files edited by this slice reported formatting differences; `ruff format` was
applied and every check above passed on the final run. No migration is added by this slice.

## 3. Full backend suite, six shards

The plan was generated from the repository root:

```bash
python3 .github/scripts/backend_ci.py plan
```

It reports six shards over 213 test files:

```text
Shard 1/6: 35 items, about 22.3 min
Shard 2/6: 37 items, about 22.3 min
Shard 3/6: 36 items, about 22.3 min
Shard 4/6: 37 items, about 22.3 min
Shard 5/6: 36 items, about 22.3 min
Shard 6/6: 36 items, about 22.3 min
```

Each shard was run sequentially from `be/` with (`--index` is zero-based):

```bash
uv run python ../.github/scripts/backend_ci.py run-shard --index N --total 6
```

| Shard | Result |
|---|---|
| 1/6 (index 0) | `1014 passed, 2 skipped in 1000.59s (0:16:40)` |
| 2/6 (index 1) | `869 passed, 1 skipped, 5 warnings in 834.66s (0:13:54)` |
| 3/6 (index 2) | `1055 passed, 1 warning in 1134.97s (0:18:54)` |
| 4/6 (index 3) | `1027 passed, 1 warning in 1634.91s (0:27:14)` |
| 5/6 (index 4) | `1593 passed, 1 skipped in 1449.16s (0:24:09)` |
| 6/6 (index 5) | `925 passed, 8 warnings in 949.14s (0:15:49)` |

Totals for the final runs: **6,483 passed, 0 failed, 4 skipped**, aggregate pytest time
**7,003.43s (1:56:43)**. The suite count grew from SAR-6's 6,455 to 6,483 (+28 tests), matching the
28 tests in the new roster-import test file. The four skips are pre-existing opt-in skips: two in
`tests/test_good_moral_authenticated_integration.py:449` (loopback Next build/live-server proxy),
one in `tests/test_good_moral_recovery_rehearsal.py:44` (disposable PostgreSQL restore opt-in), and
one in `tests/test_fixed_date_slots.py:917` (loopback Next build/live-server proxy). No new skip was
added by this slice.

## 4. Frontend unit, lint, type, build

From `fe/`:

| Command | Result |
|---|---|
| `pnpm api:generate` | Orval v8.29.0; `🎉 compass - Your OpenAPI spec has been converted into ready to use orval!` |
| `pnpm lint` | `$ eslint .` completed with no findings (exit 0) |
| `pnpm typecheck` | `$ tsc --noEmit` completed with no findings (exit 0) |
| `pnpm test` | `tests 1042`, `pass 1042`, `fail 0`, `cancelled 0`, `skipped 0`, `todo 0`, duration `71872.355375ms` |
| `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 pnpm build` | Next.js 16.3.4 (Turbopack) production build completed with exit 0 |

The production build's app-paths manifest includes
`/(portal)/portal/organization/student-academics/import/page`, so the new route is part of the build
output. `next build` rewrote `fe/next-env.d.ts` from the committed `.next/dev/types/...` references
to `.next/types/...`; the committed content was restored immediately and the file is absent from
`git status`.

The first `pnpm test` run during implementation failed one guard in `fe/tests/step-up.test.mjs`
because the new roster action legitimately uses step-up. The action's directory was added to the
existing allowlist with a comment; the rerun passed 1,042/1,042 (see §7.1).

## 5. Browser inventory, both engines

Run from `fe/` against the local Next server on `http://localhost:3107` and the local SSR fixture
fallback on port 8000, with every API request served by synthetic fixtures in `fe/tests/support/`.
No production, staging or other shared system was contacted.

The new suite was run first on each engine. The runner expects the suite name relative to `tests/`
and its documented flags (`pnpm test:ui --suite <name> --browser <engine>`); the slice's
`pnpm test:ui -- --suite tests/...` form is not accepted by this runner.

| Engine | New suite result |
|---|---|
| chromium | `6/6 browser checks passed` |
| webkit | `6/6 browser checks passed` |

The first chromium run passed 5/6: check 03 hit a Playwright strict-mode violation because
`getByRole("cell", { name: "MAIN", exact: true })` resolved to two reference-college rows. The
locator was narrowed with `.first()`; both engines then passed 6/6. This was a test-locator defect,
not a product regression.

Full inventory:

```bash
COMPASS_UI_BASE_URL=http://localhost:3107 COMPASS_UI_ARTIFACTS=/tmp/sar7-browser-final \
  pnpm test:ui
```

`tests/run-browser-regressions.mjs` runs every `*.browser.mjs` suite on `chromium`, then all of
them again on `webkit`, in one invocation. There are 86 suites per engine.

| Engine | Suites | Checks |
|---|---|---|
| chromium | `84/86 suites passed.` | 1,639/1,650 |
| webkit | `84/86 suites passed.` | 1,638/1,649 |

Across both engines: **172 suite runs, 168 passed, 3,277/3,299 browser checks passed**. The runner
exited 1 only because of the two illustration suites below; both fail identically on both engines
with the image-optimizer hang already diagnosed in `docs/sar-5/validation.md` §5.1, and neither
touches an academic route. The new roster suite passed 6/6 within the full inventory on both
engines.

Mandated suites:

| Suite | chromium | webkit |
|---|---|---|
| `student-academic-roster-import.browser.mjs` | 6/6 | 6/6 |
| `academic-record-self-view.browser.mjs` | 4/4 | 4/4 |
| `student-academic-record.browser.mjs` | 5/5 | 5/5 |
| `student-placement-provisioning.browser.mjs` | 4/4 | 4/4 |
| `ux-hardening.browser.mjs` | 60/60 | 60/60 |

Failing suites, verbatim runner output:

| Engine | Suite | Checks | Failing checks | Message |
|---|---|---|---|---|
| chromium | `public-illustrations.browser.mjs` | 11/13 | `landing-desktop`, `landing-tablet` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| chromium | `simplify-2c-illustrations.browser.mjs` | 28/37 | `student-320/390/1024/1440`, `gss-320/390/1024/1440`, `home-delayed-artwork` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| webkit | `public-illustrations.browser.mjs` | 11/13 | `landing-desktop`, `landing-tablet` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| webkit | `simplify-2c-illustrations.browser.mjs` | 28/37 | same checks as chromium | `page.waitForFunction: Timeout 12000ms exceeded.` |

These are the same two pre-existing illustration-suite failures recorded in
`docs/sar-6/validation.md` §5; neither is a SAR-7 change or an academic route.

## 6. Seed sanity

A disposable local database, `compass_sar7_validation`, was created for the seed chain. Nothing
shared was touched and `issue-credentials` was not run. Environment overrides:
`POSTGRES_DB=compass_sar7_validation`, `STAGING_SEED_ENABLED=true`,
`DJANGO_SETTINGS_MODULE=tests.settings` (local loopback PostgreSQL/Redis and ephemeral test-only
encryption keys).

```bash
cd be
export POSTGRES_DB=compass_sar7_validation STAGING_SEED_ENABLED=true \
  DJANGO_SETTINGS_MODULE=tests.settings
uv run python manage.py migrate --noinput
uv run python manage.py sync_identity_policy
uv run python manage.py sync_canonical_services
uv run python manage.py sync_institutional_forms
uv run python manage.py initialize_organization_catalog --seed
uv run python manage.py seed_staging_dataset seed
uv run python manage.py seed_staging_dataset verify
```

Every stage exited 0. The policy sync reported:

```text
Identity policy synchronization complete. Definitions: roles created=6 updated=0;
designations created=2 updated=0; capabilities created=95 updated=0.
Baseline grants: role grants created=105; designation grants created=23.
```

This matches the SAR-7 provisional totals: **95 capability definitions, 105 role grants, 23
designation grants**. Seed verification passed:

```text
Verification PASSED.
Schema readiness 5 passed, 0 failed, 0 warnings
Canonical configuration 21 passed, 0 failed, 0 warnings
Account readiness 1112 passed, 0 failed, 0 warnings
Organization routing 12 passed, 0 failed, 0 warnings
Scenario initial states 122 passed, 0 failed, 0 warnings
Workflow integrity 40 passed, 0 failed, 0 warnings
Privacy and security 149 passed, 0 failed, 0 warnings
External side effects 5 passed, 0 failed, 0 warnings
```

That is **1,466 passed, 0 failed, 0 warnings**. The database was dropped after the run and its
absence was confirmed. No seed file was changed by this slice.

## 7. Failures, discrepancies, environment notes and not-run list

### 7.1 First-run failures and fixes

1. **Focused pytest, 1 failed / 203 passed.** The frozen
   `HEAD_GUIDANCE_COUNSELOR` effective-capability expectation lacked
   `student_academics.import`. The expectation was updated for the deliberate designation grant;
   the focused rerun passed 204/204.
2. **`pnpm test`, 1 failed / 1,042.** The `step-up.test.mjs` guard flagged the new
   `student-academics/roster-import/roster-import-action.tsx` as an unlisted step-up consumer. The
   directory was added to the existing allowlist with an explanatory comment; the rerun passed
   1,042/1,042.
3. **New browser suite, 5/6 on chromium.** The strict-mode locator described in §5 was narrowed
   with `.first()`; both engines then passed 6/6.
4. **An earlier frontend unit run, 1 failed / 37.** The destination test initially
   asserted that an account with `organization.structure.view` and `student_academics.import` but
   without `student_academics.view` would not see the command destination. The destination is
   gated by the import capability itself, so it did appear; the test expectation was corrected to
   match the implemented gate. No production gate was changed.
5. **Runner argument form.** `pnpm test:ui -- --suite tests/...` fails with
   `ERR_PARSE_ARGS_UNEXPECTED_POSITIONAL`; passing `tests/...` as the suite value fails with
   `Unknown suite`. The documented basename form was used for both engines.

### 7.2 Discrepancies

1. **Browser runner invocation differs from the slice text.** The slice shows
   `pnpm test:ui -- --suite tests/student-academic-roster-import.browser.mjs --browser chromium`.
   This repository's runner takes `--suite` without the `--` separator and expects the suite name
   relative to `tests/`, so the commands actually run were
   `pnpm test:ui --suite student-academic-roster-import.browser.mjs --browser chromium` and the
   webkit equivalent. Both engines were run.
2. **The command destination is gated by `.import` alone.** The page gate and the command
   destination both use `canImportStudentAcademics`, which checks only
   `student_academics.import`; the declared `student_academics.view` dependency is enforced by the
   capability policy rather than by a second UI predicate. This matches the provisional default
   that `.import` depends on `.view` only.
3. **The slice's seed command form was not used.** As the slice anticipates, `manage.py ... verify
   --settings=tests.settings` does not parse for the seed subcommand; the chain above used
   `DJANGO_SETTINGS_MODULE=tests.settings` on the disposable database instead.

### 7.3 Environment notes

1. `next build` rewrote `fe/next-env.d.ts`; the committed content was restored and the file is not
   part of the SAR-7 diff.
2. The local Next server on port 3107 and the SSR fallback on 127.0.0.1:8000 existed only for the
   browser inventory. They were stopped after the run; both ports are closed.
3. Backend validation used `be/tests/settings.py` via pytest and `DJANGO_SETTINGS_MODULE` (local
   loopback PostgreSQL/Redis, ephemeral per-process encryption keys). No `uv run --env-file .env`
   and no real environment file was used.
4. The only non-green browser suites are `public-illustrations.browser.mjs` (11/13) and
   `simplify-2c-illustrations.browser.mjs` (28/37) on both engines. Every failing check is
   `page.waitForFunction: Timeout 12000ms exceeded.` and matches the local Next image-optimizer
   hang diagnosed in `docs/sar-5/validation.md` §5.1. Neither suite touches an academic route, and
   both failed identically before this slice.
5. The backend shard warnings are pre-existing
   `DeprecationWarning: Returning tuple (status_code, response) is deprecated` messages from
   unrelated Django Ninja operations; no SAR-7 test emitted a new warning.

### 7.4 Not run

- `seed_staging_dataset issue-credentials` was not run; no credential was issued anywhere.
- No deployment, staging or production command, and no shared database or cache was touched.
- No migration was authored, and no existing database was migrated. The only `migrate` ran against
  the newly created, empty `compass_sar7_validation` database, which was dropped.
- `contracts/openapi.json` and `fe/src/lib/api/generated/**` were not hand-edited. The contract was
  regenerated and the client was regenerated with `pnpm api:generate`.
- No manual UI pass beyond the automated browser suites was performed.

### 7.5 Repository state

- Branch `integration/ux15-modernization`, based on `8931290e`; every SAR-7 change is uncommitted
  in the working tree. Nothing was committed, merged, pushed, opened as a PR, or deployed.
- `git diff --check` reports no whitespace errors.
- `fe/next-env.d.ts` is unmodified, the disposable database is absent, and the local validation
  servers are stopped.
