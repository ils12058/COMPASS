# FAC-2 validation and review evidence

Validation date: 2026-10-31. Base is FAC-1 merge `1778359f`; target is
`integration/ux15-modernization`. These are local technical checks using synthetic
identities, temporary approval fixtures and PostgreSQL. No institutional approval,
UAT, deployment or live activation is established by them.

## Domain and compatibility coverage

Consolidated fresh-database result: **415 passed in 298.72 seconds**. Django checks,
migration drift checks and canonical OpenAPI freshness checks also pass.

The consolidated run starts with a newly created test database and covers Faculty
intake/foundation, Accounts/Account Management/capability dependencies, canonical
Referrals and confidential-content encryption, Referral/Call Slip lifecycle and
issuance provenance, Guidance Follow-Ups, institutional forms, Notifications,
OpenAPI and historical Organization/Referral migration rehearsals.

New FAC-2 cases verify CAS Faculty → CCMS Student, default policy denial, bounded
capability eligibility, exact-ID uniform negative responses, explicit approved
scopes, actor/IP rate bounds and fail-closed limiter outages. They exercise strict
request rejection, real session revocation/deactivation, current role/home/Student
identity/placement, confirmation signature/expiry/foreign actor, stable replay and
changed-payload conflict, saved-form replay, Philippine reference year, and expiry
while waiting for reference allocation. Own queries exclude foreign/GCO/voided
records and never return a reason, contact data, GCO actions or clinical outcomes.
Faculty cannot use GCO detail/PDF or mutation endpoints. Submission creates no
receipt, Action, Follow-Up, Appointment or Notification.

A supplemental final run: **58 passed in 28.26 seconds**. It includes the explicit out-of-policy negative and GCO
mutation-denial cases, GCO processing of a Faculty-origin record, and FAC-1's
unchanged concurrency/migration suites. GCO status/action/void processing retains
the original encrypted reason/referrer and immutable origin; own DTOs disclose no
new operational facts and omit the record after void.

Ten dedicated PostgreSQL concurrency cases use independent connections and observe
an actual `pg_stat_activity` lock wait. Role change, deactivation, Faculty home
change and Student placement change race against submission in both commit orders.
The losing stale submission is denied; a submission that commits first preserves
its original provenance. Same-key contention creates once and replays once. A
barrier starts GCO and Faculty at the shared annual allocator together, yielding
two unique canonical references without a form/counter deadlock.

Empty and populated disposable-database upgrades compare historical Referral
fields before/after, preserve null authenticated origin and invent no Audit events.
A historical-schema writer still inserts after upgrade using the database's
`LEGACY_UNSPECIFIED` default. Repeated migration is safe. Reversal with a real
synthetic Faculty submission is refused, preserving its provenance. PostgreSQL
constraints/trigger reject provenance rewrites, and a failed Faculty Audit rolls
back ciphertext, both creation events and the annual counter.

The existing GCO suite covers creation, original idempotency, current Student
College scope, status/action semantics, void safeguards, saved historical forms,
source PDF rendering and privacy release auditing. Canonical encryption tests
also cover binding, corruption, rotation and non-disclosure after authorization
denial. No unrelated source PDF or UX implementation is modified.

## Reproduction

From `be/`, after installing the repository's locked dependencies and starting its
test PostgreSQL/Redis services:

```sh
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
.venv/bin/python manage.py check --settings=tests.settings
.venv/bin/pytest --create-db --reuse-db -q tests/test_faculty_referrals.py tests/test_faculty_referral_concurrency.py tests/test_faculty_referral_migration.py tests/test_faculty_foundation.py tests/test_accounts.py tests/test_account_management.py tests/test_capability_dependencies.py tests/test_referrals.py tests/test_referral_confidential_content_encryption.py tests/test_referral_call_slip_lifecycle.py tests/test_call_slips.py tests/test_call_slip_issuance_provenance.py tests/test_guidance_followups.py tests/test_institutional_forms.py tests/test_organization_policy_migration.py tests/test_openapi_contract.py tests/test_notifications.py
.venv/bin/pytest --reuse-db -q tests/test_faculty_referrals.py tests/test_faculty_concurrency.py tests/test_faculty_migration.py
```

From repository root: `be/.venv/bin/ruff check be`,
`be/.venv/bin/ruff format --check be`,
`be/.venv/bin/python -m compileall -q be/compass be/tests`,
`python3 -m unittest discover -s .github/scripts`,
`python3 .github/scripts/backend_ci.py verify`, and `git diff --check`.
CI registry coverage is 206 test files, each assigned exactly once across six
full-regression shards; the CI selector's 60 self-tests pass.

From `fe/`: `pnpm api:generate && pnpm lint && pnpm typecheck && pnpm build`, then
`pnpm test`. API generation, ESLint, TypeScript and the production build pass;
all **1,028 frontend unit tests pass**. Generated Orval output is ignored and no
frontend application source is changed. FAC-3 owns the new workflow/browser tests.

## Hosted and inherited CI limits

The integration branch is outside the automatic PR triggers for these targeted
workflows, so hosted validation must be dispatched explicitly for this branch.
A passing local targeted run must not be described as a full hosted backend or
browser pass.

At the parent FAC-1 head, [backend run 41204815181](https://github.com/ils12058/COMPASS/actions/runs/41204815181)
failed five regression shards after its repaired prepare step. The inspected first
shard reports a pre-existing privacy-notice query-budget failure in
`test_notice_family_projects_current_and_draft_revisions_without_n_plus_one`
(expected at most seven queries, observed eight; 1,010 passed, one skipped in that
shard). That owning privacy-notice implementation is outside FAC-2.

FAC-1's [frontend run 41204115567](https://github.com/ils12058/COMPASS/actions/runs/41204115567)
also has unchanged `ux-p1.browser.mjs` action-layout assertions expecting former
48px icon surfaces, as recorded in its validation document. FAC-2 changes no UI
source or those assertions. These inherited failures are separate from FAC-2
technical results and do not establish current release readiness.

For future deployment compatibility and outstanding decisions, see
[the handoff](handoff.md#deployment-compatibility-for-later-authorized-work) and
[the policy register](policy-and-privacy.md#institutional-decision-register).
