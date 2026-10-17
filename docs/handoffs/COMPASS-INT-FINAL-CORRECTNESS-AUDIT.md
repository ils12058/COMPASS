# COMPASS-INT-FINAL — Independent Implementation Correctness & Security Audit

**Repository:** `ils12058/COMPASS`  
**Target Branch:** `staging` (`d41637a705eb7ff7b66cbb5340ffc81f411224d0`)  
**Integration Branch:** `integration/compass-int-final-argon`  
**Auditor & Final Integration Owner:** Gemini 4 Argon  
**Date:** October 17, 2026

---

## 1. Executive Summary & Audit Methodology

An independent, zero-trust code and runtime audit was conducted across all eight open workstream pull requests (#256, #258, #259, #260, #261, #262, #263, #264) and the intermediate branch `codex/ops-final-integration` (`8fdef7a9cfc1fa53be5a00226592af0424386843`).

### Methodology
1. **Commit Ancestry & Branch Reconstruction**: Compared `origin/staging` (`d41637a705eb7ff7b66cbb5340ffc81f411224d0`) against every individual PR branch and `codex/ops-final-integration` to verify what was actually merged vs. claimed in handoff documents.
2. **Line-by-Line Domain & Security Review**:
   - **PART A (REM-1, PR #256)**: Inspected `be/compass/appointments/reminders.py`, `be/compass/appointments/tasks.py`, `be/compass/appointments/api.py`, `be/compass/notifications/current.py`, `be/compass/notifications/policy.py`, and frontend reminder dialogs.
   - **PART B (FUP-1A–1E, PRs #259, #260, #261 + #262)**: Inspected `be/compass/followups/models.py`, `be/compass/followups/services.py`, `be/compass/followups/api.py`, `be/compass/operations/services.py`, `be/compass/reporting/services.py`, management commands, and frontend follow-up workspaces.
   - **PART C (SVC-1–5, PRs #258, #263, #264)**: Inspected `be/compass/service_catalog/models.py`, `be/compass/service_catalog/services.py`, `be/compass/service_catalog/fixed_slots_services.py`, `be/compass/service_catalog/api.py`, `be/compass/group_sessions/models.py`, `be/compass/group_sessions/services.py`, `be/compass/group_sessions/api.py`, and frontend service catalog panels.
3. **Cross-Feature Contract & Safety Gate Verification**: Evaluated compliance with COMPASS global invariants (`test_openapi_contract.py`, `test_lock_scope.py`, `test_accounts.py`, `test_notifications.py`, `test_notification_push.py`, `canonical_migrations.json`, and `.github/scripts/backend_ci.py`).

---

## 2. Discrepancies Between Handoff Claims and Repository Reality

| Handoff Claim | Repository Reality | Resolution |
|---|---|---|
| `codex/ops-final-integration` represented prior integration progress | Contained only REM-1 (#256), SVC-1 (#258), FUP-1A–1E (#259–#261), and Font prerequisite (#262); completely omitted SVC-2 (#263) and SVC-3/4/5 (#264). | Merged `origin/feat/svc-3-4-5-group-sessions` (#264, which includes #263) into `integration/compass-int-final-argon` and reconciled all conflicts. |
| `docs/handoffs/AGENT-2-SVC-FINAL-HANDOFF.md` claimed Group Sessions were integrated with COMPASS notifications, audit, RBAC, and OpenAPI contract | `be/compass/group_sessions/api.py` had `auth=None` on 3 endpoints, omitted `require_recent_mfa_for_request` on all staff mutations, raised `HttpError` instead of `APIError`, omitted `response_with_errors`, bypassed `create_notification_for_event` with raw `Notification.objects.create()`, referenced undefined `GROUP_SESSION_DELETED`, and failed `test_openapi_contract.py` and `test_lock_scope.py`. | Remediated all 14 findings across `group_sessions`, `service_catalog`, `notifications`, `audit`, `api/contract.py`, and `fe/src/features/services/`. |
| Agent 1 handoff noted two pre-existing WebKit browser test failures (`ui-information-hierarchy`, `good-moral-assisted`) | Confirmed root cause: raw `page.goto(...)` calls on line 165 of `fe/tests/ui-information-hierarchy.browser.mjs` and line 117 of `fe/tests/good-moral-assisted.browser.mjs` cancelled in-flight fetches in WebKit instead of using the harness's `navigate(page, ...)` helper. | Replaced raw `page.goto(...)` with `navigate(page, ...)` in both browser test files. |

---

## 3. Audit Assessment of REM-1 (PR #256) and FUP-1A–1E (PRs #259, #260, #261)

### Part A — REM-1 Appointment Reminders (Verified Sound)
- **Recipient & Role Boundaries**: Strictly Student-only recipients; staff initiate manual/bulk reminders (`COUNSELOR` or `GUIDANCE_SERVICES_STAFF` with `appointments.manage` and recent MFA) and are never reminder recipients. Canonical `GUIDANCE_SERVICES_STAFF` role code is used throughout.
- **Idempotency & Concurrency**: `AppointmentReminderBatch` stores SHA-256 `request_fingerprint` and locks batches/appointments with `select_for_update(of=("self",))`. Replaying an idempotency key with different parameters raises `409 Conflict` (`appointment_reminder_idempotency_conflict`).
- **Stale Suppression**: `appointment_notification_is_current` in `be/compass/notifications/current.py` verifies `AppointmentReminderOccurrence` state and `appointment_revision` before email/push dispatch.
- **No My Work Pollution**: Reminders do not create My Work items.

### Part B — FUP-1A–1E Shared Guidance Follow-Up Management (Verified Sound)
- **Confidentiality Enforcement**: Server-side enforcement of `OPERATIONAL` vs `COUNSELOR_CONFIDENTIAL` in `be/compass/followups/services.py`. `GUIDANCE_SERVICES_STAFF` cannot create, view, or be assigned `COUNSELOR_CONFIDENTIAL` follow-ups. Head Guidance, IT Admin, and DPO do not receive blanket confidential access.
- **Source Authorization & De-duplication**: Supports Standalone Student, Counseling Encounter (including E-Counseling via canonical Encounter), Referral, and Routine Interview without creating duplicate domain records.
- **Encryption & Rotation**: `summary` and `Constraint` fields use `EncryptedTextField` (`enc:v1:`); `verify_followup_encryption` and `rotate_followup_encryption` management commands are implemented and tested.
- **My Work & Notifications**: Integrated into `be/compass/operations/services.py` and `be/compass/notifications/policy.py` behind `GUIDANCE_FOLLOWUPS_ENABLED` and `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` (default `False`).

---

## 4. Detailed Findings & Remediations (SVC-1–5 & Cross-Stack Integration)

### Finding C-01 — Unauthenticated Access & Crash on Group Session Endpoints (`CRITICAL`)
- **Root Cause**: `discover_group_sessions` (`GET /api/v1/group-sessions/discover`), `get_my_registrations` (`GET /api/v1/group-sessions/me/registrations`), and `get_session` (`GET /api/v1/group-sessions/{session_id}`) in `be/compass/group_sessions/api.py` did not specify `auth=session_auth`. Unauthenticated requests bypassed authentication or crashed with `AttributeError` when accessing `request.auth_user`.
- **Affected Files**: `be/compass/group_sessions/api.py`
- **Fix Applied**: Added `auth=session_auth` and `response_with_errors(..., 401, ...)` to all 14 endpoints in `be/compass/group_sessions/api.py`.
- **Verification**: `test_group_session_api_auth_mfa_and_role_capability_boundaries` in `be/tests/test_group_sessions.py` and `be/tests/test_openapi_contract.py`.

### Finding C-02 — Missing Role & Capability Boundaries on Group Sessions and Fixed-Date Slots (`CRITICAL`)
- **Root Cause**:
  1. In `be/compass/group_sessions/api.py`, `_require_staff` checked `user.role.code in ("COUNSELOR", "GUIDANCE_SERVICES_STAFF", "HEAD_GUIDANCE", "ADMIN")` without checking `user.is_active` or `user.has_capability("appointments.manage")`, and used non-canonical role codes (`HEAD_GUIDANCE`, `ADMIN`).
  2. Student routes (`/discover`, `/me/registrations`, `/{id}/register`, `/{id}/cancel-registration`) did not verify `appointments.view_self` / `appointments.manage_self` or `is_current_student(student)`.
  3. In `be/compass/service_catalog/api.py`, `_require_slot_management` allowed `user.has_capability("services.manage")`, which granted `IT_ADMIN` access to list, create, update, and delete Guidance consultation slots and view booked student appointment metadata.
- **Affected Files**: `be/compass/group_sessions/api.py`, `be/compass/group_sessions/services.py`, `be/compass/service_catalog/api.py`
- **Fix Applied**:
  - Restricted staff group-session and fixed-slot management strictly to active `COUNSELOR` and `GUIDANCE_SERVICES_STAFF` accounts with `appointments.manage`.
  - Enforced `STUDENT` role with `appointments.view_self` / `appointments.manage_self` and `is_current_student(student)` on student discovery, booking, and registration paths.
- **Verification**: `test_group_session_api_auth_mfa_and_role_capability_boundaries`, `test_group_session_student_eligibility_and_cancelled_attendance_guard`, and `test_api_fixed_slot_authorization_scope_redaction_and_cross_service_isolation`.

### Finding C-03 — Missing Recent-MFA Enforcement on Consequential Staff Mutations (`CRITICAL`)
- **Root Cause**: All 7 staff mutation endpoints in `be/compass/group_sessions/api.py` (`create_session`, `update_session`, `publish_session`, `cancel_session`, `complete_session`, `delete_session`, `record_session_attendance`) omitted `require_recent_mfa_for_request(request)`.
- **Affected Files**: `be/compass/group_sessions/api.py`
- **Fix Applied**: Enforced `require_recent_mfa_for_request(request)` in `_require_staff(request, recent_mfa=True)` across all staff mutation endpoints.
- **Verification**: `test_group_session_api_auth_mfa_and_role_capability_boundaries` in `be/tests/test_group_sessions.py`.

### Finding C-04 — Confidentiality & PII Leaks in Fixed-Date Slots and Group Sessions (`CRITICAL`)
- **Root Cause**:
  1. `GET /api/v1/services/{service_id}/slots` returned booked `student_name`, `appointment_id`, and `appointment_reference_code` to any staff member without checking `appointment_management_access_allowed(actor, appt)`.
  2. `GET /api/v1/group-sessions/me/registrations` returned internal facilitator `attendance_notes` to the student.
  3. `GET /api/v1/group-sessions/discover` and `GET /api/v1/group-sessions/{session_id}` exposed `venue_or_meeting_url` for `ONLINE` sessions to unregistered students.
- **Affected Files**: `be/compass/service_catalog/api.py`, `be/compass/group_sessions/api.py`
- **Fix Applied**:
  - Redacted `student_name`, `appointment_id`, and `appointment_reference_code` in `_slot_response` when `not appointment_management_access_allowed(actor, appt)` (preserving `is_booked: True`).
  - Redacted `attendance_notes` (`None`) on student-facing `get_my_registrations`.
  - Redacted `venue_or_meeting_url` (`""`) on `ONLINE` group sessions for unregistered students.
- **Verification**: `test_group_session_api_privacy_redaction_and_reschedule_notification` and `test_api_fixed_slot_authorization_scope_redaction_and_cross_service_isolation`.

### Finding H-01 — Bypassed Canonical Notification Pipeline & Missing Reschedule Notification (`HIGH`)
- **Root Cause**: `be/compass/group_sessions/services.py` used raw `Notification.objects.create(...)` with unregistered event codes and `target_type="GROUP_SESSION"`, bypassing `create_notification_for_event`, email/push delivery queuing, privacy-safe copy validation, and stale-notification suppression (`current.py`). Furthermore, rescheduling a `PUBLISHED` group session did not notify registered students.
- **Affected Files**: `be/compass/notifications/policy.py`, `be/compass/notifications/push_policy.py`, `be/compass/notifications/current.py`, `be/compass/notifications/templates/notifications/email/group_session_update.txt`, `be/compass/notifications/templates/notifications/email/group_session_update.html`, `be/compass/group_sessions/services.py`, `fe/src/features/notifications/notification-targets.ts`
- **Fix Applied**:
  - Added `NotificationTargetType.GROUP_SESSION` and `NotificationEvent.GROUP_SESSION_REGISTERED`, `GROUP_SESSION_REGISTRATION_CANCELLED`, `GROUP_SESSION_CANCELLED`, and `GROUP_SESSION_RESCHEDULED` to `policy.py` and `push_policy.py`.
  - Created privacy-safe email templates `group_session_update.txt` and `.html`.
  - Implemented `group_session_notification_is_current` in `be/compass/group_sessions/services.py` and wired it into `be/compass/notifications/current.py`.
  - Replaced all raw `Notification.objects.create` calls with `create_notification_for_event` and emitted `GROUP_SESSION_RESCHEDULED` when material schedule/delivery/venue fields change on a `PUBLISHED` session.
  - Mapped `NotificationTargetType.GROUP_SESSION` in `fe/src/features/notifications/notification-targets.ts`.
- **Verification**: `be/tests/test_notifications.py`, `be/tests/test_notification_push.py`, `be/tests/test_group_sessions.py`, and `fe/tests/service-group-sessions.test.mjs`.

### Finding H-02 — Missing Audit Action Constant Causing 500 on Draft Deletion (`HIGH`)
- **Root Cause**: `delete_draft_group_session` in `be/compass/group_sessions/services.py` imported `GROUP_SESSION_DELETED` inside the function, which was missing from `be/compass/audit/actions.py`, raising `ImportError` at runtime.
- **Affected Files**: `be/compass/audit/actions.py`, `be/compass/group_sessions/services.py`
- **Fix Applied**: Added `GROUP_SESSION_DELETED = "group_session.deleted"` to `be/compass/audit/actions.py` and imported it at module level in `be/compass/group_sessions/services.py`.
- **Verification**: `be/tests/test_group_sessions.py`.

### Finding H-03 — Cross-Service Slot Mutation / Booking IDOR (`HIGH`)
- **Root Cause**: `PATCH /api/v1/services/{service_id}/slots/{slot_id}`, `DELETE /api/v1/services/{service_id}/slots/{slot_id}`, and `POST /api/v1/services/{service_id}/slots/{slot_id}/book` ignored the URL's `service_id` parameter and operated on `slot_id` globally, and returned `409 Conflict` when a slot did not exist.
- **Affected Files**: `be/compass/service_catalog/fixed_slots_services.py`, `be/compass/service_catalog/api.py`
- **Fix Applied**: Added `SlotNotFoundError` (mapped to `404 Not Found` with code `slot_not_found`) and enforced `service_id=service_id` on `update_fixed_slot`, `delete_fixed_slot`, and `book_fixed_slot`.
- **Verification**: `test_api_fixed_slot_authorization_scope_redaction_and_cross_service_isolation` in `be/tests/test_fixed_date_slots.py`.

### Finding H-04 — Unscoped `select_for_update()` Locks Failing PostgreSQL Lock-Scope Safety Check (`HIGH`)
- **Root Cause**: `cancel_student_registration` in `be/compass/group_sessions/services.py` and `update_fixed_slot` / `book_fixed_slot` in `be/compass/service_catalog/fixed_slots_services.py` combined `.select_related(...)` with `.select_for_update()` without `of=("self",)`, violating COMPASS's PostgreSQL lock-scope invariant (`be/tests/test_lock_scope.py`).
- **Affected Files**: `be/compass/group_sessions/services.py`, `be/compass/service_catalog/fixed_slots_services.py`
- **Fix Applied**: Added `select_for_update(of=("self",))` to all three queries.
- **Verification**: `be/tests/test_lock_scope.py` and concurrent registration/booking tests.

### Finding H-05 — OpenAPI Contract & CI Shard Registration Gaps (`HIGH`)
- **Root Cause**: `be/compass/group_sessions/api.py` used `HttpError` instead of `APIError` + `response_with_errors`, lacked binary schema documentation on `export_roster`, and was missing from `be/compass/api/contract.py`, `be/compass/api/v1/router.py`, `be/tests/test_openapi_contract.py`, and `.github/scripts/backend_ci.py`.
- **Affected Files**: `be/compass/group_sessions/api.py`, `be/compass/api/contract.py`, `be/compass/api/v1/router.py`, `be/tests/test_openapi_contract.py`, `.github/scripts/backend_ci.py`, `contracts/openapi.json`
- **Fix Applied**: Standardized all group-session routes on `APIError` and `response_with_errors`, documented `text/csv` binary output on `export_roster`, registered `group-sessions` tag/prefix and all 20 new `operationId`s, and added `test_fixed_date_slots.py` and `test_group_sessions.py` to `.github/scripts/backend_ci.py`.
- **Verification**: `be/tests/test_openapi_contract.py` (38/38 passed) and `.github/scripts/backend_ci.py verify` (166 test files verified across 6 shards).

### Finding M-01 — Attendance Recording on Cancelled Registrations & Metrics Denominator Inflation (`MEDIUM`)
- **Root Cause**: `record_attendance` allowed recording attendance for `CANCELLED` registrations; `get_group_session_metrics` included `DRAFT` session capacities in `total_capacity` and included cancelled registrations in `attended_count` / `absent_count`.
- **Affected Files**: `be/compass/group_sessions/services.py`
- **Fix Applied**: Restricted `record_attendance` to `RegistrationStatus.REGISTERED` rows (`select_for_update(of=("self",))`) and restricted `get_group_session_metrics` capacity denominator to `PUBLISHED` + `COMPLETED` sessions and attendance counts to `REGISTERED` participants.
- **Verification**: `test_group_session_student_eligibility_and_cancelled_attendance_guard` in `be/tests/test_group_sessions.py`.

### Finding M-02 — Frontend Role Gating & Non-Head Counselor Provider Query 403s (`MEDIUM`)
- **Root Cause**:
  1. `fe/src/features/services/service-detail-page.tsx` rendered `ServiceFixedSlotsStaffPanel` and `ServiceGroupSessionsStaffPanel` when `canManage` (`services.manage`) was true, causing `IT_ADMIN` to fire unauthorized `403` requests to `/slots` and `/group-sessions`, and rendered student panels for any user without `canManage` or `appointments.manage` (including `INSTITUTIONAL_OFFICER`).
  2. `ServiceFixedSlotsStaffPanel` and `ServiceGroupSessionsStaffPanel` unconditionally called `useServicesGetProviders(service.id)`, which requires `services.manage`, causing regular Counselors (without Head Guidance designation) to receive a `403` and an empty provider dropdown.
- **Affected Files**: `fe/src/features/services/service-detail-page.tsx`, `fe/src/features/services/service-fixed-slots-panel.tsx`, `fe/src/features/services/service-group-sessions-panel.tsx`
- **Fix Applied**:
  - Gated staff panels strictly to `(user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF") && user.capabilities.includes("appointments.manage")` and student panels strictly to `user.role === "STUDENT" && service.is_active`.
  - Gated `useServicesGetProviders(service.id)` with `enabled: user.capabilities.includes("services.manage")` and defaulted the Counselor selector to the current Counselor when `user.role === "COUNSELOR"`.
- **Verification**: `fe/tests/service-fixed-slots.test.mjs` and `fe/tests/service-group-sessions.test.mjs`.

### Finding M-03 — Browser Harness Raw `page.goto()` Race in WebKit (`MEDIUM`)
- **Root Cause**: `fe/tests/ui-information-hierarchy.browser.mjs` (line 165) and `fe/tests/good-moral-assisted.browser.mjs` (line 117) used raw `page.goto(...)` instead of `navigate(page, ...)`, cancelling in-flight link prefetch/API requests in WebKit and triggering `Fetch API cannot load ... due to access control checks` page errors.
- **Affected Files**: `fe/tests/ui-information-hierarchy.browser.mjs`, `fe/tests/good-moral-assisted.browser.mjs`
- **Fix Applied**: Replaced raw `page.goto(...)` calls with `navigate(page, ...)`.
- **Verification**: `fe/tests/ui-information-hierarchy.browser.mjs` and `fe/tests/good-moral-assisted.browser.mjs` in Chromium and WebKit.
