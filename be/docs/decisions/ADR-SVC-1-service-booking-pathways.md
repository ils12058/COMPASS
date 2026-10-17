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

## CORR-1 scheduling and facilitator reconciliation

The three pathway relationships remain independent and may coexist. Flexible
Appointment booking and a booked Fixed Slot both create the canonical
`Appointment`; a Group Session registration remains a separate record and
creates no Appointment or Counseling Encounter.

Scheduling commitments use half-open intervals. A scheduled Appointment
reserves its Student and Counselor. An available Fixed Slot reserves its
Counselor only while it is published, not withdrawn, and unbooked or linked to
a cancelled Appointment; once booked, the canonical Appointment is the only
hold. A published Group Session reserves each assigned internal facilitator,
and its registered Students. An internal Counselor therefore cannot overlap
an Appointment, an available Fixed Slot, or another published Group Session;
an external guest is never a COMPASS scheduling resource. A Student cannot
hold overlapping scheduled Appointments or registered published events.
Cancelled, completed, withdrawn, and unpublished records remain preserved but
do not reserve future intervals. Adjacent intervals are allowed.

Cross-pathway mutations serialize on participating User rows in UUID order,
then lock the Service and relevant slot or Group Session rows. Appointment
reschedule and reassignment retain their canonical Appointment row lock and
also lock participants before checking cross-pathway commitments. Conflict
reads do not take reverse Appointment row locks. This keeps the existing
Appointment model and Availability resolver authoritative without creating a
general scheduling engine.

Service activation, pathway, delivery-mode, and provider-coverage changes may
require an explicit consequence review when upcoming Appointments, available
Fixed Slots, or published Group Sessions are affected. Acknowledgement records
that review only; it never deletes, cancels, rewrites, or reassigns an existing
commitment. New work still checks current Service configuration and resource
authorization. Existing registrations and direct event history remain
available when new registration is disabled.

The event organizer owns event coordination under resource-level authority.
Internal facilitators receive only the event access granted to an assigned
facilitator; they do not become individual Appointment providers. A GSS's
candidate scope follows current direct supervision. Counselor qualification
remains role-based, and College responsibility does not restrict an explicit
Counselor choice (ADR-089). External facilitators are display-name-only guest
records with no COMPASS account, login, Appointment qualification, or
Counseling authority. If no lead is supplied, the first listed facilitator is
the lead; only one active lead is allowed. Replacements end old facilitator
rows and preserve name snapshots for authorized event history.

New reschedule notifications identify the Group Session schedule revision.
A later time or delivery-detail change makes older queued or displayed update
notices stale. Stale notices remain privacy-safe and link to the current event
details.

Lifecycle migration reverse paths are data-guarded. Rollback is permitted only
when the related operational tables contain no slots, slot bookings, or Group
Sessions; when history exists, the migration raises before removing its
database protection or schema. The existing canonical baseline remains
unchanged.

## Concurrent PR and operational implications

The concurrent CORR-2 PR #267 is still open. It modifies Appointment reminder,
Guidance Follow-up, work-queue, Notification, OpenAPI, and frontend files.
CORR-1 touches `contracts/openapi.json` and `be/tests/test_openapi_contract.py`
in common with that PR; no CORR-2 application changes are included here. After
the intended CORR-1 and CORR-2 backend changes are integrated, regenerate and
verify the combined OpenAPI contract and generated client.

Deploy only through reviewed standard migrations. PostgreSQL, Redis, encryption
keys, Celery, runtime secrets, existing user accounts, credentials and UAT
participant allocation are unchanged. The new workflow emits only the defined
in-app Group Session notifications; no external messages or calendar invitations
are emitted.

Run the canonical migration consistency check, complete backend Service Catalog
and Appointments regressions, regenerate the Orval client, lint/typecheck/build,
frontend unit tests, and browser regressions. No database or deployment mutation
is authorized by this PR.
