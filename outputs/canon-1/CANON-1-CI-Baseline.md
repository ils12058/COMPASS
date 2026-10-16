# CANON-1 CI baseline and checkpoint A

Verified base: `d353108d1f757386b9020c4d1297e081258d2e4e`, 2026-10-16 (Asia/Manila).

## Current staging workflow

[Backend full regression run 38852985121](https://github.com/ils12058/COMPASS/actions/runs/38852985121)
failed at this exact base SHA. Retrieved failed-job logs identify:

- `plan`: CI self-tests fail because test_domain_activity.py, test_good_moral_assisted.py and
  test_graduate_tracer_graduation_classification.py belong to no bundle.
- `static and contract`: Ruff formatting stops on eight files. Its subsequent lint, migration
  and contract commands did not run in that job. Locally, Ruff separately reproduces 38 lint
  findings. The committed format/lint baseline outputs retain exact locations.
- All six shards were skipped because `plan` failed. Static and shards are independent jobs;
  static failure alone does not skip shards. The full-regression aggregator fails closed.

The actual workflows are backend-full.yml, backend-targeted.yml and frontend-targeted.yml.
There is no backend-full-regression.yml. The recovered audit's claimed eight-shard/62-failure
run is not accepted as evidence; this slice runs its own reproducible checks.

## Infrastructure changes

Backend: register the three files in Activity, Good Moral and Graduate Tracer/Reports bundles;
include My Activity regression coverage for its source-domain imports; select the complete suite
on model edits (including retention_models, Graduate Tracer participation and model packages); discover both pytest naming
patterns recursively; verify split parts cover each collected node once. Existing settings,
migration, unrecognized path, always-run safety and transitive helper selection remain intact.
Validation workflows also cover the future `canon/compass-clean-baseline` target. Contract-sync
redispatch preserves the actual PR base rather than assuming staging and explicitly runs frontend
validation for the synchronized contract head. Frontend concurrency cancels superseded runs.
The auto-sync dispatch path is guarded by self-tests; it was not triggered because this contract
already matches the generator. Deployment remains manual
and its exact staging-revision guard is unchanged.
All 167 current files are planned exactly once across six full shards, including every configured
split part. New unit tests prove the previously missing discovery/selection cases.

Frontend: the baseline has 29 unit files (all matched by the existing tests/*.test.mjs script)
and 31 browser files. Eight browser files appear in no package script; three more are omitted
from CI regressions. [Machine inventory](evidence/discovery-baseline.json) lists every file.
The new runner discovers all browser files recursively, runs each on Chromium and WebKit,
logs each suite independently, continues after suite failure and returns failure if any suite
fails. CI uses four nonempty shards per engine with fail-fast disabled. Discovery/sharding and
failure propagation have unit tests. No historical browser exclusion remains.
The navigation-attention suite now uses the shared artifact directory and awaits finish, making
its output usable in CI without writing to a developer's private workstation path.

All 38 inherited Ruff findings and eight formatting failures are repaired without changing
validation messages or assertions. The unused guidance-message assignment is removed while
preserving the send call and its effect on unread counts.

## Locally reproduced validation

Isolated PostgreSQL 17 on 127.0.0.1:55463 and Redis on 127.0.0.1:56391 were initialized in a
unique temporary directory. No existing database, Redis instance, live worker, storage or provider
resource is reset. Backend tests use tests.settings with explicit isolated endpoint overrides;
keys are ephemeral test settings. Frontend browser fixtures target localhost:3117 and synthesize
API/provider responses. The Next development backend proxy points at an unused loopback port.

| Check | Result |
| --- | --- |
| CI selection/deployment guard unit tests | 42 passed |
| backend_ci.py verify | 167 files, six shards, exactly-once coverage passed |
| Ruff formatting / lint | Passed across backend |
| Locked dependencies | Installed with uv sync --frozen; lock check passed |
| Current-history fresh migrate | Passed on isolated PostgreSQL |
| Django migration drift | No changes detected |
| Django system checks | No issues |
| OpenAPI export --check | Current; no contract changes |
| Frontend API generation | Passed with locked Orval |
| Frontend ESLint / typecheck | Passed |
| Next production build | Passed |
| Frontend unit baseline / reviewed rerun | 763/764 before changes; 766/767 after registration tests; same one application failure |
| New browser registration tests | Three passed; 31 focused registration/feature checks passed |
| Targeted backend regression | Complete six shards: 1,278 passed, seven failed, zero skipped |
| Full backend regression | Complete six shards: 4,648 passed, 41 failed, 22 errored, zero skipped |
| All browser suites on both engines | Complete CI: 26/31 suites passed per engine; 25 individual cases failed |
| Exact six-shard CI execution | All six finished in run 38859891816; 4,711 unique case IDs match collected function/parameter counts |

The frontend failure names fe/src/features/good-moral/good-moral-assisted-request.ts: its
invalid_good_moral_request path displays readApiErrorMessage directly. Classification: a real
frontend copy/transport boundary violation, not a reason to weaken the test. Fix in CANON-1B.
Additional backend/browser failures must be classified from completed reports, not copied from
historical audit assertions.

## Remaining CI and application work

The base duration table lacked observations for 36 files and used the supported 30-second
fallback. All 167 files now have measured timings from the six complete JUnit reports in run
38859891816; the plan is rebalanced and its self-tests pass. See evidence/duration-provenance.json.
Seeder setup failures shorten current execution, so refresh timings again after regression repair.
No future timings or successful dataset results are inferred from this failing baseline.

Checkpoint A establishes discovery and mandatory execution; it is not application acceptance.
All required application tests remain registered and failures remain visible. CANON-1B requires
review/merge of this infrastructure before producing an independent ordinary PR on its repaired
baseline. Exact-revision full regression remains required for deployment. No check, security
assertion, browser engine or deployment gate was removed.

See [regression report](CANON-1-Regression-Report.md) for every completed browser failure,
the development/production printing comparison and confirmed backend fixture failures.
