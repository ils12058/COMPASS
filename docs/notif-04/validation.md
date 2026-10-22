# Validation — NOTIF-04

Baseline `f0b05dcf6a2a80e22193144891d23fee5865bdad`, October 23, 2026.
Python 3.13.12, Django 6.1.1, Node 26.7.0. Dedicated local PostgreSQL database
`test_compass_notif04`; locmem transport and synthetic actors. No live backend,
SMTP mailbox, institutional Student data, deployed setting or external provider.

## Scope and evidence model

Backend tests exercise actual Django/Ninja endpoints, domain services and existing
transport machinery against synthetic data. Browser scenarios exercise the real
Next/React UI with intercepted APIs and fake realtime sockets. Browser HTTP fixtures
are not live backend authorization proof; the real endpoint tests supply that layer.
Email layout checks reuse committed synthetic previews and block network access.
The campaign does not claim real SMTP/client, stakeholder, physical-device or
screen-reader acceptance.

Final machine-readable totals/per-suite results are in `evidence/validation-summary.json`.
Per-browser scenario results and screenshots are stored under `evidence/chromium/`
and `evidence/webkit/`. Backend command selection is preserved verbatim in
`evidence/backend-selection.txt`. Results below are local, never hosted CI-green.

## Development iterations (overlapping; not additive)

| Run | Actual outcome / disposition |
| --- | --- |
| First pnpm setup | Dependency metadata attempted an install and aborted before module purge without TTY. Used installed pinned dependencies with `--config.verifyDepsBeforeRun=false`; no lockfile/dependency change. |
| First reload red attempt | 0/2 reached the application: connection refused because that initial dev startup also hit the dependency check. Harness issue, not defect evidence. |
| Corrected pre-fix reload run | 0/2 passed: both MFA/setup restart links lost the destination. This is the confirmed F01 regression. |
| First post-fix auth run | 12/12 Chromium passed. Expanded below; earlier counts are not additive. |
| First joined backend suite | 34 failed / 11 passed in 40.01s: test used lowercase status strings instead of uppercase enum, invalid override effect and ignored claim-time cancelled/skipped return distinction. Test assumptions corrected; no backend production fix. |
| Second joined backend run | 44 passed / 1 fixture failure in 23.85s: override uses actual `REVOKE`, not `DENY` or lowercase `deny`. |
| Corrected affected override | 1 passed, 44 deselected in 4.72s. |
| Expanded joined baseline | 46 passed in 45.99s. Added Group ownership case and explicit rich-policy nine-actor checks afterward. |
| Final affected scope selection | 10 passed, 37 deselected in 10.68s. Coordinated run includes 47 new cases; final focused run includes all 49. |
| Early Center / expanded Center | 16/16 and 20/20 Chromium; expanded 20/20 WebKit. Final 22-case runs below supersede these. |
| Expanded auth | 19/19 both engines before adding two Back scenarios. |
| Development-server contention | Back runs 1/2 in each engine and realtime timeouts while dev compilation overlapped production build. No production workaround or increased timeout. Interrupted the redundant failing runtime run, stopped dev, completed build, then reran auth/Center on production and realtime alone on warmed dev. |
| Final lint working directory | One invocation from repository root found no frontend script; corrected to `fe/`. Final lint/typecheck pass. |
| Formatting/static feedback | Ruff fixture-name/import shadowing and line wrapping corrected; no production refactor. |

## Final coordinated backend regression

From `be/`:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif04 \
  .venv/bin/pytest \
  tests/test_notification_cross_channel.py \
  tests/test_operational_email_presentation.py \
  tests/test_appointment_email_presentation.py \
  tests/test_notification_email_links.py \
  tests/test_notification_email_presentation.py \
  tests/test_notification_delivery.py \
  tests/test_transactional_email.py \
  tests/test_notifications.py \
  tests/test_notification_push.py \
  tests/test_notification_realtime.py \
  tests/test_appointments.py \
  tests/test_appointment_reminders.py \
  tests/test_appointment_slot_reservations.py \
  tests/test_appointment_management_scope.py \
  tests/test_fixed_date_slots.py \
  tests/test_platform_email_operations.py \
  tests/test_authentication.py \
  tests/test_request_context.py \
  tests/test_common_config.py \
  tests/test_openapi_contract.py \
  tests/test_group_sessions.py \
  tests/test_good_moral.py \
  tests/test_good_moral_assisted.py \
  tests/test_good_moral_preparation.py \
  tests/test_call_slips.py \
  tests/test_call_slip_issuance_provenance.py \
  tests/test_referral_call_slip_lifecycle.py \
  tests/test_password_access.py \
  tests/test_password_change.py \
  tests/test_email_change.py \
  tests/test_mail.py \
  tests/test_guidance_followups.py \
  tests/test_shared_summaries.py \
  tests/test_feedback.py \
  tests/test_routine_interviews.py \
  tests/test_exit_interviews.py \
  tests/test_inventory.py \
  tests/test_ecounseling.py \
  -q --reuse-db --durations=8 --tb=short --junitxml=/tmp/compass-notif04-backend.xml
```

This is 38 relevant files, not all 174 backend inventory files. Selection includes
47 joined cross-channel cases, 113 Appointment presentation cases and 232 additional
operational presentation cases, source-domain/currentness, role/scope, authentication/
MFA, password/address-change, delivery/retry, Push/realtime and contract regressions.
Final coordinated result: **1,403 passed, one existing Ninja tuple-response
DeprecationWarning, in 1,048.48s (17:28)**. No failures/skips. After adding two
real MFA challenge-expiry assertions, the final focused command
`.venv/bin/pytest tests/test_notification_cross_channel.py -q --reuse-db --tb=short
--junitxml=/tmp/compass-notif04-focused49.xml` passed **49 in 29.12s** using the same
environment prefix. It overlaps 47 coordinated cases: **1,405 unique backend
cases passed**. Production implementation was stable throughout; no broad backend
rerun was needed for the added test-only coverage. Exact case-set overlap is verified
from both JUnit files, not inferred from printed progress.

## Frontend unit and browser commands

From `fe/`:

```sh
pnpm --config.verifyDepsBeforeRun=false api:generate
node --import ./tests/support/register-tsx.mjs --test \
  tests/notification*.test.mjs tests/account-cache-ownership.test.mjs tests/realtime*.test.mjs
pnpm --config.verifyDepsBeforeRun=false lint
pnpm --config.verifyDepsBeforeRun=false typecheck
pnpm --config.verifyDepsBeforeRun=false build --webpack
```

Focused Node result: **111 passed**, no failures/skips (1,867.73ms final run).
Lint and typecheck pass. Ordinary production build (no UI-test mode) passes:
95 pages generated, compiler 2.2min, TypeScript 28.4s. Webpack is explicitly used
with the reused local dependency symlink; no build configuration or package changes.
Next regenerates next-env paths for dev/build; no generated-file change is included.

The final auth and Center campaigns use that production app at localhost:3115,
started with `node_modules/.bin/next start --port 3115`. For each engine:

```sh
COMPASS_UI_BASE_URL=http://localhost:3115 COMPASS_UI_BROWSER=chromium \
  COMPASS_UI_ARTIFACTS=/tmp/compass-notif04-production-chromium \
  node tests/notification-email-auth.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3115 COMPASS_UI_BROWSER=chromium \
  COMPASS_UI_ARTIFACTS=/tmp/compass-notif04-production-chromium \
  node tests/notification-cross-channel.browser.mjs
```

Repeat with `COMPASS_UI_BROWSER=webkit` and `/tmp/compass-notif04-production-webkit`.
Final results: **21 auth + 22 Center scenarios per engine**. These include both Back
cases, reload before MFA and after setup started, required setup completion, expiry,
unsafe returns, same-tab account switch, sign-out/reopen and loading/error/read states.
Browser external requests are blocked; no real API/mail/provider call is made.
The expiry mock was corrected from 401 to the actual `400 mfa_failed` contract and
rerun with `COMPASS_UI_CHECK='expired MFA'` against localhost:3117: **1/1 in each
engine**, overlapping the 21-case campaign. Real expired verify/setup challenges
are additionally covered in the final backend suite.

Realtime uses the workflow's existing separate synthetic production build,
independently of the ordinary deployment-shaped build. Development-mode exact socket
assumptions failed (9/12 Chromium, 11/12 WebKit), even after warming routes. No
product fix or timeout increase was applied. The CI-style build resolves the test
execution mismatch. Stop local app servers before replacing the build, start
`COMPASS_TEST_API_PORT=3116 node tests/support/ssr-api-fallback.mjs`, then:

```sh
COMPASS_API_BASE_URL=http://127.0.0.1:3116 NEXT_TELEMETRY_DISABLED=1 \
  NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 \
  pnpm --config.verifyDepsBeforeRun=false build --webpack
node_modules/.bin/next start --port 3117
# In another local shell:
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=chromium \
  COMPASS_UI_ARTIFACTS=/tmp/compass-notif04-synthetic-chromium \
  node tests/realtime-runtime.browser.mjs
# Repeat with webkit and its artifact directory.
```

Synthetic build passes (compiler 30.2s, TypeScript 19.3s, 95 pages). Final realtime
result: **12/12 per engine**. This existing loopback-only test artifact is not a
deployment artifact. Combined UI coverage is **110 distinct scenario/engine cases**
(21 auth + 22 Center + 12 realtime in each engine). It covers one
socket, revoked/current session, account replacement, new/duplicate hints, another
tab marking read, reconnect and disabled-runtime/server polling fallback.

Email layouts (from `fe/`):

```sh
COMPASS_UI_ARTIFACTS=../docs/notif-04/evidence/chromium \
  node tests/notification-email-layout.browser.mjs
COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=../docs/notif-04/evidence/webkit \
  node tests/notification-email-layout.browser.mjs
```

**50 layouts per engine**: 25 reused HTML/text pairs x 390/680px. No overflow,
active/remote resources or untrusted/mismatched action links. Six saved email
screenshots plus Center images support the visual inspection; this is not a
Gmail/Outlook or full accessibility acceptance result.

## Static, Django, schema and planner checks

From repository root:

```sh
be/.venv/bin/ruff check be/compass/notifications \
  be/compass/appointments/email_presentation.py \
  be/compass/group_sessions/email_presentation.py \
  be/compass/good_moral/email_presentation.py \
  be/compass/call_slips/email_presentation.py be/tests/test_notification_cross_channel.py
be/.venv/bin/ruff format --check be/tests/test_notification_cross_channel.py
be/.venv/bin/python .github/scripts/backend_ci.py verify
be/.venv/bin/python -m unittest discover -s .github/scripts -p test_backend_ci.py
git diff --check
```

Ruff/format pass. Planner verifies 174 files each assigned exactly once across six
full-regression shards; 38 planner self-tests pass (10.190s). No trigger changes.

From `be/`, use the same test-only environment prefix as above, with
`POSTGRES_DB=test_compass_notif04`:

```sh
.venv/bin/python manage.py check --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
```

Django: no issues. Migration drift: no changes. OpenAPI: canonical contract current.
No API/model/schema change is introduced. Git ancestry/ref/diff checks are repeated
before publishing the single integration-target PR.

## Hosted and manual boundaries

Relevant backend/frontend workflows filter PR targets to staging/canonical baseline,
excluding integration/ux15-modernization. Do not modify triggers or dispatch workflows
for a green badge. Published PR #313 was checked at implementation head `38f632ae70073861f480500be1664c4af9b67eb7`: zero commit statuses and zero workflow runs.
The manifest records that head; the final agent report verifies the final evidence-
metadata head as well. Local tests are not hosted CI success.

Not executed: real SMTP, staging deployment/configuration verification, Gmail/Outlook/
phone-email acceptance, spam/inbox behavior, screen readers, physical devices and
stakeholder UAT. The [UAT matrix](uat-matrix.md) preserves manual Not executed states.
The full four-family operational_v1 bundle still Requires institutional approval.
