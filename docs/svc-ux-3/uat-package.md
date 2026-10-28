# Stakeholder UAT package

**Status for every task: NOT RUN.** Use synthetic or institution-approved UAT accounts and approved non-production records. Capture screenshots/log references without exposing confidential data.

| Actor | Prerequisites | Steps | Expected outcome | Evidence field |
|---|---|---|---|---|
| Current Student | Active account; Services with different pathway combinations | Open Student Home and booking entry; follow each pathway | Flexible, fixed, and group workflows are separate and clearly named | NOT RUN — link/screenshot and notes |
| Current Student | Flexible Service, qualified Counselor, available schedule | Complete a flexible booking; open My Appointments | One canonical Appointment with correct Service/provider/time | NOT RUN — Appointment reference and approved evidence |
| Current Student | Published fixed slot | Book once; check saved link and My Appointments | Canonical Appointment is shown; a second Student cannot take the slot | NOT RUN — slot/Appointment reference |
| Current Student | Published Group Session with capacity | Register, open detail, then My Registrations | One Group registration appears; no Appointment is created | NOT RUN — session/registration reference |
| Current Student | Existing Appointment and Group registration | Open both history views and deep links | Only authorized own records appear and each opens the correct domain record | NOT RUN — redacted screenshots |
| Counselor | `appointments.manage`, own eligible Service/provider | Create, publish, edit, and withdraw an unbooked slot | Only own permitted provider scope is available | NOT RUN — actor, slot, audit evidence |
| Supervised GSS | Active direct Counselor supervision and `appointments.manage` | Create/manage slots for supervisor; attempt another provider | In-scope work succeeds; out-of-scope request is denied by backend | NOT RUN — actor/scope and response evidence |
| IT Administrator / Head Guidance | Relevant role, no provider authority | Attempt to open or mutate Counselor slots | Service administration or designation alone does not grant provider scope | NOT RUN — denial evidence |
| Service administrator | `services.manage` | Configure pathway combinations and review catalog wording | Flexible flag remains distinct; status/configuration is not shown as an available offering | NOT RUN — configuration and screen evidence |
| Counselor / supervised GSS | Authenticator set up; consequential slot action | Trigger recent-MFA prompt, verify, review refreshed data, deliberately confirm | No blind replay; current state and scope are rechecked before commit | NOT RUN — redacted step-by-step recording |
| Student | Existing schedule conflict, occupied slot, full/closed event | Attempt affected booking/registration | Conflict is explained and no duplicate/over-capacity record is created | NOT RUN — redacted response/state evidence |
| Student | Approved test network fault plan | Interrupt response, inspect authorized history, refresh | Outcome is labeled accurately; no unsafe automatic retry or fabricated ID | NOT RUN — network trace and state evidence |
| Student | Service with existing Inventory prerequisite | Remove/omit current-year Inventory in approved test data | Typed prerequisite result appears; no booking is written | NOT RUN — error code and record counts |
| Authorized Group Session staff | Published event and registered UAT Student | Record/correct attendance and review roster | Attendance follows Group Session authority and does not create an Encounter | NOT RUN — session/attendance evidence |
| Student + staff | Approved notification test configuration | Follow booking/registration notification links and a denied other-user link | Link reaches the correct authorized record; other-user data remains denied | NOT RUN — redacted notification references |
| Student and staff | Screen reader, keyboard, native zoom, physical devices available | Complete discovery, forms, dialogs, MFA, and histories with assistive technology | Controls and announcements remain usable; issues are documented | NOT RUN — assistive tech/device/version and findings |
| GCO + records owner | Synthetic historical records and approved Service changes | Compare Appointment, slot, registration, attendance, and snapshot facts before/after | Existing commitments and historical snapshots remain unchanged | NOT RUN — redacted before/after evidence |
