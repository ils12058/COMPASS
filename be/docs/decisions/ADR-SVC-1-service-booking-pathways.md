# ADR-SVC-1 — Independent Service booking pathways foundation

Status: **Proposed implementation (COMPASS-SVC-1); no new booking endpoints shipped**.

## Ownership and audit

The current Service Catalog (`be/compass/service_catalog/models.py`,
`services.py`, `api.py`) owns service identity, active status, delivery modes,
individual booking availability, and Counselor qualification. Appointment
(`be/compass/appointments/services.py`) owns flexible booking and stores immutable
reservation provenance. Availability computes Office/Provider windows;
Organization resolves College responsibility and the default Counselor.
Neither Appointment nor Counseling is the parent of every Service workflow.
ADR-018, ADR-019, ADR-020 and ADR-089 remain in force.

The prior boolean `appointment_booking_enabled` means **flexible individual
Appointment booking only**; it is not a generic switch for a group registration or
predefined date. New Student booking still checks it, current delivery mode,
duration, Inventory prerequisite, qualified active Counselor, Availability,
and booking conflicts. Existing Appointment events, notification identities,
and audit action catalogs are unchanged.

## Normalized relationship

`ServiceBookingPathway(service, code)` is an enabled-pathway relationship,
one unique row per Service and recognized code:

| code | meaning | SVC-1 operation |
| --- | --- | --- |
| FLEXIBLE_APPOINTMENT | Existing variable-time individual booking | Existing booking works unchanged |
| FIXED_DATE_SLOT | Future provider-qualified published time slots | Configuration only |
| GROUP_SESSION | Future session/event catalog and registration | Configuration only |

Multiple rows may coexist; no row means disabled. Codes are constrained by
the application enumeration and API validation, with a DB uniqueness constraint
for the Service/code pair. There is no mutually exclusive enum, no fixed
number of future scheduling records, and no third-party calendar dependency.

`Service.appointment_booking_enabled` remains the canonical compatibility
signal for existing Appointment code. Catalog create/update transactions
synchronize the `FLEXIBLE_APPOINTMENT` relationship. Legacy clients that
omit `booking_pathways` retain prior semantics and preserve fixed/group
configuration during an Appointment toggle. Requests that explicitly send
both the old boolean and the new list must agree. Unknown/duplicate codes,
null updates, and invalid combinations are rejected. GET responses expose
all configured pathway codes, but the additional two paths do **not**
indicate active Student registration.

Migration `service_catalog.0002_booking_pathways` creates only a new table;
a forward data migration inserts a `FLEXIBLE_APPOINTMENT` row for every existing
Service with `appointment_booking_enabled=True`, including canonical Counseling.
It does not rewrite existing Service or Appointment rows. Canonical Counseling's
first-time bootstrap creates the flexible relationship too. The reverse data
operation is a no-op to avoid destructive data loss.

## Future owner boundaries

**SVC-2 — Fixed-Date Slot publishing:** a fixed slot belongs to a Service,
uses an active/qualified Counselor provider and supported delivery mode, carries
a capacity of one (or an explicit design decision), and uses its own time
interval/availability and lifecycle checks. No Group registration is an Appointment.

**SVC-3 — Group Sessions / Events:** a separate session/event model defines
organizers, facilitators, capacity, location/mode, registration windows and
access. A facilitator is not silently an individual Appointment provider:
an organizer may coordinate without Counseling authority. Counseling access
remains relationship-based and role-gated.

**SVC-4 — Registration / attendance lifecycle:** transactional capacity,
idempotency, cancellation, waitlist decision, audit and scoped participation
views. Registration creates no Appointment or Counseling Encounter automatically.

**SVC-5 — Notifications, exports and operational rollout:** dedicated
student/supervisor notification decisions, privacy-safe templates, report
authorization, and UAT scenarios once live booking models are implemented.

Group or fixed-slot rows/registrations **do not yet exist**. Before SVC-2/3
allow booking, enforce new-work activation/transition guards that prevent
configuration changes from silently orphaning reservations or registrations.
SVC-1 reuses current ADR-089 scheduling acknowledgement if switching off
flexible booking, removing delivery modes, or changing Counselor qualification
affects scheduled Appointments. No existing reservation is rewritten.

## Security and compatibility

`services.catalog.view` governs active catalog reads; inactive Service reads
require `services.manage`. Catalog create/update/enable/disable use existing
`services.manage`, recent MFA, PostgreSQL transactions, audit actions, and
client cache invalidation. Student catalog reads cannot mutate configuration.
The additional pathway flags grant **no** Appointment, Counseling,
E-Counseling, organizational, or provider authorization.

The fixed-date pathway will reuse Counselor qualification but does not
introduce time slots yet. Group sessions will have distinct organizer and
facilitator roles and separate resource authorization; neither GSS nor a
Head Guidance designation gains Counselor-only or institution-wide access
through the flags.

## Concurrent PR and operational implications

The parallel Appointment Reminders PR #256 modifies `appointments/`,
`notifications/`, `audit/actions.py`, `config/settings.py`, and Appointment
frontend pages. SVC-1 modifies **only** `service_catalog/`, its frontend
administrator views, dedicated tests and this ADR. No shared changed files,
no reminder migration dependency, and no new reminder/notification event codes.

Deploy only through reviewed standard migrations. PostgreSQL, Redis, encryption
keys, Celery, runtime secrets, existing user accounts, credentials and UAT
participant allocation are unchanged. The new pathway options are safe metadata
configuration only; no external messages or calendar invitations are emitted.

Run the canonical migration consistency check, complete backend Service Catalog
and Appointments regressions, regenerate the Orval client, lint/typecheck/build,
frontend unit tests, and browser regressions. No database or deployment mutation
is authorized by this PR.
