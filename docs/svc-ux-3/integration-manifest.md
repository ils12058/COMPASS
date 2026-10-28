# Integration manifest

## Merged slices

| Slice | Responsibility | Current boundary |
|---|---|---|
| SVC-UX-0 / PR #331 | Audit of catalog, booking paths, authority, and open decisions | Audit only; decisions remain with the institution/team |
| SVC-UX-1 / PR #332 | Student pathway discovery, context, recovery, and route clarity | UX presentation; existing booking domains remain separate |
| SVC-UX-2 / PR #333 | Service configuration UX and scoped fixed-slot operations | `services.manage` remains distinct from `appointments.manage` |
| Inventory contract fix | Typed fixed-slot error mapping | HTTP 409 `current_academic_year_not_configured` / `current_inventory_required` |
| SVC-UX-3 | Integrated validation and focused tests | No production-code correction was required |

## Operation ownership

| Operation | API / UI entry | Domain owner |
|---|---|---|
| Flexible appointment booking | `POST /api/v1/appointments`; `/portal/appointments/book` | Appointments, Availability, Service Catalog qualification/configuration |
| Fixed-slot publication and booking | `/api/v1/services/{service_id}/slots...`; `/portal/appointments/slots` and Student fixed-slot panel | Service Catalog slot and booking records, canonical Appointments, scheduling services |
| Group Session lifecycle | `/api/v1/group-sessions...`; `/portal/group-sessions/*` | Group Sessions, registrations, attendance, facilitators |
| Service configuration | `/api/v1/services...`; `/portal/services` | Service Catalog; `services.manage` |
| Authentication and step-up | `/api/v1/auth/*`; shared StepUpDialog | Authentication/session services; server-side capability and recent-MFA enforcement |

## Compatibility boundaries

- `appointment_booking_enabled` controls flexible appointment booking. It is not an umbrella availability flag.
- Service activity and configured pathways do not imply a published or Student-eligible opportunity.
- Fixed-slot bookings create canonical Appointments and retain slot provenance.
- Group registration/attendance is not an Appointment or Counseling Encounter.
- Counselor provider scope, supervised GSS scope, Service administration, and Group Session organizer/facilitator authority remain separate.
- No SVC-UX-3 migration, generated API change, capability grant, or policy change was introduced.
