# COMPASS CORR-1A — Architecture Reconciliation

**Status (2026-10-17): Historical CORR-1A-only snapshot.** CORR-1A implementation commit `a000e9c99231de7c87f6f73d894de3839555ab84` is the unmerged dependency for the consolidated CORR-1B implementation. The open-scope and deferred-verification sections below describe the earlier A-only checkpoint and are superseded by [the integrated CORR-1B handoff](COMPASS-CORR-1B-INTEGRATED-SERVICE-RECONCILIATION.md).

**Repository:** `ils12058/COMPASS`  
**Base:** `origin/staging` at `9e83a8c2cc5692b4ee504be56fc3d1567cecbc29`  
**Correction branch:** `fix/service-catalog-corr-1a-security-lifecycle`  
**Scope:** P0 resource authorization, participant privacy, and non-destructive operational lifecycles.  
**Deployment / merge:** Not authorized.

## Audit method and concurrent work

The audit used the exact staging source for Service Catalog, Group Sessions, Appointments, Availability, Organization, Accounts/capabilities, Audit, Notifications, API contracts, frontend flows, migrations, and tests. Decisions reviewed: ADR-018, ADR-019, ADR-020, ADR-089, ADR-SVC-1, ADR-011, ADR-061, ADR-069, ADR-072, and ADR-114. Implementation/integration material reviewed: `docs/handoffs/AGENT-2-SVC-FINAL-HANDOFF.md` and the COMPASS-INT-FINAL correctness, integration, validation, and deployment reports.

ADR-SVC-1 is the only SVC-specific ADR present. It defines independent pathways, keeps flexible Appointments canonical, and says group registration creates no Appointment or Encounter. SVC-2 through SVC-5 details in the Agent-2 handoff and COMPASS-INT-FINAL reports are historical implementation claims, not accepted architecture. The COMPASS-INT-FINAL manifest names an older `staging` SHA (`d41637a…`); it was not used as the baseline.

At audit time, the only open PRs were #260 and #261, both Follow-Up work; their changed paths do not overlap this correction. The existing `feat/compass-svc-3-group-sessions` worktree was clean and was left untouched. The source worktree for this correction starts at the verified latest staging SHA above. The primary checkout's untracked deployment/UAT evidence was left untouched.

The canonical migration registry includes `service_catalog` 0002/0003 and `group_sessions` 0001; canonical 0001 baselines are unchanged. The implementation handoff documents merged SVC PRs #263/#264; no active SVC PR was found. ADR-011 describes the audit trail as append-only by application design and says to disable actor accounts rather than delete them. ADR-072 states no effective approved retention rule means no destructive treatment. Neither establishes a Service Catalog disposal schedule.

## Requirement-to-implementation reconciliation

| Requirement | Intended architecture | Current implementation at baseline | Evidence | Classification | Correction / disposition |
|---|---|---|---|---|---|
| Independent service pathways | Flexible appointments, fixed slots, and group sessions may coexist; pathway flags grant no provider or record authority. | `ServiceBookingPathway` is a unique Service/code relation and the UI can enable multiple pathways. | ADR-SVC-1; `service_catalog.models.ServiceBookingPathway`; `service_catalog.services.update_service`. | Correctly implemented | Preserve. Schedule conflict and configuration-transition gaps are handed to CORR-1B. |
| Canonical individual booking | Fixed-slot booking creates the canonical Appointment; group registration creates neither Appointment nor Counseling Encounter. | Fixed-slot booking creates `appointments.Appointment`; group registration creates `GroupSessionRegistration`. | `fixed_slots_services.book_fixed_slot`; `group_sessions.services.register_student`; ADR-SVC-1. | Correctly implemented | Preserve both domain boundaries. |
| Fixed Slot lifecycle | Historical slots, identifiers, providers, and Appointment provenance remain; ordinary staff cannot hard-delete a slot. | `DELETE /services/{service_id}/slots/{slot_id}` invokes `delete_fixed_slot()` and calls `slot.delete()`. Its guard only treats a linked `SCHEDULED` Appointment at the original start time as booked; a cancelled/completed/no-show slot can therefore be deleted. | `service_catalog.api.services_delete_slot`; `fixed_slots_services.is_slot_booked` / `delete_fixed_slot`; `ServiceAppointmentSlot`. | Confirmed architectural violation | Remove DELETE operation. Add irreversible `withdrawn_at` lifecycle state; preserve Appointment links and booking history; protect Service and Appointment foreign keys. |
| Fixed Slot rebooking provenance | Rebooking after a cancelled appointment must not discard the earlier Appointment-to-slot relationship. | A cancelled linked Appointment makes the slot bookable again; `book_fixed_slot()` replaces the slot's only `current_appointment` pointer. | `fixed_slots_services.list_student_bookable_slots` / `book_fixed_slot`; `ServiceAppointmentSlot.current_appointment`. | Confirmed implementation bug | Add a durable slot-booking history relation and backfill the existing pointer additively; retain `current_appointment` as the latest booking pointer. |
| Group Session lifecycle | A draft may be withdrawn without removing its identity, organizer, facilitators, or Audit history. | `DELETE /group-sessions/{id}` physically deletes DRAFT sessions and facilitator rows; `CANCELLED` already accepts DRAFT and draft registration is disallowed. | `group_sessions.api.delete_session`; `group_sessions.services.delete_group_session` / `cancel_group_session`; `GroupSessionStatus`. | Confirmed architectural violation | Remove DELETE operation and service. Add explicit draft withdrawal using existing `CANCELLED`, with a distinct append-only `group_session.withdrawn` audit action; do not add a new status. |
| Session-level authority | General eligibility is separate from authority over one session. Head designation is not blanket event authority. | Staff endpoints require active Counselor/GSS plus `appointments.manage`; staff lists/details, metrics, mutations, roster, attendance, and export then operate across all sessions. | `group_sessions.api._require_staff`, `list_group_sessions`, `get_session`, metrics/roster/attendance/export routes. | Confirmed security/privacy defect | Scope each session by organizer or current direct Counselor supervision of a GSS-organized session. Assigned Counselors can view and take attendance for their session only; this does not grant event administration. Enforce again in locked domain operations. |
| GSS supervision | GSS authority follows an active supervision relationship and a specific resource assignment. | The group API does not consult `StaffSupervision` or the operational responsibility policy. | `group_sessions.api._require_staff`; `organization.models.StaffSupervision`; `organization.access_scope.resolve_operational_responsibility_scope`. | Confirmed security/privacy defect | Require active current GSS supervision, capability, and resource ownership/supervision; fail closed outside that scope. |
| Participant identities and attendance notes | Only resource-authorized operational staff may read identifiable roster information or staff-authored notes. Students retain self-only views and never see staff attendance notes. | All eligible staff can list all registration identities, emails, cancellation data, attendance, and notes. Student self-registration is self-filtered and `attendance_notes` are redacted. | `group_sessions.api.list_registrations`, `get_my_registrations`; `group_sessions.services.export_roster_csv`. | Confirmed security/privacy defect; student boundary correctly implemented | Organizer/current supervisor receives full roster and notes. Assigned facilitator gets only the minimal roster fields needed for attendance; no email, institutional ID, notes, or exports. Preserve student self-service behavior. |
| Group Session lists and metrics | Lists and aggregates are filtered to resources in the caller's authorized scope before pagination/aggregation. | Staff session list and metrics query all sessions. A scoped role/capability still exposes unrelated sessions and aggregates. | `group_sessions.api.list_group_sessions` / `get_metrics`; `group_sessions.services.get_group_session_metrics`. | Confirmed security/privacy defect | Apply resource scope in querysets before serialization and aggregation. |
| Fixed Slot provider scope | Counselor manages only their own provider slots; GSS management follows direct supervision; Head designation does not broaden provider scope. | `_require_slot_management()` checks role and `appointments.manage`; list and mutations accept any provider/slot ID. Some linked Appointment PII is redacted, but redaction does not constrain mutation. | `service_catalog.api._require_slot_management`; `fixed_slots_services.list_staff_fixed_slots`, `create_fixed_slot`, `update_fixed_slot`; Appointment access policy. | Confirmed security/privacy defect | Filter lists by allowed provider and re-check provider scope inside create/update/withdraw transactions. Preserve qualification, appointment privacy, and recent MFA. |
| Fixed Slot foreign-key preservation | Service and Appointment provenance must not be removed by parent deletion. | Slot `service` uses `CASCADE`; `current_appointment` uses `SET_NULL`. | `ServiceAppointmentSlot` and `service_catalog.0003_fixed_date_slots`. | Confirmed architectural violation | Change both to `PROTECT` in an additive migration. Add booking history without rewriting existing operational rows. |
| Group Session foreign-key preservation | Facilitator and registration records remain attached to their operational session history. | Registration/session and organizer relations are protected, but facilitator/session uses `CASCADE`; the ordinary delete workflow deletes facilitators explicitly. | `GroupSessionFacilitator`, `GroupSessionRegistration`; `delete_group_session`. | Confirmed implementation risk | Remove the delete workflow and use `PROTECT` for facilitator/session linkage in a forward migration. |
| Appointment professional boundaries | Existing qualification and Appointment management checks remain authoritative; IT Admin does not gain Counselor event authority. | Fixed Slot staff gate excludes IT Admin and requires `appointments.manage`; Appointment PII uses `appointment_management_access_allowed`. Group staff roles also exclude IT Admin. | `service_catalog.api._require_slot_management`; `appointments.access`; `group_sessions.api._require_staff`. | Correctly implemented in part | Keep these gates; add resource-level checks without changing appointment or counseling authority. |
| Service configuration changes | Disabling a pathway, Service, delivery mode, or provider coverage must not silently orphan existing operational records. | `_scheduling_consequences()` reviews only scheduled Appointments. Removing fixed/group pathways or disabling a Service does not inspect slots, sessions, registrations, or attendance. | `service_catalog.services._scheduling_consequences`, `update_service`, `set_service_active`; slot/session models. | Confirmed incomplete implementation | CORR-1B: define per-pathway dependency guards, consequences, and confirmation contracts; do not fold into CORR-1A. |
| Scheduling promises across pathways | Flexible Appointments, fixed slots, and Group Sessions must not promise conflicting times to Students or Counselors. | Fixed slot creation checks scheduled Appointments and other slots. Appointment booking does not consider open fixed slots or group facilitation; group session creation/update/registration do not check Counselor/Student schedule overlaps or provider Availability. | `fixed_slots_services._validate_service_and_counselor`; `appointments.services._has_overlap`; `group_sessions.services.create_group_session`, `update_group_session`, `register_student`. | Confirmed incomplete implementation | CORR-1B: design shared conflict and concurrency policy across booking, publishing, registration, rescheduling, and facilitation. |
| Organizer and facilitator distinction | Organizer coordinates; facilitator participation does not confer Counseling authority. Guest/non-Counselor facilitators need not have fake Counselor accounts. | Organizer is a user; every facilitator is a user FK treated as a qualified Counselor, and API input accepts only Counselor UUIDs. | `GroupSession`, `GroupSessionFacilitator`; `is_counselor_qualified`; create/update schemas. | Confirmed incomplete implementation; institutional policy required for external identity/visibility | CORR-1C: add the smallest separate internal/external facilitator representation and define organizer/facilitator visibility and edit rights. Do not grant COMPASS access to external speakers. |
| Frontend lifecycle/API consistency | Staff UI uses the non-destructive operation and accurately reflects implemented pathways and authorization. | Staff panels expose Delete; service detail still says fixed-slot booking and group registration are “coming later”; the GSS facilitator picker is enabled only with `services.manage`; export button calls `/roster.csv` while backend route is `/roster/export`. | `service-fixed-slots-panel.tsx`; `service-group-sessions-panel.tsx`; `service-detail-page.tsx`; `group_sessions.api.export_roster`. | Confirmed implementation bugs / UX inconsistencies | CORR-1A changes Delete actions to Withdraw and gates session controls from backend resource capability fields. CORR-1D owns stale pathway copy, provider-selection contract, and export-route correction. |

## Authorization decisions for CORR-1A

`appointments.manage` and active Counselor/GSS identity remain the general eligibility gate. For Fixed Slots, a Counselor may manage their own provider resources; a GSS may manage only the directly supervised active Counselor's resources while that supervision remains valid. The Head Guidance designation adds no slot scope. Queries are scoped before returning rows; each locked mutation repeats current actor/capability/supervision/provider checks.

For Group Sessions, the organizer owns session administration. A Counselor may also manage a GSS-organized session only while that GSS is currently and directly supervised by them. A GSS must have an active Counselor supervisor to operate their own session. A listed Counselor facilitator can view the event and the minimal participant roster and record attendance for that session; facilitator status grants no metadata editing, event cancellation/publication, attendance-note access, or export. Organizer/supervisor can access full participant data and export. Unrelated staff receive an empty filtered list or a not-found response for direct IDs. Student self-registration and self-view remain unchanged.

## CORR-1A implementation tracker

**Current work is CORR-1A only.** CORR-1B through CORR-1D are intentionally unstarted pending the user's next implementation prompt. The audit matrix above describes the verified baseline; the following tracker records the A-only working-tree changes. No merge, deployment, or final validation has been authorized.

| Area | Files changed or added | A-scope implementation |
|---|---|---|
| Fixed Slot authorization and lifecycle | `be/compass/service_catalog/access.py` (new); `be/compass/service_catalog/fixed_slots_services.py`; `be/compass/service_catalog/api.py`; `be/compass/service_catalog/models.py`; `be/compass/service_catalog/migrations/0004_serviceappointmentslot_withdrawn_at_and_more.py` (new) | Counselor/GSS provider scope and transactional rechecks; withdraw instead of delete; preserve slot and appointment provenance; booking-history backfill and rolling-deployment pointer trigger; protected foreign keys and PostgreSQL delete guards. |
| Group Session authorization and lifecycle | `be/compass/group_sessions/access.py` (new); `be/compass/group_sessions/api.py`; `be/compass/group_sessions/services.py`; `be/compass/group_sessions/models.py`; `be/compass/group_sessions/migrations/0002_alter_groupsessionfacilitator_group_session.py` (new); `be/compass/audit/actions.py` | Resource-scoped management and metrics; minimal facilitator roster/attendance authority; draft withdrawal; protected facilitator/session relationship and PostgreSQL session delete guard. |
| Contracts and migration registry | `be/compass/common/canonical_migrations.json`; `contracts/openapi.json`; `be/tests/test_openapi_contract.py` | Register additive migration leaves and reflect withdraw routes, removed DELETE routes, and capability fields in the API contract. Frontend client generation is required from this OpenAPI file. |
| Regression tests authored, not run | `be/tests/test_fixed_date_slots.py`; `be/tests/test_group_sessions.py`; `fe/tests/service-fixed-slots.test.mjs`; `fe/tests/service-group-sessions.test.mjs` | Cover lifecycle preservation, authorization scope, identity/capability changes, participant privacy, withdrawal audits, PostgreSQL delete and rolling-deployment guards, concurrent withdrawal/capacity behavior, and UI action gating. |
| A-scope UI lifecycle and permissions | `fe/src/features/services/service-fixed-slots-panel.tsx`; `fe/src/features/services/service-group-sessions-panel.tsx`; `fe/tests/service-fixed-slots.test.mjs`; `fe/tests/service-group-sessions.test.mjs` | Replace delete actions with withdrawal and use API capability fields to gate Group Session actions and participant data. The provider-selection and remaining pathway UX corrections are left to 1D. |
| Reconciliation and handoff | `docs/handoffs/COMPASS-CORR-1A-ARCHITECTURE-RECONCILIATION.md` | This audit, implementation tracker, migration dependencies, unresolved cross-scope work, and deferred verification plan. |

**Migration dependency graph:** `service_catalog.0004` depends on `appointments.0001_canonical_baseline` and `service_catalog.0003_fixed_date_slots`; it adds `withdrawn_at`, changes slot foreign keys to `PROTECT`, creates and backfills booking history, adds a PostgreSQL trigger to capture legacy `current_appointment` pointer writes during rolling deployment, and adds PostgreSQL delete guards. `group_sessions.0002` depends on `group_sessions.0001_initial`; it changes facilitator/session deletion to `PROTECT` and adds a PostgreSQL session delete guard. Both migration leaves are listed in `be/compass/common/canonical_migrations.json`. The booking-history backfill and lifecycle protections are forward-only because rollback would erase provenance or restore destructive deletion behavior.

**A-scope open items:** CORR-1B still owns cross-pathway scheduling conflicts and service/pathway/provider configuration consequences. CORR-1C still owns internal/external facilitator representation and policy. CORR-1D still owns the stale pathway copy, least-privilege provider picker, roster-export URL mismatch, fixed-slot table inconsistency, and broader responsive/error-state review. In particular, the A API access rules are enforced server-side, while GSS provider selection in the existing UI still depends on the separate provider-selection correction in 1D. Do not fold those items into this A-only implementation.

## Deferred verification plan

Per the user's testing-strategy adjustment, test suites, full regression, frontend builds, browser suites, migration validation, Ruff, TypeScript, ESLint, and comprehensive checks remain deferred until CORR-1A and consolidated CORR-1B–1D are implemented and integrated. Regression tests are being added alongside changes; none have been executed in this worktree. No check below is reported as passing.

After full CORR-1 integration, run the following against the PostgreSQL-backed test configuration and the integrated branch:

```sh
# Full PostgreSQL-backed suite (creates a clean test database and applies migrations)
cd be
uv run pytest -q --create-db

# Focused CORR-1 security, lifecycle, Appointment, and contract regressions
uv run pytest tests/test_fixed_date_slots.py tests/test_group_sessions.py \
  tests/test_appointment_management_scope.py tests/test_appointments.py \
  tests/test_appointment_slot_reservations.py tests/test_service_catalog.py \
  tests/test_openapi_contract.py -q --reuse-db

# Migration graph, database state, canonical registry, and generated API contract
uv run python manage.py check --settings=tests.settings
uv run python manage.py makemigrations --check --dry-run --settings=tests.settings
uv run pytest tests/test_canonical_baseline.py -q --reuse-db
uv run python manage.py export_openapi --settings=tests.settings \
  --output ../contracts/openapi.json --check

# Python static checks
uv run ruff check .
uv run ruff format --check .

# Frontend generated API, unit tests, static checks, production build, and all browser suites
cd ../fe
pnpm api:generate
pnpm test
pnpm lint
pnpm typecheck
pnpm build
pnpm test:ui
```

`pytest --create-db` must target PostgreSQL and is the clean-database migration application check; run destructive migration experiments only against a disposable database. Add any CORR-1B–1D-specific commands to this list as their contracts and regression suites are defined. Record exact commands and outcomes here only after that consolidated verification is performed.

## Prioritized implementation handoff

### CORR-1B — Scheduling and configuration integrity (P1; separate PR)

**Confirmed entry points:** Appointment overlap detection is Appointment-only; fixed-slot creation checks Appointments and other slots but not group events; Group Session creation/update/registration lacks provider and Student overlap checks. Configuration consequence review sees only Appointments.  
**Work:** Define whether published slots reserve Counselors, whether facilitation blocks individual Availability, how overlapping Student groups/Appointments are rejected, and how cancellation/reschedule restores availability. Enforce under a common PostgreSQL lock order; test publish-vs-book, register-vs-appointment, and reschedule-vs-facilitation races. Add pathway/service/mode/provider-coverage transition guards that report exact dependent slot/session/registration counts and require explicit review. Preserve group registration as independent from Appointment/Encounter.  
**Dependencies:** CORR-1A resource policies and lifecycle state; institutional decision for whether group attendance is a scheduling commitment and how group schedule scope interacts with Service availability. Suggested ownership: Appointments + Service Catalog + Group Sessions, one coordinated PR after CORR-1A merges.

### CORR-1C — Organizers and facilitators (P1; separate PR)

**Confirmed entry point:** `GroupSessionFacilitator.counselor` is a protected FK and all create/update validation requires a Service-qualified Counselor.  
**Work:** Represent internal Counselors and external speakers without fake accounts; keep organizer, individual Appointment provider, and event facilitator as distinct concepts. Define which resource actions belong to organizer, internal facilitator, external facilitator, and GSS. External participation must not create a COMPASS login, Counselor authority, Appointment, or Counseling Encounter. Decide whether external names/contact data require retention or attendee visibility policy before adding fields.  
**Dependencies:** CORR-1A session resource permissions; institution must decide which participant data external facilitators may receive and which staff own event governance. Suggested ownership: Group Sessions domain + frontend, with Organization/identity review.

### CORR-1D — Frontend and operational consistency (P2; separate PR)

**Confirmed findings:** pathway facts still say booking/registration are coming later; GSS facilitator selection depends on `services.manage`; roster export URL is stale; fixed-slot table has a duplicated Counselor cell under a different heading; discovery and error feedback need a complete state review.  
**Work:** Use a narrowly scoped eligible-Counselor selection contract that does not grant broad catalog management; show only backend-authorized actions; correct export URL; update pathway availability and empty/error states; review status, capacity, registration, and attendance feedback at mobile widths. Confirm whether institutionally defined student audience restrictions exist before adding filters. Preserve the distinctions between service appointment providers and group facilitators.  
**Dependencies:** CORR-1A backend resource-capability response and CORR-1C facilitator model. No College/Program audience limits without an approved institutional basis. Suggested ownership: Frontend + Service Catalog API.

## Migration and operational safety

The A-scope schema changes are additive and forward-only as listed above. Existing non-null `current_appointment` links are copied into history without changing current pointers. During rolling deployment, a PostgreSQL trigger records pointer changes made by an older application process, while the new application writes history explicitly; a unique pair constraint makes the trigger's duplicate insert harmless. No production-like database, staging data, canonical baseline, or already-applied migration was rewritten in this worktree. PostgreSQL guards reject direct physical deletion of slot, slot-booking-history, and group-session records even when an older application path is present. Deployment and merge remain unauthorized.

## Verification record

Implementation review only: Python syntax compilation, OpenAPI export, frontend API generation, and `git diff --check` were completed earlier in this A-only work. These are not test-suite, migration, lint, type, build, browser, or final-validation results. All deferred commands above remain unrun until the complete CORR-1 scope is integrated.
