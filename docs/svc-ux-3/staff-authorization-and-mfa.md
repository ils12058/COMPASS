# Staff authorization and MFA

## Verified model

- Service Catalog changes require `services.manage`.
- Fixed-slot operations require appointment-management authority plus resource-level provider/supervision scope. A Counselor manages permitted own-provider slots; a GSS operator is restricted by direct active Counselor supervision and backend qualification.
- IT Service administration authority does not itself grant provider-scoped slots. Head Guidance designation does not override the appointment scope check.
- Group Session organizer, facilitator, roster, and attendance permissions remain Group Sessions rules; facilitation is not Counselor appointment qualification.
- Recent MFA is checked on consequential slot mutations in the backend. The UI's shared StepUpDialog refreshes state and requires deliberate confirmation rather than replaying the old action.

Backend selections in `test_fixed_date_slots.py`, `test_appointment_management_scope.py`, `test_group_sessions.py`, and `test_authentication.py` exercised capability denial, scoped actors, active supervision, CSRF/session handling, TOTP verification, and recent-MFA enforcement. Selected tests also cover revocation/staleness at the API layer.

## Limits

The real browser integration ran as a Student and did not exercise staff slot editing. Browser StepUpDialog scenarios use synthetic API fixtures; real authenticator completion followed by UI refresh/re-confirmation under concurrent scope changes was not run end to end. Mark staff-browser assurance PARTIAL.
