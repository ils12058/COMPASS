# Requirements traceability

| Requirement | Implementation owner | Evidence | Verdict |
|---|---|---|---|
| Keep three distinct booking pathways | Service Catalog, Appointments, Group Sessions | `fe/tests/svc-ux-1.browser.mjs`; backend pathway suites | PASS for selected cases |
| Avoid claiming opportunities from configuration alone | Student catalog/detail panels | SVC-UX-1 browser cases for empty slots, empty groups, pathway combinations, and stale context | PASS for tested UI cases; pagination matrix is not exhaustive |
| Preserve flexible booking/idempotency | Appointments API | `tests/test_appointments.py`, `test_service_cross_pathway_scheduling.py`; `fe/tests/appointment-booking-outcome.test.mjs` | PASS for selected API/unit cases; no real flexible browser chain |
| Preserve fixed-slot Appointment identity/provenance | Service Catalog + Appointments | `test_fixed_date_slots.py`; opt-in real browser integration test | PASS for focused fixed path |
| Preserve Group Session registration and attendance lifecycle | Group Sessions | `tests/test_group_sessions.py`; `fe/tests/service-group-sessions.browser.mjs` | PASS for selected API and mocked-browser cases; no real browser chain |
| Keep Counselor/GSS scope separate from Service administration | Accounts, supervision, Service Catalog, slot API | `test_fixed_date_slots.py`, `test_appointment_management_scope.py`, group staff-boundary tests | PASS for selected backend cases; browser staff operation is partial |
| Enforce recent MFA | Authentication + slot/config APIs | `tests/test_authentication.py` and slot authorization tests | PASS at API/session level; full staff browser re-confirmation not executed |
| Map Inventory prerequisites to typed 409 | `compass/service_catalog/api.py::_raise_slot_error` | New authenticated API test verifies both codes and no Appointment/provenance write | PASS |
| Recover safely from uncertain mutation outcomes | Frontend recovery helpers + domain APIs | SVC-UX-1 recovery tests/browser cases; flexible idempotency API cases | PASS for selected cases; full real browser matrix partial |
| Preserve history, notifications, and confidential boundaries | Domain APIs and access policies | appointment, group, notification-link, scheduling-consequence tests | PASS for selected tests; external delivery not exercised |
| Validate accessibility and responsiveness | UX15 primitives and browser suites | 320px/tablet/desktop, keyboard, and 200% CSS text-size scenarios | PARTIAL; manual screen-reader/native-zoom/physical checks absent |
| Confirm deployment and institutional readiness | Human operators and GCO/team | No deployment or institutional UAT was run | NOT EXECUTED / BLOCKED |
