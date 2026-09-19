# ADR-041: Notifications and Email Delivery Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: durable in-app Notifications, durable asynchronous email delivery, and Call Slip as the first integration

## Context

COMPASS already had SMTP through `compass.integrations.mail.Mailer`, Redis-backed Celery, request
correlation propagation, and a dedicated Email OTP Celery path. Those pieces could send email, but
normal domain actions had no durable Notification intent or recoverable email-delivery state.

ADR-028 intentionally deferred Call Slip notification delivery because no durable notification or
outbox domain existed at that time. This ADR adds that missing foundation without rewriting the
historical ADR-028 decision.

A successful business mutation must not depend on synchronous SMTP, and a committed operational
notification must not silently disappear because an immediate broker enqueue fails.

## Decision

Add a focused `compass.notifications` Django app with three durable models:

- `Notification` — the in-app product record and immutable logical event intent
- `EmailDelivery` — asynchronous email transport state for a Notification
- `NotificationPreference` — the user's narrow OPTIONAL_INFORMATIONAL email preference

This is not a generic event bus, workflow engine, database-configurable event registry, or template
CMS.

## Code-owned policy and event catalog

Notification policy is owned by code:

- `MANDATORY_SECURITY`
- `MANDATORY_OPERATIONAL`
- `OPTIONAL_INFORMATIONAL`

The first production event is:

- event code: `call_slip.issued`
- policy: `MANDATORY_OPERATIONAL`
- channels: in-app Notification + email

Administrators cannot reclassify event policy through database CRUD.

The optional email preference applies only to `OPTIONAL_INFORMATIONAL` email. Mandatory security
and mandatory operational email are not suppressible by that preference.

## Durable Notification identity and deduplication

Notification uses UUID identity and stores only explicit privacy-safe fields:

- recipient
- event code
- policy snapshot
- title/message
- source type/source UUID
- optional target type/target UUID
- created/read timestamps

There is no arbitrary metadata JSON requirement.

The database uniquely constrains:

recipient + event_code + source_type + source_id

so one logical event cannot create duplicate Notification intent under request retry or concurrency.

For Call Slip:

- source_type = `call_slip`
- source_id = CallSlip UUID
- target_type = `CALL_SLIP`
- target_id = CallSlip UUID

Target metadata is navigation metadata only. Authorization for the source record remains in the
Call Slip domain.

## EmailDelivery and current recipient identity

EmailDelivery is separate from Notification and is one-to-one with a Notification in this
foundation.

It stores:

- UUID
- status
- attempt count
- next/last attempt timestamps
- sent timestamp
- safe failure code
- temporary claim token and expiry
- created/updated timestamps

It does not store SMTP credentials, provider payloads, exception text, recipient-email snapshots,
email bodies, arbitrary provider metadata, or tracebacks.

The worker resolves the recipient's current canonical account email at delivery time. If the account
is inactive before delivery, the delivery becomes terminal `CANCELLED` with safe code
`recipient_inactive`; COMPASS does not send to the inactive account.

## Transactional Call Slip integration

`notify_student` is added to the Call Slip creation command with default `true`.

It is command intent, not controlled-form content, and is not persisted as a CallSlip form field or
returned in ordinary Call Slip read schemas.

`notify_student=true` means live digital issuance. In the existing Call Slip PostgreSQL
transaction COMPASS persists:

1. CallSlip
2. Call Slip audit event
3. Notification
4. EmailDelivery PENDING

If durable Notification/EmailDelivery persistence fails, the Call Slip transaction rolls back.

`notify_student=false` means deliberate historical/back-entry encoding. The CallSlip and audit
record are created, but no live Notification event exists and therefore no EmailDelivery is created.

Historical/live behavior is never inferred from `report_at`. A past `report_at` can still be a
live issuance when the command says to notify.

Existing persistent Call Slip idempotency remains authoritative. The POST request fingerprint
already includes the complete body, so changing `notify_student` changes the fingerprint. The
existing same-key/same-fingerprint retry returns the existing CallSlip before notification creation.
The Notification database uniqueness constraint provides an additional durable deduplication layer.

## Post-commit delivery kick and recovery

SMTP never runs inside the Call Slip transaction.

When a new EmailDelivery is created, `transaction.on_commit(...)` requests immediate Celery
processing using only the EmailDelivery UUID as the task argument.

The callback is deliberately best effort. If broker enqueue fails after commit:

- CallSlip remains committed
- Notification remains committed
- EmailDelivery remains PENDING
- no notification intent is lost

Celery Beat runs one narrow recurring recovery task using
`NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS`. Recovery identifies due PENDING deliveries and
expired PROCESSING claims and re-enqueues only their EmailDelivery UUIDs.

Redis is transport infrastructure, not the durable outbox. PostgreSQL EmailDelivery state is the
recovery source of truth.

## Concurrency-safe claim and crash recovery

Delivery workers claim an eligible EmailDelivery under a PostgreSQL row lock. A claim records a
random claim token and expiry.

A second worker encountering an unexpired PROCESSING claim returns without sending. If a worker
dies, the claim expires and periodic recovery may reclaim the row.

Final SENT/failure updates require the same claim token. This prevents an older worker from casually
overwriting state after another worker has reclaimed an expired lease.

## Retry and terminal behavior

Settings are deployment-owned and validated:

- `NOTIFICATION_EMAIL_MAX_ATTEMPTS`
- `NOTIFICATION_EMAIL_RETRY_BASE_SECONDS`
- `NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS`
- `NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS`

Transport failures and zero-send results use bounded exponential retry. At the maximum attempt count
the delivery becomes terminal `FAILED`.

Template rendering errors are treated as terminal `FAILED` because repeating the same code-owned
template failure is not expected to become transient.

Success sets `SENT`, records `sent_at`, and clears retry/claim state. Duplicate tasks for SENT,
FAILED, or CANCELLED rows are harmless no-ops.

Persisted failure information is restricted to safe classifications such as:

- `transport_error`
- `template_error`
- `send_returned_zero`
- `recipient_inactive`

Logs contain only safe identifiers/status classifications and correlation IDs when available. Email
bodies, recipient addresses, source-domain private text, provider exception payloads, and
credentials are not logged by this foundation.

## Delivery guarantee

Notification and EmailDelivery intent creation is strongly deduplicated per logical Notification
event.

External SMTP transport is **at-least-once**, not exactly-once. There is an unavoidable crash window
where SMTP may accept a message but COMPASS may fail before recording SENT. An expired claim may
therefore theoretically cause a later duplicate email. The design provides durable intent,
concurrency-safe claims, bounded retry, and crash recovery without making an impossible exactly-once
SMTP claim.

## Email rendering and Mailer

The existing `Mailer` remains the only SMTP adapter. It is extended narrowly to support an optional
HTML alternative while preserving required plain-text body and existing attachment behavior.

Notification email templates are code-owned Django templates with autoescaping. There is no
database-editable HTML, raw domain HTML, JavaScript, tracking pixel, or externally hosted tracking
resource.

The Call Slip email is intentionally minimal:

- subject: `New COMPASS Call Slip`
- states that a Call Slip was issued
- tells the recipient to sign in to COMPASS to review details

It does not include Referral reason/actions/remarks, counseling/case content, Course/Year snapshot,
custom destination, Student profile data, or other sensitive Guidance records.

No Call Slip PDF is attached.

COMPASS has no verified public frontend base URL in this slice. Email therefore contains no invented
absolute deep link and does not derive one from API, Host, CORS, CSRF, or ALLOWED_HOSTS settings.

## In-app self-service API

Authenticated users can access only their own Notification records:

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `PATCH /api/v1/notifications/{notification_id}/read`
- `GET /api/v1/notifications/preferences`
- `PATCH /api/v1/notifications/preferences`

No capability is required for self-notification access.

Listing is bounded, newest-first pagination. Mark-read is self-only, server-timestamped, and
idempotent. There is no mark-unread, delete, broadcast, arbitrary resend, recipient inspection, or
delivery-monitoring administrator endpoint.

The API does not expose EmailDelivery status, attempts, failure codes, lease state, recipient email,
or embedded source-domain records.

## Email OTP boundary

Email OTP remains a special security flow:

`EmailOTPChallenge -> dedicated deliver_email_otp Celery task -> Mailer`

The database continues to store only `code_hash`; plaintext OTP remains transient. OTP is not
converted into Notification or EmailDelivery persistence and is not placed in generic notification
metadata, logs, Celery result state, or database email bodies.

The Mailer HTML extension does not require OTP to provide HTML; its existing plain-text
`Mailer().send(...)` call remains valid.

This ADR does not redesign OTP enqueue durability. Stronger reliability for a short-lived plaintext
security secret requires a separate security-specific design.

## Explicit non-goals

This foundation does not add:

- Kafka, RabbitMQ, EventBus, MessageBus, or workflow engine
- database-editable Notification definitions or templates
- SMS, browser push, Firebase, APNs, Messenger, Viber, Telegram, SSE, or WebSocket
- frontend Notification components
- automatic notification integration for Appointments, Good Moral, Counseling, E-Counseling,
  Exit Interview, Feedback/CSM, Graduate Tracer, Referrals, Account Management, or other domains
- Notification deletion/retention scheduler
- administrator delivery-management API
- public frontend/base-URL setting
- synchronous SMTP inside business transactions

## Persistence and migration

This slice adds `notifications/0001_initial.py` for Notification, EmailDelivery, and
NotificationPreference.

No unrelated domain schema is changed. The CallSlip model itself gains no new persisted field for
`notify_student`.

## Consequences

COMPASS now has a reusable but deliberately small durable Notification/email foundation and one real
proving integration.

A committed live Call Slip can survive immediate broker or SMTP failure without losing its
Notification intent, while historical back-entry remains explicit and quiet. Future domains may
integrate through the same explicit service boundary one at a time, with their own privacy-safe
event definitions and policy classification.
