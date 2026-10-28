# Student pathways

## Existing routes

- Flexible individual appointment: `/portal/appointments/book` and My Appointments at `/portal/appointments/my`.
- Scheduled individual slot: `/portal/appointments/book?pathway=FIXED_DATE_SLOT`; fixed-slot context is a Service UUID, not authorization.
- Group Session discovery, detail, and history: `/portal/group-sessions/discover`, `/portal/group-sessions/{sessionId}`, and `/portal/group-sessions/my`.

Student Home and the booking entry expose separate links for flexible appointments, scheduled slots, and Group Sessions. Fixed-slot and group discovery can carry Service context while retaining their own workflow rules. A direct fixed-slot link with invalid or inactive Service context fails safely.

## Availability wording

An active Service can have no enabled pathway, and an enabled pathway can have no published offering. A published slot/event can still be unavailable because of capacity, status, eligibility, schedule conflicts, or current prerequisites. The UI must describe each from the appropriate API state. Catalog pagination is page-local; no new unbounded fetch or universal pathway filter was added.

Selected SVC-UX-1 browser cases cover separate pathway links, page-local search with page 2, stale/invalid Service context, empty slot/group lists, fixed-slot conflict, saved-Appointment link, group registration recovery, current-Student restriction, and 200% CSS text sizing. These are synthetic API fixtures. The opt-in real Browser→Next→Django→PostgreSQL test covers the fixed-slot transaction only.

Existing flexible scheduling remains independent and keeps its idempotency contract. Fixed booking has no idempotent replay guarantee and is not automatically retried. Group registration uses its own registration collection and cancellation lifecycle.
