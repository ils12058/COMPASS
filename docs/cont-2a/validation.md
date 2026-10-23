# Executed validation and limits

Executed 2026-10-23 from the isolated CONT-2A worktree at starting integration `1cdad9dd9378b1307140ba92a1023ed0e68a720f`. Fetch before publication confirmed that integration remained at that SHA. `staging` stayed `0a843dae20c01984d0fb9aa46d5eef34102ab386`; `main` stayed `1a9933535a0b8c0cbd7764c35f301e8402f48375`.

## Local backend evidence

Python 3.13.12 / Django 6.1.1, PostgreSQL **17.11 (Homebrew)** and dedicated Redis on randomly allocated loopback ports. The test wrapper supplies `DJANGO_SETTINGS_MODULE=tests.settings`, a dedicated synthetic database name and local service addresses. Tests generate ephemeral purpose keys through existing test settings. No live/deployed database or keyring is read or changed; no worker or external provider runs. PostgreSQL database creation/migrations are real; **no `--nomigrations`** was used.

From `be/`, in that isolated environment:

```sh
python manage.py migrate --noinput
python manage.py check --database default
python manage.py makemigrations --check --dry-run

python -m pytest -q tests/test_continuity.py tests/test_continuity_contract.py \
  tests/test_continuity_migrations.py tests/test_canonical_baseline.py -x \
  --junitxml=/tmp/cont2a-foundation-final.xml
# 124 passed in 60.95s

python -m pytest -q \
  tests/test_accounts.py tests/test_capability_dependencies.py \
  tests/test_account_management.py tests/test_counseling_context.py \
  tests/test_student_session_summaries.py tests/test_routine_interviews.py \
  tests/test_appointment_management_scope.py \
  tests/test_guidance_followups.py::test_source_classification_cannot_be_downgraded \
  tests/test_guidance_followups.py::test_source_matches_student_and_current_actor \
  tests/test_guidance_followups.py::test_capability_deactivation_and_direct_object_scope \
  tests/test_guidance_followups.py::test_confidential_source_options_do_not_offer_gss \
  -x --junitxml=/tmp/cont2a-regression.xml
# 134 passed in 125.85s; one existing Routine Ninja tuple-response warning
```

**258 unique backend cases** in the two final green sets, excluding overlapping preliminary/focused executions. Foundation breakdown: 116 continuity cases, two DB-free contract/provider cases, one PostgreSQL migration rehearsal, five canonical baseline/graph/constraint/history cases. Regression breakdown: Accounts 19, capability dependencies 12, Account Management 25, Context 30, Student Session Summary seven, Routine 24, Appointment management scope 13 and Follow-Up four. Preliminary failures (fixture identity setup, obsolete capability-count expectation, import/CSRF test assertions) were corrected; repeated runs are not additional unique cases. New routes use Ninja `Status` responses.

Coverage includes inactive/unsupported identities with overrides; current Head/designation/capability/override expiry; missing/unapproved/expired/changed policy evidence; unauthorized Acting Head; requester/receiver self-approval; exact source/Student/projection/lifecycle/revision; immutable snapshots including timezone-equivalent dates; reason/interval bounds; exact expiry/scheduled/terminal states; affiliation transfer/lifecycle changes; original-author departure; stale versions; request replay/conflict; forbidden ordinary source reads/mutations despite an approved Grant; scoped pagination/guessed UUIDs; CSRF/cache headers; audit actor spoof/failure rollback and metadata no-decryption/no-ciphertext-query assertions. Spies cover Routine Intake/Evaluation, Inventory, Summary, Referral, Assessment and media retrieval plus the shared decryption primitive.

Real PostgreSQL races cover overlapping/duplicate requests, approval/approval, approval/decline, approval/cancel, stale approval/revoke, revoke/metadata, capability revocation and deactivation. The suite includes actual administrative `set_account_active` and `set_capability_override` flows with synthetic verified-MFA sessions, in addition to the low-level setter's shared User lock. Source contention verifies NOWAIT conflict instead of a reversed-order wait; authority expiry after selection is rechecked. These establish the documented supported lock boundary, not universal coordination with all direct database/organizational/policy writers.

## Migration proof

The fresh dedicated database applied the complete graph from empty. Pytest independently installed the graph while creating its test database. `test_continuity_migrations` moves Counseling back to current integration `0002`, creates unrelated synthetic identities, Encounter, existing canonical encrypted Summary and Audit evidence, applies the new migration, compares every saved row field, and rehearses empty-foundation rollback/reapply with another unchanged-row comparison. It does not decrypt that Summary or reset a retained dataset.

Canonical checks preserve every baseline hash and CONT-1B migration byte, register exactly one additive migration, verify one leaf per app, check declared PostgreSQL indexes/constraints and assert no model drift. Database negative cases exercise positive versions, valid decisions/kinds/reasons, evidence/provenance pairing, finite intervals, exact scope uniqueness/pairs and protected references. Django check and model-state check both passed.

## Contracts and frontend integration

OpenAPI export and `export_openapi --check` passed with `BaseDatabaseWrapper.ensure_connection` patched to raise if called in the export subprocess. Structural comparison against baseline found **no changed existing Counseling or Routine path**, no removed schema/path, six added continuity paths with seven metadata-only operations, and the five new codes added to canonical CapabilityCode. The existing account-override path's capability parameter now references that shared expanded enum instead of repeating its former inline enum; its authorization and request/response behavior remain unchanged.

From `fe/` after a real offline frozen-lockfile installation:

```sh
pnpm api:generate
pnpm typecheck
pnpm lint
COMPASS_API_BASE_URL= NEXT_TELEMETRY_DISABLED=1 pnpm build
```

All passed; ordinary production build generated 95 static pages. Generated Orval clients contain the seven typed operations and remain ignored/uncommitted. No dependency/lockfile or handwritten frontend change is included. Build-generated `next-env.d.ts` route-import path churn was restored to baseline. No user-facing UI changed, so no browser result is claimed or needed for this slice.

## CI selection, static checks and publication boundaries

The three new test files are registered in the Counseling CI suite. Measured final JUnit weights are continuity **47.1s**, contract **0.0s** (rounded measured value) and migration **2.4s**; these are scheduling weights, not standalone benchmark claims. CI planner unit tests: **38 passed**, separately counted from the backend cases above. Planner verification covers all **179 test files** exactly once over six full-regression shards. Migration/model/authority changes retain conservative full-suite selection. Hosted CI status is read from the PR separately; local evidence does not mean hosted CI ran.

Ruff lint and format checks passed for all 16 affected non-migration backend Python files, as did `git diff --check`. Source byte comparison confirms Context resolver/projections/API, ordinary Summary service, Routine service, Appointment access and Follow-Up policy are unchanged. No existing domain predicate accepts continuity as a source-write relationship.

Policy/delegation approval, all-writer/provider synchronization, professional source disclosure adapters, client cache/expiry behavior and institutional UAT remain blockers for later operational activation. No SSH, DigitalOcean operation, deployment, live migration/reset, key provisioning or automatic merge occurred. Dedicated local validation services are stopped after completion. The PR stops open against integration; actual PR/head/mergeability are reported separately.
