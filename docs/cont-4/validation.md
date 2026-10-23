# Executed validation and limitations

Date: 2026-10-24 (Asia/Manila). Verified base `33d645db7fb5599fb916bac36c691539ec5aa675`. Isolated managed worktree and dedicated loopback PostgreSQL 17.11 / Redis. Python 3.13.12, Django 6.1.1, pytest 9.1.1; Node 26.7.0, package-selected pnpm 11.19.0. Dependencies installed from frozen locks/offline stores; no dependency change. Hosted Node 22/container/production role behavior is not inferred from this local runtime.

## Backend runs and honest case accounting

The initial 975-case selection finished with **973 passed / 2 failed in 636.80s**, plus two existing Ninja tuple-response deprecation warnings in ordinary Counseling/Routine tests. Reproduction and root cause:

- `test_openapi_contract::test_all_public_operations_have_stable_unique_ids_and_approved_tags`: generated 416 operations versus the old pinned inventory of 400. The missing 16 are precisely the merged continuity/workflow/Handoff operations.
- `test_openapi_contract::test_policy_enums_and_sensitive_model_fields_are_contract_safe`: the explicit expected capability inventory omitted the five continuity and two Handoff codes.

The canonical exported schema and implementation already agreed. The narrow correction updates the explicit independent expected inventories, preserving uniqueness/tag/capability assertions, and includes the new DTOs in the existing sensitive-field checks. It does not derive expectations from generated output or change the API. An added Handoff contract case pins structural metadata, caller-unsettable identities, strict inputs and absence of a Student Handoff route. These are demonstrated validation defects; **no application security fix, provider activation, migration or contract change was needed**.

The initial new 11-case integration run passed after correcting two fixture request-UUID reuse errors; the request idempotency guard behaved correctly. A final additional exact-scope case distinguishes two real approved Grants, proving a source selected only in the first cannot be read through an independently valid second Grant. Final affected rerun covers the complete 39-case OpenAPI file, four continuity contract cases and 12 integrated CONT-4 cases. A separate adjacent run passed **13/13**: all seven ordinary Student Summary cases, four Follow-Up source/actor boundary cases and two E-Counseling relationship cases.

Final union: **1,001 distinct backend cases PASS**, by `(classname, parametrized name)`, with the two original failures replaced by their affected passing reruns. This is **not one uninterrupted 1,001-case green run** and is not the whole backend suite. Repeats/fixture-repair runs are not added. [Per-case final inventory](evidence/backend-cases.tsv) and [run/class counts](evidence/validation-summary.json) preserve accounting and original failed-run totals.

The integrated additions cover effective Grant/Handoff versus draft/published Student Summary audiences, Student publication versus Handoff denial, two concurrent Handoff reads including one Audit rollback, two valid Grant ciphertext substitution, exact source selection under another valid Grant, and multi-key rotation with corrupt-row/metadata/Audit/Notification/delivery preservation and exact counts-only output.

## PostgreSQL, encryption, migrations and seed

**59 real PostgreSQL concurrency/coordination cases:** 32 selected-release, 14 Handoff, two new Handoff read/Audit races, and 11 foundation PostgreSQL cases. Threads use independent connections and explicitly close them. Existing cases observe PostgreSQL waits, all ten authority-relation DML fences and absent-row REVOKE phantoms; NOWAIT controls inverted source order. Covered races include revoke, capability/role/account/designation/affiliation/College/Campus/source/Handoff/policy change, exact expiry after actual wait, overlaps, competing decisions, draft changes, submission and Audit failure. Expiry advances backend test time after an observed real wait; it is not a wall-clock-duration benchmark.

Fresh graph application to an empty scratch database, real pytest migrations, database system check and `makemigrations --check --dry-run` passed. Cutover/Grant/Handoff populated upgrade and disposable rollback/reapply tests passed; guard/constraint/ContentType/protected-reference checks remain intact. No SQLite, mocked row locks or `--nomigrations` substitutes were used. Canonical 26 baseline hashes and 113 migration/historical-document files are preserved. [Static manifest](evidence/static-manifest.json) includes graph leaves, exact contract hash and all 16 continuity/workflow/Handoff operations.

Full Summary/Routine encryption groups, 19 Handoff configuration cases, 101 Handoff cases, runtime inventory/Compose, seed compatibility, cutoff/recovery/refusal and canonical graph groups passed. The full seed file contributes 49 cases, including full dataset verification, repeat behavior, account/credential preservation, links/affiliations and scoped Summary regeneration. No live dataset or credentials were inspected/changed; no delivery worker was started. All key-bearing test operations use synthetic test configuration/fixtures. Real key restore/custody and deployed secret/mount state remain NOT VALIDATED.

## Commands

All backend commands use `tests.settings` against **separately provisioned empty disposable local services**. Example session endpoints used here: PostgreSQL `127.0.0.1:55444`, synthetic role `compass`; Redis `127.0.0.1:56444`, isolated logical databases. The base DB is `compass_test`; pytest creates `test_compass_test`. Supplemental runs use `cont4_extra` / `cont4_adjacent` and separate Redis DB indices. Never copy these commands into a deployed database session. Existing test settings generate purpose keys; do not supply deployment keys.

```sh
# From be/, with POSTGRES_* and REDIS_* pointing to the isolated services:
uv sync --frozen --offline
.venv/bin/python manage.py migrate --noinput --settings=tests.settings
.venv/bin/python manage.py check --database default --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
xargs .venv/bin/python -m pytest -q --junitxml=/tmp/cont4-backend.xml \
  < ../docs/cont-4/evidence/backend-targets.txt
.venv/bin/python -m pytest -q tests/test_openapi_contract.py \
  tests/test_continuity_contract.py tests/test_cont4_final_security.py
.venv/bin/python -m pytest -q tests/test_student_session_summaries.py \
  tests/test_guidance_followups.py::test_source_classification_cannot_be_downgraded \
  tests/test_guidance_followups.py::test_source_matches_student_and_current_actor \
  tests/test_guidance_followups.py::test_capability_deactivation_and_direct_object_scope \
  tests/test_guidance_followups.py::test_confidential_source_options_do_not_offer_gss \
  tests/test_ecounseling.py::test_capabilities_are_explicit_and_do_not_grant_gss_it_or_head_blanket_access \
  tests/test_ecounseling.py::test_workspace_is_read_only_relationship_scoped_and_does_not_provision_room
.venv/bin/ruff check .
.venv/bin/ruff format --check .
uv lock --check
.venv/bin/python -m compileall -q compass tests
```

Database-free OpenAPI export and `--check` ran with `BaseDatabaseWrapper.ensure_connection` patched to raise. Disk-loaded migration autodetection reported no changes; static baseline/history checks compared bytes to the exact base. The canonical contract hash remains `a697d6ab73234f35a315b317d039a8405ea10590e8e45451a71209c386196bd2`. Generated Orval clients remain ignored and unedited.

```sh
# From fe/:
pnpm install --frozen-lockfile --offline
pnpm api:generate
pnpm typecheck
pnpm lint
pnpm build
node --import ./tests/support/register-tsx.mjs --test --test-concurrency=1 \
  tests/case-coverage.test.mjs tests/counseling-context-confidentiality.test.mjs \
  tests/counseling-encounter-consistency.test.mjs tests/account-cache-ownership.test.mjs \
  tests/portal-shell.test.mjs
node --test --test-concurrency=1 tests/browser-registration.test.mjs
pnpm start --hostname 127.0.0.1 --port 3144
# Against that production server, once with each COMPASS_UI_BROWSER=chromium / webkit:
COMPASS_UI_BASE_URL=http://127.0.0.1:3144 node tests/case-coverage.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3144 node tests/cont4-final-security.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3144 node tests/counseling-context-confidentiality.browser.mjs
# From repository root:
python3 -m unittest discover -s .github/scripts
python3 .github/scripts/backend_ci.py verify
git diff --check
```

## Frontend, static and CI

Orval, TypeScript, ESLint and production build passed (96 static pages). Build-generated `next-env.d.ts` import-path churn was restored. **47 frontend unit cases + four browser-registration cases = 51 distinct Node cases PASS.** Earlier accidental command selection matched only 25 existing cases; that partial run is not represented as the final selection or added to the count. **67 scenarios PASS in each engine: 134 engine outcomes** (41 coverage + six CONT-4 + 20 Summary confidentiality), with mocked synthetic API responses and blocked external providers. [Chromium coverage](evidence/chromium-case-coverage.json), [Chromium additions](evidence/chromium-cont4-final-security.json), [Chromium Summary](evidence/chromium-cont1a-summary-confidentiality.json), [WebKit coverage](evidence/webkit-case-coverage.json), [WebKit additions](evidence/webkit-cont4-final-security.json), [WebKit Summary](evidence/webkit-cont1a-summary-confidentiality.json). Representative mobile screenshots were visually inspected.

Ruff lint/format (824 files), locked dependency check, compile and diff checks passed. CI planner/deployment helper unittest discovery: **60 PASS**, counted separately from backend/Node tests; **186 backend files** bundled exactly once across six full-regression shards. The new test file is in Counseling's bundle with an actually measured JUnit scheduling weight. Automatic browser discovery includes the new suite once per engine/shard.

Hosted workflows filter PR targets to `staging` / `canon/compass-clean-baseline`; this PR targets integration. The actual PR check rollup must be read after publication. **No hosted checks is NOT VALIDATED, not CI-green**. No unrelated workflow is changed or dispatched to manufacture a green status. Final SHA/state/mergeability/check snapshot is reported on the PR and in the agent handoff.

Local raw logs/JUnit/screenshots are under `/tmp/compass-cont4.9AHSvG/`; committed evidence contains content-free counts/case identities and static/lineage inventories. Temporary service artifacts are not institutional records. Real-device/assistive technology, institutional UAT, production contention/role/mount/provider state, real-key recovery and deployed cutover/restore are NOT VALIDATED. Governance/provider/custody/activation gates remain BLOCKED.
