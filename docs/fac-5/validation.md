# FAC-5 validation evidence and reproduction

Use [preflight](preflight.md) for exact baseline and excluded invalid local harness runs,
and [CI matrix](ci-failures.md) for failure ownership and preserved assertions.
The implementation PR records the exact submitted implementation SHA and hosted links.
A job is not accepted from another SHA, an incomplete run or a successful subset of jobs.

## Local backend evidence

The inherited backend stabilization run verified the privacy budget, lock scope, realtime
revocation and summary/continuity protections. Its initial forward-rehearsal fixture defect
was corrected, then the isolated rehearsal passed. Across final unique cases the current
safe [backend report](evidence/backend-local.json) records **472 passes**, including the
legacy Referral/PDF, Call Slip, Follow-Up, OpenAPI, canonical and Audit compatibility run.

The clean-created consolidated FAC-1–4 run passed **161 tests**, including the new actual-
session/CSRF cross-College lifecycle and 20 direct protected API boundaries. Two additional
cases pass for an unsupervised GSS and a genuinely expired session created at a past time
(keeping the database's expiry-after-creation invariant). Existing negative/current-policy,
role/activity/home/Student placement, stale/duplicate/void and actual PostgreSQL race tests
are retained. The integration case verifies annual reference/counter stability, encryption,
actual receipt/closure actor/time, exact owned projection and unchanged source on replay.

Fresh test database installation applies all current canonical/additive migrations. FAC-1,
FAC-2 and FAC-4 suites exercise their own actual prior-schema populated upgrades and refusal
to discard immutable Faculty history. The postbaseline rehearsal now uses an owned disposable
PostgreSQL database and forward recovery, never reversal of the shared database or editing
Organization 0002. Original-column/ciphertext comparisons and historical-column reads are
not a claim that every old application binary is operationally compatible.

Backend Ruff lint/format, whitespace, canonical/CI inventory and migration/contract checks
remain required. The planner registers all **210 test files** exactly once. The historical
migration files and canonical manifest are unchanged by FAC-5. The exact-head hosted static
job independently checks drift, fresh migrate, Django check and current OpenAPI.

## Browser and frontend evidence

**1,032 frontend unit tests pass.** API generation, ESLint, TypeScript, a normal production
build and the separate loopback-only synthetic browser build pass. Normal builds bake the
fake-call seam off; runtime environment changes cannot activate it. No generated client is
manually edited or committed and no API DTO changes are introduced by this slice.

The safe [browser report](evidence/browser-local.json) records **762 passing checks**, 381 per engine, from
both Chromium and WebKit. The expanded Faculty/GCO suite has **108 cases per engine**:
all three persisted Faculty states in Home/list/detail at 320/390/768/1024/1440px and
100/200% text, GCO closure review at those widths/scales, role/privacy/availability errors,
canonical stale/uncertain result recovery, keyboard/dialog/status semantics and origin
filtering. No overflow assertion is removed. The old 35-case FAC-3 and 11-case FAC-1
regressions run in each engine as well.

The corrected inherited suites pass per engine: E-Counseling Call 40, information hierarchy
18, UX-P2A six and user copy 44. Their new assertions retain meaningful accessibility,
resource links, read-only/no-mutation, privacy, preserved input and no-automatic-retry
boundaries. The real narrow-call defect is fixed without hiding identity or controls.
The expanded 200% run also exposed and corrected actual available-width rail/facts/status
wrapping defects; these are scoped layout corrections, not a redesign.

The first complete hosted frontend run also exposed persistent-call save-label/status,
UX-P1 action/rail, WebKit public-popover focus and test-triggered hard-reload races. The
corrected complete suites pass in both engines: runtime 17, P1 16, public shell 21, email
change 11 and notification email/auth 21 per engine. Public Escape explicitly closes its
native popover and restores the real trigger; an Appointment rail width correction retains
the original two-line label check. Test reloads use the existing bounded settling helper,
without suppressing page errors or weakening auth/session assertions.

Actual backend browser proof uses existing disposable fixture infrastructure with actual
sessions, CSRF and PostgreSQL: CAS Faculty submission, commit/lost response, intervening
CCMS GCO acknowledgment, deliberate identical-key/body canonical replay, explicit receipt/
closure, safe owned tracking, wrong owner/role denial and authoritative GCO filtering.
All eight actual-backend cases and 25 existing Call Slip permission cases pass in each
engine and are included in the report. Real providers remain unavailable throughout normal
application code. Owned fixture/server cleanup is verified before handoff.

OS light/dark preference, reduced motion, keyboard interaction, focus return, long synthetic
names, loading/empty/error and slow/lost response cases are exercised. Intentional light
application styling is retained. Physical devices, real assistive technology and actual
institutional participant sign-off remain outstanding; automated labels/status/dialog
semantics do not constitute screen-reader UAT.

## Reproduction

From `be/`, run shared-default database pytest processes sequentially:

```sh
.venv/bin/pytest tests/test_privacy_governance_contract.py tests/test_lock_scope.py tests/test_realtime_tickets.py tests/test_postbaseline_upgrade.py tests/test_student_session_summary_cutover.py tests/test_continuity.py --reuse-db -q
.venv/bin/pytest tests/test_faculty_foundation.py tests/test_faculty_concurrency.py tests/test_faculty_migration.py tests/test_faculty_referrals.py tests/test_faculty_referral_concurrency.py tests/test_faculty_referral_migration.py tests/test_referral_administration.py tests/test_referral_administration_concurrency.py tests/test_referral_administration_migration.py tests/test_faculty_integration_assurance.py --create-db --reuse-db -q
.venv/bin/pytest tests/test_referrals.py tests/test_call_slips.py tests/test_guidance_followups.py tests/test_openapi_contract.py tests/test_canonical_baseline.py tests/test_audit.py --reuse-db -q
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
```

From `fe/`, generate/lint/typecheck/test and build ordinary production separately from the
synthetic provider build. Stop a running server before replacing its build; wait for build
completion and a successful HTTP health/navigation probe before starting browser cases.

```sh
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm test
COMPASS_API_BASE_URL=http://127.0.0.1:8033 pnpm build
NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 COMPASS_API_BASE_URL=http://127.0.0.1:8033 pnpm build
COMPASS_API_BASE_URL=http://127.0.0.1:8033 pnpm start --hostname 127.0.0.1 --port 3107
node tests/ecounseling-call.browser.mjs
node tests/ui-information-hierarchy.browser.mjs
node tests/ux-p2a.browser.mjs
node tests/ecounseling-runtime.browser.mjs
node tests/ux-p1.browser.mjs
node tests/simplify-3b-public-shell.browser.mjs
node tests/email-change.browser.mjs
node tests/notification-email-auth.browser.mjs
node tests/user-copy.browser.mjs
node tests/referral-administration.browser.mjs
node tests/faculty-referrals.browser.mjs
node tests/faculty-foundation.browser.mjs
```

Repeat browser commands with `COMPASS_UI_BROWSER=webkit`. Synthetic call builds need the
loopback-only provider seam and `tests/support/ssr-api-fallback.mjs` on their configured
API port. The fallback returns unavailable for server-side requests, never real data.
Do not deploy the synthetic browser build.

For actual backend proof, stop the fallback, run from `be/`:

```sh
.venv/bin/python -m tests.faculty_portal_server /tmp/compass-fac5-session.json
```

Use the normal matching frontend build/server and run in both engines:

```sh
COMPASS_FAC4_FIXTURE_MANIFEST=/tmp/compass-fac5-session.json node tests/integration/faculty-referral-administration.live.mjs
node tests/call-slip-permissions.browser.mjs
```

The 0600 manifest contains only synthetic session cookies. Stop the owned fixture afterward;
its finally block removes its owned unique database and manifest. Never overwrite another
fixture manifest or point these scenarios at a live institutional account/database.

The browser dependency helper also passes Bash syntax checking and the planner self-tests.
Its actual Ubuntu/APT/install behavior is verified in the final hosted jobs, including both
targeted and full backend workflows; no macOS/local shell-only result certifies runner setup.

## Hosted gate assessment

The integration branch is outside current automatic PR triggers; dispatch the existing
backend/frontend workflows against the implementation branch and its actual integration
base. Use exact head SHA from run metadata. Both the static/unit checks and every required
backend/browser shard must finish successfully before a complete pipeline pass is claimed.

The PR contains actual run/job URLs, final outcome and any unresolved owner/explanation.
Cancellation, external runner failures and dependency installation failures are distinct from
test failures. The baseline workflow already disables matrix fail-fast; no cancellation
cause is guessed. A genuine new regression is corrected in code or justified contract/tests,
then revalidated on the updated exact SHA. Unrelated assertions are not removed to get green.

The local reports intentionally exclude rejected/invalid harness attempts and contain only
safe case identifiers/results, not SQL row values, request bodies, session cookies, tokens or
keys. Institutional and deployment readiness are assessed separately in [readiness](readiness.md).

Representative synthetic screenshots inspected for usable layout:

- [Narrow-phone call stage and controls](screenshots/call-narrow-phone.png)
- [GCO closure review, 1024px / 200% text](screenshots/gco-review-1024-200.png)
- [Faculty closed detail, 320px / 200% text](screenshots/faculty-closed-320-200.png)
- [Default unavailable Faculty Home](screenshots/faculty-home-unavailable.png)
- [Actual-backend Faculty tracking](screenshots/actual-faculty-closed.png)
- [Actual-backend GCO receipt](screenshots/actual-gco-received.png)
