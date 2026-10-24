# ORG-0 validation evidence

Source inspected: `origin/integration/ux15-modernization` fetched at
`7522e55c94193a28e2e8c6773c634426be48856c`.
Audit began 2026-10-24; report completed 2026-10-25 (Asia/Manila).
Only `docs/org-0/` is proposed for commit. No runtime test implementation is added.

## Evidence classification

| Class | Evidence / limits |
|---|---|
| VERIFIED CODE FACT | Current models, exact code identity map, canonical writers and consumers, migration graph, capability/MFA checks, UI gates and snapshot fields were read at the pinned SHA |
| TESTED BEHAVIOR | 176 distinct existing pytest cases passed on isolated PostgreSQL; details below |
| PROPOSED DESIGN | All new schema, migration, initialization receipt, concurrency gate, endpoints, capabilities, impact checks, UX and ORG-1–4 completion criteria are unimplemented |
| INSTITUTIONAL DECISION REQUIRED | Authority delegation, policy, activation/retirement remediation, historical-name expectations, rollout and UAT decisions in open-decisions.md |
| UNVERIFIED DEPLOYED STATE | Current deployment image, cron/one-off writers, real catalog counts, real users/grants, academic approvals, live-data readiness, UAT and rollback operability |

## Repository preparation and read-only source audit

Executed from the original checkout before worktree creation:

```sh
git status --short --branch
git fetch origin integration/ux15-modernization
git rev-parse origin/integration/ux15-modernization
git worktree list
git branch --list 'audit/org-0-catalog-authority'
```

The original checkout was `staging` with pre-existing untracked outputs; no file there was edited.
A managed isolated worktree was created at
`/Users/reynantlntno/.codex/worktrees/org-0-catalog-authority/COMPASS`, from the fetched integration
ref, then `git switch -c audit/org-0-catalog-authority` was executed there. No existing integration,
other agent worktree, main or staging branch was changed. The backend interpreter below is reused
read-only from the original checkout; tests/imports execute this worktree's source.

Read applicable repository/frontend guidance and relevant ADRs (017/064/067/099/116), proposal #2
from the saved Fifteen Proposals source, Organization source/migrations/management commands,
Accounts/import/access policy, Inventory, Good Moral, Tracer, Exit/Routine, reports/selectors,
appointments/Counseling/continuity and other scope consumers, deployment/CI/Compose/startup/tasks.
The proposal's staging `0a843dae` findings were treated as older context, never current proof.

Searches included these literal identifiers across the repository, then narrower full-file reads:

```sh
rg -n 'CANONICAL_CAMPUSES|CANONICAL_CAMPUS_CODES|CANONICAL_COLLEGE_IDENTITIES|CANONICAL_PROGRAM_IDENTITIES|CANONICAL_PROGRAM_BY_IDENTITY|canonical_program_metadata|sync_organization_catalog|EXPECTED_CAMPUS_COUNT|EXPECTED_COLLEGE_COUNT|EXPECTED_PROGRAM_COUNT|AcademicClassification|YearLevelPolicyStatus' --glob '!archived/**' --glob '!uv.lock' --glob '!pnpm-lock.yaml'
rg -n 'sync_organization_catalog|organization.bootstrap|CANONICAL_(CAMPUS|COLLEGE|PROGRAM)|canonical_program_metadata' --hidden --glob '!.git' --glob '!archived/**' --glob '!docs/**' --glob '!be/docs/**' --glob '!contracts/**' .
rg -n 'organization\.(Campus|College|Program)|ForeignKey\((Campus|College|Program)' be/compass --glob '*models.py'
rg -n 'sync_organization_catalog|organization.bootstrap|CANONICAL_(CAMPUS|COLLEGE|PROGRAM)|EXPECTED_(CAMPUS|COLLEGE|PROGRAM)_COUNT' .github be/config be/compass/common be/compose.yaml be/compose.staging.yaml be/Containerfile archived --glob '!*.lock'
```

Follow-up searches covered code-based Campus/College/Program filters, literal baseline codes,
classifications, active flags, snapshot fields, student affiliation joins, default/handled/general
Guidance scope, CLI modes, worker/Beat tasks and hidden tracked workflow scripts. An initial broad
search also hit nonexistent optional paths/globs; those search-invocation errors were corrected
with actual paths. They are not failed application checks. The invocation inventory documents
negative findings only within the inspected source; it cannot prove external deployed jobs absent.

## Isolated test environment

Used existing Python 3.13.12 dependencies and a **new** local Homebrew PostgreSQL 17.11 cluster:

```sh
mktemp -d /private/tmp/compass-org0.XXXXXX
/opt/homebrew/opt/postgresql@17/bin/initdb -D /private/tmp/compass-org0.ve8QCW/pg -U compass --auth=trust --no-locale
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /private/tmp/compass-org0.ve8QCW/pg -l /private/tmp/compass-org0.ve8QCW/postgres.log -o '-h 127.0.0.1 -p 56547 -k /private/tmp/compass-org0.ve8QCW' start
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 56547 -U compass compass_org0
```

initdb output was redirected to the temporary directory. The cluster listens only on loopback, on
a dedicated port, with a private socket directory. All tests used `env -i`, explicit local database
settings and `tests.settings`; no repository `.env`, real key, live database credential, SMTP or
Droplet connection was loaded. Test settings generate ephemeral encryption keys and test-only
configuration. pytest creates/migrates/destroys its synthetic test database. These baseline schema
operations are distinct from an ORG migration or operational migration.

`--no-locale` selected SQL_ASCII encoding on this host; production locale/encoding/collation
compatibility is **not** established. The observed PostgreSQL constraint/transaction behaviors are
still the executed baseline evidence; future migration/concurrency rehearsals should explicitly
use UTF8 and deployment-matching locale. The disposable cluster was stopped after validation with
`pg_ctl -D /private/tmp/compass-org0.ve8QCW/pg stop -m fast` (exit 0). No PostgreSQL cluster
configuration or database used by another task was modified. No new dependency installation or runtime-source edit was required.

## Exact test commands and results

All following commands ran from `<worktree>/be`. Each full invocation used this prefix (literal
test-only values, not secrets):

```sh
env -i PATH='/opt/homebrew/bin:/usr/bin:/bin' \
  POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=56547 POSTGRES_DB=compass_org0 \
  POSTGRES_USER=compass POSTGRES_PASSWORD=test-only DJANGO_SETTINGS_MODULE=tests.settings \
  /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
```

Append the following argv to that prefix; stdout/stderr were redirected to the named log beside
each XML in `/private/tmp/compass-org0.ve8QCW/`:

```sh
-m pytest tests/test_organization_catalog.py tests/test_organization.py tests/test_program_inventory_academic_context.py tests/test_capability_dependencies.py tests/test_canonical_baseline.py tests/test_good_moral.py -k 'not real_chromium and not official_f4_pdf_rendering' -q --junitxml=/private/tmp/compass-org0.ve8QCW/focused.xml
```

**TESTED BEHAVIOR:** 136 passed, 8 deselected, 73.25 seconds.

```sh
-m pytest tests/test_appointment_management_scope.py tests/test_institutional_identity.py tests/test_graduate_tracer_graduation_classification.py tests/test_step_up_policy.py -q --junitxml=/private/tmp/compass-org0.ve8QCW/dependencies.xml
```

**TESTED BEHAVIOR:** 32 passed, 33.65 seconds.

```sh
-m pytest tests/test_inventory.py::test_configured_bachelors_year_levels_and_pending_postgraduate_compatibility tests/test_inventory.py::test_submission_rejects_unsupported_bachelors_year_level_saved_in_a_draft tests/test_inventory.py::test_unmodified_or_inactive_program_draft_values_remain_editable tests/test_graduate_tracer.py::test_submission_freezes_response_and_repeat_submit_is_idempotent tests/test_graduate_tracer.py::test_lifecycle_change_blocks_self_service_but_preserves_historical_operational_review tests/test_graduate_tracer_reports.py::test_population_is_submitted_schema_v1_history_and_ignores_later_account_state tests/test_openapi_contract.py::test_core_schemas_and_realistic_error_responses_are_typed tests/test_openapi_contract.py::test_all_public_operations_have_stable_unique_ids_and_approved_tags -q --junitxml=/private/tmp/compass-org0.ve8QCW/compatibility.xml
```

**TESTED BEHAVIOR:** 8 passed, 14.07 seconds. XML `(classname, name)` identities were compared:
176 total cases = **176 distinct cases**, no overlaps, failures, errors or skips. The eight deselected
cases are one real-Chromium Good Moral smoke test and seven official F4 PDF-render scenarios.
Real browser/PDF rendering was intentionally not executed in this source/documentation audit.

| Test file | Distinct passing cases |
|---|---:|
| test_organization_catalog.py | 6 |
| test_organization.py | 18 |
| test_program_inventory_academic_context.py | 8 |
| test_capability_dependencies.py | 12 |
| test_canonical_baseline.py | 5 |
| test_good_moral.py (selected) | 87 |
| test_appointment_management_scope.py | 13 |
| test_institutional_identity.py | 5 |
| test_graduate_tracer_graduation_classification.py | 6 |
| test_step_up_policy.py | 8 |
| test_inventory.py (three selected nodes) | 3 |
| test_graduate_tracer.py (two selected nodes) | 2 |
| test_graduate_tracer_reports.py (one selected node) | 1 |
| test_openapi_contract.py (two selected nodes) | 2 |
| **Total** | **176** |

Evidence XML SHA-256:

```text
focused.xml       bcfeb7823fb535d9eb6758c5693ba07567f412eb763aae337a0a4a77bc6227fd
dependencies.xml  df102bd9d967b55657d8ec9403d45a4b93d66ca8366dafec743a0d8759056dd7
compatibility.xml 9273465d8047fc39ab447787827748bb65b2ad1dfbf5848278955ebf53b4c940
```

The catalog tests demonstrate the existing destructive-reconciliation authority and rollback, not
the future DB-authority design. Good Moral tests include F4/F6 eligibility, history, issuance,
request replay and saved rendering-provenance behavior; the omitted real-browser cases are not
counted as passes. Existing baseline tests inspect graph, immutable hashes, real PostgreSQL
constraints and lineage checks. No proposed ORG-1 migration is available to rehearse yet.

## Static/contract and documentation checks

Using the same clean-environment prefix:

```sh
manage.py makemigrations --check --dry-run --settings=tests.settings
manage.py export_openapi --check --settings=tests.settings
```

Both exited 0: **No changes detected**; **OpenAPI contract is current**. These are check-only commands;
no migration or generated API output was written.

All source links were generated against the inspected SHA and checked for existing source paths
and valid matching line anchors. Documentation QA passed: 11 required files, 202 pinned source
links (171 distinct anchors), 24 local document links and balanced code fences. The final staged
diff is restricted to the eleven requested Markdown files; `git diff --cached --check` passed
before commit. Commit SHA and final worktree/PR state are reported in the agent handoff,
not self-referentially embedded in the commit.

## Hosted CI and unexecuted work

The inspected Backend targeted and Frontend targeted pull-request workflows target `staging` and
`canon/compass-clean-baseline` with source-path filters. They do not target this integration/docs PR.
Backend full is a separate workflow. No workflow is dispatched by ORG-0; the final PR check listing
must be reported as observed (absence of checks is not a CI pass).
Sources: [.github/workflows/backend-targeted.yml:9](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/backend-targeted.yml#L9);
[.github/workflows/frontend-targeted.yml:4](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/frontend-targeted.yml#L4);
[.github/workflows/backend-full.yml:16](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/backend-full.yml#L16).

Not executed: proposed metadata/backfill migration, proposed initializer/repeated deployment,
new CRUD/optimistic concurrency or deactivation races, full seeder, broad full suites, authenticated
browser integration, screen-reader/zoom/manual accessibility, actual certificate browser/PDF QA,
institutional UAT, deployed-state inspection, live backup/recovery, external email or notifications.
These limits are explicit ORG-1–4 handoff gates rather than invented passing results.

Final scope confirmation: documentation only; no runtime/source/API/frontend/capability/grant change,
new migration, StudentAffiliation migration, student lifecycle mutation, historical-record rewrite,
policy activation, real institutional data operation, SSH, deployment or automatic merge.
