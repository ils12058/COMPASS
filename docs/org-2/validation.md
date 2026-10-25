# ORG-2 validation

Baseline: `077d98a29855f9822599c938d81cb6b5d7102684`, fetched integration head before changes and
rechecked unchanged during review. Worktree:
`/Users/reynantlntno/.codex/worktrees/org-2-catalog-crud-integrity/COMPASS`.
Branch: `feature/org-2-catalog-crud-integrity`. Date: 2026-10-25 (Asia/Manila).
Final commit/PR/check state is reported in the PR and handoff, avoiding a self-referential source SHA.

## Local environment and boundaries

Python 3.13.12, Django 6.1.1, PostgreSQL 17.11, UTF8/C locale. Node v26.7.0; project pnpm 11.19.0;
Orval 8.29.0; Next.js 16.3.4. Existing backend dependencies/interpreter were reused; frontend install
used the locked offline store, 727 reused packages and zero downloads. No dependency upgrade occurred.
No repository `.env`, real key, real user population, live DB, SMTP, SSH or deployment workflow was
used. Tests use ephemeral test-only encryption/authentication settings. Actual Chromium certificate
rendering/PDF tests ran within the selected existing backend suites; this is not ORG-3 UI/UAT proof.

Task-owned isolated PostgreSQL setup:

```sh
mktemp -d /private/tmp/compass-org2.XXXXXX
/opt/homebrew/opt/postgresql@17/bin/initdb -D /private/tmp/compass-org2.oCAzLC/pg -U compass --auth=trust --locale=C --encoding=UTF8
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /private/tmp/compass-org2.oCAzLC/pg -l /private/tmp/compass-org2.oCAzLC/postgres.log -o '-h 127.0.0.1 -p 56549 -k /private/tmp/compass-org2.oCAzLC' start
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56549 -U compass compass_org2
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56549 -U compass compass_org2_guard
```

All application Python commands below run from `<worktree>/be` with this clean prefix:

```sh
env -i PATH='/opt/homebrew/bin:/usr/bin:/bin' \
 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=56549 POSTGRES_DB=compass_org2 \
 POSTGRES_USER=compass POSTGRES_PASSWORD=test-only DJANGO_SETTINGS_MODULE=tests.settings \
 /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
```

pytest creates/destroys its synthetic `test_...` DB. The final refinement uses the same prefix with
POSTGRES_DB=compass_org2_guard so its test database is independent of the broad selection. Populated
migration tests create/drop additional random org1_upgrade_* databases on this same task-owned
server. Those historical tests retain their existing fixture name; no real database is upgraded.

## Final backend evidence

Broad coherent selection, append to the prefix above:

```sh
-m pytest tests/test_catalog_services.py tests/test_catalog_concurrency.py tests/test_catalog_version_migration.py tests/test_program_policy.py tests/test_organization_catalog.py tests/test_organization_policy_migration.py tests/test_organization.py tests/test_accounts.py tests/test_account_management.py tests/test_capability_dependencies.py tests/test_institutional_identity.py tests/test_step_up_policy.py tests/test_audit.py tests/test_inventory.py tests/test_program_inventory_academic_context.py tests/test_inventory_documents.py tests/test_inventory_counseling_regression.py tests/test_good_moral.py tests/test_good_moral_preparation.py tests/test_good_moral_assisted.py tests/test_good_moral_final_preservation.py tests/test_good_moral_receipts.py tests/test_good_moral_verification.py tests/test_good_moral_verification_concurrency.py tests/test_good_moral_receipt_migration.py tests/test_good_moral_verification_migration.py tests/test_appointments.py tests/test_appointment_management_scope.py tests/test_guidance_messages.py tests/test_guidance_messages_concurrency.py tests/test_guidance_messages_handlers.py tests/test_guidance_followups.py tests/test_graduate_tracer.py tests/test_graduate_tracer_graduation_classification.py tests/test_graduate_tracer_reports.py tests/test_exit_interview_documents.py tests/test_routine_inventory_decoupling.py tests/test_staging_seed.py tests/test_staging_deployment.py tests/test_canonical_baseline.py tests/test_openapi_contract.py tests/test_operational_students.py -q --tb=short --junitxml=/private/tmp/compass-org2.oCAzLC/final.xml
```

**1,076 passed and one failed**, no errors/skips, 842.04 seconds. The sole failure was
`test_initializer_refuses_an_unapplied_schema_even_with_a_receipt`, diagnosed below and fixed
without weakening history validation. This broad run is not represented as an all-green run.

After reproducing the missing-0002/recorded-0003 schema-history refusal and tightening adopted-value
updates, run the final focused affected selection against compass_org2_guard:

```sh
-m pytest tests/test_catalog_services.py tests/test_catalog_concurrency.py tests/test_catalog_version_migration.py tests/test_organization_catalog.py tests/test_organization_policy_migration.py tests/test_openapi_contract.py -q --tb=short --maxfail=3 --junitxml=/private/tmp/compass-org2.oCAzLC/refinement.xml
```

**167 passed**, no failures/errors/skips, 234.71 seconds, against final runtime source. This includes
all new Catalog services and races, the typed schema refusal fix, adopted-value preservation,
composed service-created Program→Inventory→F4 and exact capability-composition tests. Broad downstream
regressions use the same domain integrations; no downstream behavior was changed after their run.
The later catalog save refinement affects only new protected services, all re-exercised here.

JUnit `(classname, name)` identities were reconciled with the final refinement superseding prior
results for overlapping cases: 1,077 + 167 − 162 = **1,082 unique passing cases**. The 167 final-source
cases include the previously failed schema-refusal case and five added cases. No known selected
failure remains. Early development runs (including 142 and 105 passes) are not added.

| Area | Distinct passing cases |
|---|---:|
| New Catalog service/security/API/history tests | 88 |
| New Catalog independent-connection races | 26 |
| New populated resource-version migration | 1 |
| ORG-1 policy/catalog/migration and Organization | 67 |
| Accounts/Account Management/capabilities/identity/MFA | 69 |
| Audit | 17 |
| Inventory/context/documents/confidential boundary | 32 |
| Good Moral F4/F6/core/preparation/assisted/final snapshots | 163 |
| GM-OR receipts/verification/concurrency/migrations | 206 |
| Appointments and management scope | 39 |
| Guidance Messages/handlers/concurrency and Follow-Ups | 168 |
| Graduate Tracer/graduation/reporting | 44 |
| Exit documents and Routine decoupling | 17 |
| Seeder | 50 |
| Deployment/preflight | 41 |
| Canonical migration controls | 5 |
| Operational Student selectors | 9 |
| OpenAPI | 40 |
| **Total** | **1,082** |

XML SHA-256:

```text
final.xml      c215813678e126480cd126c8ea03dd598984630f4b64ed91e04bc28bd7e9ac7b
refinement.xml 23f2616aa38c2834688b8f59e9db14d4d6799bf8c4188a747c4d9f3fcfe37644
```

The new foundation includes separate-connection races for every requested scenario family: duplicate
Campus/College/Program and equivalent normalization, two renames, rename/status, parent/child create
both orders, College/Program activation, Student affiliation, Counselor responsibility, account
reactivation, Inventory submit/selection, F4 creation both policy orders, pending correction, stale
preview, revoked capability, expired MFA, Audit failure and rollback after version increment.
Actual PostgreSQL lock timeout and a test-only injected deadlock both yield safe typed conflicts.
The harness observes independent backend PIDs and ungranted advisory locks before releasing the
first transaction; a timed sequential mock is not race evidence.

Other new cases exercise raw SQL positive-version CHECKs for all three models, shared ORG-1 policy
validation, strict requests, MFA/session/role/dependency/override denials, aggregate counts without
private contents, target-safe paginated history, transaction/Audit rollback, no-op silence and
identity/history retention. New 0003 migration test uses populated historical schema and compares
all original fields before/after; existing 0001→0002 frozen backfill/failure tests still pass.

## Fresh CLI and static/contract checks

Using the application prefix on the disposable base DB:

```sh
manage.py migrate --noinput --settings=tests.settings
manage.py initialize_organization_catalog --seed --reference synthetic-ORG2-fresh-rehearsal --settings=tests.settings
manage.py initialize_organization_catalog --check --settings=tests.settings
manage.py sync_identity_policy --settings=tests.settings
manage.py check --database default --settings=tests.settings
manage.py check --settings=tests.settings
manage.py makemigrations --check --dry-run --settings=tests.settings
manage.py export_openapi --check --settings=tests.settings
```

Fresh migrate passed. Seed reported changed=True, subsequent check changed=False. Every seeded
Campus/College/Program version is 1. Identity sync installed the new definition and **zero** catalog
role grants / **zero** designation grants. Django checks passed, model drift reported no changes,
and committed OpenAPI matches generated output. No live migration/seed/adoption is implied.

From worktree root:

```sh
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff check be
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff format --check be
python3 -m unittest discover -s .github/scripts
python3 .github/scripts/backend_ci.py verify
python3 .github/scripts/backend_ci.py select --base 077d98a29855f9822599c938d81cb6b5d7102684 --head HEAD --paths be/compass/organization/models.py be/compass/organization/catalog_services.py be/compass/accounts/policy.py be/compass/inventory/services.py be/compass/good_moral/services.py
```

Ruff lint/format passed (851 files formatted/current). CI selection/safety self-tests: **60 passed**,
separate from backend pytest counts. All **199 test files** are bundled exactly once across six
full-regression shards; the three new test modules are registered. Selector requests full regression
because Organization/model/identity are shared. The local 42-file selection is focused integration
evidence; the complete 199-file suite was not run locally. No test/shard/guard was disabled.

From `<worktree>/fe`:

```sh
CI=true pnpm install --frozen-lockfile --offline
pnpm api:generate
pnpm typecheck
pnpm lint
pnpm build
```

All passed. Orval output was regenerated again and SHA-256 compared over all **924 generated TS
files**, producing the same digest `0bde9c99b65d2eba7e4028217d06c5bd7fae47034432ce5132394909377eb1d6`.
Ignored generated clients are not hand-edited or committed. Next build's automatic next-env.d.ts
path change was restored to the original tracked file, then typecheck passed again. No frontend
source/UI change is necessary; the current app compiles with the extended contract.

Documentation QA verifies eleven required documents, existing relative links, balanced fences and
all **26 unchanged baseline migration hashes**. git diff --check passes. New migration is additive
and registered; prior migrations/allowlists and docs/org-0/docs/org-1 are untouched.

## Development failures and corrections

- Early fixtures used prompt lifecycle names not present in the actual enum; tests now use
  CURRENT/GRADUATED/FORMER and the blocker covers every active Student lifecycle. No lifecycle policy changed.
- Legacy tests asserted no Catalog POST endpoints/capability enum; those assertions were updated for
  the explicitly requested new operations while arbitrary PATCH/legacy enable/disable remain absent.
- A race test imported GoodMoralError from a nonexistent errors module; corrected to its real service.
- Historical migration-test state initially included latest Organization fields or omitted other
  domain apps; it now composes the tested Organization target with the actual other applied leaves.
- A deliberate missing-0002 history fixture with recorded 0003 raised Django InconsistentMigrationHistory
  outside the initializer's typed error. Reproduced in its own disposable DB; the history guard stays
  strict and now translates that failure to the existing incompatible-schema refusal.
- Review found model save normalization could change an adopted code/name in memory despite omitted
  update_fields, fabricating Audit differences. Protected updates now write only validated changed
  columns; a preservation/no-op regression passes.
- An early development overlap reused a test DB and produced a teardown warning. That intermediate
  run is excluded from evidence; subsequent concurrent pytest processes use independent base/test DBs.
  Final broad/refinement evidence has no such overlap or database teardown warning.

## Hosted checks and operational limits

The configured targeted PR workflows filter staging/canonical branches, not the integration
target. Hosted check/run state is inspected on the opened PR and recorded in the final handoff.
No hosted success is inferred from local validation.

No deployment workflow is dispatched. Hosted absence is not CI-green. No full institutional UAT,
ORG-3 authenticated management UI, manual screen-reader/zoom/mobile review, deployed old-writer
inventory, production collation compatibility or live backup/recovery proof is claimed. Source,
synthetic PostgreSQL and current frontend compilation are the delivered engineering evidence.
No SSH, live migration, real-data inspection, actual Catalog grants, institutional edits, deployment,
editing activation or automatic merge occurred. ORG-1 cutover and institutional decisions remain
blocked pending separately approved operations. The task-owned cluster was stopped after tests with
`pg_ctl -D /private/tmp/compass-org2.oCAzLC/pg stop -m fast` (exit 0, server stopped). Logs/XML
remain in that directory; no other task database/server was stopped.
