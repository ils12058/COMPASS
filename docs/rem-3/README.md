# REM-3 — One Reminders page for staff

A single Reminders workspace for staff who manage Appointments: the upcoming Appointments and the
reminders already sent for them, with a manual send that reuses the existing Appointment reminder
eligibility, preview, confirmation and delivery path unchanged.

This is the thin version of Proposal #14's REM-3. The shared cross-domain reminder core (REM-1) and
the Appointment migration onto it (REM-2) are **not** built. Form reminders are **not** built. The
page is shaped as a source-filtered view with one source, **Appointments**, so another source can be
added later without redesigning the route.

## What the page does

Route: `/portal/reminders` (`fe/src/app/(portal)/portal/reminders/page.tsx`), rendered by
`fe/src/features/reminders/reminders-page.tsx`.

- **Navigation** — "Reminders" sits immediately after "Appointments" in the portal's Scheduling
  group. It is visible only when `getAppointmentAccess(user).canManage` is true. No role code is
  hard-coded; the same helper that gates the Appointments workspace gates this page, and the page
  itself shows an unavailable message to everyone else.
- **Upcoming view** — Scheduled Appointments in the actor's managed scope inside the reminder
  window, ordered by start (earliest or latest, reported by the backend). Columns: Appointment
  reference, Student, Counselor, Service, Starts, next automatic reminder, last reminder, and
  whether a manual reminder can be sent now with the plain reason when it cannot.
- **Manual send** — eligible rows carry checkboxes (up to the existing bulk limit of 25). "Send
  reminder" opens the existing `ReminderSender` from
  `fe/src/features/appointments/appointment-reminders.tsx`. It previews eligibility, requires the
  confirmation dialog, supports step-up continuation, and is the only place that calls the send
  mutation. Neither opening the page nor rendering the list ever previews or sends anything.
- **Sent view** — recent reminder occurrences across managed Appointments, newest first. Shows the
  reminder kind (24-hour, 3-hour, manual), when it was issued, whether it is still current or was
  superseded by a reschedule, who issued it (or that it was automatic), the Appointment reference
  and Student, and the in-app, email and browser-push states in plain words.
- **Filters** — both views share From/To dates and a Source selector with one option
  ("Appointments"). Upcoming adds manual availability (ready / cannot send now) and, for accounts
  that can read the counselor directory (`availability.manage`), a Counselor filter; the filter is
  hidden for accounts without that capability, whose scope is already narrow. Sent adds reminder
  kind and delivery state. Filters and paging live in the URL.
- **Help** — `ContextHelp` explains the 24-hour and 3-hour automatic reminders, that manual
  reminders need preview and confirmation, the eligibility and three-hour cooldown rules, what
  "Sent" does and does not mean, and that only managed Appointments appear.

The page reuses the portal's `PageHeader`, `ContextHelp`, `FilterToolbar`, `Panel`,
`SortableColumnHeader`, `CanonicalPagination`, `RowsSkeleton` and `WorkspaceTabs`, and shows
loading, empty and error states at phone width without horizontal scrolling (the wide tables become
cards below `md`).

## API

Two read-only operations on the existing Appointments router, using `session_auth`,
`response_with_errors`, and page/page_size/has_next metadata:

### `GET /api/v1/appointments/reminders/upcoming`

`operation_id="appointmentsListUpcomingReminders"`. Response `AppointmentReminderUpcomingPage`.

- Only Scheduled Appointments returned by `scope_managed_appointments(...)`.
- Window: `from_date` defaults to today in Philippine Time; `to_date` defaults to `from_date + 6`.
  The inclusive window may not exceed 30 days (422 otherwise). The lower bound is never earlier
  than now.
- Optional filters: `provider_id`, `manual_available=true|false`.
- Closed ordering `AppointmentListOrdering` (earliest/latest start), reported as `ordering`.
- Row: `appointment_id`, `reference_code`, `student_name`, `counselor {id, display_name}`,
  `service_name`, `starts_at`, `next_automatic`, `last_reminder_kind`, `last_reminder_at`,
  `manual_available`, `manual_reason`.

`next_automatic` mirrors the dispatcher's own conditions (global automatic reminders switch, active
STUDENT recipient, reminder not already issued for the current schedule revision, window not past
its late allowance). When automatic sending is off it reports none. `manual_available` and
`manual_reason` come from the same `_decision` the sender uses; the list path only batches the
cooldown lookup through `cooling=` so there is still one eligibility rule.

### `GET /api/v1/appointments/reminders/activity`

`operation_id="appointmentsListReminderActivity"`. Response `AppointmentReminderActivityPage`.

- Recent occurrences for Appointments in `scope_managed_appointments(...)`, newest first, paginated.
- Optional filters: `kind` (`AUTO_24H`, `AUTO_3H`, `MANUAL`), `from_date`/`to_date`, `delivery`.
  `delivery` matches an occurrence when either its email or its browser-push delivery is in the
  chosen state; `NOT_REQUESTED` means neither transport has a delivery row.
- Row: every field of the per-Appointment reminder history plus `appointment_id`, `reference_code`
  and `student_name`.
- Delivery-state filtering uses `Exists` subqueries over `Notification`, `EmailDelivery` and
  `PushDelivery`; history rows are built by one batched builder, so neither list is N+1.

Both endpoints return 403 to non-managers and never reveal an Appointment outside the actor's
scope. Neither exposes transport diagnostics, failure codes, endpoints, read receipts or counseling
content; tests assert the exact row field sets.

## Reused, not duplicated

- `preview_reminders`, `issue_manual_reminder`, `issue_bulk_reminders`, `_decision`,
  `current_reminder_occurrences` and the notification/delivery write path in
  `be/compass/appointments/reminders.py`.
- `scope_managed_appointments` and `appointment_management_access_allowed` in
  `be/compass/appointments/access.py`; the manager check (`_manager`) is unchanged.
- `reminder_history` now delegates to the shared `_history_rows` builder; the per-Appointment
  endpoint response is byte-for-byte the same field set (tested).
- The frontend's `ReminderSender` and its `reminderReason` plain-language map are imported
  unchanged, so the page cannot drift from the existing contextual senders.
- Automatic reminder timing, the scheduler (`reminder_tasks.py`, `dispatch_due_reminders`), the
  email template, and the existing senders on the managed Appointments list and Appointment Detail
  are untouched.

## Not built

- REM-1 shared reminder core and REM-2 Appointment migration (deliberately skipped).
- Form or any other reminder source; the Source selector has exactly one option.
- Scheduling, pausing or editing automatic reminders; changing timing or templates.
- Transport diagnostics, delivery retries or read receipts on this page.

## Validation (targeted only; the full suite and browser specs were not run)

From `be/` (a separate `POSTGRES_DB` was used so a concurrent worktree could not share the test
database):

```
POSTGRES_DB=compass_rem3 uv run pytest tests/test_appointment_reminders.py \
  tests/test_appointment_reminder_overview.py tests/test_openapi_contract.py \
  tests/test_canonical_baseline.py -q -p no:cacheprovider
uv run ruff format --check compass/appointments/api.py compass/appointments/reminders.py \
  tests/test_appointment_reminder_overview.py tests/test_openapi_contract.py
uv run ruff check compass/appointments/api.py compass/appointments/reminders.py \
  tests/test_appointment_reminder_overview.py tests/test_openapi_contract.py
uv run python manage.py makemigrations --check --dry-run --settings=tests.settings
uv run python manage.py export_openapi --check --settings=tests.settings
uv run python ../.github/scripts/backend_ci.py verify
```

Results: pytest **89 passed, 0 failed**; ruff format and check **passed**; no pending migrations;
OpenAPI contract current; `backend_ci.py verify` reports only the five pre-existing unbundled files
(`test_case_communication.py`, `test_counseling_documentation_review.py`,
`test_counseling_finish.py`, `test_counseling_finish_concurrency.py`,
`test_fup3a_faculty_referral_journey.py`) and not `test_appointment_reminder_overview.py`.

From `fe/`:

```
pnpm -s typecheck
pnpm -s exec eslint src/features/reminders src/features/appointments src/features/portal \
  tests/reminders-page.test.mjs
node --import ./tests/support/register-tsx.mjs --test tests/reminders-page.test.mjs
```

Results: typecheck **passed**; ESLint **passed**; node tests **7 passed, 0 failed**.

The new backend test file is registered in the scheduling bundle of
`.github/scripts/backend_ci.py` next to `test_appointment_reminders.py`. Both new operation IDs are
in `EXPECTED_OPERATION_IDS` and the upcoming list is in `SORTABLE_COLLECTIONS` in
`be/tests/test_openapi_contract.py`.

`contracts/openapi.json` was regenerated with `export_openapi`; the frontend client was regenerated
with `pnpm api:generate`. Neither was edited by hand.
