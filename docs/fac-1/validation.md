# FAC-1 validation evidence

Validated locally on 2026-10-31 against integration base `478166b7`. All users,
content, database upgrades and browser responses in these checks are synthetic.
No staging/production operation or institutional UAT was performed.

## Backend

The initial integrated run covered Accounts, Account Management/CSV, institutional
identity, Organization initialization/services/catalog/concurrency, Referrals,
Follow-Ups, Notifications, Overview, Faculty and additive migration rehearsals:
308 passed and two failed. Those failures identified the expected-role count and
a missing strict catalog-impact DTO update; both were corrected and rechecked.

Final focused integration: **201 passed** in 86.26 seconds, covering all Account,
Account Management/CSV, institutional identity, Catalog service, Faculty migration,
Faculty concurrency and Service Catalog tests. The later final Faculty suite is
**17 passed** (including additional preview/commit drift and role-transition checks).
Supplemental authentication, capability dependencies and continuity contract run:
41 passed plus one outdated exact session-key assertion. The assertion now
explicitly includes `faculty_affiliation` and verifies it is null for Students;
its focused rerun passed. No authorization assertion was removed or relaxed.

The four Faculty PostgreSQL race scenarios observe an actual ungranted advisory
lock on an independent connection. Assignment or single-account creation races
College retirement in both orders; only one operation may commit. Additional
checks cover stale versions, active/inactive ancestry, deactivation/reactivation,
role change session revocation, duplicate provisioning, exact CSV identity/home
conflicts, all-or-nothing CSV writes, commit revalidation after preview, denied
self/profile affiliation mutation, audit-failure rollback, and persisted authority
that must remain ineffective for Faculty.

The two disposable-database migration rehearsals upgrade empty and populated
pre-FAC Organization schemas and compare all Catalog/StudentAffiliation values
before/after, then repeat migration. No Student data or routing is backfilled.

Commands (from repository root; backend virtual environment already installed):

```sh
be/.venv/bin/pytest be/tests/test_accounts.py be/tests/test_account_management.py be/tests/test_account_csv_import.py be/tests/test_institutional_identity.py be/tests/test_catalog_services.py be/tests/test_faculty_foundation.py be/tests/test_faculty_concurrency.py be/tests/test_faculty_migration.py be/tests/test_service_catalog.py --reuse-db -q
be/.venv/bin/pytest be/tests/test_capability_dependencies.py be/tests/test_authentication.py be/tests/test_continuity_contract.py --reuse-db -q
be/.venv/bin/ruff check be
be/.venv/bin/ruff format --check be
be/.venv/bin/python be/manage.py makemigrations --check --dry-run --settings=tests.settings
be/.venv/bin/python be/manage.py check --settings=tests.settings
be/.venv/bin/python be/manage.py export_openapi --check --settings=tests.settings
```

Ruff lint/format, migration drift, Django system checks and OpenAPI currency pass.
Two untouched baseline test files needed formatting normalization to pass the
repository-wide formatter; they contain no behavior change.

## Frontend

API generation, ESLint, TypeScript and the final production build pass.
Full node suite: **1,028 passed**, zero failures. The existing Student Home suite
needed a bounded test-only `next/font/google` fixture because Node cannot execute
Next's build-time font transform. Real font rendering still uses the production
build. Generated Orval files remain ignored and are not committed.

Chromium: **11/11**; WebKit: **11/11**, both against the final local production
build. Checks cover Faculty Home at 1440px/390px and 320px with 200% text, no
horizontal overflow, truthful missing affiliation/unavailable Referrals, command
palette exclusion, five direct operational routes blocked before protected queries
mount, reviewed administrator creation, stale affiliation recovery requiring fresh
review, and CSV College references. Browser request assertions detect unintended
clinical, Student or administrative queries from Faculty pages.

```sh
cd fe
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm test
pnpm build
# With the local production app on port 3107 and synthetic SSR fallback on 8000:
COMPASS_UI_ARTIFACTS=/tmp/compass-fac-1-final/chromium node tests/faculty-foundation.browser.mjs
COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-fac-1-final/webkit node tests/faculty-foundation.browser.mjs
```

Committed evidence:

- [Chromium results](browser-evidence/chromium-results.json)
- [WebKit results](browser-evidence/webkit-results.json)
- [Faculty Home desktop](browser-evidence/faculty-home-desktop.png)
- [Faculty Home at 320px, enlarged text](browser-evidence/faculty-home-320-enlarged.png)
- [Managed Faculty affiliation on a phone](browser-evidence/faculty-managed-phone.png)

## Limits

Local checks do not establish institutional acceptance, hosted accessibility,
production/staging readiness, live database upgrade safety, Faculty eligibility,
SAR availability or authority to use a digital Referral Slip. No full all-domain
backend/browser rerun is claimed. Hosted CI status belongs to the PR checks.
FAC-2 policy decisions remain unresolved as recorded in `fac-2-contract.md`.
