# Validation evidence — October 22, 2026

## Environment

Isolated worktree based on integration `f268d1a5`. Python 3.13.12, Django 6.1.1,
Homebrew PostgreSQL 17.11 and Redis on loopback. Tests use `tests.settings`,
ephemeral test encryption keys and dedicated `test_compass_notif01` database.
Email/push/queue transports use local memory or mocks. No deployed database,
institutional record, participant, SMTP recipient, secret file or live environment
was accessed. Backend dependencies reuse the local virtualenv through an ignored
symlink. Frontend dependencies were installed offline from the existing pnpm
store; no lockfile/dependency change. Node 26.7.0, pnpm 11.19.0, Next 16.3.4.

## Backend regression

From `be/`, each pytest invocation used this environment prefix:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif01
```

`unused` is a test-only dummy, not a deployment credential. The variables were
applied directly before `.venv/bin/pytest` in the actual commands.

```sh
.venv/bin/pytest \
  tests/test_notification_email_links.py \
  tests/test_notification_email_presentation.py \
  tests/test_notifications.py \
  tests/test_notification_delivery.py \
  tests/test_transactional_email.py \
  tests/test_notification_push.py \
  tests/test_notification_realtime.py \
  tests/test_appointment_reminders.py \
  tests/test_appointments.py \
  tests/test_appointment_management_scope.py \
  tests/test_authentication.py \
  tests/test_group_sessions.py \
  tests/test_request_context.py \
  tests/test_common_config.py \
  tests/test_openapi_contract.py \
  -q --reuse-db --durations=5
```

**509 passed in 218.72s.** Includes 137 new backend cases, real booking producers,
real endpoint 401/authorized/404 behavior, PostgreSQL concurrent linked-email
claims, existing recovery/retry/security-email/OTP/currentness/push/realtime
regressions. New tests cover origin parsing, hostile headers/input independence,
frontend routes/pages, HTML/text parity, legacy/generic fallback, private source
exclusion, former/unrelated recipients, capabilities, GSS College/supervision
scope, current email, post-render races and safe failure logs.

```sh
.venv/bin/pytest tests/test_fixed_date_slots.py \
  tests/test_platform_email_operations.py -q --reuse-db
```

**37 passed in 38.65s.** Covers the second Scheduled producer's canonical pathway
and existing operator/retry contracts. **546 backend tests passed across the two
regression invocations**, not a full repository run.

A final internal reason-mapping cleanup explicitly maps unavailable non-origin
links to generic `invalid_target`. Directly affected fallback tests were rerun:

```sh
.venv/bin/pytest tests/test_notification_email_presentation.py \
  -k legacy_or_incomplete --reuse-db -q
```

**6 passed, 33 deselected in 3.95s.** No broad regression was repeated for this
behavior-preserving cleanup; final changed-file Ruff checks passed afterward.

## Iteration and corrections

- Existing delivery/transactional-email baseline: **172 passed in 15.82s**.
- First new suites: **130 passed, 3 failed**. All three failures came from the new
  fixture using `allow=False` instead of actual `UserCapabilityOverride.effect=REVOKE`.
  Corrected; affected rerun: **3 passed, 32 deselected**. New suites then passed
  **133 in 23.41s**. Four more concurrency/scope/stale-source cases directly passed
  (**4 passed, 35 deselected**) before the coordinated 509-case run.
- Initial pnpm tried to repair a borrowed `node_modules` symlink and stopped with
  `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`. Removed that worktree-only symlink,
  then `CI=true pnpm install --offline --frozen-lockfile --ignore-scripts` succeeded.
  No dependency/lockfile change; generation and all subsequent frontend checks passed.
- Initial root-level lint invocations included unchanged planner/style diagnostics
  under global or incorrectly scoped configuration. Changed backend files were
  checked from `be/` with their repository configuration and passed. Planner
  self-tests/inventory checks passed; no unrelated planner reformat was made.

## Static checks, schema and previews

From `be/`, `ruff check` and `ruff format --check` passed for all nine changed
backend Python production/test files: Appointment projection, delivery, links,
presentation, common email, JSON logging, settings and both new suites.

```sh
# Repository root
python3 .github/scripts/backend_ci.py verify
python3 -m unittest discover -s .github/scripts -p 'test_backend_ci.py'
git diff --check
```

Inventory: **171 test files** bundled and assigned exactly once across six full
regression shards. **38 planner self-tests passed**. Only two test names were
added to the Notifications bundle; no workflow filters changed. Static AST/doc
reconciliation confirmed **30/30 catalog rows**; actual producer calls, including
Fixed-Date Slots and safe seed wrappers, were inspected.

From `be/`, with test settings and the disposable test database:

```sh
.venv/bin/python manage.py check --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
.venv/bin/python manage.py render_email_previews --settings=tests.settings \
  --output-dir /tmp/compass-notif01-email-previews
```

Django: no issues. Migrations: no changes. OpenAPI: current, no schema diff.
**31 generic/security previews** written without sending. A linked Scheduled
preview was separately rendered with a synthetic `.example` origin and UUID.
Chromium checked 390px/680px layout: one action, no horizontal overflow or remote
resource requests. The 390px screenshot was visually inspected. These are local
HTML checks, not external mail-client acceptance.

## Frontend and authentication

From `fe/`:

```sh
pnpm api:generate
node --import ./tests/support/register-tsx.mjs --test tests/notification-email-auth.test.mjs
pnpm lint
pnpm typecheck
pnpm build
```

Generation/lint/typecheck passed; **26 Node tests passed**. Ordinary Turbopack
production build passed, generating **95 static pages**. Frontend production code
is unchanged. The build-generated `next-env.d.ts` path diff was restored to its
tracked content after validation.

The production build ran locally at `http://localhost:3127`. API requests were
intercepted with synthetic fixtures; the harness blocks nonlocal HTTP(S) traffic.

```sh
COMPASS_UI_BASE_URL=http://localhost:3127 node tests/notification-email-auth.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3127 COMPASS_UI_BROWSER=webkit \
  node tests/notification-email-auth.browser.mjs
```

**9/9 Chromium, 9/9 WebKit** passed: signed-in access, password, ordinary MFA,
post-login denial, session expiry and four unsafe return destinations. An added
mandatory-setup case was run with `COMPASS_UI_CHECK='mandatory authenticator'` in
each engine: **1/1 Chromium, 1/1 WebKit**. It proves setup → recovery-code
acknowledgment → fresh sign-in → MFA → original Appointment. **10 distinct browser
scenarios per engine**, across those two invocations. Changed test files passed
focused ESLint after that addition. Existing browser discovery registers the suite
for all four shards and both engines; no workflow change.

## Hosted CI and limits

Backend/frontend workflow filters exclude `integration/ux15-modernization`.
No workflow was modified or manually dispatched to obtain checks. Local results
are not hosted CI-green claims; final PR/head status is checked after publication.

No full backend/frontend/browser inventory rerun, staging UAT, real-device or
screen-reader evaluation, external Gmail/Outlook check, real SMTP smoke,
inbox/open/read proof, institutional privacy/content approval, live configuration
or deployment. Mid-MFA reload/restart is source-audited, not browser-exercised;
the existing in-memory challenge flow loses continuation on reload. No automatic
merge or protected-branch change is part of this work.
