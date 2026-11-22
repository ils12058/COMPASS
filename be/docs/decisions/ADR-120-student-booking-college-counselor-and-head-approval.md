# ADR-120: Student Appointment booking restricted to College Counselor and Head-approved exceptions

- Status: Accepted owner decision (post-evaluation update after `b4fc84d9`).
- Date: 2026-11-21
- Supersedes the "College scope is never consulted" / unrestricted explicit Counselor choice part of
  [ADR-089](ADR-089-service-catalog-consolidation-and-counselor-qualification.md) for Student
  Appointment booking (both flexible Appointments and fixed-date Appointment slots). Service
  qualification, delivery modes, Availability, existing-Appointment provenance, direct Counseling,
  direct Routine Interviews, rescheduling, and reassignment rules in ADR-089 stand unchanged.

## Context

Under ADR-089, `list_eligible_counselors()` offered every active Counselor qualified for the
selected Service across all Campuses, and `create_student_appointment()` / `book_fixed_slot()`
accepted any qualified `provider_id`. College responsibility only marked the Student's default
Counselor.

During the November 17–20, 2026 UCN Guidance and Counseling Office (GCO) evaluation, a GCO
Counselor established the operational rule:

- A Student should see and book only the Counselor assigned to their own College.
- Booking with a different Counselor requires the Head Guidance Counselor's permission.

## Decision

### 1. Permitted Counselors for Student booking

For every new Student booking (flexible Appointments and fixed-date slots), server-side discovery
and locked booking transactions admit only Counselors in the Student's current permitted set:

1. **Default Counselor:** the active Counselor assigned to the Student's current College
   (`CounselorResponsibility`), or the single active Head Guidance Counselor when the Student's
   College has no active assigned Counselor (`HEAD_GUIDANCE_FALLBACK`).
2. **Active Counseling Case Counselors:** the current primary Counselor of any `ACTIVE` Counseling
   Case belonging to the Student (following approved transfers), and any active receiving Counselor
   holding an `ACCEPTED` temporary coverage window on that case while `starts_at <= now < expires_at`.
3. **Head-approved Counselor:** an active Counselor held in a standing `StudentCounselorApproval`
   granted for this Student by the Head Guidance Counselor.

Service qualification (`service_counselor_eligible`) still applies on top of this set. If none of
the Student's permitted Counselors provides the selected Service, COMPASS offers no other
Counselors, explains the boundary plainly, and offers a request to the Head Guidance Counselor.

### 2. Requests for a different Counselor and standing approvals

- A current Student may submit a `CounselorBookingRequest` from the booking page, with an optional
  preferred Counselor (chosen from active Counselors qualified for the canonical Counseling Service)
  and an optional free-text reason.
- At most one `PENDING` request may exist per Student (enforced in the transaction and by a partial
  unique database constraint).
- The free-text reason is confidential: it is encrypted at rest as a bound, versioned Fernet JSON
  envelope (`document_kind: "COUNSELOR_BOOKING_REQUEST_REASON_V1"`) using the web-only
  `COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS` keyring (already provisioned for web processes and
  cleared in workers), decrypted only in the Head Guidance Counselor's request detail endpoint, and
  excluded from Student responses, Work Queue projections, Notifications, emails, logs, and Audit
  metadata.
- Request routing uses the existing `active_head_guidance_counselors()` helper. If there is not
  exactly one active Head Guidance Counselor (zero or more than one), request submission and
  Head decision/approval mutations are blocked with a plain message to contact the Guidance Office;
  requests are never routed to anyone else.
- Pending requests appear in the Head's Work Queue and on Portal Overview, accompanied by an in-app
  Notification and a strictly content-free email ("A student asked for a different counselor", plus
  a link to the request detail page, with no Student name and no reason).
- The Head may approve a request (choosing or confirming any active Counselor qualified for
  Counseling) or decline it with an optional note to the Student.
- An approval is stored as a standing `StudentCounselorApproval` (at most one active row per
  Student) and lasts until the Head changes the approved Counselor or ends the approval; it is not
  single-appointment and does not expire with the Academic Year.
- If an approved Counselor becomes inactive (or stops holding the Counselor role), the Student
  falls back to their default Counselor automatically at read and booking time.
- Every Head decision, approval change, or approval ending notifies the Student in-app and via a
  content-free email linking back to Appointment booking.

### 3. Staff booking, rescheduling, reassignment, and existing Appointments

- The Head Guidance Counselor may book or arrange Appointments with any Service-qualified active
  Counselor (checked inside the locked booking transaction against the Head's live designation and
  `appointments.manage` capability).
- Non-Head staff booking on a Student's behalf are subject to the same permitted-Counselor rule as
  the Student.
- Existing Appointments are never modified or invalidated. Rescheduling keeps the Appointment's
  existing Counselor, and existing Head-approved case reassignment remains unchanged.

## Consequences

- `list_eligible_counselors()`, `list_bookable_slots()`, `create_student_appointment()`,
  `list_student_bookable_slots()`, and `book_fixed_slot()` all enforce the permitted-Counselor rule
  server-side; UI filtering is presentation only.
- Additive migration `appointments/migrations/0003_counselor_booking_access.py` adds
  `CounselorBookingRequest` and `StudentCounselorApproval` without modifying existing tables or
  data.
- No new capability or runtime secret file is required for deployment; only `migrate` is needed.
