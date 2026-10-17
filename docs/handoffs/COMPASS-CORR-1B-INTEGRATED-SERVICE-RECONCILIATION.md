# COMPASS CORR-1B — Integrated Service Reconciliation

**Status:** Implementation integrated; consolidated verification was stopped at the user's direction. PR and merge are authorized without waiting for CI.
**Repository:** `ils12058/COMPASS`
**Branch:** `fix/compass-corr-1b-integrated-service-reconciliation`
**PR target:** `staging`
**Merge:** Explicitly authorized by the user without waiting for CI. **Deployment:** Not authorized.

## A. Baseline and coordination

- Latest fetched `origin/staging`: `18c4b1dc3428c25de127edff8a286d0ab4965dd8`, including CORR-2 PR #267 and CORR-3 PR #269.
- CORR-1A dependency commit: `a000e9c99231de7c87f6f73d894de3839555ab84`. It is the unmerged parent of this implementation; no separate CORR-1A PR was found. The branch started from staging `9e83a8c2cc5692b4ee504be56fc3d1567cecbc29` and must integrate the newer staging tip before PR creation.
- The CORR-1A-only [architecture reconciliation](COMPASS-CORR-1A-ARCHITECTURE-RECONCILIATION.md) is a historical snapshot; this document records the consolidated scope.
- CORR-2 PR [#267](https://github.com/ils12058/COMPASS/pull/267) and CORR-3 PR [#269](https://github.com/ils12058/COMPASS/pull/269) are already represented in the fetched staging branch. The CORR-2 overlap includes OpenAPI, appointment/notification, and frontend paths; preserve both changes during integration.

## B. Architecture decisions

### Scheduling policy

- All intervals use half-open overlap semantics: adjacent events are allowed.
- A scheduled Appointment reserves its Student and Counselor.
- A published, unwithdrawn, unbooked Fixed Slot reserves its Counselor. A slot linked to a cancelled Appointment is again an available commitment. A currently booked slot is represented only by its canonical Appointment and is not double-counted.
- A published Group Session reserves each active internal facilitator and each registered Student. External guest speakers are not COMPASS scheduling resources.
- Students cannot hold overlapping scheduled Appointments or registered, published Group Sessions across pathways. Cancellation ends the active commitment while preserving its historical record.
- Completed/cancelled Appointments, withdrawn/unpublished slots, cancelled/completed sessions, and cancelled registrations remain preserved and do not reserve future intervals.
- Cross-pathway mutations lock affected Users in UUID order, then the Service and relevant slot/session rows. Appointment operations keep the existing Appointment lifecycle and locking model. Participant snapshot changes during Group Session schedule operations fail with a retryable conflict.

### Service transitions

Service activation, pathway, delivery-mode, and provider-coverage changes review affected upcoming Appointments, available slots, and published sessions. The API returns distinct dependency flags. Acknowledgement records the review but cannot delete, cancel, rewrite, or reassign commitments. New work checks current Service configuration; historical detail and registration access remain available.

### Organizer and facilitator model

- Organizers coordinate events under the CORR-1A resource policy; this does not grant Counseling authority.
- Internal facilitators are separately represented from Appointment providers. Qualified Counselors remain the only individual Appointment providers. Internal event facilitators follow the event role and scope checks.
- External facilitators use a display-name-only guest representation without a COMPASS account, login, Counselor qualification, or Counseling authority.
- Existing facilitator relationships retain their underlying database column through an additive field rename. Identity snapshots and ended rows preserve authorized event history; changing a facilitator does not transfer organizer permissions.
- Candidate APIs remain read-only and scoped to current operational responsibility; they do not grant `services.manage` to GSS staff.

### Notifications and frontend

Group Session reschedule notifications carry the schedule revision in their source type. Later schedule/detail changes make older notices stale for display and email delivery. Existing registered Student workflows have discovery, register/cancel, detail, and history views; service administration explains configuration, availability, capacity, and lifecycle state without claiming that pathway enablement publishes dates.

## C. Implementation and migration notes

Backend changes reconcile Appointment booking/rescheduling/reassignment, Fixed Slot publication/booking, Group Session schedule/publication/registration, Service consequence review, facilitator candidates, and versioned notification currentness. Frontend changes complete service administration, scoped provider/facilitator selection, Group Session student detail/history, and actionable error/empty/confirmation states. OpenAPI was exported from backend schemas and the Orval client regenerated.

Migration dependencies:

- `group_sessions.0003_group_session_scheduling_and_external_facilitators` depends on `group_sessions.0002_alter_groupsessionfacilitator_group_session` and the configured User model.
- `service_catalog.0004_serviceappointmentslot_withdrawn_at_and_more` depends on the canonical Appointment baseline and `service_catalog.0003_fixed_date_slots`.
- The existing Fixed Slot and Group Session lifecycle migration reverse hooks now permit rollback only when their operational tables have no slot, booking, or Group Session history; otherwise they stop before removing the protection. Canonical baseline migrations are unchanged.
- No live database, staging data, or reset was changed. PR/merge are authorized; deployment is not authorized.

### Changed files

- CI coverage: `.github/scripts/backend_ci.py`, `.github/scripts/test_backend_ci.py`.
- Backend scheduling and lifecycle: `be/compass/appointments/services.py`; `be/compass/service_catalog/access.py`, `api.py`, `fixed_slots_services.py`, `models.py`, `scheduling.py`, `services.py`, `migrations/0004_serviceappointmentslot_withdrawn_at_and_more.py`; `be/compass/group_sessions/access.py`, `api.py`, `models.py`, `services.py`, `migrations/0002_alter_groupsessionfacilitator_group_session.py`, `migrations/0003_group_session_scheduling_and_external_facilitators.py`; `be/compass/notifications/api.py`, `current.py`; `be/compass/common/canonical_migrations.json`.
- Backend regressions and contracts: `be/tests/test_fixed_date_slots.py`, `test_group_sessions.py`, `test_openapi_contract.py`, `test_postbaseline_upgrade.py`, `test_service_cross_pathway_scheduling.py`, `test_service_scheduling_consequences.py`.
- Architecture and handoff: `be/docs/decisions/ADR-SVC-1-service-booking-pathways.md`, this report, and the historical status note in `docs/handoffs/COMPASS-CORR-1A-ARCHITECTURE-RECONCILIATION.md`.
- API contract: `contracts/openapi.json`, exported from backend schemas. The Orval-generated client output is ignored by Git and was regenerated for frontend validation.
- Frontend: `fe/src/features/notifications/notification-targets.ts`, `fe/src/features/portal/components/portal-command-destinations.ts`, `portal-workspaces.ts`; `fe/src/features/services/service-detail-page.tsx`, `service-editor-page.tsx`, `service-fixed-slots-panel.tsx`, `service-group-sessions-panel.tsx`, `services-shared.tsx`; `fe/src/features/group-sessions/group-session-detail-page.tsx`, `group-sessions-history-page.tsx`; `fe/src/app/(portal)/portal/group-sessions/[sessionId]/page.tsx`, `fe/src/app/(portal)/portal/group-sessions/my/page.tsx`.
- Frontend regressions: `fe/tests/service-catalog-consolidation.test.mjs`, `service-group-sessions.test.mjs`, `service-group-sessions.browser.mjs`.

The exact final commit SHA will be added after validation and commit.

## D. Verification record

Regression tests were added for cross-pathway conflicts, transaction races, facilitator lifecycle/privacy, service consequences, current notification revisions, and lifecycle migration protections. The final consolidated verification was not completed because the user directed that tests stop and CI should not be awaited.

Completed local checks recorded before the stop:

- Focused PostgreSQL regression: 11 tests passed.
- Frontend unit suite: 791 passed; `pnpm typecheck` and `pnpm lint` passed; production build passed and included `/portal/group-sessions/discover`.
- Targeted Group Session browser coverage: 2/2 passed in Chromium and 2/2 in WebKit. A subsequent broad browser run was interrupted by the user during the e-counseling suite, so the full browser matrix is incomplete.
- Ruff check/format, Django system check, OpenAPI freshness check, and `git diff --check` passed before/at the stop.
- Full PostgreSQL suite printed `2264 passed, 6 warnings in 3543.37s`, but Ctrl-C landed during teardown; pytest exited 130 with `KeyboardInterrupt`. This is not recorded as a clean full-suite pass.
- CI has not been awaited for the final integrated branch. Any pending, failing, or incomplete checks must be reported separately from the user-authorized merge.

No tests or builds are to be run during the remaining PR/merge steps. Expected consolidated verification commands, if run later, are:

```text
cd be
uv run pytest -q --create-db
uv run python manage.py check --settings=tests.settings
uv run python manage.py makemigrations --check --dry-run --settings=tests.settings
uv run python manage.py export_openapi --check --settings=tests.settings
uv run ruff check .
uv run ruff format --check .

cd ../fe
pnpm api:generate
pnpm test
pnpm lint
pnpm typecheck
pnpm build
pnpm test:ui
```

## E. Delivery

Open one consolidated PR to `staging` and merge it without waiting for CI, as the user explicitly instructed. Report the exact PR/head and the live check states; do not describe the merge as CI-green. Do not deploy. No merge bypass of GitHub branch protection is authorized.
