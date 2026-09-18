# ADR-028: Interview Permit / Call Slip Foundation

## Context

The Guidance and Counseling Office uses the historical controlled one-page
`INTERVIEW PERMIT / CALL SLIP`, identified as `CNSC-OP-GTA-01F8`, Revision 0,
Page 1 of 1. It directs a Student where and when to report, identifies the
Guidance Counselor who issued the permit, and provides source blanks for when
the interview ended.

The controlled code is historical QMS identity. COMPASS must not rewrite it to
a later institutional brand or manufacture a replacement `UCN-OP-GCO-01F8`.

A Call Slip is a reporting permit. It is not an Appointment, Referral,
Counseling Encounter, Routine Interview, Case Record, notification, scheduling
engine, workflow engine, or generic form-builder instance.

## Decision

### Focused domain

Create `compass.call_slips` with one `CallSlip` aggregate. The record uses a
UUID primary key only. The source form contains no human reference number, so
COMPASS does not invent `CSL-*`, `CALL-*`, or any yearly counter.

The model stores:

- canonical Student FK plus server-derived historical Student-name snapshot
- source `Course/Year` snapshot, without introducing an SIS course/year/block model
- `GUIDANCE_OFFICE` or `OTHER` destination semantics
- timezone-aware `report_at`, combining the paper Date and Time fields
- active Counselor `issued_by` plus historical issuer-name snapshot
- authenticated `recorded_by`, kept distinct from the institutional issuer
- required historical `FormRevision`
- optional one-to-one Referral provenance
- nullable immutable timezone-aware `interview_ended_at`
- actor-scoped persistent creation-idempotency digests
- server persistence timestamps

All Call Slip models disable Django default model permissions.

### Controlled form identity

Institutional Forms family `call_slip` supports internal schema version 1.
Forward migration `0005_call_slip_family.py` bootstraps:

- title: `Interview Permit / Call Slip`
- official code: `CNSC-OP-GTA-01F8`
- official revision: `0`
- internal schema version: `1`
- status: `ACTIVE`

Creation requires the current active *supported* `call_slip` FormRevision.
Future QMS activation affects new Call Slips only; historical records retain the
revision they originally referenced.

### Time semantics

`report_at` is the date/time at which the Student was instructed to report.
It may be in the past or future because COMPASS may encode historical paper
Call Slips. It is not Appointment schedule truth or Counseling occurrence time.

`created_at` is when COMPASS persisted/encoded the digital Call Slip. It must
not be presented as a historical paper issuance timestamp. The source form
contains no independent `issued_at` field, so this foundation does not invent
one.

`interview_ended_at` is narrow operational completion metadata from the source
form. It must be timezone-aware and cannot initially be future-dated. Once set,
the same instant may be retried idempotently but a different instant conflicts.
No rule requires it to be later than `report_at` or `created_at`.

### Destination invariant

`GUIDANCE_OFFICE` requires an empty `other_destination`.
`OTHER` requires meaningful non-whitespace destination text. Service
validation and a database check constraint preserve this source invariant
without introducing a generic office/location hierarchy.

### Issuer versus recorder

A Counselor actor issues only as themselves.

Guidance Services Staff may encode a Call Slip only on behalf of their current,
active supervising Counselor. Creation resolves and locks the StaffSupervision
relationship and supervising User inside the database transaction. The API does
not accept arbitrary `issued_by_id`.

Head Guidance Counselor remains a Counselor and issues as themselves.

Snapshots are server-derived from the Student and issued Counselor. No signature
image, cryptographic signature, or generated signed PDF is part of this slice.

### Resource scope

Capabilities are necessary but not sufficient. Call Slip evaluates current
Organization relationships in its own authorization helpers rather than
importing Referral private helpers or treating
`effective_responsibility_colleges()` as a resource-access decision.

- Head Guidance Counselor: institution-wide Student scope.
- ordinary Counselor: Students currently affiliated with colleges assigned to that Counselor.
- Guidance Services Staff: scope inherited from the current supervising Counselor.
- Staff supervised by Head inherit Head's institution-wide operational scope.
- Student: self-view only.
- IT Admin and DPO: no Call Slip content access by default.

### Optional Referral provenance

A Call Slip may be created directly without a Referral.

When `referral_id` is supplied, the Referral is locked in the creation
transaction and must:

- exist within the actor's current operational Student scope
- belong to the same Student
- already contain `SEND_CALL_SLIP_INTERVIEW_PERMIT`
- not already be linked to another Call Slip

The database enforces at most one linked Call Slip per Referral with a nullable
OneToOne relationship.

Call Slip creation never creates a ReferralAction, never changes Referral
reason/status, and never copies Referral reason, referrer, status, actions, or
remarks into the Call Slip.

### Persistent creation idempotency

Create requires `Idempotency-Key`. COMPASS stores only an actor-scoped SHA-256
digest and request fingerprint on the Call Slip. The raw key and completed HTTP
response are not stored in Redis.

Creation locks the authenticated actor before duplicate lookup. Same actor/key
and same request returns the same Call Slip UUID after current authorization and
scope are re-checked. Reusing the key for a different request conflicts.

### Student privacy boundary

The Call Slip is directed to the Student, so Students receive
`call_slips.view_self` and may list/get only their own records.

Student-facing schemas expose only the permit content intended for the Student:
own identity/snapshot, Course/Year, destination, `report_at`, issuer identity
and snapshot, form display metadata, `interview_ended_at`, UUID, and
`created_at`.

Student responses do not expose the linked Referral identifier/reference,
Referral content, or `recorded_by`. Operational Guidance responses may expose
only the linked Referral UUID/reference and safe recorder identity; Referral
content remains available only through the independently authorized Referral
API.

### API and capabilities

The v1 `call-slips` domain exposes:

- `POST /api/v1/call-slips` — `callSlipsCreate`
- `GET /api/v1/call-slips` — `callSlipsList`
- `GET /api/v1/call-slips/{call_slip_id}` — `callSlipsGet`
- `GET /api/v1/call-slips/me` — `callSlipsListMy`
- `GET /api/v1/call-slips/me/{call_slip_id}` — `callSlipsGetMy`
- `PATCH /api/v1/call-slips/{call_slip_id}/interview-ended` —
  `callSlipsRecordInterviewEnded`

The static `/me` routes are registered before the dynamic UUID route.

Capabilities:

- Counselor: `call_slips.view`, `call_slips.manage`
- Guidance Services Staff: `call_slips.view`, `call_slips.manage`
- Student: `call_slips.view_self`
- IT Admin/DPO: none

Deployments continue to run `python manage.py sync_identity_policy`.

### Audit and privacy

Successful creation and first interview-end recording synchronously append
`call_slip.created` and `call_slip.interview_ended` in the same transaction
as the business mutation. Audit target type is `callslips.callslip` because
Audit target segments do not permit underscores.

Safe metadata is restricted to operational identifiers such as destination type,
issuer UUID, and controlled-form identity. Audit excludes Student and issuer
name snapshots, Course/Year, custom destination, Referral content, email
addresses, notification bodies, and full request payloads.

Call Slip content is not projected into Security/My Activity.

### Notification readiness, not implementation

The repository has generic Celery/Redis plumbing but no established
notification/outbox domain. This foundation therefore creates no email, in-app
notification, notification table, outbox row, reminder scheduler, Celery
notification task, push delivery, parent message, or delivery/read state.

A future notification design should transactionally persist the Call Slip and a
durable notification/outbox intent, then perform delivery after commit.
Delivery failure must never roll back or delete the institutional Call Slip.
Student notification and the Referral parent-notification action remain
separate concerns.

### Downstream independence

Creating or completing a Call Slip does not create or mutate Appointment,
Counseling Encounter, Routine Interview, Counseling Shared Summary,
E-Counseling room, Case Record, notification, or email. It does not require
Inventory, Academic Year, Appointment, Counseling Encounter, Routine Interview,
or Referral.

There is no status enum, generic edit endpoint, reissue/correction engine,
delete/archive/retention policy, or print/PDF generation in this foundation.

### Validation

Targeted GitHub Actions remains read-only. Existing targeted regression suites
remain in place and `tests/test_call_slips.py` is added. The full backend suite
is not required by default.

## Consequences

COMPASS can faithfully record the controlled Interview Permit / Call Slip,
including historical back-entry and Student self-view, without conflating the
permit with scheduling, counseling, Referral content, notification delivery, or
invented document numbering.

Future work may deliberately add notification/outbox delivery, print rendering,
reissue/correction semantics, or explicit scheduling orchestration when
authoritative workflow evidence establishes those requirements.
