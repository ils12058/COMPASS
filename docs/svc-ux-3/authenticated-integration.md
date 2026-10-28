# Authenticated integration evidence

## Executed chain

One opt-in Chromium test completed **Browser → production Next.js → Django API → disposable PostgreSQL** for a fixed-slot booking. Next.js was built with a loopback API rewrite. The final run used Django `live_server` at `127.0.0.1:8212` and Next at `127.0.0.1:3112`; the backend test database was in the task-owned PostgreSQL cluster on port 55446.

The Counselor slot was created through an authenticated API client using a persisted opaque application session and real CSRF. The Student browser received an opaque session token minted by the application's session service as an HttpOnly cookie. Browser API reads and the booking POST passed through Next's rewrite to Django; CSRF was enforced. Only the loopback Next origin was added to the test process's `CSRF_TRUSTED_ORIGINS` for that run. No API responses were mocked or fulfilled by Playwright.

The browser selected the Service and slot, confirmed the booking, saw the saved Appointment link, and opened My Appointments. The test verified the exact reference in both the authenticated `/api/v1/appointments/me` response and rendered list. It then queried PostgreSQL and checked Student, Counselor, Service, `ServiceAppointmentSlotBooking.appointment_id`, and `ServiceAppointmentSlot.current_appointment_id`. Result: **1 passed**.

The opt-in requires a production Next build with `COMPASS_API_BASE_URL` set to the same loopback Django port used by pytest's `--liveserver`. The test opts in with `COMPASS_SVC_REAL_FRONTEND_URL` and `COMPASS_SVC_REAL_API_PORT`; without these variables it is skipped. The documented run used a dedicated disposable PostgreSQL cluster and `--reuse-db`.

## Limits

The browser session was issued through the application's session helper; this test does not claim to cover the login form or authenticator ceremony. Actual TOTP/session/step-up behavior has separate backend tests. Flexible and Group Session journeys were validated with authenticated backend tests and mocked-browser UX tests, not a real browser-to-API run. Staff operations, concurrent browser requests, notifications through external providers, and response-loss scenarios were not executed in this end-to-end harness.
