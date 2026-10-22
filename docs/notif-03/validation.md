# NOTIF-03 validation

Local validation on October 22, 2026, baseline
`6d6f3e0accbef09302f6b158295632059b9ff211`. Python 3.13.12, Django 6.1.1,
PostgreSQL 17.11. Dedicated local database: `test_compass_notif03`. Existing local
virtualenv and frontend Playwright dependencies were reused. No Docker, real
SMTP, institutional account, live setting or deployed service was required.

## Development evidence and failed iterations

| Iteration | Exact result / explanation |
| --- | --- |
| NOTIF-02 baseline selection | 323 passed, one subprocess import failure in 109.50s; launched from repository root instead of `be/`, so the subprocess could not import `tests.settings`. |
| Baseline isolated cwd correction | 1 passed, 112 deselected in 0.34s from `be/`; no production defect or workaround. |
| Central policy tests before implementation | 5 expected failures, 40 deselected in 0.97s: missing central setting and obsolete keys still accepted/read. |
| First Group registration tests before implementation | 2 expected failures, 43 deselected in 0.97s: both policies still returned generic without a link. |
| First adapters, 45 cases | 38 passed / 7 fixture failures in 7.60s: cancellation registration timestamp was later than cancellation, and a synthetic form tried to create a second active revision. |
| Corrected first fixtures | 45 passed in 6.88s. Used valid participant time and existing active form. |
| Expanded source/authority/transaction cases | 159 passed / 3 fixture failures in 24.19s: synthetic title exceeded the real 255-character column. Corrected to the maximum length. |
| Renderer/endpoint/F4-F6/preview subset | 48 passed / 2 fixture failures, 159 deselected in 9.32s: self-service fixture omitted required idempotency/major parameters, and a second long-title fixture exceeded 255. |
| Confidential-event test update | One collection error / 194 deselected: typo in the existing Follow-Up enum name; corrected to `FOLLOWUP_ASSIGNED`. |
| Corrective self-service/previews/confidential rerun | 19 passed, 303 deselected in 2.83s. |
| Provenance/value/origin/F4-F6 and corrected long-title subset | 22 passed, 204 deselected in 2.48s. |
| Excluded-field/current-schedule/minimal-policy boundary subset | 6 passed, 226 deselected in 1.67s. |

Selections overlap and are not additive totals. Initial red tests became green;
fixture/harness failures were corrected without weakening source/privacy rules.
Ruff import/line-length feedback was resolved with repository tools. One template
editing script initially used a repository-relative path from `be/`; it stopped
before editing and was rerun with the correct path. No deployment workaround.

The baseline selection was `test_appointment_email_presentation.py`,
`test_notification_email_presentation.py`, `test_notification_delivery.py` and
`test_transactional_email.py`, with `-q --reuse-db`. Development commands use:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif03 \
  .venv/bin/pytest tests/test_operational_email_presentation.py -q --reuse-db --tb=short
```

The first central red run selected `-k 'real_settings_default or obsolete_environment'`;
the domain red run selected `-k 'all_operational and group_session.registered'`.
Later affected selections are named in the table and the final coordinated run
includes every new case, all existing Appointment cases and source-domain suites.

## Final coordinated regression

From `be/`:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif03 \
  .venv/bin/pytest \
  tests/test_operational_email_presentation.py tests/test_appointment_email_presentation.py \
  tests/test_notification_email_links.py tests/test_notification_email_presentation.py \
  tests/test_notification_delivery.py tests/test_transactional_email.py tests/test_notifications.py \
  tests/test_notification_push.py tests/test_notification_realtime.py \
  tests/test_appointments.py tests/test_appointment_reminders.py \
  tests/test_appointment_slot_reservations.py tests/test_appointment_management_scope.py \
  tests/test_fixed_date_slots.py tests/test_platform_email_operations.py \
  tests/test_authentication.py tests/test_request_context.py tests/test_common_config.py \
  tests/test_openapi_contract.py tests/test_group_sessions.py \
  tests/test_good_moral.py tests/test_good_moral_assisted.py tests/test_good_moral_preparation.py \
  tests/test_call_slips.py tests/test_call_slip_issuance_provenance.py \
  tests/test_referral_call_slip_lifecycle.py -q --reuse-db --durations=5 --tb=short
```

**Final result: 1,113 passed in 481.71s (8:01).** No failures or skipped cases.
The selection includes 232 NOTIF-03 cases and 113 Appointment presentation cases.
It is a relevant coordinated regression, not the entire backend inventory.

Coverage includes all fifteen admitted events, defaults/unknown policy/obsolete
key rejection, explicit recipient fields, real self-endpoint authorization,
F4/F6, exact source/target, versioned/legacy Group sources, timestamp participant
proof, missing/unauthorized data, Call Slip LIVE/HISTORICAL/unknown semantics,
delayed/superseded events, plain/HTML parity, unsafe values, confidential exclusions,
duplicate claims/retries, logs, recipient/policy/origin mutations and channel
separation. Three new transaction-enabled worker-thread tests commit a source
mutation from a separate connection before final SMTP revalidation; the three
existing Appointment transaction tests remain included.

## Static, planner and contract checks

From `be/`, Ruff and format check cover these changed Python files:

```sh
.venv/bin/ruff check \
  compass/appointments/email_presentation.py compass/common/email_presentation.py \
  compass/group_sessions/email_presentation.py compass/good_moral/email_presentation.py \
  compass/call_slips/email_presentation.py compass/notifications/email_disclosure.py \
  compass/notifications/email_presentation.py compass/notifications/operational_email_rendering.py \
  compass/notifications/delivery.py config/settings.py \
  tests/test_operational_email_presentation.py tests/test_appointment_email_presentation.py
```

Run the same file list with `.venv/bin/ruff format --check`. Both pass. Then:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif03 \
  .venv/bin/python manage.py check --settings=tests.settings
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif03 \
  .venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif03 \
  .venv/bin/python manage.py export_openapi --check --settings=tests.settings
```

Results: Django no issues; no migration changes; canonical OpenAPI contract current.
No API generation/contract update is necessary. From repository root:

```sh
be/.venv/bin/python .github/scripts/backend_ci.py verify
be/.venv/bin/python -m unittest discover -s .github/scripts -p test_backend_ci.py
git diff --check
```

Inventory: **173 test files**, registered exactly once across six full-regression
shards. CI planner: **38 passed in 5.057s**. New suite joins the existing notifications
bundle; no workflow filters change. Staged diff/link checks are repeated before commit.

## Frontend and rendering scope

`node --test fe/tests/notification-email-auth.test.mjs`: **26 passed**. Three
additional direct Node assertions verify Group Session/Good Moral/Call Slip
destinations survive `loginPathForPortal`/`safePortalDestination` with only the
internal `next` parameter. Node reports its existing module-type inference warning;
no package metadata change is justified. Actual source API self-endpoint tests
check retained cancelled/voided access for owners and 404 for another Student.

All 13 HTML fixtures pass at 390px/680px: **26 Chromium layouts**, no overflow,
embedded/remote resources or unsafe hrefs. Seven screenshots, including standard
desktop/mobile and omitted long sensitive title. Group desktop/Good Moral mobile
images were visually reviewed. See [previews](previews.md) for exact fixture export
command and limitations. Suppressed events have status evidence, no invented body.

No frontend production files or API contracts changed. Frontend API generation,
lint/typecheck/build and broad authenticated browser suites were not rerun. Existing
NOTIF-01 login/MFA continuation is reused; local email layouts and Node redirect
checks do not constitute a new end-to-end login/MFA browser campaign.

Hosted CI status is inspected on the exact PR head separately. Existing workflow
filters exclude this integration target; local results are not hosted CI success.
No manual workflow dispatch or trigger change is used. Gmail/Outlook, assistive
technology, authorized staging SMTP, live deployment and institutional approval
remain future/manual checks. No real mail, live configuration or protected branch
change was performed.
