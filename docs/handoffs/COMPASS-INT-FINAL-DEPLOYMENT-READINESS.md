# COMPASS-INT-FINAL — Operational Deployment Readiness & Runbook

> RELEASE-UNBLOCK-1 update (2026-10-18): the global `GUIDANCE_FOLLOWUPS_ENABLED` gate and
> its environment contract are retired. Gate instructions below describe the historical
> rollout decision; use the current Follow-Up operations runbook for availability.
> Institutional decisions remain unresolved unless separately documented; this update
> neither establishes sign-off nor enables external email/push dispatch.

**Repository:** `ils12058/COMPASS`  
**Target Environment:** `staging` / Pre-Defense Release Candidate  
**Integration Branch:** `integration/compass-int-final-argon`  
**Date:** October 17, 2026

> **CORR-5 clarification (October 17, 2026):** This runbook's environment examples are not evidence
> of effective live staging configuration. Follow-Up rollout remains institutionally unapproved per
> ADR-FUP-1A; do not activate it until the approvals, web-only keyring, and identity-policy sync are
> verified. `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` controls external email/Web Push dispatch only;
> it does not hide authorized in-app Follow-Up notices. Automatic reminders are scheduled every
> 60 seconds, not every five minutes. The dedicated
> [CORR-5 readiness handoff](COMPASS-CORR-5-ACTIVATION-READINESS.md) records current blockers and
> the operational checks required before activation.

---

## 1. Safe-by-Default Feature Flag Posture

All new background-dispatch and rollout-gated capabilities ship **disabled by default** in `be/config/settings.py`:

| Setting / Environment Variable | Code Default | Purpose |
|---|---|---|
| `GUIDANCE_FOLLOWUPS_ENABLED` | `False` | Gates Follow-Up HTTP APIs, My Work projections, and related current-event integrations. Retain until institutional approval, key provisioning, and identity-policy synchronization are verified. |
| `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` | `False` | Pauses Follow-Up external email/Web Push delivery. In-app Notification intents, center visibility, and unread counts remain independent. |
| `APPOINTMENT_AUTO_REMINDERS_ENABLED` | `False` | Pauses creation of new automatic Student reminder occurrences in the 24-hour and 3-hour windows. Manual issuance is independent. |

> **Note:** Service Catalog Booking Pathways (`SVC-1`), Fixed-Date Appointment Slots (`SVC-2`), and Group Sessions (`SVC-3/4/5`) are per-service opt-in via `ServiceBookingPathway` configuration (`FIXED_DATE_SLOT`, `GROUP_SESSION`). Existing services retain `FLEXIBLE_APPOINTMENT` (or non-booking) behavior unchanged until an authorized administrator enables additional pathways on a specific Service.

---

## 2. Pre-Deployment Checklist

1. **Database Backup**: Take a point-in-time PostgreSQL snapshot of the target environment prior to running migrations.
2. **Environment Configuration Verification**:
   - Confirm the independent `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS_FILE` points to
     `/run/secrets/guidance_followup_encryption_keys`. The Follow-Up keyring must be distinct from
     existing encryption domains and mounted only in the web/operator context.
   - Treat these as example values, not live state. Verify approved target values without printing a full environment dump. Keep each switch false until its separate approval and readiness checks are complete.
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

# 4. Synchronize institutional forms
python manage.py sync_institutional_forms

# 5. Do not rotate keys during initial provisioning. If protected Follow-Up records exist,
#    inspect them in the web/operator context only.
python manage.py rotate_guidance_followup_encryption --dry-run

# 6. Run Django system check
python manage.py check
```

---

## 4. Worker, Beat & Encryption Operational Requirements

### Celery Worker & Beat Schedule
- **`compass.appointments.reminders.dispatch_due`**:
  - Registered in `CELERY_BEAT_SCHEDULE` every 60 seconds and imported by `compass.appointments.reminder_tasks`.
  - Safe when `APPOINTMENT_AUTO_REMINDERS_ENABLED=False`; it returns before candidate discovery.
  - When enabled, issues due 24-hour and 3-hour occurrences in bounded 15-minute windows. Each Appointment revision/window is idempotent; expired windows are not backfilled. This setting does not govern manual reminder issuance.
- **Notification Delivery Tasks**:
  - `compass.notifications.tasks` processes email and web push deliveries for supported `appointment.reminder_*`, `guidance_follow_up.*`, and `group_session.*` events, rechecking recipient/source eligibility before provider handoff.
  - Follow-Up in-app intents are created independently of `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED`; that switch gates external delivery only. Check pending deliveries before re-enabling it because previously queued pending items can resume.

### Follow-Up Encryption Verification & Key Rotation
- The merged application provides `rotate_guidance_followup_encryption`. Its dry run verifies
  protected records without changing ciphertext. For newly initialized tables, inspect whether
  protected records exist before interpreting a zero-record result:
  ```bash
  python manage.py rotate_guidance_followup_encryption --dry-run
  ```
- During an approved rotation, prepend the new primary to all still-required keys in
  `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS`, retain the existing keys, and use the same command:
  ```bash
  python manage.py rotate_guidance_followup_encryption --dry-run
  python manage.py rotate_guidance_followup_encryption
  python manage.py rotate_guidance_followup_encryption --dry-run
  ```

---

## 5. Staged Feature Activation Sequence

Only after the applicable institutional approvals, secret provisioning, identity-policy sync, and
delivery checks are complete, use a reviewed configuration release. Current Follow-Up approval and
live-runtime readiness are not established by this static runbook.

1. **Stage 1 — Enable Shared Guidance Follow-Up Workspace (`GUIDANCE_FOLLOWUPS_ENABLED=True`)**:
   - Update environment variable `GUIDANCE_FOLLOWUPS_ENABLED=True` on web and worker processes and restart gracefully.
   - Verify `/portal/follow-ups`, contextual creation from Counseling/Referrals/Routine Interviews, and `/portal/work` Follow-Up items.
2. **Stage 2 — Enable Follow-Up Staff Notifications (`GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=True`)**:
   - Review pending email/push deliveries and approved destinations before updating
     `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=True` on web and delivery workers.
   - Verify the authorized in-app notification independently from the synthetic email or opted-in
     push delivery. This setting does not control in-app visibility and no overdue reminder cadence
     is created by the Follow-Up notification integration.
3. **Stage 3 — Enable Automatic Appointment Reminders (`APPOINTMENT_AUTO_REMINDERS_ENABLED=True`)**:
   - Confirm manual/bulk reminder preview and issuance on `/portal/appointments/manage`.
   - Update the worker's `APPOINTMENT_AUTO_REMINDERS_ENABLED` value and reload/restart workers that
     execute the reminder task. Web/manual issuance does not use this flag; Beat continues to
     enqueue the registered 60-second task and does not need the flag or a restart solely for this
     change.
   - Monitor worker logs for `compass.appointments.reminders.dispatch_due` execution.
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
  - For automatic Reminders, set the value false in the task-executing worker and reload/restart it; Beat continues enqueueing the task, which then returns zero. This stops new automatic occurrences but does not retract already-created reminder transports. For Follow-Up external dispatch, set the value false on web and delivery workers and reload/restart them; this pauses external email/push but leaves in-app notices available. The core Follow-Up switch disables its APIs and work/event integrations and must remain false until its institutional/security gates are met. Inspect queued deliveries separately. Database rollback is not required for an operational pause.
  - Disable `FIXED_DATE_SLOT` or `GROUP_SESSION` pathways on individual Services via the Service editor if a pathway needs to be withdrawn for new bookings.
- **Database Migration Rollback**:
  - The six staged migrations are `appointments.0002`, `guidance_followups.0001`,
    `guidance_followups.0002`, `group_sessions.0001`, `service_catalog.0002`, and
    `service_catalog.0003`. They add reminder fields/tables, new feature tables and constraints,
    and a Service Booking Pathway backfill. Do not reverse them after schema changes; use reviewed
    forward recovery while preserving the canonical database and UAT records.
