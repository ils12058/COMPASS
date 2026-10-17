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
cooldown from *any* issued reminder. It never blocks later automatic windows.

## Authorization and safe content

Only active Counselor/GSS staff with `appointments.manage` may request a
reminder; existing resource scope is evaluated for each Appointment. Preview
does not expose unauthorized recipients or details. The Student must match the
Appointment and remain active. Neither staff notifications nor My Work items
are created.

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
