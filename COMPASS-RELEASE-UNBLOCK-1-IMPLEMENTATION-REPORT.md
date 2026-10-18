# COMPASS-RELEASE-UNBLOCK-1 — Implementation and release verification

Date: 2026-10-18 (Asia/Manila). Repository: `ils12058/COMPASS`.
Branch: `codex/release-unblock-1`; target: `staging`.

## Starting state and evidence boundaries

Fetched latest `origin/staging` before creating the dedicated worktree:
`7d362b2b736b9425e460917dea992fd09cb157b4`.
Worktree: `/Users/reynantlntno/.codex/worktrees/compass-release-unblock-1/COMPASS`.
The primary checkout and its untracked UAT/import artifacts were preserved.
Recent merged changes include avatar presentation (#290/#291), MFA continuation (#289),
email-change verification (#287), and OpenAPI test alignment (#292).

Read-only checks during this task confirmed:

- Backend `/api/v1/meta`: the same full SHA and `environment=live-staging`.
- `/api/v1/health/ready`: application, database and canonical Services all `ok`.
- Actions [39121100875](https://github.com/ils12058/COMPASS/actions/runs/39121100875):
  successful backend deployment of that exact SHA. This is deployment evidence, not a current
  authenticated check of every feature.
- Vercel deployment `dpl_3ubA297qjyeCUCAF7UK4zrccu2C8`: `READY`; authenticated Vercel deployment
  API reports `source=cli`, `githubCommitRef=staging`, and the same `githubCommitSha`.
  Alias: `https://staging.compass-gco.com`.
- Frontend same-origin `/api/v1/meta`: HTTP 200; protected Group Sessions and Follow-Ups:
  HTTP 401 when unauthenticated. CSRF bootstrap: HTTP 200, Secure and SameSite=Lax cookie.
  No session credential or CSRF value is retained in this report.
- SSH with the configured staging identity and strict known-host checking timed out on port 22.
  Host settings, applied migrations, key consumption, process state and current identity sync
  could not be independently inspected. No firewall, credential, secret or runtime setting changed.

There is no observed stale frontend/backend revision mismatch. Public readiness does not prove
worker/Beat/realtime health, authenticated cookies, every capability, or usable Follow-Up keys.
The owner confirms keyring provisioning; runtime usability remains unverified in this task.
No available authenticated staging session or protected credential handoff was used. All browser
operations below use synthetic intercepted API responses on localhost, never institutional records.

## Runtime availability and error-resolution matrix

| Area | Observed evidence / cause | Candidate correction and proof | Live boundary |
| --- | --- | --- | --- |
| Follow-Up APIs, My Work, current notification projection | Source at deployed SHA contains a default-false global gate; prior deployment report states it was false. No authenticated live 503 was captured. | Removed setting, environment contract, HTTP gate and integration early returns. Authorized HTTP reads succeed without the flag; Student access stays 403. Existing encryption, source, assignment, MFA and lifecycle tests pass. | Candidate is not deployed; authenticated live verification pending. |
| Student Group Session discovery | Reproduced HTTP failures with synthetic fixtures; `data ?? []` plus no error branch rendered an empty list. | Explicit pending/error/denied/unavailable/empty/success branches; Retry. Browser checks cover 403/500/503 and recovery to a valid empty response. | No evidence that a particular live user had one of these exact statuses. |
| Staff session list and metrics | Same source failure masking in list; metric failure had no feedback. | Separate errors and Retry; session operations hidden with failed collection data; creation disabled on collection failure. | Current live staff scope cannot be verified without authentication. |
| Session rosters | Source treated a failed roster read as no registrations. | Error and Retry instead of empty; attendance save disabled on failed reads. Permission projections still decide roster, notes, export and attendance actions. | No live participant data accessed. |
| Attendance save with cancelled registrations | Actual backend accepts only REGISTERED rows; frontend previously submitted cancelled rows from the initialized table too, producing a validation failure. | Submit active registrations only; cancelled rows stay disabled. Counselor/GSS browser scenarios assert the outgoing registration IDs. | Backend domain rule unchanged. |
| Fixed-date appointment slots | Both panels masked pending/failed reads as empty. Browser reproduction also proved the Student panel was trapped under the management-only Services layout, so no slot read occurred. | Explicit states/Retry; existing Student panel now reachable through Book appointment → Scheduled slots (`?pathway=FIXED_DATE_SLOT`). Reuses the existing slot API and current-Student booking gate; Services management stays restricted. | Synthetic route/read/booking checks; no claim that a particular live slot is bookable. |
| Services / appointment availability | Routes and contracts inspected; 62 backend Group Session/Service/slot tests passed. | Existing Service pathways, scheduling, qualification and permission rules retained. No speculative backend fix. | No authenticated live 403/409/422/500 reproduced in these workflows. |
| API routing / authentication | Same-origin proxy serves meta and CSRF, protects collection reads with 401. | No routing rewrite or cookie policy change warranted by evidence. | Successful authenticated sign-in and cross-origin/session behavior remain a release check. |

A route returning 401 without a session is expected protection, not feature unavailability.
No generic frontend fallback is presented as proof that a backend failure was fixed.

## Follow-Up gate retirement and preserved controls

Removed `GUIDANCE_FOLLOWUPS_ENABLED` from `config/settings.py` and active environment examples.
Removed `_enabled()` and `followups_not_enabled`, plus gate-dependent My Work/current-event
projection early returns. This does not add public routes or bypass `session_auth`.

Unchanged protections include current Counselor/GSS identity and capability reloads, assignment
and supervision/Student scope, source-specific Counselor confidentiality, record/event/section-bound
ciphertext, recent MFA, durable idempotency, optimistic versions, terminal state rules and Audit.
Missing or malformed keyrings still produce `followup_content_unavailable` (503) for protected
HTTP reads; summaries do not contain protected text.

`GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED`, `APPOINTMENT_AUTO_REMINDERS_ENABLED`, `WEB_PUSH_ENABLED`
and `DAILY_ENABLED` remain independent controls. No external dispatch is enabled. Existing
in-app/current-event policy remains independent of external email/push. Worker/Beat/realtime
content-key boundaries and Compose mounts were not broadened. No key was generated or rotated.

Current operations/runbooks describe the retired gate. Historical CORR-5/ADR/handoff findings
are preserved with a dated supersession note. Their unresolved institutional decisions remain
unresolved: written GCO/DPO/Records approval for the intended UAT, categories, confidentiality,
retention/hold/disposition and recovery cannot be inferred from owner key-provisioning confirmation,
code changes, or a healthy deployment.

## Group Sessions coverage by role

| Role | Entry and local navigation | Existing actions reused | Access boundaries |
| --- | --- | --- | --- |
| Student | Exactly one `/portal/group-sessions` sidebar entry → Browse Sessions; My Registrations tab | Discovery, current eligibility feedback, registration/cancellation; upcoming/past/cancelled history, attendance and session details | `appointments.view_self` controls workspace; backend still enforces lifecycle, inventory, windows, capacity and overlap. |
| Counselor | Same entry → Manage Sessions; Registrations & Attendance | Scoped all-Service collection, status/Service/date filters, eligible Service selection, draft creation, edit/publish/cancel/complete/withdraw, session-specific roster and attendance | Existing scoped `groupSessionsListStaff` and per-resource `can_*` projections; facilitator visibility does not imply organizer/export/notes rights. |
| GSS | Same staff navigation | Reuses the same scoped management and participant components | Current supervisor and resource scope are enforced server-side. Missing supervision returns a real denial; no creation is offered after a failed collection read. |
| IT Admin | No operational Group Sessions sidebar/management workspace | Existing Service configuration remains | `services.manage` alone does not grant participant/attendance rights. Browser verifies no participant/Group Sessions API request from the denied staff page. |

Preserved `/discover`, `/my`, and `/[sessionId]` deep links. Added `/manage` and `/attendance`.
Canonical entry chooses the role-appropriate tab. Tabs use `WorkspaceTabs`, `workspaceTabClass`
and `aria-current=page`; collection filters use existing floating portal tools.
Service detail panels remain available as contextual entry points.

The staff workspace reuses `ServiceGroupSessionsStaffPanel` with an optional Service scope and
attendance mode rather than duplicating lifecycle/MFA logic. Catalog selection pages/searches
existing active Service data and offers only `GROUP_SESSION` Services; it does not update pathways.
Catalog read access is required to select a Service; staff without it can still use their authorized
session summaries and operations. Server creation validation remains authoritative.

Staff status filtering uses the existing API. Service/date filters refine the already scoped returned
collection; dates use Philippine Time. The existing unpaginated Group Session collection contract
is retained. No global participant directory, new capability, domain model, migration or dependency.

A focused browser check uncovered an additional existing-pathway integration defect: the Student
fixed-slot panel was only mounted inside the management-gated Services layout. It was unreachable
for ordinary Students despite existing booking APIs. The Book appointment page now links to its
scheduled-slot presentation using a query parameter. It selects an active `FIXED_DATE_SLOT`
Service from the existing catalog, retains current-Student/self-booking authority, and reuses the
existing slot panel, confirmation and endpoint. No Service management permission is granted.
A WebKit denial timing check also found that staff creation needed to remain disabled while the
initial scoped list was pending, as well as after it failed; that boundary is now explicit.

## Contextual Help coverage

| Pages | Header / Help correction | Visible feedback preserved |
| --- | --- | --- |
| My availability | Short weekly-hours description; existing `PageHeader.help` via minimally extended heading wrapper | Unsaved changes, validation, save/removal feedback and unavailability restrictions |
| Office hours | Short Office-hours description; Help covers combined scheduling rules | Closures, current hours and action restrictions |
| Counselor schedules / individual schedule | Exact requested directory copy: “Find a counselor to manage their availability.” Help covers delegated management and scheduling | Inactive/legacy provider restrictions remain inline |
| Group Sessions browse, registrations and detail | Shared role-appropriate Help in header; one local navigation group | Eligibility/window/capacity/conflict blockers, cancellation reason and request failures |
| Staff management and attendance | Help explains draft/publish/completion, scoped rosters and attendance | Per-session operation permissions, capacity, status, errors and confirmations |
| Follow-Up list/create/detail/report/recovery | Shared concise Help: responsibility, due date, completion/cancellation, confidentiality and staff notifications | Student non-notification explanation on creation, confidential boundaries, validation, conflicts and consequential confirmations |
| Appointments and Service Catalog | Existing Help implementations reviewed and reused unchanged | Existing booking restrictions, critical warnings, Service change consequences |

Help is supplementary. No privacy, consent, eligibility blocker, security alert or irreversible-action
warning was moved into a dialog. Keyboard activation, Escape, return focus, and desktop/tablet/phone
layout checks use the existing shared dialog and browser harness. Existing avatars remain intact.

## Validation

- Follow-Ups: 31 existing/updated tests passed; 2 additional HTTP keyring-failure scenarios passed.
- Group Sessions + Service Catalog + fixed-date slots: 62 tests passed.
- Common configuration + My Work + notifications + runtime secrets/Compose: 123 tests passed.
- Total focused backend checks: **218 passed**. The initially mistyped nonexistent
  `test_operations.py` invocation collected nothing; corrected to `test_work_queue.py` above.
- Frontend unit suite: **828 passed** on the final source. The final focused scheduled-slot/navigation/booking rerun also passed 27 tests. The header semantic-contract check passed all 21 scenarios after using the canonical page action component.
- API export freshness: current contract unchanged; generated client rebuilt with Orval.
- Django system check and `makemigrations --check --dry-run`: clean, no new migrations.
- Ruff check/format and `git diff --check`: passed.
- Frontend typecheck, lint and final production build: passed.
- Final release browser suite: 12/12 Chromium and 12/12 WebKit.
- Existing Group Sessions/MFA browser suite: 3/3 Chromium and 3/3 WebKit.
- Follow-Up browser suite: 19/19 Chromium and 19/19 WebKit. Initial browser failures included stale copy assertions, the unreachable Student fixed-slot
  entry, and a staff-access loading race. Copy assertions were updated to the required wording;
  the two actual UI integration defects were fixed and their scenarios retained. No assertion
  was disabled.
- Applicable GitHub Actions are required on the PR's final head. Their authoritative status is
  available in the PR Checks tab; a local pass is not a claim that CI passed.

## Controlled release and authenticated UAT checklist

1. Confirm institutional authorization for this UAT context. No sign-off is fabricated here.
2. Review/merge this PR only with owner authorization. Choose the resulting full latest-`staging`
   SHA as both expected backend revision and frontend source revision; the future merge SHA does
   not exist yet and is not inferred from this branch's base.
3. Verify the existing independent keyring inside the web process without printing it: load
   `guidance_followups.content._keyring()` and validate parsing, then exercise a permitted
   protected read/write against an approved synthetic test record. Do not regenerate/provision
   a replacement. Confirm workers/Beat/realtime retain no Follow-Up key grant.
4. Check applied migrations read-only against the running release; this change adds none.
   Verify current identity policy, Counselor responsibility scope and GSS supervision; confirm
   intended role capabilities rather than adding ad hoc participant authority.
5. Keep external notification/reminder/provider switches at their separately approved values.
   The obsolete core flag may be removed from the host environment during a reviewed release;
   any leftover value is ignored by the new code.
6. Use the established exact-SHA backend Actions workflow and independent root Vercel project
   deployment only after separate authorization. Recheck both revisions and readiness afterward.
7. Use existing approved test accounts (passwords/tokens are not in this report):

| Role | Successful authenticated checks | Expected denials / restrictions |
| --- | --- | --- |
| Student | Canonical entry, tabs, discovery, own registration history/detail and eligible synthetic registration | Staff list/roster denied; non-current/ineligible/window/full/overlap registration restrictions visible |
| Counselor | Follow-Ups list/protected detail, My Work, assigned operational and permitted confidential records; managed sessions, authorized roster/attendance | Unrelated/confidential-source/out-of-scope records denied; protected writes still require MFA |
| GSS | Supervisor-scoped Follow-Ups, My Work and organized/facilitated sessions | Counselor-confidential details and unrelated participants denied; lost supervision causes denial |
| IT Admin | Service configuration, account/organization access | Follow-Up and operational Group Session/participant access denied despite configuration authority |

Verify expected 200/201 success, 401 without authentication, 403 authority denial, 404 for
out-of-scope opaque resources, 409 for conflicts, 422 validation, and fail-closed 503 for unusable
protected content. Record only status/error code and synthetic identifiers.

8. Recheck session cookies after refresh/reauthentication, notification controls, facilitator versus
   organizer notes/export permissions, existing MFA continuation and avatar presentation.
9. Rollback: use a reviewed revert PR to `staging`, then deploy that resulting exact latest SHA
   through the normal workflow; Vercel can be separately rolled back to the prior Ready deployment.
   Preserve data, canonical volumes, complete Follow-Up keyring and historical ciphertext. Do not
   reset/fake/reverse data migrations, rotate keys, or assume this workflow accepts an arbitrary
   old `expected_staging_sha` while remote `staging` points elsewhere.

## Remaining limitations and genuine release checks

- Live SSH access timed out; current process/keyring/migration/identity state and authenticated
  cross-role live smoke matrix remain **unverified**, not passed. An authorized operator/session
  must complete the above matrix before claiming runtime/UAT availability is resolved.
- The old deployed build still contains the core gate. This PR changes source only.
- Written institutional UAT approval is not established by the supplied historical evidence.
- No broad redesign, academic/Good Moral eligibility changes, authorization expansion, external
  notification activation, merge, deployment, reset, credential change or key rotation occurred.
  ACAD-1 and GM-UX-2/F6 degree-verification limitations are unchanged.

## Browser presentation evidence

Synthetic records only. Keyboard Help tests cover Enter, Escape and focus return; viewport
checks cover phone, tablet and desktop, including horizontal overflow.

- [Student tabs, phone](docs/evidence/release-unblock-1/student-tabs-phone.png)
- [GSS attendance entry, phone](docs/evidence/release-unblock-1/gss-attendance-phone.png)
- [Availability Help placement, tablet](docs/evidence/release-unblock-1/availability-help-tablet.png)

## Files changed

The following list covers the dedicated branch diff, including new routes, tests, Help and evidence.

- `COMPASS-RELEASE-UNBLOCK-1-IMPLEMENTATION-REPORT.md`
- `be/compass/guidance_followups/api.py`
- `be/compass/guidance_followups/integration.py`
- `be/config/settings.py`
- `be/deploy/runtime-secrets/runtime.env.example`
- `be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md`
- `be/docs/guidance-followups-operations.md`
- `be/docs/guidance-followups-workspace.md`
- `be/docs/runtime-secrets.md`
- `be/docs/staging-deployment.md`
- `be/tests/test_guidance_followups.py`
- `docs/evidence/release-unblock-1/availability-help-tablet.png`
- `docs/evidence/release-unblock-1/gss-attendance-phone.png`
- `docs/evidence/release-unblock-1/student-tabs-phone.png`
- `docs/handoffs/AGENT-1-OPS-FINAL-HANDOFF.md`
- `docs/handoffs/AGENT-1-OPS-FINAL-READINESS.md`
- `docs/handoffs/COMPASS-CORR-5-ACTIVATION-READINESS.md`
- `docs/handoffs/COMPASS-INT-FINAL-DEPLOYMENT-READINESS.md`
- `fe/src/app/(portal)/portal/appointments/book/page.tsx`
- `fe/src/app/(portal)/portal/group-sessions/attendance/page.tsx`
- `fe/src/app/(portal)/portal/group-sessions/manage/page.tsx`
- `fe/src/app/(portal)/portal/group-sessions/page.tsx`
- `fe/src/features/appointments/appointment-booking-page.tsx`
- `fe/src/features/appointments/appointment-fixed-date-booking.tsx`
- `fe/src/features/availability/availability-help.tsx`
- `fe/src/features/availability/availability-pages.tsx`
- `fe/src/features/availability/availability-shared.tsx`
- `fe/src/features/group-sessions/group-session-detail-page.tsx`
- `fe/src/features/group-sessions/group-sessions-access.ts`
- `fe/src/features/group-sessions/group-sessions-discovery-page.tsx`
- `fe/src/features/group-sessions/group-sessions-history-page.tsx`
- `fe/src/features/group-sessions/group-sessions-shared.tsx`
- `fe/src/features/group-sessions/group-sessions-staff-page.tsx`
- `fe/src/features/guidance-followups/followups-create.tsx`
- `fe/src/features/guidance-followups/followups-detail.tsx`
- `fe/src/features/guidance-followups/followups-help.tsx`
- `fe/src/features/guidance-followups/followups-list.tsx`
- `fe/src/features/guidance-followups/followups-reassignment.tsx`
- `fe/src/features/guidance-followups/followups-report.tsx`
- `fe/src/features/guidance-followups/followups-shared.tsx`
- `fe/src/features/portal/components/portal-workspaces.ts`
- `fe/src/features/services/service-fixed-slots-panel.tsx`
- `fe/src/features/services/service-group-sessions-panel.tsx`
- `fe/tests/availability-schedule.test.mjs`
- `fe/tests/guidance-followups.browser.mjs`
- `fe/tests/release-unblock.browser.mjs`
- `fe/tests/service-fixed-slots.test.mjs`
- `fe/tests/service-group-sessions.browser.mjs`
- `fe/tests/service-group-sessions.test.mjs`
