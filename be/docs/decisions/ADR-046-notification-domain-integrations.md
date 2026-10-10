# ADR-046: Notification Domain Integrations

- Status: Accepted
- Date: 2026-09-19
- Scope: backend-only integration of the ADR-041 Notification and EmailDelivery foundation with selected COMPASS domain and account-security workflows

## Context

ADR-041 remains authoritative for durable Notification intent, EmailDelivery persistence, deduplication,
delivery claims, retries, current canonical recipient-email resolution, inactive-recipient cancellation,
post-commit Celery dispatch, and Beat recovery.

This decision does not redesign that infrastructure. It connects selected existing business facts to the
existing code-owned Notification event catalog. PostgreSQL remains the durable source of truth and
Celery remains delivery transport. SMTP is never performed synchronously by the business request.

Email OTP remains a separate authentication mechanism:

`EmailOTPChallenge -> dedicated OTP Celery task -> Mailer`.

OTP values, recovery codes, TOTP secrets, passwords, session identifiers, and other credential material
must never be copied into generic Notifications, EmailDelivery rows, templates, logs, or Celery
arguments.

## Event catalog and policy

All events in this ADR use `IN_APP + EMAIL`.

Mandatory operational events are:

- `call_slip.issued` (existing and unchanged)
- `appointment.scheduled`
- `appointment.cancelled`
- `good_moral.issued`
- `exit_interview.reopened`
- `counseling.shared_summary.published`
- `ecounseling.consent.requested`

The optional informational event is:

- `feedback.invitation`

Mandatory security events are:

- `security.password.reset`
- `security.mfa.disabled`
- `security.recovery_codes.regenerated`
- `security.mfa.admin_reset`
- `security.account_access.changed`

Optional-email preference suppresses EMAIL only for `OPTIONAL_INFORMATIONAL`. The in-app
`feedback.invitation` still exists when optional email is disabled. Mandatory operational and
mandatory security email cannot be suppressed by that preference.

The catalog and templates remain code-owned. No database-configurable event catalog or editable email
template CMS is introduced.

## Privacy-safe content

Notification and email wording states only that a meaningful event occurred and directs the recipient to
sign in to COMPASS when review is appropriate.

Generic Notification/email content does not include Counseling notes or summaries, referral reasons,
Exit Interview answers or reopen reason, Good Moral certificate/receipt details, E-Counseling room
credentials or media/transcript data, account override reasons, passwords, OTPs, recovery codes, TOTP
secrets, session identifiers, or raw audit metadata.

There is no verified frontend base URL, so this ADR adds no absolute URL or deep link. Templates remain
static and render without arbitrary domain context. No JavaScript, tracking pixel, external tracking
asset, or attachment is introduced.

## Operational integrations

### Appointments

Successful `create_student_appointment(...)` creates one `appointment.scheduled` Notification for
the Student and one for the Appointment provider. The persisted Appointment UUID is the logical source
and target.

A successful first `cancel_appointment(...)` creates `appointment.cancelled` for the same two
recipients. An already-cancelled idempotent call creates no additional Notification.

Appointment reminders are deferred. No reminder scheduler or Beat task is added.

### Good Moral and Feedback

The first successful `REQUESTED -> ISSUED` transition creates:

- mandatory `good_moral.issued` for the Student; and
- optional `feedback.invitation` for the Student.

Both use the Good Moral request UUID as source identity but remain distinct logical events because the
event codes differ. Repeated issuance is idempotent and creates neither again.

Feedback invitation does not create or prefill a Customer Feedback or CSM response.

### Counseling

Creation of a new `CounselingEncounter` is the existing completed-service fact because actual
`started_at` and `ended_at` already exist. It creates one optional `feedback.invitation` for the
Student, using the Encounter UUID as source identity.

No fake Counseling COMPLETED state is introduced. Notification persistence is inside the same
authoritative transaction as Encounter creation and its AuditEvent, including the existing nested
`_create_row(...)` transaction structure.

First publication of a Counseling Shared Summary creates mandatory
`counseling.shared_summary.published` for the Student. Re-publishing an already-published summary
does not create another Notification, and summary content is never copied into generic notification
content.

### Exit Interview

A successful `SUBMITTED -> DRAFT` correction reopen creates `exit_interview.reopened` for the
Student using the Exit Interview UUID as source/target identity. The reopen reason and Interview
answers are not copied into Notification/email.

### E-Counseling consent

One `request_consents(...)` command may create several new consent scopes but produces at most one
`ecounseling.consent.requested` Notification.

If no consent row is newly created, no Notification is created. If one or more rows are new, the first
new consent UUID is the durable source identity and the Appointment UUID is the E-Counseling target.
A later command that genuinely introduces a new scope may therefore create a new Notification without
a random batch identifier or additional batch model.

## Security-event identity and recipients

Security notifications are created only for successful sensitive state changes. Failed password login,
failed TOTP verification, failed recovery-code verification, and rate-limit rejection remain
Audit/security-observability facts and never trigger generic Notification/email. This prevents an
unauthenticated attacker from using failed authentication to generate victim email.

Repeating account-security mutations must not use the User UUID as the Notification source because
that would suppress legitimate later mutations under the existing logical uniqueness key:

`recipient + event_code + source_type + source_id`.

Instead, the canonical successful `AuditEvent` UUID is the source identity and the affected User UUID
is the `ACCOUNT_SECURITY` target.

The integrations are:

- existing-account password reset -> `security.password.reset`; initial password setup is excluded;
- successful self-service TOTP disable -> `security.mfa.disabled`;
- successful recovery-code regeneration -> `security.recovery_codes.regenerated`;
- actual administrative MFA reset -> `security.mfa.admin_reset`;
- actual role, designation assignment/removal, or capability override set/removal ->
  `security.account_access.changed`.

Administrative no-ops do not notify.

Account disable/enable, Student lifecycle change, ordinary identity correction, administrative email
change, and session revocation are intentionally excluded. Email-change security alerting is deferred
because current EmailDelivery semantics resolve only the account's current canonical email and do not
preserve the previous address.

## Transaction and delivery semantics

For mandatory operational/security events, successful state mutation, canonical AuditEvent,
Notification, and EmailDelivery PENDING intent are persisted in the same authoritative PostgreSQL
transaction. If Notification/EmailDelivery persistence fails before commit, the corresponding state
mutation rolls back.

Feedback invitation is optional informational but is also persisted in the same domain transaction for
deterministic creation and deduplication.

Delivery dispatch remains `transaction.on_commit(...)`. A broker/Celery enqueue failure after commit
does not roll back the business action: the committed EmailDelivery remains PENDING and existing Beat
recovery may retry it.

ADR-041's SMTP semantics remain at-least-once, not exactly-once.

## Deduplication and historical data

The existing Notification uniqueness constraint is unchanged.

Ordinary domain events use their persisted domain row as source identity. Repeating security mutations
use their successful AuditEvent UUID. E-Counseling consent-request batches use the first consent row
newly created by the command.

No historical Notification backfill is performed and no migration scans existing domain rows or
security AuditEvents. This ADR affects future successful transitions only.

## API and persistence impact

No new Notification API is introduced. Existing self-service list, unread count, mark-read, and
preference endpoints remain authoritative. EmailDelivery remains internal/operator-facing and its
technical delivery state is not exposed to ordinary users.

No Notification schema change or new domain notification field is required. No OpenAPI surface change
is intended.

## Explicitly deferred

This ADR does not add Appointment reminders, SMS, push/browser push, WebSocket, SSE, Firebase/APNs,
third-party messaging, arbitrary broadcast, admin compose-email, custom recipient lists, editable
templates, file attachments, marketing/newsletter email, failed-login email, account email-change
alerts, session-revocation email, generic Referral notification, every-AuditEvent notification,
notification-retention scheduling, or frontend notification UI.
