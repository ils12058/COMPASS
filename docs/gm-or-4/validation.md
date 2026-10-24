# GM-OR-4 validation record

Date: 2026-10-24 Asia/Manila. Exact fetched base: `8872db0a7325239ccab6d6f0ca3f68ffd312de8c`; no intervening changes. Implementation/test candidate: `9ab9cb414c41d886e6b3d78d70a5c2213ba033e6`. Original checkout stays on staging; work occurred only in the managed `gm-or-4-final-validation/COMPASS` worktree on `audit/gm-or-4-final-validation`.

## Environment and command conventions

Local evidence/log root is `/tmp/gm-or-4/`. `setup.py` initializes a new PostgreSQL 17.11 cluster and disposable Redis bound to 127.0.0.1 on free nondefault ports under `synthetic-*`, creates only synthetic databases and writes a private local environment JSON. No deployed environment files are loaded. `run.py` is a local wrapper executing `/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python` with that clean environment and this worktree's `be/` as cwd/PYTHONPATH. The interpreter is Python 3.13.12 / Django 6.1.1 / pytest 9.1.1 / psycopg 3.3.5. Node 26.7.0 and actual pnpm 11.26.0 use frozen repository dependencies; package.json declares pnpm 11.19.0. No dependency/lockfile change was made.

`run_integration.py` adds `POSTGRES_DB=gm_or_4_api_synthetic` (pytest creates `test_gm_or_4_api_synthetic`), `COMPASS_GM_REAL_FRONTEND_URL=http://localhost:3164`, `CSRF_TRUSTED_ORIGINS=http://testserver,http://localhost,http://localhost:3164`, `COMPASS_GM_RECOVERY_REHEARSAL=1`, and `COMPASS_GM_PG_BIN=/opt/homebrew/opt/postgresql@17/bin`. The normal test settings generate ephemeral content keys. These wrappers/configuration are local execution artifacts, not operational scripts or committed application settings.

For reproduction in another disposable environment, configure equivalent loopback `POSTGRES_*` and isolated `REDIS_*` URLs, `DJANGO_SETTINGS_MODULE=tests.settings`, optional `CELERY_*` URLs, and the explicit opt-in variables above; run the commands below with that environment's Python. Never supply deployed credentials/databases. No actual approved policy is installed: pytest owns the fictional resolver and ephemeral accounts/grants. The optional browser and restore cases skip in ordinary backend runs unless explicitly configured; CI registration does not falsely imply those seams run hosted.

## Executed commands

From the isolated repository root, unless `be/` is specified:

```sh
git fetch origin integration/ux15-modernization
git log --oneline 8872db0a7325239ccab6d6f0ca3f68ffd312de8c..origin/integration/ux15-modernization
git rev-parse origin/integration/ux15-modernization
# Managed worktree created via Codex create_worktree, then:
git switch -c audit/gm-or-4-final-validation
CI=true pnpm --dir fe install --frozen-lockfile
python3 /tmp/gm-or-4/setup.py
# From be/:
python3 /tmp/gm-or-4/run.py manage.py migrate --noinput
# From repository root:
pnpm --dir fe api:generate
pnpm --dir fe build
COMPASS_API_BASE_URL=http://localhost:8764 pnpm --dir fe build
pnpm --dir fe start --hostname 127.0.0.1 --port 3164
```

The second optimized build deliberately includes only the loopback API proxy for real integration. The UI test-mode flag remains its ordinary false default. All browser/API data are disposable or mocked, never institutional.

The first coherent existing backend selection (from `be/`, using `run.py`) passed **548/548** in 355.52s. After harness development, the three new modules passed **36/36** together in 61.90s. These are **584 distinct pytest cases**, not 548 plus every focused rerun. The final combined run on the committed implementation candidate passed **584/584**, with zero failures/errors/skips, in 328.776s; it is recorded in [results](evidence/results.json), using:

```sh
python3 /tmp/gm-or-4/run_integration.py -m pytest \
  tests/test_good_moral.py tests/test_good_moral_assisted.py \
  tests/test_good_moral_preparation.py tests/test_good_moral_receipts.py \
  tests/test_good_moral_receipt_migration.py tests/test_good_moral_verification.py \
  tests/test_good_moral_verification_concurrency.py \
  tests/test_good_moral_verification_migration.py \
  tests/test_good_moral_authenticated_integration.py \
  tests/test_good_moral_recovery_rehearsal.py tests/test_good_moral_final_preservation.py \
  tests/test_canonical_baseline.py tests/test_openapi_contract.py \
  tests/test_audit.py tests/test_accounts.py tests/test_privacy_release_audit.py \
  tests/test_notifications.py tests/test_feedback.py \
  -q --reuse-db --liveserver=localhost:8764 \
  --junitxml=/tmp/gm-or-4/combined-final.xml
```

No complete repository backend/frontend suite was run. This is the stated Good Moral and dependency selection. The two real browser cases and 41 independent-connection cases are already included in the 584 total. The latter are 15 retained receipt coordination cases, 23 retained inspection coordination cases and three new cancellation/preparation/replacement cases. Transaction fault injections are reported separately in the 25-item matrix, not relabeled as independent distributed races.

```sh
# From be/:
python3 /tmp/gm-or-4/run.py -m ruff check .
python3 /tmp/gm-or-4/run.py -m ruff format --check .
python3 /tmp/gm-or-4/run.py manage.py check
python3 /tmp/gm-or-4/run.py manage.py makemigrations --check --dry-run
python3 /tmp/gm-or-4/run.py manage.py export_openapi --check
python3 /tmp/gm-or-4/run.py -m pytest ../.github/scripts/test_backend_ci.py -q
# From repository root:
pnpm --dir fe lint
pnpm --dir fe typecheck
node --import ./fe/tests/support/register-tsx.mjs --test \
  fe/tests/good-moral-receipt.test.mjs fe/tests/good-moral-preparation.test.mjs \
  fe/tests/good-moral-print.test.mjs fe/tests/good-moral-assisted.test.mjs \
  fe/tests/good-moral-request-standardization.test.mjs fe/tests/account-cache-ownership.test.mjs
```

For each `ENGINE=chromium` and `ENGINE=webkit`, each of these was executed with `COMPASS_UI_BASE_URL=http://localhost:3164 COMPASS_UI_BROWSER=$ENGINE`:

```sh
node fe/tests/good-moral-receipt.browser.mjs
node fe/tests/good-moral-print.browser.mjs
node fe/tests/good-moral-receipt-correction.browser.mjs
node fe/tests/good-moral-request.browser.mjs
node fe/tests/good-moral-assisted.browser.mjs
```

Each full suite passed: **37 + 24 + 5 + 2 + 13 = 81 per engine**, all MOCK-UI. The separate REAL-BROWSER pytest cases are Chromium-only. Node: **55 passed**, including six account-cache ownership cases. CI planner: **38 tests and 19 subtests passed**, separately counted. Ruff, final format, Django checks, migration drift, canonical graph/hash tests, OpenAPI, Orval, ESLint, TypeScript and optimized builds passed. Build-generated `fe/next-env.d.ts` was restored to the committed source followed by a passing typecheck; it is not a product change.

Local browser screenshots/results use the existing harness's temporary `compass-good-moral-*` directories. Current run logs in `/tmp/gm-or-4/browser-*.log` and current results determine counts; old files named `*-failure.png` from earlier tasks in the shared temporary directory are not evidence of this run. Current 320px Chromium and 768px WebKit/200% root-text screenshots were visually inspected; no manual keyboard/device/native zoom claim is made. The committed case inventory retains safe test names/statuses only, not tokens, raw request bodies or environment secrets.

## Development failures and repairs

All fixes were to **new test harness code**; no application defect/fix was established. Initial test assertions used Notification `user` rather than `recipient`, an invalid REVOKE spelling during draft construction, a guessed owned-detail path, and missing required issuance payload tokens. Tests now use canonical fields/routes, valid issuance payloads and assert exact permission denials (schema refusal alone is not counted). Long OR PDF text wraps, while issuer text is uppercased by the supported presentation; assertions compare whitespace-normalized receipt text and case-normalized issuer text without changing saved facts. The live Playwright loop initially caused Django synchronous-ORM rejection; browser-time database assertions now run on an independent managed thread/connection rather than disabling Django async protection. Identity lookup now uses the actual uppercase canonical key. New cancellation races use the authorized Counselor, the canonical cancellation Audit action and the exact stale-preparation conflict. Imported fixtures include their explicit provider fixture. The restore comparison initially mixed Django string JSON decoding with psycopg object decoding; both now compare full PostgreSQL `to_jsonb(row)::text` with UTC session serialization, retaining every field.

These failed draft runs are not added to passing distinct counts. The final new-module run passed all 36 cases. No failed browser scenario or security assertion was removed, no guard was disabled by new code, and no retry/authority/policy boundary was relaxed.

## Hosted CI and limits

Existing targeted/full workflow PR filters name `staging` and `canon/compass-clean-baseline`, excluding this integration base. No trigger or manual dispatch was changed to manufacture hosted evidence. Exact PR HEAD checks/workflows are read after PR creation and reported in the handoff. No hosted run must be described as passed when none exists.

Engineering/security/recovery verdicts and unexecuted cases remain explicit in [final assessment](final-assessment.md), the [25-item matrix](identity-and-concurrency.md), and the [human boundary](frontend-and-accessibility.md). No production performance, privileged-owner resistance, physical authenticity, real policy approval or institutional UAT is claimed.

All test-owned local servers are stopped at final handoff. No merge/deployment/SSH/live inspection/import/migration, real grant/fee activation or production reset occurred.
