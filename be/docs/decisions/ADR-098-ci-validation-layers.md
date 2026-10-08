# ADR-098: CI validation layers: targeted pull requests, full staging regression, gated deploy

## Status

Accepted.

## Context

`Backend targeted validation` was targeted only by its path trigger. Every backend pull request ran
`pytest tests`. That was 3,016 tests (the 2,983 cited earlier is from an older count) in one serial
job, and pytest alone took about 1 h 40 min. Setup was about a minute of each run. Every pull
request paid the full regression cost, the frontend workflow did not run the frontend tests, and
staging deployment did not depend on any test result.

## Decision

COMPASS pull requests get fast, dependency-aware validation. Complete regression coverage is still
required, for the exact staging revision, before deployment.

### 1. Pull request: `Backend targeted validation` (`backend-targeted.yml`)

- **`prepare`** runs:
  - The static and migration checks: lock, Ruff format and lint, `compileall`,
    `makemigrations --check`, migrate, and Django check.
  - The OpenAPI generate, sync, and check, then `git diff --check`.
  - Test selection.
- OpenAPI exact-head sync behaves as before:
  - A same-repository pull request whose generated contract differs gets one bot commit.
  - The job then dispatches validation of the new head. Dispatched runs never commit, so there is
    no loop.
- **Selection** uses `.github/scripts/backend_ci.py select`:
  - It diffs the exact pull-request head against its merge base with the base branch, so GitHub's
    synthetic merge commit is never what gets validated.
  - It maps each changed path to an area and each area to explicit test bundles.
  - It logs the changed areas, the selected bundles, and the selected files.
- **`tests`** runs the selection in one to six shards. Each shard has its own PostgreSQL and Redis.
  The shard count grows with the selection's measured runtime.
- **`targeted-backend`** is the single required result.

#### Bundles

The always-run `safety` bundle is cheap. It covers system-wide invariants:

- settings readiness and institutional time
- health and build metadata, request context
- lock scoping and database-error mapping
- the audit trail
- capability dependencies and step-up policy
- the meta endpoint and the typed OpenAPI contract

Domain bundles come from the real import topology:

- each domain's own tests
- the tests of domains that import it
- the cross-domain test files that exercise it

For example, an Inventory change also runs the Counseling, Routine Interview, Exit Interview, Good
Moral, Student Support, report, and Inventory-encryption tests.

`verify` fails CI if any test file is in no bundle, a bundle names a missing file, or a `compass/`
app has no mapping.

#### Fail-safe expansion to the complete suite

Any of these selects the complete suite:

- Shared infrastructure:
  - `accounts`, `authentication`, `audit`, `common`, `api`
  - `confidential_data`, `notifications`, `organization`
  - the Celery task registry
- `be/config/` and any `migrations/` directory.
- `pyproject.toml`, `uv.lock`, `manage.py`.
- Test configuration: `conftest.py`, test settings, the test package.
- Unrecognized `be/` paths, unrecognized integration clients, and test helpers that no test module
  imports.

A changed test module, or a changed helper, selects itself and every test module that imports it,
transitively.

### 2. Staging: `Backend full regression` (`backend-full.yml`)

The workflow runs:

- on every push to `staging`;
- on pull requests that change it or `.github/scripts/`, so changes to selection and sharding are
  proven on the complete suite before merge;
- on demand for any branch. GitHub allows manual dispatch only once the workflow file is on the
  default branch.

Every run checks out the exact commit it reports as `head_sha`. For a pull request that is the head
commit, not GitHub's merge commit. The workflow has four parts:

- **`plan`** proves that every `be/tests/test_*.py` runs in exactly one shard.
  - Coverage holds by construction: shards are computed from the files on disk, and a new file
    gets a default weight.
  - The two slowest encryption files are split round-robin by node ID. They use only
    function-scoped fixtures, so the split adds no duplicate setup.
- **`static`** repeats the static checks. It verifies the committed contract but never writes it.
- **Six `shard` jobs** each have their own runner, PostgreSQL, and Redis.
- **`full-regression`** passes only if every part passed. It also publishes measured per-file
  durations for rebalancing.

The workflow is read-only. A newer staging push cancels the regression of the revision it
replaces; a cancelled run never satisfies the deploy gate.

pytest-xdist is not used. The tests share PostgreSQL, Redis, and transactional and
concurrency-sensitive state, so parallelism comes from isolated jobs first. Chromium installs in
every test job (about 20 s), because document rendering is spread across many domains.

### 3. Deployment: `Deploy staging backend`

The workflow already verifies that `origin/staging` equals `expected_staging_sha`. After that check,
`require_full_regression.py` requires a completed, successful `Backend full regression` run whose
`head_sha` is exactly the deploy SHA. The job's only added permission is `actions: read`. These
never satisfy the gate:

- an older staging revision
- a pull-request head
- a running run
- a failed or cancelled run

Dispatch the deploy with `--ref staging`. A copy of this workflow on another branch only has the gate
once that branch contains this change.

### Frontend

`Frontend targeted validation` adds a parallel `frontend-tests` job that runs `pnpm test`: about
340 `node:test` tests, around 15 s, after API generation.

- The tests run on Node 26.7.0, the release they are maintained on. Node 22.18's synchronous
  module hooks cannot load Next's CommonJS entry points through the TSX test loader.
- Lint, typecheck, and the production build still run on the pinned 22.18 runtime.

## Consequences

"Targeted" never means a test is skipped for good: the complete suite is authoritative before every
deployment. Merging can happen before the staging regression finishes; deploying cannot. Keep the
bundles in `backend_ci.py` current when adding tests or cross-domain dependencies; `verify` reports
unmapped files.

To rebalance shards, copy the `backend-test-durations` artifact of a full run to
`.github/scripts/backend_test_durations.json`.
