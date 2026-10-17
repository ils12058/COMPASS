# COMPASS-INT-FINAL — Integration Manifest

**Repository:** `ils12058/COMPASS`  
**Target Base Branch:** `staging` (`d41637a705eb7ff7b66cbb5340ffc81f411224d0`)  
**Integration Candidate Branch:** `integration/compass-int-final-argon`  
**Integration Owner:** Gemini 4 Argon  
**Date:** October 17, 2026

---

## 1. Source Branches & Commit Ancestry

| Stream / PR | Branch Name | Head SHA Inspected | Scope | Integration Status |
|---|---|---|---|---|
| Base (`staging`) | `origin/staging` | `d41637a705eb7ff7b66cbb5340ffc81f411224d0` | Canonical pre-integration baseline | Base ancestor |
| PR #256 | `origin/codex/rem-1-appointment-reminders` | `5eb1ca2e99a32bd858a5bf3b2e37ef9a0df96ff9` | REM-1 Appointment Reminders | Integrated |
| PR #258 | `origin/feat/svc-1-booking-pathways` | `b4b06b3556fb5ceab86f275a4e938a3919fb36a7` | SVC-1 Service Booking Pathways | Integrated |
| PR #259 | `origin/codex/fup-1a-guidance-followups-backend` | `8a84b76e9a98b1eb097250bc972c37d04ca973bd` | FUP-1A Secure Backend Foundation | Integrated |
| PR #260 | `origin/codex/fup-1b-1c-workspace-reporting` | `07df5b7546be2202dd70f4dc858be372191bb840` | FUP-1B/1C Workspace, Linked Workflows, Scoped Reporting | Integrated |
| PR #261 | `origin/codex/fup-1d-1e-my-work-notifications-hardening` | `b83a476bf826e1fc39ab3cc729998a4a6e179cf3` | FUP-1D/1E My Work, Notifications, Hardening | Integrated |
| PR #262 | `origin/codex/ops-font-build-prereq` | `3da7fb59d292eb73da42e001f44e7767b9bc05bc` | Deterministic Local Font/Build Prerequisite | Integrated |
| PR #263 | `origin/feat/svc-2-fixed-date-slots` | `d30203a0a27ef80b7f07df1da61b47dc6a42fa89` | SVC-2 Fixed-Date Appointment Slots | Integrated |
| PR #264 | `origin/feat/svc-3-4-5-group-sessions` | `a2ab7d6f5f9e0a6ebedff3beff4d84d180ab0a22` | SVC-3/4/5 Group Sessions, Registration, Attendance, Notifications & Reporting | Integrated |
| Prior Candidate | `origin/codex/ops-final-integration` | `8fdef7a9cfc1fa53be5a00226592af0424386843` | Partial integration (REM-1 + FUP-1A–1E + SVC-1 + Font Prereq; lacked SVC-2–5) | Superseded & reconciled |

---

## 2. Integration Order & Conflict Resolutions

1. **Base Initialization**: Created `integration/compass-int-final-argon` starting from the verified ancestor incorporating `staging` (`d41637a705eb7ff7b66cbb5340ffc81f411224d0`), REM-1 (#256), SVC-1 (#258), FUP-1A–1E (#259, #260, #261), and Font Build Prerequisite (#262).
2. **Service Catalog Expansion Merge**: Merged `origin/feat/svc-3-4-5-group-sessions` (`a2ab7d6f5f9e0a6ebedff3beff4d84d180ab0a22`, which contains `origin/feat/svc-2-fixed-date-slots` `d30203a0a27ef80b7f07df1da61b47dc6a42fa89`).
3. **Conflict & Cross-Stream Reconciliations**:
   - **`be/compass/common/canonical_migrations.json`**: Reconciled the canonical migration manifest to retain `0001_canonical_baseline` for all existing apps while registering all 6 additive feature migrations across `appointments`, `audit`, `followups`, `group_sessions`, `notifications`, and `service_catalog`.
   - **`be/compass/audit/actions.py`**: Unified REM-1 (`APPOINTMENT_REMINDER_*`), FUP-1 (`GUIDANCE_FOLLOW_UP_*`), SVC-2 (`SERVICE_SLOT_*`), and SVC-3/4/5 (`GROUP_SESSION_*`, including `GROUP_SESSION_DELETED`) audit action constants.
   - **`be/compass/notifications/policy.py`, `push_policy.py`, `current.py`**: Unified notification target types (`GUIDANCE_FOLLOW_UP`, `GROUP_SESSION`), event codes (`appointment.reminder_*`, `guidance_follow_up.*`, `group_session.*`), push policies, and currentness evaluators (`appointment_notification_is_current`, `guidance_follow_up_notification_is_current`, `group_session_notification_is_current`).
   - **`be/compass/api/contract.py`, `be/compass/api/v1/router.py`, `be/tests/test_openapi_contract.py`**: Unified router prefixes (`/api/v1/follow-ups`, `/api/v1/group-sessions`, `/api/v1/services/{id}/slots`), OpenAPI tags, and `EXPECTED_OPERATION_IDS`.
   - **`.github/scripts/backend_ci.py`**: Registered `group_sessions` app prefix and added `tests/test_fixed_date_slots.py` and `tests/test_group_sessions.py` to the `appointments_services` CI bundle so all 166 backend test files are covered across the 6 full-regression shards.
   - **`fe/src/features/notifications/notification-targets.ts`**: Unified `NotificationTargetType.GUIDANCE_FOLLOW_UP` (`/portal/follow-ups/{id}`) and `NotificationTargetType.GROUP_SESSION` (`/portal/services`).

---

## 3. Canonical Migration Graph

No `0001_canonical_baseline.py` migration files were modified. All schema changes are additive migrations layered cleanly on top of the canonical baseline:

| App | Canonical Baseline | Additive Migrations on Integration Branch |
|---|---|---|
| `appointments` | `0001_canonical_baseline` | `0002_appointmentreminderbatch_and_more` |
| `audit` | `0001_canonical_baseline` | `0002_alter_auditevent_action` |
| `followups` | — (new domain app) | `0001_initial` |
| `group_sessions` | — (new domain app) | `0001_initial` |
| `notifications` | `0001_canonical_baseline` | `0002_guidancenotificationpreference_and_more` |
| `service_catalog` | `0001_canonical_baseline` | `0002_servicebookingpathway`, `0003_serviceappointmentslot` |

---

## 4. OpenAPI & Orval Client Regeneration

1. Exported canonical OpenAPI schema from the integrated backend:
   ```bash
   DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi
   ```
2. Verified zero drift with `export_openapi --check` and `be/tests/test_openapi_contract.py`.
3. Regenerated typed frontend API hooks and models in `fe/src/lib/api/generated/`:
   ```bash
   pnpm --dir fe api:generate
   ```
