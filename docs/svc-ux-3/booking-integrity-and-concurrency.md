# Booking integrity and concurrency

## Domain guarantees verified

- Flexible booking persists canonical Appointment data and retains the existing request-idempotency contract.
- Fixed-slot booking uses a row-locked slot, creates a canonical Appointment, and records `ServiceAppointmentSlotBooking` provenance; the opt-in real browser test verified those persisted relationships.
- Group Sessions use a distinct registration/attendance lifecycle. Backend PostgreSQL tests cover capacity, active-registration uniqueness, cancellation/withdrawal, and scheduling interactions.
- Cross-pathway tests use independent PostgreSQL connections for selected Appointment/Group registration and publication conflicts, Appointment/fixed-slot conflicts, Group capacity/withdrawal, and other scheduling consequences.
- Slot publishing/withdrawal and Service changes re-evaluate current scheduling state; the work did not add a global lock or relax database constraints.

Evidence: `tests/test_service_cross_pathway_scheduling.py`, `test_service_scheduling_consequences.py`, `test_service_provider_qualification.py`, `test_appointment_slot_reservations.py`, `test_fixed_date_slots.py`, `test_group_sessions.py`, and `test_appointments.py`.

## Limits

The current run covers selected races already encoded by those suites, not every one of the 18 proposed race combinations. The real browser test is a single Student fixed-slot success path, not a concurrency test. No concurrent Browser→Next transaction was run. Stale MFA and concurrent scope updates are covered at backend/API level only where the existing tests specify them; do not extrapolate to untested cases.
