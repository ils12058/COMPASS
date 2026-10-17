# COMPASS-INT-FINAL — Operational Deployment Readiness & Runbook

**Repository:** `ils12058/COMPASS`  
**Target Environment:** `staging` / Pre-Defense Release Candidate  
**Integration Branch:** `integration/compass-int-final-argon`  
**Date:** October 17, 2026

---

## 1. Safe-by-Default Feature Flag Posture

All new background-dispatch and rollout-gated capabilities ship **disabled by default** in `be/config/settings.py`:

| Setting / Environment Variable | Code Default | Purpose |
|---|---|---|
| `GUIDANCE_FOLLOWUPS_ENABLED` | `False` | Gates the Shared Guidance Follow-Up Management API, My Work integration, and reporting endpoints. |
| `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` | `False` | Gates staff in-app/email/push notifications for Follow-Up assignment, updates, and overdue transitions. |
| `APPOINTMENT_AUTO_REMINDERS_ENABLED` | `False` | Gates the periodic Celery Beat task (`send_automatic_appointment_reminders`) for 24-hour and 3-hour automatic student reminders. |

> **Note:** Service Catalog Booking Pathways (`SVC-1`), Fixed-Date Appointment Slots (`SVC-2`), and Group Sessions (`SVC-3/4/5`) are per-service opt-in via `ServiceBookingPathway` configuration (`FIXED_DATE_SLOT`, `GROUP_SESSION`). Existing services retain `FLEXIBLE_APPOINTMENT` (or non-booking) behavior unchanged until an authorized administrator enables additional pathways on a specific Service.

---

## 2. Pre-Deployment Checklist

1. **Database Backup**: Take a point-in-time PostgreSQL snapshot of the target environment prior to running migrations.
2. **Environment Configuration Verification**:
   - Confirm `FIELD_ENCRYPTION_KEYS` is configured and matches existing active encryption key material.
   - Confirm `GUIDANCE_FOLLOWUPS_ENABLED=False`, `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=False`, and `APPOINTMENT_AUTO_REMINDERS_ENABLED=False` for initial dark-deploy rollout.
   - Confirm Redis broker connectivity (`CELERY_BROKER_URL`) and worker/Beat process health.

---

## 3. Exact Deployment & Migration Sequence

Execute the following commands in order from the backend deployment container/environment:

```bash
# 1. Apply additive database migrations
python manage.py migrate --noinput

# 2. Synchronize canonical identity policy (roles, designations, 80 capabilities, 99 role grants)
python manage.py sync_identity_policy

# 3. Synchronize canonical services (COUNSELING service and default pathways)
python manage.py sync_canonical_services

# 4. Synchronize default institutional forms
python manage.py sync_default_forms

# 5. Verify existing encrypted fields and follow-up encryption readiness
python manage.py verify_encrypted_fields --check
python manage.py verify_followup_encryption --check

# 6. Run Django system check
python manage.py check
```

---

## 4. Worker, Beat & Encryption Operational Requirements

### Celery Worker & Beat Schedule
- **`compass.appointments.tasks.send_automatic_appointment_reminders`**:
  - Registered in `CELERY_BEAT_SCHEDULE` to run every `300.0` seconds (5 minutes).
  - Safe when `APPOINTMENT_AUTO_REMINDERS_ENABLED=False` (exits immediately as a no-op).
  - When enabled, claims due 24h and 3h reminder occurrences transactionally using `select_for_update` and dispatches notifications only if `appointment_notification_is_current` passes.
- **Notification Delivery Tasks**:
  - `compass.notifications.tasks` dispatches email and web push notifications for `appointment.reminder_*`, `guidance_follow_up.*`, and `group_session.*` events, verifying `notification_is_current(notification)` before external provider handoff.

### Follow-Up Encryption Verification & Key Rotation
- To audit Follow-Up ciphertext integrity at any time:
  ```bash
  python manage.py verify_followup_encryption --check
  ```
- During key rotation (after prepending a new primary key to `FIELD_ENCRYPTION_KEYS`):
  ```bash
  python manage.py rotate_followup_encryption --dry-run
  python manage.py rotate_followup_encryption
  python manage.py verify_followup_encryption --check
  ```

---

## 5. Staged Feature Activation Sequence

After deploying with flags disabled and completing baseline smoke checks:

1. **Stage 1 — Enable Shared Guidance Follow-Up Workspace (`GUIDANCE_FOLLOWUPS_ENABLED=True`)**:
   - Update environment variable `GUIDANCE_FOLLOWUPS_ENABLED=True` on web and worker processes and restart gracefully.
   - Verify `/portal/follow-ups`, contextual creation from Counseling/Referrals/Routine Interviews, and `/portal/work` Follow-Up items.
2. **Stage 2 — Enable Follow-Up Staff Notifications (`GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=True`)**:
   - Update `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=True` on web and worker processes.
   - Verify staff notification preferences (`/api/v1/notifications/guidance-preferences`) and assignment/overdue notification delivery.
3. **Stage 3 — Enable Automatic Appointment Reminders (`APPOINTMENT_AUTO_REMINDERS_ENABLED=True`)**:
   - Confirm manual/bulk reminder preview and issuance on `/portal/appointments/manage`.
   - Update `APPOINTMENT_AUTO_REMINDERS_ENABLED=True` on web, worker, and Beat processes.
   - Monitor worker logs for `send_automatic_appointment_reminders` execution.
4. **Stage 4 — Configure Fixed-Date Slots & Group Sessions per Service**:
   - Head Guidance or IT Admin enables `FIXED_DATE_SLOT` and/or `GROUP_SESSION` pathways on target Services via `/portal/services/{id}/edit`.
   - Counselors/GSS publish Fixed-Date Slots or Group Sessions via `/portal/services/{id}`.

---

## 6. Post-Deployment Smoke Checks & Rollback Plan

### Post-Deployment Smoke Checks
- [ ] `GET /api/v1/meta` returns `200 OK` with expected release metadata.
- [ ] Student login -> `/portal/services` and `/portal/appointments` load without console or network errors.
- [ ] Counselor login -> `/portal/work`, `/portal/appointments/manage` (reminder preview), `/portal/follow-ups`, and `/portal/services/{id}` (fixed slots & group sessions) load and enforce recent MFA on mutations.
- [ ] IT Admin login -> `/portal/services/{id}` loads service configuration without firing `403` requests to `/slots` or `/group-sessions`.

### Rollback Considerations
- **Feature-Level Instant Rollback (Zero Downtime)**:
  - Set `APPOINTMENT_AUTO_REMINDERS_ENABLED=False`, `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=False`, or `GUIDANCE_FOLLOWUPS_ENABLED=False` and restart web/worker processes to immediately disable automatic reminders or follow-up workflows without database rollback.
  - Disable `FIXED_DATE_SLOT` or `GROUP_SESSION` pathways on individual Services via the Service editor if a pathway needs to be withdrawn for new bookings.
- **Database Migration Rollback**:
  - All 6 migrations (`appointments.0002`, `audit.0002`, `followups.0001`, `group_sessions.0001`, `notifications.0002`, `service_catalog.0002`, `service_catalog.0003`) are strictly additive (new tables and expanded `AuditEvent.action` choice metadata) and do not mutate or drop any pre-existing columns or rows.
