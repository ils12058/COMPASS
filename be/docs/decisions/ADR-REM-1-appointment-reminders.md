# COMPASS-REM-1: Student Appointment reminders

Status: implementation review (not enabled on staging).

## Model and occurrence identity

`Appointment.reminder_revision` changes whenever the scheduled time or counselor
assignment changes. `AppointmentReminderOccurrence` holds its own UUID, the
Appointment, schedule revision, scheduled start, recipient, issuer, type, and
issuance time. Automatic occurrences are unique by Appointment, revision and
window. Notification source identity is the occurrence UUID, while target type
`APPOINTMENT` and target ID remain the canonical Appointment.

The Appointment row lock serializes manual requests and periodic automatic
dispatch. Notification creation happens inside that same transaction. Bulk
requests have an explicit UUID confirmation key and durable replay record.

## Timing

Both 24-hour and 3-hour windows are based on timezone-aware Appointment
instants; the institution's civil timezone is `INSTITUTION_TIME_ZONE`.
The Beat dispatcher runs every 60 seconds and accepts only
`due <= now < due + 15 minutes`. Bookings or schedule revisions after the
window target do not qualify. This intentionally does not backfill downtime.

Manual issuance requires at least 15 minutes before start and a three-hour
anti-spam cooldown from prior *manual* reminders on that Appointment (CORR-2A).
Automatic 24-hour and 3-hour windows remain independently idempotent by
`(appointment, revision, window)`. An automatic reminder never prohibits an
authorized manual reminder, and a prior manual reminder never silently suppresses
a subsequent automatic reminder window.

## Authorization and safe content

Only active Counselor/GSS staff with `appointments.manage` may request, preview,
or review reminder history; existing resource scope is evaluated for each Appointment.
Manual single and bulk reminder submissions require recent MFA through the
established `require_recent_mfa_for_request` convention, ensuring durable confirmation
replays cannot bypass active step-up policy. Preview and reminder history are read-only
and do not require step-up. Preview does not expose unauthorized recipients or details.
The Student must match the Appointment and remain active. Neither staff notifications
nor My Work items are created.

A read-only staff reminder history (`GET /api/v1/appointments/{appointment_id}/reminders`)
reports occurrence issuance, in-app notification creation, and external email and
browser-push states (`NOT_REQUESTED`, `PENDING`, `SENT`, `FAILED`, `CANCELLED`).
`SENT` honestly reflects successful hand-off to the transport provider, not confirmed
recipient delivery. Transport diagnostics, tokens, and other students' notification
records are never exposed.

All outbound reminder wording is generic and uses the existing notification,
email and browser-push channels. No reason, referral, notes, or counseling
details are rendered. Pending external delivery revalidates occurrence against
the current Appointment revision and Student state. Delivered external messages
are not recallable.

## Migration and enablement

Apply `appointments.0002_appointment_reminders` after the canonical baseline.
Do not edit previous migrations. The migration is additive and no existing
records are backfilled.

`APPOINTMENT_AUTO_REMINDERS_ENABLED` defaults to false in **both** staging
modes. Operator must verify all synthetic/UAT email destinations, opt-in to
outbound transport, then explicitly enable the flag through normal approved
configuration release. Do not enable on deployed staging as part of this PR.
Celery Beat must register `compass.appointments.reminders.dispatch_due` every
60 seconds with workers running. Existing delivery queues and recovery jobs
remain responsible for external transports.

Rollback: disable automatic reminders first and stop new manual API use.
Outstanding notifications and already-delivered mail/push cannot be recalled.
Forward recovery: fix the issue, re-run worker and Beat after validating
outbound addresses. Older automatic windows are deliberately skipped rather
than backfilled. Preserve occurrence and batch records for audit.

## Verification required before integration

Run backend Django migration checks, tests including multi-worker PostgreSQL
concurrency, Ruff; regenerate the frontend Orval API client; run frontend
lint, TypeScript, build and browser regression tests. Verify email/push stale
intent races, MFA applicability, and operational outbound suppression.

## OPS-FINAL repair and integration contract

The persisted staff role is `GUIDANCE_SERVICES_STAFF`. Single and bulk requests require a UUID
confirmation key; one durable actor/key/selection record survives the cooldown and worker retries.
Stored replay results omit names and reference codes; responses recheck current resource access.
All issuers serialize on the Appointment. Automatic discovery excludes issued and recent occurrences
before its 500-row limit, so a repeated scheduler progresses. A `(status, starts_at, id)` index
supports discovery. Both lead windows are half-open 15-minute windows, with no retrospective backfill.
Existing `CELERY_IMPORTS` explicitly registers the Reminder task module.

In-app lists and unread counts suppress obsolete occurrences in SQL before pagination. Email and
push revalidate source ownership, revision, active Student recipient and scheduled future status at
claim and immediately before external handoff. Email also rechecks claim ownership and destination.
The final database read and external provider submission cannot be atomic: an accepted provider
message cannot be recalled, and a worker interrupted after provider acceptance may retry. Durable
claims prevent concurrent sends; SMTP/web-push do not guarantee exactly-once external delivery.

Automatic/manual concurrency isolates independent automatic window idempotency from manual
anti-spam: manual reminders enforce a three-hour manual-to-manual cooldown, while automatic
24-hour and 3-hour windows evaluate only their own unique window occurrence. An automatic
reminder does not prevent a manual reminder, and a manual reminder does not block a scheduled
automatic window. Bulk confirmation previews are advisory; submission rechecks each Appointment
under its row lock and validates recent MFA. Reassignment/rescheduling creates a new Appointment
revision. Group registrations are outside this Appointment-only producer.

## Enablement, migration and rollback

`APPOINTMENT_AUTO_REMINDERS_ENABLED=false` remains the default in every environment. The worker
executing the dispatcher task must load the approved value. Beat continues to register and enqueue
the task every 60 seconds regardless of this value; it does not evaluate the switch. Existing
email/SMTP and opt-in `WEB_PUSH_*` settings apply; no new secret
or keyring is required. Before enabling automatic dispatch, an operator must verify the approved
recipient destinations and delivery integration. Tests use synthetic recipients and mocked transports.
No Student enrollment, UAT allocation or canonical data change is required.

### Operator control

This setting is an explicit pause for **creation of new automatic reminder occurrences**. When false,
`dispatch_due_reminders` returns before discovering appointments. When true, the existing task checks
the 24-hour and 3-hour windows every 60 seconds, issues each `(appointment, revision, window)` at most
once, and skips expired windows rather than backfilling. It does not control manual issuance, and
manual issuance does not suppress an automatic window. Turning the switch off does not retract an
already-created occurrence or automatically cancel its pending email/push delivery; those deliveries
continue through the existing notification recovery and currentness checks.

Before a change, verify the approved recipient destinations, email preference and opted-in push
subscriptions, the registered task `compass.appointments.reminders.dispatch_due`, one healthy Beat,
and workers able to process that task. Change the value in the worker's effective configuration and
reload/restart the worker that executes the task. No web restart is needed for automatic dispatch;
manual issuance remains independent. Do not disable or restart Beat to pause reminders: it must keep
registering/enqueuing the 60-second task, whose worker returns zero while the switch is false. To pause
after an incident, set the worker value false and confirm dispatch returns zero while the task remains
registered. Review existing occurrence and Notification delivery states separately; already accepted
provider messages cannot be recalled. Resume only after the incident is resolved and the delivery
destinations and currentness safeguards are verified again. Do not backfill skipped windows.

Apply schema-only `appointments.0002_appointment_reminders` after the immutable canonical baseline,
before deploying producers. It adds revision fields, two durable intent/replay tables, constraints
and a discovery index. It does not rewrite canonical migrations or run data mutations.
`compass/common/canonical_migrations.json` pins every canonical migration checksum and explicitly
registers additions; unknown historical migrations continue to fail closed. Agent 2 must register
its independent additions and preserve one graph leaf per app; any shared Appointment leaf needs
an explicit merge migration with both parents. Never fake, reset or drop canonical data.

Rollback: disable automatic dispatch in the worker first, drain or stop relevant workers, then roll
back application code while retaining additive tables and occurrence history. Reversing
0002 drops reminder history/replay tables and requires a separate approved recovery plan.
Smoke: check task registration, preview one synthetic eligible/ineligible selection, issue/replay
the same key, verify one in-app occurrence and safe email/push fixture, then reschedule/cancel
before dispatch and verify cancellation. No test may contact real participants.
