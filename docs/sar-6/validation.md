# SAR-6 validation — real commands and results

All commands were run on 2026-11-04 on the local working tree at base `a3b2d99b` plus the
uncommitted SAR-6 changes. No staging or production contact occurred; only local test databases
were used.

## 1. Focused backend regression

From `be/`:

```bash
uv run pytest \
  tests/test_student_academic_records.py tests/test_student_academic_reads.py \
  tests/test_account_management.py tests/test_account_csv_import.py \
  tests/test_capability_dependencies.py tests/test_profiles.py \
  tests/test_student_profiling_report_coverage.py \
  tests/test_student_profiling_pdf.py tests/test_student_profiling_xlsx.py \
  tests/test_operational_students.py tests/test_good_moral.py \
  tests/test_openapi_contract.py tests/test_documents.py -q
```

Result:

```text
433 passed in 269.40s (0:04:29)
```

`uv run` was used without `--env-file .env`: `be/tests/settings.py` supplies the local test
PostgreSQL/Redis defaults, while `.env` targets the compose hosts. The first attempt with
`--env-file .env` produced 108 database-setup errors (`postgres` host unresolvable from the host
machine); it was discarded and the command above was used.

## 2. Static and contract checks

| # | Command (directory) | Result |
|---|---|---|
| 1 | `python3 .github/scripts/backend_ci.py verify` (repository root) | `OK: 212 test files are bundled and each runs exactly once across 6 full-regression shards.` |
| 2 | `uv lock --check` (`be/`) | `Resolved 72 packages` |
| 3 | `uv run ruff format --check .` (`be/`) | `888 files already formatted` |
| 4 | `uv run ruff check .` (`be/`) | `All checks passed!` |
| 5 | `uv run python -m compileall -q compass tests` (`be/`) | no output (exit 0) |
| 6 | `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` (`be/`) | `No changes detected` |
| 7 | `uv run python manage.py check --settings=tests.settings` (`be/`) | `System check identified no issues (0 silenced).` |
| 8 | `uv run python manage.py export_openapi --check --settings=tests.settings` (`be/`) | `OpenAPI contract is current: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |

The first format check failed on six files edited by this slice; `ruff format` was applied to
exactly those files, then one `E501` remained in
`be/compass/account_management/services.py` (the exact 105-character capability message). The
literal was split into adjacent string literals, preserving the runtime message byte-for-byte,
and all eight checks then passed.

No migration is added by this slice.

## 3. Full backend suite, six shards

Shard plan from the repository root:

```bash
python3 .github/scripts/backend_ci.py plan
```

The plan reports six shards over 212 test files:

```text
Shard 1/6: 35 items, about 22.2 min
Shard 2/6: 36 items, about 22.2 min
Shard 3/6: 36 items, about 22.2 min
Shard 4/6: 37 items, about 22.2 min
Shard 5/6: 36 items, about 22.2 min
Shard 6/6: 36 items, about 22.2 min
```

Each shard was run sequentially from `be/` with (`--index` is zero-based):

```bash
uv run python ../.github/scripts/backend_ci.py run-shard --index N --total 6
```

| Shard | Result |
|---|---|
| 1/6 | `1127 passed, 2 skipped, 6 warnings in 607.73s (0:10:07)` |
| 2/6 | `1082 passed, 1 skipped in 501.26s (0:08:21)` |
| 3/6 | `825 passed, 1 warning in 511.99s (0:08:31)` |
| 4/6 | `959 passed, 5 warnings in 600.94s (0:10:00)` |
| 5/6 | `1470 passed, 1 skipped in 592.26s (0:09:52)` |
| 6/6 (first run) | `2 failed, 990 passed, 4 warnings in 402.26s (0:06:42)` |
| 6/6 (after fix) | `992 passed, 4 warnings in 401.35s (0:06:41)` |

Totals for the final runs: **6,455 passed, 0 failed, 4 skipped**, aggregate pytest time
**3,215.53s (0:53:35)**. The suite count grew from SAR-5's 6,443 to 6,455 (+12 tests) with the
same 212 bundled files; 4 explicit opt-in skips remain (no new skip was added by this slice).

### 3.1 First shard 6/6 run — two real failures and their fix

The first run of shard 6/6 failed two frozen assertions in `be/tests/test_accounts.py`, both
directly caused by the three new capability grants:

```text
FAILED tests/test_accounts.py::test_policy_sync_is_idempotent_and_does_not_create_django_model_permissions
  assert 104 == 101          # RoleCapability count
  assert 22 == 20            # DesignationCapability count

FAILED tests/test_accounts.py::test_effective_capabilities_combine_role_designation_and_overrides
  assert frozenset({'a...manage', ...}) == {'academic_ye....manage', ...}
```

The counts changed because IT_ADMIN gained two role grants, STUDENT gained one role grant, and
HEAD_GUIDANCE_COUNSELOR gained two designation grants. The test expectations were updated to
104 role grants and 22 designation grants, and the HEAD_GUIDANCE_COUNSELOR effective set gained
`student_academics.view` and `student_academics.manage`. No production behavior was changed to
make the tests pass. `tests/test_accounts.py` then passed 19/19, and shard 6/6 was rerun cleanly
with `992 passed`. The totals above use the rerun.

This is a real test-data expectation change, not an environmental failure; it is recorded rather
than hidden.

## 4. Frontend unit, lint, type, build

From `fe/`:

| Command | Result |
|---|---|
| `pnpm api:generate` | Orval v8.29.0; `🎉 compass - Your OpenAPI spec has been converted into ready to use orval!` |
| `pnpm lint` | `eslint .` completed with no findings (exit 0) |
| `pnpm typecheck` | `tsc --noEmit` completed with no findings (exit 0) |
| `pnpm test` | `tests 1035`, `pass 1035`, `fail 0`, `cancelled 0`, `skipped 0`, `todo 0`, duration `41615.807667ms` |
| `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 pnpm build` | Next.js 16.3.4 (Turbopack) production build completed with exit 0; the route table was generated, including `/portal/academic-record` |

`next build` rewrote the committed `fe/next-env.d.ts` type references from `.next/dev/types/...`
to `.next/types/...`. The committed content was restored immediately after the build and is not a
SAR change.

## 5. Browser inventory, both engines

Run from `fe/` against the local Next server on `http://localhost:3107` and the local SSR fallback
on port 8000, with every API request served by the synthetic fixtures in `fe/tests/support/`. No
production, staging or other shared system was contacted.

```bash
COMPASS_UI_BASE_URL=http://localhost:3107 COMPASS_UI_ARTIFACTS=/tmp/sar6-browser-final \
  pnpm test:ui
```

`tests/run-browser-regressions.mjs` runs every `*.browser.mjs` suite on `chromium`, then all of them
again on `webkit`, in one invocation. There are 85 suites per engine.

| Engine | Suites | Checks |
|---|---|---|
| chromium | `83/85 suites passed.` | 1,633/1,644 |
| webkit | `83/85 suites passed.` | 1,632/1,643 |

Across both engines: **170 suite runs, 166 passed, 3,265/3,287 browser checks passed**. The runner
exited 1 only because of the two illustration suites below; both fail identically on both engines
with the image-optimizer hang already diagnosed in `docs/sar-5/validation.md` §5.1, and neither
touches an academic route.

Mandated suites:

| Suite | chromium | webkit |
|---|---|---|
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

The first full-inventory chromium pass exposed a real fixture gap in
`fe/tests/support/ux-hardening-fixtures.mjs`: the synthetic actor held `organization.manage` but
not `student_academics.manage`, so the newly gated placement writes were correctly blocked and
three checks failed verbatim with `locator.fill: Timeout 12000ms exceeded.`
(`clear-placements-timer`, `clear-placements-in-flight`) and
`locator.elementHandle: Timeout 12000ms exceeded.` (`newest-intent-placements`). The fixture was
given the two new capabilities; no production gate was relaxed. Because that chromium pass
predated the fix while the webkit pass followed it, both engines were rerun in full and the tables
above come from that clean run. The webkit `ux15-feedback-csm` check that failed once in the SAR-5
inventory passed on both engines here.

## 6. Seed sanity

The literal slice command does not parse: Django's `manage.py` accepts `--settings` only before
the subcommand, and the seed subparser rejects it.

```bash
uv run python manage.py seed_staging_dataset verify --settings=tests.settings
```

```text
manage.py seed_staging_dataset: error: unrecognized arguments: --settings=tests.settings
```

Using `DJANGO_SETTINGS_MODULE=tests.settings` instead connected to the local `compass_test`
database, which is the pytest database and contains no staging manifest. The verification failed
because the dataset was absent, not because of a SAR-6 defect:

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py seed_staging_dataset verify
```

```text
Verification FAILED.
  Schema readiness                4 passed,   1 failed,   0 warnings
  Canonical configuration         2 passed,  19 failed,   0 warnings
  Account readiness               3 passed, 116 failed,   0 warnings
  Organization routing            0 passed,  12 failed,   0 warnings
  Scenario initial states         0 passed, 122 failed,   0 warnings
  Workflow integrity              1 passed,   7 failed,   0 warnings
  Privacy and security           31 passed,   1 failed,   0 warnings
  External side effects           5 passed,   0 failed,   0 warnings
```

The slice text allows the local-staging configuration when the test-settings path is not usable.
A disposable local database, `compass_sar6_validation`, was created, seeded through the documented
reset path, verified, and dropped. Nothing shared was touched and `issue-credentials` was not run.
Environment overrides: `POSTGRES_DB=compass_sar6_validation`, `STAGING_SEED_ENABLED=true`,
`DJANGO_SETTINGS_MODULE=tests.settings` (which keeps the local loopback PostgreSQL/Redis and
ephemeral test-only encryption keys).

```bash
export POSTGRES_DB=compass_sar6_validation STAGING_SEED_ENABLED=true \
  DJANGO_SETTINGS_MODULE=tests.settings
uv run python manage.py migrate --noinput
uv run python manage.py sync_identity_policy
uv run python manage.py sync_canonical_services
uv run python manage.py sync_institutional_forms
uv run python manage.py initialize_organization_catalog --seed
uv run python manage.py seed_staging_dataset seed
uv run python manage.py seed_staging_dataset verify
```

Results — every stage exited 0:

| Stage | Result |
|---|---|
| `migrate --noinput` | all migrations applied, no error |
| `sync_identity_policy` | `roles created=6`; `designations created=2`; `capabilities created=94`; `role grants created=104`; `designation grants created=22` |
| `sync_canonical_services` | `Canonical Counseling Service created` |
| `sync_institutional_forms` | `Families: created=8`; `revisions: created=13 updated=0 activated=8` |
| `initialize_organization_catalog --seed` | `Catalog SEEDED; changed=True; baseline=ucn-2026-09-27-v1` |
| `seed_staging_dataset seed` | `Manifest: 116 accounts, 102 Students`; `624 item(s) created, 100 already present and reused`; no credential was set |
| `seed_staging_dataset verify` | `Verification PASSED.` |

Verification detail: Schema readiness 5, Canonical configuration 21, Account readiness 1,112,
Organization routing 12, Scenario initial states 122, Workflow integrity 40, Privacy and security
149, External side effects 5 — **1,466 passed, 0 failed, 0 warnings**. The new capability grants
appear in the seeded policy (94 capabilities, 104 role grants, 22 designation grants). The
database was dropped after the run. No seed file was changed by this slice.

## 7. Failures, discrepancies, environment notes and not-run list

### 7.1 Discrepancies

1. **The fail-closed resolver does not match slice A4.4.** The slice says a synthetic `.manage`-only
   grant resolves `.view` through `resolve_capability_dependencies`; the implemented resolver
   returns the largest dependency-coherent subset, so a `.manage`-only set resolves to the empty
   set. The dependency itself is declared as required
   (`required_capabilities("student_academics.manage") == {"student_academics.view"}`), and
   `be/tests/test_capability_dependencies.py` asserts the actual fail-closed behavior. This is a
   documentation discrepancy in the slice text, not an access expansion; it is recorded in
   `docs/sar-6/decisions.md` §5.
2. **Frozen policy totals in `be/tests/test_accounts.py` changed.** The new grants raised the
   expected role-grant count from 101 to 104, the designation-grant count from 20 to 22, and added
   `student_academics.view`/`student_academics.manage` to the expected
   HEAD_GUIDANCE_COUNSELOR effective set. This is a test-data expectation change; no production
   behavior was altered to satisfy it. After the update `tests/test_accounts.py` passed 19/19 and
   shard 6/6 was rerun cleanly at 992 passed (see §3).
3. **The seed-verify command in the slice text does not parse.** Django accepts `--settings` only
   before the subcommand, so
   `manage.py seed_staging_dataset verify --settings=tests.settings` exits with
   `unrecognized arguments: --settings=tests.settings`. Verification through
   `DJANGO_SETTINGS_MODULE=tests.settings` then pointed at the unseeded pytest database
   `compass_test` and failed for absence of the manifest, not for a SAR-6 defect. The documented
   reset path was run on the disposable local database `compass_sar6_validation` instead and
   passed 1,466 checks with 0 failures and 0 warnings (see §6). The database was dropped.

### 7.2 Environment notes

1. `next build` rewrote the committed `fe/next-env.d.ts` type references from
   `.next/dev/types/...` to `.next/types/...`. The committed content was restored immediately and
   the file is absent from `git status`; it is not a SAR-6 change.
2. The only non-green browser suites are `public-illustrations.browser.mjs` (11/13) and
   `simplify-2c-illustrations.browser.mjs` (28/37) on both engines. Every failing check is
   `page.waitForFunction: Timeout 12000ms exceeded.` and matches the local Next image-optimizer
   hang diagnosed in `docs/sar-5/validation.md` §5.1. Neither suite touches an academic route, and
   both failed identically before this slice.
3. The first full-inventory run exposed a fixture gap, not a product regression: the synthetic
   actor in `fe/tests/support/ux-hardening-fixtures.mjs` lacked the two new staff capabilities and
   the now-gated placement writes timed out. The fixture was updated and both engines were rerun in
   full; the final inventory is 60/60 for `ux-hardening.browser.mjs` on both engines.
4. Backend validation used `be/tests/settings.py` via pytest and `DJANGO_SETTINGS_MODULE` (local
   loopback PostgreSQL/Redis, ephemeral per-process encryption keys). No `uv run --env-file .env`
   and no real environment file was used.
5. The local Next server on port 3107 and the local SSR fixture fallback on port 8000 existed only
   for the browser inventory. Both were stopped after the run and both ports are closed. No browser
   suite ran against a Django server.

### 7.3 Not run

- `seed_staging_dataset issue-credentials` was not run; no credential was issued anywhere.
- No deployment, no staging or production command, and no shared database or cache was touched.
- No migration was authored, and no existing database was migrated. The only `migrate` ran against
  the newly created, empty `compass_sar6_validation` database, which was dropped.
- `contracts/openapi.json` and `fe/src/lib/api/generated/**` were not hand-edited. The contract was
  regenerated with `manage.py export_openapi` and the client with `pnpm api:generate`.
- No manual UI pass beyond the automated browser suites was performed.

### 7.4 Repository state

- Branch `integration/ux15-modernization`, based on `a3b2d99b`; every SAR-6 change is uncommitted
  in the working tree. Nothing was committed, merged, pushed, opened as a PR, or deployed.
- `git diff --check` reports no whitespace errors; `uv run ruff format --check .` reports
  `888 files already formatted`; `uv run ruff check .` reports `All checks passed!` after the final
  edits.
- `fe/next-env.d.ts` is unmodified, the disposable database is absent, and the local validation
  servers are stopped.
