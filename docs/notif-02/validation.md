# Validation evidence

Local validation on October 22, 2026 against integration baseline
`6f73efd981023a29fef0b0ea10ecbaacbe16212b`. Python 3.13.12, Django 6.1.1 and local
PostgreSQL 17.11. Commands below run from `be/` unless stated otherwise, using the
existing virtualenv and dedicated local `test_compass_notif02` database. All email
tests use synthetic data and mocked/locmem transport; no real mail was sent.

## Baseline and development iterations

| Selection | Result |
| --- | --- |
| NOTIF-01 baseline: email presentation, delivery, transactional email | 211 passed in 40.00s |
| New approved projection regression before implementation | 2 expected failures, 26 deselected: missing `appointment_facts` |
| First implemented projection/render coverage | 40 passed in 28.01s |
| Same affected selection after safety cleanup | 40 passed in 27.99s |
| Added policy/currentness/concurrency subset | 25 passed, 40 deselected in 11.90s |
| Privacy/legacy and generated examples subset | 39 passed, 65 deselected in 28.03s |
| Sequential 9→10→14 / A→B→C, GSS and other-family subset | 8 passed, 104 deselected in 3.90s |
| Post-render guard/origin snapshot subset | 6 passed, 107 deselected in 5.30s |
| Final preview export after whitespace normalization | 13 passed, 100 deselected in 10.10s |

These are overlapping development selections, not additive test totals. Early
Ruff line-length findings were corrected through the repository formatter; final
lint/format checks passed. The intended initial red tests passed after implementation.

The baseline command was:

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif02 \
  .venv/bin/pytest tests/test_notification_email_presentation.py \
  tests/test_notification_delivery.py tests/test_transactional_email.py -q --reuse-db
```

Focused development used the same environment and
`tests/test_appointment_email_presentation.py` with `-k` selections for the affected
new cases. The final coordinated run includes all 113 new parameterized cases;
development subset counts are recorded to distinguish iteration from final proof.

## Final coordinated backend regression

```sh
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif02 \
  .venv/bin/pytest \
  tests/test_appointment_email_presentation.py \
  tests/test_notification_email_links.py tests/test_notification_email_presentation.py \
  tests/test_notification_delivery.py tests/test_transactional_email.py tests/test_notifications.py \
  tests/test_notification_push.py tests/test_notification_realtime.py \
  tests/test_appointments.py tests/test_appointment_reminders.py \
  tests/test_appointment_slot_reservations.py tests/test_appointment_management_scope.py \
  tests/test_fixed_date_slots.py tests/test_platform_email_operations.py \
  tests/test_authentication.py tests/test_request_context.py tests/test_common_config.py \
  tests/test_openapi_contract.py -q --reuse-db --durations=5
```

**643 passed in 300.99s.** This is a coordinated relevant regression, not the entire
repository suite. It covers seven events, exact source identity/supersession,
source/target/type mismatches, initial/legacy Scheduled behavior, terminal/past
state, revoked/inactive/unrelated recipients, former-provider independent scope,
GSS pilot scope, recipient field exclusions, revision/window/cooldown/idempotency,
claim/retry/transport failures, post-render policy/email/origin/source changes,
escaping/time boundaries and source-confidentiality diagnostics. Three true
transaction-enabled worker-thread tests commit concurrent schedule, role and
reminder-revision mutations before the final transport check. Push/realtime,
authentication/MFA and fixed-slot behavior remain covered.

## Static and contract checks

```sh
.venv/bin/ruff check compass/appointments/email_presentation.py compass/appointments/reminders.py \
  compass/notifications/email_presentation.py compass/notifications/delivery.py \
  compass/common/email.py config/settings.py tests/test_appointment_email_presentation.py
.venv/bin/ruff format --check compass/appointments/email_presentation.py compass/appointments/reminders.py \
  compass/notifications/email_presentation.py compass/notifications/delivery.py \
  compass/common/email.py config/settings.py tests/test_appointment_email_presentation.py
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif02 \
  .venv/bin/python manage.py check --settings=tests.settings
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif02 \
  .venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=test_compass_notif02 \
  .venv/bin/python manage.py export_openapi --check --settings=tests.settings
```

Results: Ruff clean; formatting clean; Django no issues; no migration changes;
OpenAPI contract current. No schema/contract file was regenerated or changed.
From repository root:

```sh
be/.venv/bin/python .github/scripts/backend_ci.py verify
be/.venv/bin/python -m unittest discover -s .github/scripts -p test_backend_ci.py
git diff --check
```

Inventory: **172 files**, registered exactly once across six full-regression shards.
Planner self-tests: **38 passed in 5.422s**. Diff whitespace check clean.
The new suite joins the notifications bundle; workflow triggers are untouched.

## Synthetic rendering and not-run checks

The dedicated test's `EXAMPLES` cases generate 12 HTML/text pairs and 13 status
records when `COMPASS_EMAIL_PREVIEW_DIR` explicitly points to `docs/notif-02/previews`.
Without that variable they write only to pytest temporary paths. The obsolete
case has a suppression record and no invented email. See [screenshots](screenshots.md).
The final fixture export command was:

```sh
COMPASS_EMAIL_PREVIEW_DIR=../docs/notif-02/previews \
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif02 \
  .venv/bin/pytest tests/test_appointment_email_presentation.py \
  -k synthetic_preview_examples -q --reuse-db
```

Chromium checks both 390px and 680px layouts, wrapping, closed safe hrefs and no
scripts/embedded/remote resources. Seven screenshots include long/missing labels;
standard desktop and long mobile images were visually inspected.

The standalone layout invocation initially used an unavailable `@playwright/test`
import; it was corrected to the repository's installed `playwright` package with
no dependency change. The completed run printed: `PASS 24 layouts (12 messages at
390px/680px), no overflow/remote resources; 7 screenshots.`
The staged diff check then found whitespace-only lines inherited from the shared
rendered shell. The preview exporter now strips trailing whitespace only in saved
review fixtures; transport rendering is untouched. The 13-case export rerun passed.

No frontend code or integration contract changed. Frontend API generation,
lint/typecheck/build and the broad authenticated browser suites were not rerun;
the unchanged NOTIF-01 login/MFA/record-link flow is reused. Local email layout
checks are separate from authenticated application browser validation.
Gmail/Outlook, accessibility with assistive technology, staging SMTP, real delivery,
deployment and institutional disclosure approval remain manual/future work.
Hosted checks are not represented by these local results; PR head workflow/status
inspection is reported separately at PR creation. No workflow dispatch or trigger
change is used to manufacture hosted CI evidence.
