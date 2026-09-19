# ADR-044: Runtime Operations Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: backend-only Maintenance Mode, EmailDelivery operator recovery, and curated technical runtime activity

## Context

ADR-043 established read-only Platform Operations diagnostics. COMPASS now needs a deliberately
narrow runtime-operations layer without turning the application into a deployment control plane,
generic job runner, browser shell, or global Audit Trail viewer.

The existing architecture already provides the required foundations:

- capability-based authorization;
- opaque authenticated sessions and recent-MFA step-up;
- append-only `audit.AuditEvent` with synchronous `record_event()`;
- durable Notification and `EmailDelivery` state in PostgreSQL;
- Celery delivery and Beat-based due-delivery recovery;
- public liveness/readiness contracts with deployment semantics;
- closed-world activity presenter/projection patterns.

This slice remains backend-only. There is no frontend.

## Authorization

Add canonical capability:

- `platform_operations.manage`

Baseline grant is IT_ADMIN only.

`platform_operations.view` continues to authorize read-only Platform Operations. Mutating runtime
operations require both `platform_operations.manage` and the existing
`require_recent_mfa()` session primitive.

Routes evaluate effective capabilities; they do not authorize by comparing `role.code`.

No new step-up mechanism is introduced.

## Maintenance Mode persistence

Add one singleton `platform_ops.MaintenanceConfiguration` row with canonical primary key `1`.

Persist only current configuration:

- manual enabled flag;
- bounded plain-text manual message;
- optional informational manual expected-end timestamp;
- optional scheduled start/end pair;
- bounded plain-text scheduled message;
- updated timestamp.

A database constraint requires the scheduled timestamps to be either both null or both non-null with
end later than start.

Audit Trail remains the historical record. There is no separate maintenance-history table.

## Manual and scheduled semantics

Manual and relevant scheduled control are intentionally mutually exclusive.

Manual enable is rejected while a current or future schedule exists. Scheduling is rejected while
manual mode is enabled. An expired schedule may be replaced. Explicit schedule cancellation clears
the scheduled fields.

The effective state is derived from persisted facts and the current timestamp:

- manual enabled -> `MAINTENANCE`;
- scheduled window before start -> `SCHEDULED`;
- scheduled start <= now < end -> `MAINTENANCE`;
- scheduled end <= now -> `NORMAL`;
- otherwise -> `NORMAL`.

Reads do not clear an expired schedule.

The manual expected-end timestamp is informational only. Passing that timestamp does not disable
manual maintenance. Manual mode remains active until an authorized operator disables it.

## Scheduled maintenance does not depend on Celery

Scheduled correctness is timestamp-derived on every effective-state evaluation.

There is no maintenance start/end Celery task, Beat job, scheduler table, reconciliation table, or
heartbeat. Maintenance begins and ends according to its stored timestamps even when Celery worker or
Beat is unavailable.

## Maintenance HTTP gate

Add `MaintenanceModeMiddleware` immediately inside the existing request-correlation middleware.

It gates ordinary `/api/v1/` requests only while the effective state is `MAINTENANCE`.

The following bypass before any maintenance database lookup:

- `/api/v1/health/live`;
- `/api/v1/health/ready`;
- `/api/v1/auth/*`;
- `/api/v1/platform/*`;
- `/api/v1/integrations/daily/webhook`.

This preserves process health semantics, operator authentication/MFA/recovery, Platform Operations,
and the existing provider callback. There is no blanket IT Admin bypass for ordinary domain APIs.

Blocked requests receive the standard COMPASS JSON error envelope with HTTP 503,
`maintenance_mode`, and the configured plain-text message.

Active scheduled maintenance includes `Retry-After` based on its known automatic end. Manual
expected-end is informational and is never presented as a guaranteed Retry-After deadline.

Background Celery worker and Beat execution are unaffected because Maintenance Mode is an HTTP gate.

## Maintenance auditing

Maintenance mutations are row-locked and transactional. The state mutation and successful audit
append occur in the same PostgreSQL transaction.

Canonical actions are:

- `platform.maintenance.enabled`;
- `platform.maintenance.disabled`;
- `platform.maintenance.scheduled`;
- `platform.maintenance.schedule_cancelled`.

Audit metadata may include the informational expected-end or scheduled start/end timestamps. The
maintenance message and raw request payload are excluded.

Derived state changes and maintenance-rejected requests do not generate AuditEvent noise.

## EmailDelivery operator projection

Reuse the existing `notifications.EmailDelivery` table and delivery state machine.

Add read-only Platform Operations projections for:

- aggregate counts for PENDING, PROCESSING, FAILED, and CANCELLED;
- sent-today count using the configured application timezone;
- oldest pending timestamp;
- due-pending count;
- bounded newest-first delivery listing with optional status filter.

The list exposes only technical fields: delivery UUID, event code, status, attempt count,
created/updated/attempt/retry/sent timestamps, and safe failure code.

It does not expose recipient identity, Notification title/message, rendered email, source/target
domain IDs, provider exception data, claim token, claim expiry, or arbitrary metadata.

## Controlled manual EmailDelivery retry

Add one purpose-built retry operation.

Eligibility is deliberately narrow:

- current status is `FAILED`;
- failure code is `transport_error` or `send_returned_zero`;
- recipient account remains active.

PENDING, PROCESSING, SENT, CANCELLED, template failures, inactive-recipient deliveries, and unknown
deliveries are not retryable.

The retry transaction locks the EmailDelivery row, revalidates state, preserves lifetime
`attempt_count`, sets the delivery to durable PENDING due now, clears stale safe failure/claim
state, and appends:

- `notification.email.retry_requested`

to the shared Audit Trail. Audit failure rolls back the delivery mutation.

After commit, COMPASS best-effort enqueues the existing
`compass.notifications.email.deliver` task using only the EmailDelivery UUID. HTTP never calls SMTP
synchronously.

If broker enqueue fails, the committed PENDING retry remains durable and the existing Beat recovery
path can discover it. No second retry scheduler or task type is introduced.

Row locking ensures two concurrent retry requests cannot both create intentional retry transitions
from the same FAILED state.

## Delivery guarantee

ADR-041 remains authoritative: external SMTP transport is at-least-once, not exactly-once.

A previous transport failure can have an ambiguous provider outcome. An authorized manual retry can
therefore theoretically lead to duplicate external delivery. This slice does not claim exactly-once
email semantics.

There is no bulk retry, retry-all, arbitrary cancellation, manual SENT marking, recipient editing,
Notification editing, arbitrary email composition, or attempt-counter reset.

## Technical Operations Activity

Add a curated projection over the existing append-only `audit.AuditEvent`; do not create another
audit table.

The initial closed whitelist is exactly:

- `platform.maintenance.enabled`;
- `platform.maintenance.disabled`;
- `platform.maintenance.scheduled`;
- `platform.maintenance.schedule_cancelled`;
- `notification.email.retry_requested`.

The projection uses deterministic newest-first bounded pagination and code-owned presenters. It
returns safe technical title/description, event time, actor type, and safe operator display name.

Raw AuditEvent metadata, request details, recipient email, Notification content, counseling/student
identities, and unrelated audited domains are not returned. Malformed or incompletely registered
technical records fail closed.

This is not a global Audit Trail browser.

Automatic Celery delivery attempts are not duplicated into the Audit Trail merely for this
projection; the existing delivery state/logging remains authoritative for transport processing.

## API surface

All routes extend the existing `platform-operations` OpenAPI domain.

Read operations require `platform_operations.view`:

- `GET /api/v1/platform/maintenance`;
- `GET /api/v1/platform/email-deliveries/summary`;
- `GET /api/v1/platform/email-deliveries`;
- `GET /api/v1/platform/activity`.

Mutations require `platform_operations.manage` plus recent MFA:

- `POST /api/v1/platform/maintenance/enable`;
- `POST /api/v1/platform/maintenance/disable`;
- `PUT /api/v1/platform/maintenance/schedule`;
- `DELETE /api/v1/platform/maintenance/schedule`;
- `POST /api/v1/platform/email-deliveries/{delivery_id}/retry`.

The ADR-043 health, environment, and command-catalog APIs remain read-only.

## Frontend deferral

No React, Vue, JavaScript, CSS, dashboards, cards, charts, maintenance pages, or admin templates are
added. A future frontend may consume these backend contracts.

## Backup and restore exclusion

Backup, point-in-time recovery, snapshot orchestration, dump/download/upload, and restore remain
deployment/infrastructure responsibilities.

This slice adds no backup API, management command, scheduler, archive, status page, or restore
control.

## Consequences

COMPASS gains narrow runtime operational control while preserving strong transaction/audit
boundaries and the existing infrastructure contracts.

Platform Operations remains purpose-built rather than becoming a generic infrastructure console.
