# ORG-4 executed validation

Date: 2026-10-26 Asia/Manila. Fetched integration/base/runtime SHA:
`d91d64c2893ac834c6b70c1e00f4a823e11478f7`. Isolated worktree/branch are in README.
Runtime, migrations, contract and product frontend are unchanged. Test/harness candidate and final
PR head are pinned in the README/PR, avoiding a self-referential commit hash. Tested implementation
commit: `4323f3a759036621ccfe252321361b9cb8635248`; subsequent delivery evidence changes docs only.

## Environment

Local macOS, Python 3.13.12 / Django 6.1.1 from the existing read-only backend venv; PostgreSQL
17.11 UTF8/C locale; Redis 8.10.2; Node v26.7.0; project pnpm 11.19.0; Next 16.3.4; React 19.2.8;
Orval 8.29.0; TypeScript 5.9.3; frontend Playwright 1.62.1. The global root pnpm is 11.26.0;
frontend commands resolve the packageManager-pinned 11.19.0. Locked offline install reused 727
packages, zero downloads. No dependency or lockfile was changed. Existing browser engines were reused.

No repository .env, deployed connection, actual account/key, SMTP or external provider was used.
Pytest encryption/TOTP settings are ephemeral. The real browser fixture uses private generated
test state with stable ephemeral keyrings shared by its local processes.

Task-owned cluster and databases:

```sh
mktemp -d /private/tmp/compass-org4.XXXXXX
/opt/homebrew/opt/postgresql@17/bin/initdb -D /private/tmp/compass-org4.I9H5cI/pg -U compass --auth=trust --locale=C --encoding=UTF8
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /private/tmp/compass-org4.I9H5cI/pg -l /private/tmp/compass-org4.I9H5cI/postgres.log -o '-h 127.0.0.1 -p 56649 -k /private/tmp/compass-org4.I9H5cI' start
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56649 -U compass compass_org4
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56649 -U compass compass_org4_focus
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56649 -U compass compass_org4_browser
redis-server --bind 127.0.0.1 --port 56650 --save '' --appendonly no --dir /private/tmp/compass-org4.I9H5cI --logfile /private/tmp/compass-org4.I9H5cI/redis.log
```

All backend pytest/management commands below ran from `<worktree>/be` with this prefix, changing
POSTGRES_DB to `compass_org4_focus` for focused/historical selections:

```sh
env -i PATH='/opt/homebrew/bin:/usr/bin:/bin' \
 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=56649 POSTGRES_DB=compass_org4 \
 POSTGRES_USER=compass POSTGRES_PASSWORD=test-only DJANGO_SETTINGS_MODULE=tests.settings \
 /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
```

Pytest creates/destroys its own `test_...` DBs. Populated migration cases use additional random
databases on this same isolated server. No overlapping pytest processes share a test DB.

## Backend selections and distinct accounting

Append to the clean Python prefix:

```sh
-m pytest tests/test_catalog_services.py tests/test_catalog_concurrency.py tests/test_catalog_version_migration.py tests/test_program_policy.py tests/test_organization_catalog.py tests/test_organization_policy_migration.py tests/test_organization.py tests/test_accounts.py tests/test_account_management.py tests/test_capability_dependencies.py tests/test_institutional_identity.py tests/test_step_up_policy.py tests/test_audit.py tests/test_inventory.py tests/test_program_inventory_academic_context.py tests/test_inventory_documents.py tests/test_inventory_counseling_regression.py tests/test_good_moral.py tests/test_good_moral_preparation.py tests/test_good_moral_assisted.py tests/test_good_moral_final_preservation.py tests/test_good_moral_receipts.py tests/test_good_moral_verification.py tests/test_good_moral_verification_concurrency.py tests/test_good_moral_receipt_migration.py tests/test_good_moral_verification_migration.py tests/test_appointments.py tests/test_appointment_management_scope.py tests/test_guidance_messages.py tests/test_guidance_messages_concurrency.py tests/test_guidance_messages_handlers.py tests/test_guidance_followups.py tests/test_graduate_tracer.py tests/test_graduate_tracer_graduation_classification.py tests/test_graduate_tracer_reports.py tests/test_exit_interview_documents.py tests/test_routine_inventory_decoupling.py tests/test_staging_seed.py tests/test_staging_deployment.py tests/test_canonical_baseline.py tests/test_openapi_contract.py tests/test_operational_students.py tests/test_authentication.py -q --tb=short --junitxml=/private/tmp/compass-org4.I9H5cI/backend.xml

-m pytest tests/test_catalog_final_integration.py -q --tb=short --junitxml=/private/tmp/compass-org4.I9H5cI/final-integration.xml

-m pytest tests/test_student_profiling_reports.py tests/test_student_profiling_report_aggregates.py tests/test_student_profiling_report_coverage.py tests/test_exit_interviews.py tests/test_routine_interviews.py -q --tb=short --junitxml=/private/tmp/compass-org4.I9H5cI/historical-neighbors.xml
```

| Final selection | Result | Wall time |
|---|---|---|
| Existing coherent 43-file backend selection | 1,108 passed, zero failed/errors/skipped | 758.00 s |
| Final new ORG-4 module | 17 passed, zero failed/errors/skipped | 19.14 s |
| Five additional historical/report modules | 106 passed, zero failed/errors/skipped | 71.41 s |
| Distinct backend cases (disjoint JUnit identities) | **1,231 passed** | Three selections, not one full-repository invocation |

The historical selection emitted one existing Django Ninja tuple-response DeprecationWarning in
`test_direct_options_and_student_candidates_preserve_create_direct_authority_without_org_scope`.
No selected assertion failed. No runtime API convention was changed merely to silence a warning.

The new module was run at 10, then 12, then final 17 cases while adding coverage. Only the final
17 are counted. Those focused reruns add **zero** to the final distinct count. The broad suite was
not repeated for each test-only refinement. All production runtime was unchanged throughout.

Catalog-specific PostgreSQL races: **40 distinct** = 26 existing + 12 ORG-4 + two initializer cases.
They are already included in the backend total. Other existing Guidance/GM-OR concurrency suites
are not added to this Catalog race total. The late-MFA-after-Audit time-injection test is a separate
non-race assertion. Three populated Organization migration cases also sit inside the backend count.

Fresh CLI migrate/seed/check, post-edit full dump/restore, repeat initializer/alias preservation and
later-commit mismatch detection are separate synthetic command-level rehearsals, not extra pytest
counts. All-table restore matched 117 tables/514 rows. See migration-bootstrap-and-recovery.md.

## Frontend and real browser commands

From `<worktree>/fe`:

```sh
CI=true pnpm install --frozen-lockfile --offline
pnpm api:generate
pnpm test
pnpm lint
pnpm typecheck
COMPASS_API_BASE_URL=http://127.0.0.1:8164 pnpm build
pnpm start --port 3164
```

Orval, full Node 1,021, ESLint, TypeScript and production build passed. Next's automatic
next-env.d.ts generated import-path change was restored from the task's HEAD; final typecheck
passed with the original tracked file. Generated clients remain ignored and unedited.

From worktree root, each command below was run with Chromium, then with
`COMPASS_UI_BROWSER=webkit`; COMPASS_UI_ARTIFACTS used separate suite/engine directories:

```sh
COMPASS_UI_BASE_URL=http://localhost:3164 node fe/tests/organization-catalog.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3164 node fe/tests/good-moral-print.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3164 node fe/tests/good-moral-receipt.browser.mjs
```

Catalog 53/53, print 24/24 and receipt 37/37 passed per engine. Total **114 scenarios per engine**;
these are mocked API component regressions, not 228 distinct business cases or actual auth evidence.
Two final Catalog screenshots were visually inspected (narrow form and 200%-text confirmation).

Real browser prefix, in addition to the backend clean environment but without a trailing Python:

```sh
COMPASS_ORG4_DISPOSABLE=1
POSTGRES_DB=compass_org4_browser
REDIS_URL=redis://127.0.0.1:56650/0
REDIS_CACHE_URL=redis://127.0.0.1:56650/1
REDIS_RATE_LIMIT_URL=redis://127.0.0.1:56650/2
REDIS_IDEMPOTENCY_URL=redis://127.0.0.1:56650/3
REDIS_REALTIME_URL=redis://127.0.0.1:56650/4
CSRF_TRUSTED_ORIGINS=http://localhost:3164,http://127.0.0.1:3164
COMPASS_UI_BASE_URL=http://localhost:3164
COMPASS_ORG4_STATE=/private/tmp/compass-org4.I9H5cI/auth-state.json
COMPASS_ORG4_PYTHON=/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
COMPASS_UI_ARTIFACTS=/private/tmp/compass-org4.I9H5cI
```

These are environment assignments for the command runner, not secrets or institutional config.
The private task-owned `run-clean.sh` applies them under env -i. From `be/`, invoke the helper's
prepare/serve actions as documented; from `fe/`, invoke
`node tests/organization-catalog.authenticated.mjs`. **18/18 real Chromium scenarios passed with
all 16 real operation families**. No arbitrary API response was mocked. The lost-response scenario
injects transport loss only after actual backend commit. Early aborted harness attempts are excluded.

## Static, migration and CI selection commands

With the backend clean prefix:

```sh
manage.py migrate --noinput --settings=tests.settings
manage.py initialize_organization_catalog --seed --reference Synthetic-ORG4-fresh --settings=tests.settings
manage.py initialize_organization_catalog --check --settings=tests.settings
manage.py check --database default --settings=tests.settings
manage.py makemigrations --check --dry-run --settings=tests.settings
manage.py export_openapi --check --settings=tests.settings
```

All passed: fresh migrate/seed/check, no Django issues, no migration drift, current canonical
OpenAPI. Populated backup restore separately checked the initializer under compatible source.
Canonical baseline tests verify all 26 original migration hashes. No migration/allowlist changed.

From worktree root:

```sh
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff check be
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff format --check be
python3 -m unittest discover -s .github/scripts
python3 .github/scripts/backend_ci.py verify
python3 .github/scripts/backend_ci.py select --base d91d64c2893ac834c6b70c1e00f4a823e11478f7 --head HEAD --paths be/tests/test_catalog_final_integration.py .github/scripts/backend_ci.py
git diff --check
```

Ruff passed, 853 files formatted/current. CI self-tests: **60 passed**, separate from pytest.
The new module is registered; all **200 test files** are bundled once across six full-regression
shards. Targeted selection includes the new tests plus safety bundle. No workflow/test guard was
disabled. The opt-in real backend harness is not automatically dispatched in hosted mocked-browser
CI; its complete local evidence is separate. This local work ran **49 selected backend files**,
not the complete 200-file repository suite.

## Evidence, corrections and limitations

Machine-readable counts/module mapping and SHA-256 hashes of the final JUnit and authenticated JSON
are committed in evidence.json. Local logs/artifacts remain in `/private/tmp/compass-org4.I9H5cI/`:
`backend*`, `final-integration*`, `historical-neighbors*`, `node.log`, `orval.log`, `lint-final.log`,
`typecheck-final.log`, `build.log`, `chromium/`, `webkit/`, `print-*`, `receipt-*`, `authenticated*`,
`django.log`, migration/bootstrap logs and backup/recovery manifests/dump. Private state and dumps
are not repository artifacts. Only task-owned local servers/cluster are stopped after validation.

Harness-only preparation/selector/filter corrections are detailed in authenticated-integration.md.
Two incidental wrong-path/glob invocations and an initial Ruff command from the wrong working
directory were corrected; they are not passing application checks. No runtime defect or production
fix was found/introduced. Final selected application assertions have no unresolved failure.

PR #330 is OPEN and unmerged. At implementation head `4323f3a759036621ccfe252321361b9cb8635248`,
the connected GitHub status/workflow APIs and app check diagnostics returned **zero check runs,
zero status contexts, zero PR workflow runs**, no annotations/jobs. Final delivery head is rechecked
after the documentation-only evidence push. Local passes are not hosted CI; absence is not
CI-green. No deployment/workflow dispatch or auto-merge was performed.

Task-owned Django/Next/Redis stopped, then `pg_ctl -D /private/tmp/compass-org4.I9H5cI/pg stop -m fast`
completed with server stopped. Other servers/worktrees were not stopped or edited. A final fetch
still matched the original base SHA. The source worktree is retained for review.

Manual accessibility/native zoom/physical devices/native OS print and institutional UAT remain
NOT EXECUTED. Actual environment/locale/writer/image/key/media backup compatibility remains
UNVERIFIED. Recovery point reconciliation after later institutional edits is required, not automated
by this slice. Staging remains BLOCKED and activation NOT AUTHORIZED.
