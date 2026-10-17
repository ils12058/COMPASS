# COMPASS-CORR-5 — Feature Activation Cleanup & Operational Readiness

**Status:** Static code/configuration audit and focused regression work. This worktree agent made no
live/staging migration, activation, configuration change or secret operation, and did not dispatch
notifications, merge or deploy. The parent task owner will create the PR after review.
**Repository:** `ils12058/COMPASS`
**Branch:** `fix/compass-corr-5-activation-cleanup`
**Base:** `origin/staging` at `92b7543fdb9c7b676d8e8c50d18d57c732601b82`

## 1. Baseline and CORR-1 through CORR-4

The exact implementation commits below are ancestors of the CORR-5 base:

| Work | Commit / staging merge |
|---|---|
| CORR-1A secure service lifecycle dependency | `a000e9c99231de7c87f6f73d894de3839555ab84` |
| CORR-1B integrated service reconciliation | implementation `26f59a9f`; PR #270 merge `92b7543f` |
| CORR-2 reminder and Follow-Up reconciliation | `07a71d88`; PR #267 |
| CORR-3 E-Counseling pre-join check | `bdba573d`; PR #269 |
| CORR-4 portal UX | `3e8af189`; PR #268 |

Ancestor checks returned success for each implementation commit. The worktree started clean at the
exact fetched `origin/staging` SHA above.

## 2. Activation flag inventory

Values below describe checked-in defaults/examples, not effective live Droplet values.

| Setting | Classification | False behavior | True behavior | CORR-5 decision |
|---|---|---|---|---|
| `GUIDANCE_FOLLOWUPS_ENABLED` | Institutionally controlled configuration and deployment/security prerequisite (classes 4 and 5) | Follow-Up APIs return disabled-state 503; My Work and Follow-Up current-event integrations return no projection/eligible notices. | Enables the existing endpoints and integrations, which still enforce current identity, capability, resource, confidentiality, lifecycle and encryption-key checks. | Retain for now. ADR-FUP-1A says the rollout is **not approved**. It is not yet a safely obsolete rollout gate. |
| `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` | External transport capability plus operational pause (classes 2 and 3) | With the core feature available, durable in-app Notification intents, current Notification Center entries, unread counts and realtime freshness remain. New Follow-Up email/push delivery rows are not created. A pending external attempt processed while off is cancelled. | New eligible events may create content-minimized email and opted-in browser-push deliveries, subject to transport, currentness and recipient checks. Follow-Up email uses `MANDATORY_OPERATIONAL` policy, so the optional-email preference does not suppress it. Existing still-pending deliveries can become eligible when switched on. | Retain as a clearly documented external-dispatch pause. Never treat it as the in-app notification switch. Inspect pending records before enabling. |
| `WEB_PUSH_ENABLED` | Shared infrastructure capability (class 2) | Browser-push setup APIs and delivery are disabled for all event types; in-app and email behavior are independent. | Permits browser-push setup and delivery when the VAPID pair, contact and storage key are valid, and an active opted-in subscription/session plus recipient/source checks pass. Follow-Up push still requires `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=true`. | Retain as the shared Web Push infrastructure control. Do not enable without the existing key/migration and subscription-readiness procedure. |
| `APPOINTMENT_AUTO_REMINDERS_ENABLED` | Institutionally controlled configuration and emergency/operational pause (classes 3 and 4) | Automatic discovery returns before querying and creates no new automatic occurrences. Manual reminder issuance remains separately authorized. | Enables new 24-hour and 3-hour automatic occurrences in bounded 15-minute windows, once per Appointment revision/window; expired windows are not backfilled. Existing occurrence transports retain their current recovery behavior. | Retain. This protects against unapproved automated Student communications. |

The unrelated E-Counseling webhook replay and media reconciliation controls, maintenance and abuse
protections, staging seeding safeguards, and per-Service booking pathway controls were outside this
CORR-5 change and remain unchanged.

`GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS` is a required dedicated secret, not a feature switch. The current
runtime source contract requires its non-empty host file and grants it to web only. That deployment
requirement does not constitute approval to expose Follow-Ups. Worker, Beat and realtime remain
keyless for this domain; no key reuse or plaintext fallback is permitted.

## 3. Follow-Up activation blockers

`be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md` is explicit: “Implementation proposal;
institutionally gated / NOT an approved rollout.” It lists these unresolved institutional decisions:

- GCO, DPO and Records approval for allowed categories, GSS coordination boundaries, confidentiality
  classes, retention/hold/disposition, reassignment recovery, key provisioning/rotation and live-staging
  enablement.
- A separately approved, independent ordered Follow-Up keyring provisioned for the web service.
- Explicit `sync_identity_policy` after approval; migrations do not install the capabilities.
- Verification that applicable identity roles, capabilities, College/supervision scopes and source
  relationships match the approved access boundaries.
- A live read-only check of whether Follow-Up ciphertext exists and, if it does, verification that its
  historical keyring can decrypt every bound envelope before any activation.

The backend uses record-bound encryption and fails protected reads/writes closed when keys are absent
or invalid. It has no plaintext fallback. Authorization is revalidated against current actor,
capability, resource and confidentiality policy. Do not remove the core switch or silently enable the
feature until the listed gates are satisfied.

## 4. Notification lifecycle and pause behavior

The source transaction creates a durable in-app `Notification` and realtime freshness hint before the
external-delivery check. Follow-Up Notification Center and unread-count queries use the authorized,
current-event SQL scope; they do not depend on the external switch. When the external switch is false,
creation of email/push delivery records is skipped. If a queued delivery is claimed while the switch is
false, it is cancelled before provider handoff. Recipient/source currentness is rechecked at claim and
again before email/push handoff. Content stays generic and excludes student names and protected text.

The repository cannot establish whether live staging currently has pending external delivery rows or
suppressed records. The read-only SSH attempt timed out. Before any external enablement, an authorized
operator must inspect delivery status counts without printing payloads or destinations, review every
pending item against the current source and recipient, and resolve old pending work before changing the
switch. No email or push was sent during this task.

## 5. Appointment reminder audit

The implementation registers `compass.appointments.reminders.dispatch_due` in
`CELERY_BEAT_SCHEDULE` every 60 seconds and imports `compass.appointments.reminder_tasks` through
`CELERY_IMPORTS`. The dispatcher returns before candidate discovery when the operational switch is
false. The two automatic windows are 24 hours and 3 hours with a 15-minute late window, timezone-aware
instants, row-lock/idempotency protection, and no historical backfill. Manual issuance has separate
authorization, MFA and manual-to-manual cooldown rules; neither manual nor automatic issuance suppresses
the other's window. Turning automatic dispatch off does not cancel already-created reminder occurrences
or their pending transport work.

The operator docs now identify which services must reload the same setting, how to verify Beat and
worker readiness, how to pause safely, and how to recover without backfilling. Examples remain false;
no live staging value was read or changed.

## 6. Runtime/deployment evidence

Static inspection confirmed:

- `be/deploy/runtime-secrets/runtime_secrets.py` requires the Follow-Up key as a non-empty runtime
  source; `be/compose.staging.yaml` mounts it to web only and explicitly clears worker/Beat key forms.
- The manifest and runtime pointer example comprise 25 source files. The runtime-secret inventory
  documentation was corrected to the 25-source contract and now separates key presence from feature
  approval.
- The Follow-Up key setting/file is independent of the feature flag. The repository does not contain
  or generate the production key.
- The reminder task is imported and registered at 60 seconds by the checked-in Celery configuration.
  The worker executing it evaluates `APPOINTMENT_AUTO_REMINDERS_ENABLED`; Beat continues enqueueing
  the task and does not evaluate the switch.

The documented staging Droplet was found active through the authorized cloud inventory check, but the
read-only SSH connection timed out. Therefore the following live facts remain **unknown**: effective
web/worker/Beat environment values; key-file presence/validity and keyring compatibility; applied
migration state; identity-policy synchronization; task registration in the running worker/Beat; and
pending/previously suppressed notification counts. No `.env`, host secret, service, database, or queue
was read or changed by this implementation task. Values in examples are not evidence of live state.

## 7. Readiness status

| Area | Code readiness | Deployment readiness | Institutional approval | Live verification |
|---|---|---|---|---|
| Shared Guidance Follow-Ups | Foundation and scoped integrations exist; preserve the gate and focused security coverage. | Blocked pending web keyring, identity sync, migration/runtime checks and ciphertext compatibility review. | Not approved per ADR-FUP-1A. | Not verified. |
| Automatic Appointment reminders | Task, 24h/3h windows, idempotency and independent manual path are implemented. | Unknown until the worker's effective flag, a single healthy Beat and eligible workers are verified. | Separate automated Student reminder rollout approval remains required. | Not verified; samples default false. |
| Follow-Up email/Web Push | Durable in-app intents are independent; external paths retain dispatch/currentness checks. | Blocked pending approved destinations, SMTP/Web Push readiness and review/resolution of pending delivery rows. | External dispatch approval not evidenced. | Not verified; queue state unknown. |

## 8. Deployment handoff checklist

1. Obtain written GCO/DPO/Records approval for the exact Follow-Up categories, confidentiality and
   GSS scope, retention/holds/disposition, recovery policy and staging rollout.
2. Review whether any Follow-Up records exist and validate every historical envelope using the
   corresponding protected keyring. Provision the independent ordered keyring through the approved
   host procedure; verify only safe presence/validity and web-only grants. Keep workers, Beat and
   realtime keyless. Preserve all needed historical keys and an approved recovery copy.
3. Verify and explicitly run the approved `sync_identity_policy`; check current role/capability,
   College/supervision and source-policy behavior before exposing the web routes. Review the guarded
   migration plan and migration state before deployment; do not reset or rewrite canonical history.
4. Keep `GUIDANCE_FOLLOWUPS_ENABLED=false` until steps 1–3 and a reviewed deployment are complete.
   Reload/restart web consumers and use approved synthetic staff/Student fixtures for denial, scope,
   confidential-source and key-failure smoke checks. Confirm no plaintext fallback.
5. Keep external Follow-Up dispatch false while reviewing pending email/push state, recipient
   eligibility, the mandatory operational email policy, opt-in subscriptions and approved SMTP/Web Push
   destinations. Resolve old pending deliveries before enabling; then verify only synthetic/approved
   recipients and content-minimized templates. Never use real recipients in smoke tests.
6. For automatic reminders, keep the pause false until the institution separately approves student
   communications. Confirm `dispatch_due` registration, exactly one Beat, workers able to process it,
   approved destinations, and the 24h/3h bounded-window/idempotency behavior. Set and reload the flag
   on the task-executing worker; Beat keeps enqueueing the task and does not need a restart solely for
   this switch. Manual operations remain governed separately.
7. Emergency pause: set the affected switch false in each process that evaluates it and reload/restart
   those processes. For reminders, that is the worker executing the task; Beat keeps enqueueing a
   no-op until the worker is healthy again. The external Follow-Up pause stops new
   email/push attempts but does not hide in-app items; the core Follow-Up pause disables its APIs and
   work/current-event integrations. Inspect queued delivery state separately because accepted provider
   messages cannot be recalled.
8. Recovery: identify and correct the cause, review current recipients/source state and delivery
   failures, confirm queues and workers are healthy, then re-enable only through the approved
   configuration release. Skipped reminder windows are not backfilled. Roll back compatible app code
   while retaining additive schema, encrypted content, Notification history and reminder occurrences;
   never drop feature tables or reset canonical/UAT data as an incident shortcut.

## 9. CORR-5 implementation and verification record

The bounded implementation consists of in-app/external-pause regression tests, clearer operator
settings examples, and corrections to the Follow-Up, Reminder, runtime-secret, and deployment
readiness documents. No rollout gate was removed, no automatic dispatch was enabled, and no new flag
was introduced. No frontend source changed, so no frontend test suite was run.

| Check | Exact command | Outcome |
|---|---|---|
| Focused backend regressions and runtime-secret/Compose contract | `cd be && uv run pytest -q tests/test_guidance_followups.py tests/test_appointment_reminders.py tests/test_runtime_secrets_compose.py` | **66 passed, 0 skipped** in 94.20s. Both Compose rendering cases ran using the available standalone `docker-compose` CLI; no Docker daemon was required. No real email or push was sent. |
| Django system check | `cd be && uv run python manage.py check --settings=tests.settings` | Passed: no issues (0 silenced). |
| Migration drift check | `cd be && uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` | No changes detected. Django warned the local `compass_test` database does not exist, so database-history consistency was not checked by this command. No model/schema files changed in CORR-5. |
| Ruff lint | `cd be && uv run ruff check tests/test_guidance_followups.py` | Passed. |
| Ruff format | `cd be && uv run ruff format --check tests/test_guidance_followups.py` | Passed; file already formatted. |
| Whitespace/error check | `git diff --check` | Passed. |

This worktree agent did not create a PR or trigger PR CI. The parent task owner handles PR creation
after review, and checks on that PR have not run yet. The final commit SHA is reported in the task
completion message after the changes are committed.
