# ADR-020: Appointment foundation

> **Backend Slice 2 appointment authorization alignment (2026-10-11).** Head Guidance
> has institution-wide eligible College visibility for **general Guidance / Office Messages**
> (Backend Slice 1), but **managed Appointment access is assigned-provider-only**, for
> *every* Service including non-Counseling. The former Head-only organizational bypass
> in `appointments.access` has been removed from both single-resource and queryset checks.
> No institution-wide appointment grant follows the designation, a College assignment,
> or the unique-Head routing fallback.
>
> Ordinary Counselors retain provider access and existing handled-College
> non-Counseling management; GSS retains current-supervisor handled-workload
> delegation for non-Counseling appointments subject to their **own**
> `appointments.manage` capability. Counseling appointments are provider/Student
> relationship-only. Appointment detail, history, upcoming counts, action availability,
> cancel/reschedule/reassign/complete/no-show and their lookup endpoints share these
> canonical resource gates. A provider reassignment changes this authority immediately.
> Student `view_self`/`manage_self` and Counselor provider `view_self` stay distinct
> from staff-management rights. These rules neither change routing nor authorize any
> Counseling encounter, E-Counseling room, Routine Interview, Shared Summary or
> Counseling Message without its own relationship check.
>
> The original ADR below documents the booking foundation, not an exception to the
> current provider boundary. Assessment Type capability alignment is **Slice 3**.


## Status

Accepted. [ADR-089](ADR-089-service-catalog-consolidation-and-counselor-qualification.md) makes booking use two-state booking capability and Service-specific Counselor qualification, keeps College responsibility out of explicit Counselor choice, and lets existing Appointments be fulfilled as booked after later Catalog changes; rescheduling and reassignment follow current rules. Where this decision interprets UCN civil time in `settings.TIME_ZONE`, [ADR-097](ADR-097-institutional-civil-time-independent-of-runtime-timezone.md) uses `INSTITUTION_TIME_ZONE`.

## Context

COMPASS needs a shared reservation domain that records which Student reserved which Service, with
which Provider, delivery mode, and scheduled interval. Organization remains the source of default
Counselor routing, Service Catalog remains the source of appointment policy, delivery modes,
default schedulable duration, provider-role eligibility, and cancellation policy, and Availability
remains the source of potential Office/Provider time.

Appointment is not Counseling, ServiceDelivery, or Availability. This slice deliberately excludes
rescheduling, completion/no-show states, Call Slip, rooms, notifications, e-Counseling delivery,
and persisted slots.

## Decision

Create a dedicated `compass.appointments` domain with `Appointment` and
`AppointmentReferenceCounter`.

Appointments use UUID primary keys plus unique human references formatted
`APT-YYYY-NNNNNN`. The year is the Appointment creation year in `settings.TIME_ZONE`, not the
scheduled year. Allocation happens after routine booking validation inside the same PostgreSQL
transaction. The yearly counter is locked with `select_for_update`; first-row creation relies on
its unique year key plus retry/re-fetch behavior under concurrency.

Appointment lifecycle is intentionally limited to `SCHEDULED` and `CANCELLED`. Cancellation is
a state transition; Appointment rows are not deleted. Student, Provider, and Service foreign keys
use `PROTECT`; creator/canceller actor links use `SET_NULL`.

Service Catalog gains nullable non-negative `cancellation_cutoff_minutes`. Active Services with
`appointment_policy = NONE` must not configure a cutoff. OPTIONAL/REQUIRED Services may configure
one. Booking snapshots both the derived `ends_at` and current cancellation cutoff so later Service
changes never rewrite existing reservations.

Student self-booking derives the Student from `request.auth_user`. An explicit Provider must be an
active Counselor eligible for the Service. Organizational College scope does not restrict explicit
Counselor selection. If Provider is omitted, Appointments calls the canonical Organization default
Counselor resolver. Availability failure never causes silent Head fallback or replacement-provider
search.

Booking accepts a timezone-aware start, normalizes it to `settings.TIME_ZONE`, locks Student and
Provider User rows in deterministic UUID order, then locks the Service row. Under those locks it
revalidates active roles and Service policy, derives end time from
`Service.default_duration_minutes`, requires the complete half-open Appointment interval to fit
inside one canonical Availability interval, checks overlapping SCHEDULED reservations for both
Provider and Student, allocates a reference, creates the Appointment, and records Audit.

SCHEDULED overlaps use half-open semantics:
`existing.starts_at < requested_end and existing.ends_at > requested_start`. CANCELLED rows do
not reserve time. No persisted slot model or arbitrary 15/30/60-minute grid is introduced.

Booking is the first endpoint to consume the existing Redis idempotency boundary. The key is scoped
by actor + POST + route + Idempotency-Key and compared by request fingerprint. Successful responses
are stored for replay; an owned in-progress reservation can be abandoned after a rolled-back domain
failure so validation errors do not poison the key. Redis unavailability fails closed. PostgreSQL
locks and conflict queries remain authoritative because Redis replay state is not transactionally
atomic with the Appointment commit; ADR-009's crash-window limitation remains explicit.

Student self-cancellation requires ownership, `appointments.manage_self`, SCHEDULED state, a
pre-start request, and the snapshotted cutoff. The exact cutoff boundary is allowed. Administrative
cancellation requires `appointments.manage` plus recent MFA, may bypass the Student cutoff, but
still cannot cancel after start in this foundation. Repeated cancellation returns the existing
CANCELLED state without a second Audit event.

Capabilities are `appointments.view_self`, `appointments.manage_self`, and
`appointments.manage`. Student receives view_self/manage_self. Counselor and Guidance Services
Staff receive view_self for Appointments assigned to them as Provider. Head Guidance Counselor
designation adds manage. IT Admin and DPO receive no Appointment business capability by default.

Account Management explicitly invokes Organization, Availability, then Appointment role-transition
validators. Leaving STUDENT or a provider role is blocked while the user has a SCHEDULED
Appointment with `ends_at > now`; cancelled and historically ended reservations do not permanently
trap role changes.

## Consequences

The public Appointment API is intentionally small: create own booking, list own assigned records,
managed list, detail, cancellation, and eligible-Counselor discovery. There is no general PATCH or
DELETE. Counseling's current 60-minute norm is represented only through Service configuration;
the confirmed 30-minute Counseling cancellation notice is likewise Service configuration, not a
Counseling-specific conditional.

Changes to Availability, Service policy, user status, or Organization after booking do not silently
move, reassign, resize, or cancel existing Appointment records. Future explicit workflows may add
rescheduling, conflict resolution, Call Slip integration, Counseling encounters, service delivery,
and notifications.
