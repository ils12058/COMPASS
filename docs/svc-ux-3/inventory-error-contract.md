# Fixed-slot Inventory error contract

The correction was already present in the fetched baseline; SVC-UX-3 did not reimplement it. `compass/service_catalog/api.py::_raise_slot_error` maps:

| Domain exception | HTTP | API code |
|---|---:|---|
| `AppointmentCurrentAcademicYearNotConfigured` | 409 | `current_academic_year_not_configured` |
| `AppointmentCurrentInventoryRequired` | 409 | `current_inventory_required` |

The new `test_api_fixed_slot_inventory_prerequisite_errors_are_authenticated_409_responses` uses an authenticated Django session cookie and CSRF token. It publishes a fixed slot through the API, books without a configured current Academic Year, then creates a synthetic current year and retries without Inventory. Each request returns the expected typed 409; neither creates an Appointment nor sets `current_appointment_id`.

Frontend handling in `appointmentErrorMessage` recognizes both codes as definite refusal. The fixed-slot panel treats a typed 409 as a known conflict/eligibility result; timeouts, unreadable results, and 5xx remain unconfirmed. No new Inventory rule, migration, response code, or pathway requirement was added.
