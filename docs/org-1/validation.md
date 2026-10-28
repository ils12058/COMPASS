# ORG-1 validation evidence

Baseline: `e7db50e0b23dd21a7ff7ec44c9d08708eb24ee12`, fetched again unchanged before final review.
Worktree: `/Users/reynantlntno/.codex/worktrees/org-1-database-catalog-authority/COMPASS`.
Branch: `feature/org-1-database-catalog-authority`. Date: 2026-10-25 (Asia/Manila).

## Environment and scope

All application test/management invocations used a clean environment and a new disposable local
PostgreSQL cluster. Python 3.13.12 reused the installed backend dependencies read-only; Django 6.1.1,
PostgreSQL 17.11, UTF8 encoding with C locale. No `.env`, real key, institutional dataset, SMTP,
Droplet credential, SSH or deployment workflow was used. Real Chromium was already installed and
rendered synthetic certificate data locally. Test settings supplied ephemeral test-only keyrings.

```sh
mktemp -d /private/tmp/compass-org1.XXXXXX
/opt/homebrew/opt/postgresql@17/bin/initdb -D /private/tmp/compass-org1.OdXuDd/pg -U compass --auth=trust --locale=C --encoding=UTF8
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /private/tmp/compass-org1.OdXuDd/pg -l /private/tmp/compass-org1.OdXuDd/postgres.log -o '-h 127.0.0.1 -p 56548 -k /private/tmp/compass-org1.OdXuDd' start
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56548 -U compass compass_org1
```

initdb output was saved in the temporary directory. pytest created/destroyed its own test DB;
upgrade tests created/dropped separate random `org1_upgrade_*` databases on this same isolated server.
The task-owned cluster was stopped after validation with
`pg_ctl -D /private/tmp/compass-org1.OdXuDd/pg stop -m fast` (exit 0); logs/XML remain in that directory.
These are synthetic migrations, not deployed/operational schema changes. UTF8 is verified; this does
not establish the actual deployment's collation/locale or real writer retirement.

All following Python application argv used this prefix from `<worktree>/be`:

```sh
env -i PATH='/opt/homebrew/bin:/usr/bin:/bin' \
  POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=56548 POSTGRES_DB=compass_org1 \
  POSTGRES_USER=compass POSTGRES_PASSWORD=test-only DJANGO_SETTINGS_MODULE=tests.settings \
  /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
```

## Final backend evidence — 685 distinct passing cases

The coherent final integration command (append to the prefix above):

```sh
-m pytest tests/test_program_policy.py tests/test_organization_catalog.py tests/test_organization_policy_migration.py tests/test_organization.py tests/test_inventory.py tests/test_program_inventory_academic_context.py tests/test_inventory_documents.py tests/test_inventory_counseling_regression.py tests/test_good_moral.py tests/test_good_moral_preparation.py tests/test_good_moral_assisted.py tests/test_good_moral_final_preservation.py tests/test_good_moral_receipts.py tests/test_good_moral_verification.py tests/test_good_moral_verification_concurrency.py tests/test_good_moral_receipt_migration.py tests/test_good_moral_verification_migration.py tests/test_capability_dependencies.py tests/test_institutional_identity.py tests/test_step_up_policy.py tests/test_appointment_management_scope.py tests/test_graduate_tracer_graduation_classification.py tests/test_graduate_tracer_reports.py tests/test_exit_interview_documents.py tests/test_routine_inventory_decoupling.py tests/test_staging_seed.py tests/test_staging_deployment.py tests/test_canonical_baseline.py tests/test_openapi_contract.py tests/test_operational_students.py -q --junitxml=/private/tmp/compass-org1.OdXuDd/final.xml
```

Result: **672 passed**, no skips/failures/errors, 470.62 seconds. This includes the real certificate
browser/PDF scenarios omitted in ORG-0, and GM-OR receipt/preparation/issuance/concurrency/migration
preservation tests. No template, receipt-ledger activation or verification policy was changed.

A subsequent preflight refinement added actual read-only database-state checks plus their focused
cases; it was verified separately against the final source:

```sh
-m pytest tests/test_staging_deployment.py -k catalog_preflight -q --junitxml=/private/tmp/compass-org1.OdXuDd/preflight.xml
```

Result: **13 passed**, 28 deselected, no failures/errors, 9.40 seconds. Ten exercise the explicit
plan/receipt/action matrix; three invoke the real preflight against disposable PostgreSQL with
simulated destination mode and prove check/refusal/explicit-adoption planning never adopts or
changes catalog data. They do not contact any host, provider or real destination.

JUnit `(classname, name)` identities were compared: 672 + 13 = **685 unique cases**, no overlap.
Early focused runs (171; 56; five new-workflow cases) are deliberately **not added** to that total.

| Final area | Cases |
|---|---:|
| Program policy | 37 |
| Catalog/bootstrap | 10 |
| Organization populated/failure migrations | 2 |
| Existing Organization | 18 |
| Inventory/core academic context/documents/counseling regression | 32 |
| Good Moral core/preparation/assisted/final preservation | 163 |
| GM-OR receipt/verification/concurrency/migration | 206 |
| Capability dependencies/institutional identity/MFA | 25 |
| Appointment scope | 13 |
| Tracer graduation/reporting | 18 |
| Exit documents/Routine inventory decoupling | 17 |
| Seeder (including class methods) | 50 |
| Deployment/preflight (28 + 13) | 41 |
| Canonical graph/hash/actual constraints | 5 |
| OpenAPI contract | 39 |
| Operational Student selectors | 9 |
| **Total** | **685** |

The Catalog/policy/upgrade/preflight foundation alone includes **37 database-specific cases**:
23 policy/selection/API/Inventory/F4 cases, nine initialization/authority cases, two real populated
migration cases, and three real read-only preflight cases. Among them are 13 direct SQL invalid-state
rejections and two separate-connection concurrent initialization/adoption cases. Many additional
backend cases in the table also use PostgreSQL; 37 is the scoped foundation count, not a claim that
all other cases are database-free.

Evidence SHA-256 (local XML files retained beside logs):

```text
final.xml     1a3e9deca0765e625f056ff5f213b345cd14a98cff1d1d7c07b95249d4df96fe
preflight.xml 0a818e17cbefcfe74db3e3fd52dd06315e74fab3b4c6b790a536fbb5083f2eb3
```

## New and revised regression coverage

- `test_program_policy.py`: typed input rejection before model coercion; raw SQL enum/NULL/array
  shape/range/order/duplicate rejection; permitted configured/pending classifications; unknown
  compatibility; active ancestry versus historical reads; database-only Program API/degree options;
  actual Inventory submission and F4 creation with saved facts preserved after a later rename/policy change.
- `test_organization_policy_migration.py`: full old-schema disposable DB, frozen exact identity
  matching, modified/additional/missing/inactive rows, complete original-field/FK/timestamp comparisons,
  forward failure after backfill, successful retry, repeat no-op and irreversible reverse boundary.
  Synthetic fixture has 39 Programs: 35 exact policy matches and four unresolved identities.
- Organization catalog tests replace old repair/retirement expectations with seed/adoption/no-op,
  nonempty refusal, empty receipt, immutable application receipt paths, audit rollback, two real
  concurrent installer cases, actual deployment-source command replay, seeder prerequisite preservation,
  and incompatible-schema refusal.
- Seeder tests explicitly initialize their synthetic fixture, retain external-boundary prohibitions
  and read-only verification, and prove a full replay refuses a retired persona Program without repair.
- Deployment tests keep the new migration unapproved for routine deployment and exercise the explicit
  action/receipt/schema boundary. Existing safety and unknown/backwards-migration checks remain.
- Good Moral fixture helpers now persist expected policy, including assisted postgraduate fixtures;
  no runtime code supplies a canonical fallback to make tests pass.

## Checks and fresh CLI rehearsal

Using the application prefix above, the following ran on the disposable `compass_org1` database:

```sh
manage.py migrate --noinput --settings=tests.settings
manage.py initialize_organization_catalog --seed --reference synthetic-ORG-1-fresh-rehearsal --settings=tests.settings
manage.py initialize_organization_catalog --check --settings=tests.settings
manage.py sync_organization_catalog --settings=tests.settings
manage.py check --database default --settings=tests.settings
manage.py makemigrations --check --dry-run --settings=tests.settings
manage.py export_openapi --check --settings=tests.settings
```

Fresh migration succeeded; seed reported SEEDED/changed=True; check and legacy replay reported
changed=False. System check found no issues, model drift found no changes, and OpenAPI was current.
No generated API or frontend contract change was necessary.

Other checks, from worktree root:

```sh
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff check be
/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/ruff format --check be
bash -n be/deploy/staging/deploy.sh
python3 -m unittest discover -s .github/scripts
python3 .github/scripts/backend_ci.py verify
python3 .github/scripts/backend_ci.py select --base e7db50e0b23dd21a7ff7ec44c9d08708eb24ee12 --head HEAD --paths be/compass/organization/models.py be/compass/organization/bootstrap.py be/compass/common/canonical_migrations.json be/compass/inventory/services.py be/compass/good_moral/api.py
```

Ruff lint/format and Bash syntax passed. Workflow/CI safety self-tests: **60 passed** (separate from
685 pytest cases). Bundle verification: all **196 test files** assigned exactly once across six
full-regression shards. New test files were added to the Organization bundle.

The selector conservatively requests the complete 196-file suite for model/shared Organization
changes. Local execution used the focused 30-file integration selection above, plus the 13-case
preflight refinement; the full 196-file suite was not run locally. Hosted full regression remains
separate release evidence, not implied by these passes.

OpenAPI is byte-compatible; frontend source/contracts were not changed. Orval regeneration and
frontend typecheck/browser UI suites were not applicable/run. Actual backend certificate PDF
rendering was run and passed. Documentation QA passed: ten required files, 27 local links, balanced code fences and all 26
unchanged baseline hashes. Canonical graph tests and `git diff --check` passed before commit.

## Failures fixed during development

An early new Inventory→F4 test omitted the existing required request idempotency key/fingerprint;
its fixture was corrected to use that unchanged service contract. No issuance rule was relaxed.
The CI selector self-test initially identified the two new files as unbundled; both were registered,
and the complete 60-case self-test plus bundle verification passed afterward. A postgraduate test
fixture was updated to persist its explicit Masters policy rather than rely on old Python inference.
No known failing selected test/check remains.

## Hosted CI, approvals and limits

The existing targeted PR workflows filter to staging/canonical branches, not the integration target.
No workflow is dispatched by ORG-1. Final hosted check/run status is read from the opened PR and
reported in the handoff; absent checks are not a CI pass. A source merge does not authorize live
migration, institutional adoption, editor/grant activation, deployment or policy approval.

No actual old-writer inventory/fencing, production-data migration, backup recovery, deployment locale
verification, institutional UAT or new Catalog UI/accessibility review was performed. ORG-0 D1/D2/D8/D19
and editor/policy/remediation decisions remain operational gates. Routine preflight deliberately
refuses the unreviewed ORG-1 migration. Only source code and disposable synthetic state were changed.
