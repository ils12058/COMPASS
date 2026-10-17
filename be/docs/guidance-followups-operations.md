# Follow-Up work, delivery, recovery and rollout contract

## Scope and authority

FUP-1D1/FUP-1D2/FUP-1E depend on workspace PR #260 and foundation #259. This slice adds a read-only
My Work source, staff notification intents, durable HTTP mutation receipts, operational reassignment
recovery and web-only key rotation tooling. It does not own Service Catalog or Group Session work.

| Reader | Operational Follow-Ups | Confidential Follow-Ups | Recovery |
|---|---|---|---|
| Counselor | Assigned records in current handled scope | Assigned canonical source relationship plus current source capabilities | Operational records in current scope whose owner is ineligible |
| Guidance Services Staff | Assigned records in current supervisor-derived scope | None | Same narrow operational recovery scope |
| Head Guidance Counselor | Assigned operational records; institutional operational scope | Own assigned source relationship only | Operational institutional scope only |
| Student, IT Administrator, DPO without a Guidance business role | None | None | None |

Capabilities remain `guidance_followups.view` and `.manage`, with manage depending on view. The
server reloads current account state. A designation alone does not grant confidential authority.
Recovery exposes summary facts only, never descriptions, outcomes or source IDs; it permits only
reassignment. Normal detail/edit access still requires ownership and resource policy. Reassignment
then independently validates the new owner. Deactivation, capability dependency revocation,
supervisor changes and Student affiliation changes are evaluated against current state. Confidential
recovery after loss of a professional source relationship requires a separately authorized source
workflow; no administrative bypass is introduced.

## Durable lifecycle and My Work

Creation has a durable actor/key/fingerprint identity. Every HTTP lifecycle write additionally
requires `Idempotency-Key` and `expected_version`. A schema-only receipt stores actor, digest,
fingerprint, operation, follow-up and resulting revision. Identical retries return currently
authorized state without reapplying the mutation; changed payload/operation with the same key is
409. Reassignment retries return a minimized receipt when the caller no longer owns the record.
The receipt is not another Task/Case lifecycle and contains no protected text. No-op updates are
also covered. Domain callers without transport keys retain optimistic version enforcement.

`GUIDANCE_FOLLOW_UP` is a read-only projection of currently assigned, authorized PENDING records.
The owning domain scopes and orders a bounded prefix before the queue composes it with Messages,
Routine Evaluation, Good Moral and Call Slips. Cards contain Student display name, due time and
opaque Follow-Up identity, never descriptions, outcomes or source content. The confirmed queue
`generated_at` controls overdue language. Completion/cancellation/reassignment/access loss removes
a card on the next canonical read. Reminders create no staff work cards.

`followups.changed` is a content-free realtime hint. Current and previous owners reconcile their
caches, including removal after transfer. The same socket runtime handles it; no feature socket is
created. Focus/reconnect/generation recovery and a visible-page 60-second safety poll preserve
correctness without realtime. Confirmed writes invalidate the domain and existing work projections.

## Notification matrix

| Event | Recipient | Occurrence | External channels |
|---|---|---|---|
| `guidance_followup.assigned` | Authorized assigned staff | CREATED history-event UUID | Email and supported opt-in browser push only when enabled |
| `guidance_followup.reassigned` | Authorized new assignee | REASSIGNED history-event UUID | Same |
| `guidance_followup.due_changed` | Authorized current assignee | Material UPDATED history-event UUID | Same |
| `appointment.reminder_24h`, `.reminder_3h`, `.reminder_manual` | Student only, owned by REM-1 | Independent appointment_reminder occurrence UUID | Existing Reminder delivery contract |
| Service/Group events | Agent 2 owns policy and implementation | Must use distinct identities | Requires deliberate shared integration review |

Follow-Up notification source is `guidance_followup_event`, destination is `GUIDANCE_FOLLOW_UP`.
Intents are created inside the domain transaction. Notification uniqueness uses the immutable event
UUID; email/push reuse existing durable claim/retry state. Payloads contain fixed generic copy and
safe navigation only, with no Student names or confidential text. In-app lists/counts suppress stale
events in SQL before pagination. The latest material event supersedes previous assignment/due-change
events even if ownership later returns to an earlier owner. Activities and description-only changes
do not send notifications. Terminal state, recipient/capability/scope/source-access loss and feature
disablement make old occurrences ineligible. Workers validate eligibility without content keys.

Claim and final provider handoff recheck current eligibility. Existing email claim ownership,
expiry and recipient destination are rechecked. Provider acceptance cannot be recalled. Interruption
after provider acceptance can cause an external retry; SMTP/web-push do not provide an exactly-once
external handoff guarantee. No internal Follow-Up sends automatic Student notifications. No deadline
reminder schedule or retention duration is invented.

## Environment and secret inventory

| Setting | Default / consumer | Prerequisite |
|---|---|---|
| `GUIDANCE_FOLLOWUPS_ENABLED` | false; web, worker/Beat where shared settings load | Approved workspace rollout and provisioned web content keyring |
| `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS` or `_FILE` | empty; web/operator rotation only | Independent ordered Fernet keyring; primary first; no reuse of another domain or Django/TOTP secrets |
| `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED` | false; web and delivery workers | Approved destinations, SMTP and browser-push validation |
| `APPOINTMENT_AUTO_REMINDERS_ENABLED` | false; REM web/worker/Beat | Separate approved Student Reminder rollout |
| Existing `WEB_PUSH_*`, SMTP, Redis/Celery settings | Existing delivery policy | Approved external integration, active device/session and opt-in subscription |

Compose grants `guidance_followup_encryption_keys` only to web. Worker/Beat explicitly clear both
Follow-Up keyring forms; realtime has no Django/database/content secrets. The deployment inventory
and synthetic Compose checks include the new file. These edits provision no actual secret. The
staging Compose file requires the reviewed secret file before deploying its web service, even while
the feature flag is false. Follow-Up workers remain keyless; existing unrelated legacy key mounts
are preserved.

Rotation: put the approved new primary before all still-needed old keys in the web keyring. Run
`python manage.py rotate_guidance_followup_encryption --dry-run`, investigate every unreadable
count, then run without dry-run in the authorized web/operator environment. It validates exact
record/event/section bindings, updates ciphertext only in bounded locked batches and is resumable.
Verify again before removing any old wrapping key. Business versions, timestamps, events and
notification identities are unchanged. Retain backups plus the complete associated keyring under
approved separate custody; a missing historical key cannot be reconstructed from ciphertext. A
missing/malformed key fails protected operations closed. Restores must use a schema-compatible
canonical backup and verified keyring; never fake pre-canonical history. No institutional backup or
retention duration is selected here.

## Migration, deployment order, rollback and smoke tests

1. Review exact compatible REM/FUP/Service candidate SHAs and complete all CI/integration checks.
2. Obtain explicit merge/deployment and key-provisioning approvals. No approval is implied here.
3. Take and verify the approved canonical PostgreSQL backup and separately secured keyring backup.
4. Provision the web-only Follow-Up keyring and approved runtime variables. Keep all new dispatch
   flags false; verify worker/Beat/realtime key exclusions using rendered Compose configuration.
5. Run history/preflight checks and review `migrate --plan`. Apply guarded additive migrations:
   REM appointments.0002; Follow-Up 0001_initial then 0002_guidancefollowupmutation; Agent 2's reviewed
   independent migration graph. Existing canonical migration bytes remain immutable and unknown
   historical migrations remain refused. No reset or destructive reseeding is part of this rollout.
6. Synchronize identity policy to install Follow-Up capabilities and dependency-coherent grants.
7. Deploy compatible web, worker, one Beat and frontend; retain existing Redis/realtime boundaries.
8. With synthetic/approved fixtures, smoke role denial, confidential source access, create/retry,
   activity/version conflict, complete/cancel, authorized reassignment, recovery, My Work removal,
   report scope and keyless eligibility. Verify no source workflow or UAT data was changed.
9. Validate approved SMTP and opt-in push recipients, stale-event cancellation, claim recovery and
   task registration. Enable Follow-Up external delivery and automatic Student Reminders separately,
   only after their own approvals. No historical backfill is performed on enablement.

Rollback: disable the relevant feature/external dispatch flags in web and workers first. Stop/drain
relevant producers if required. Roll back compatible application images while retaining additive
schema, encrypted content, durable receipts and notification history. Reversing the new tables
would destroy feature history and requires a separate approved recovery operation. Tested disposable
migration rehearsal and exact-commit evidence belong in the final integration report. Restore only
reviewed backups with corresponding keys; never drop or reset canonical UAT data to fix a migration.

## Open policy and cross-agent decisions

Deadline reminders, retention periods and institutional broad analytics remain outside this release
unless separately approved. Existing on-screen reports use the reader-selected interval and no
free-text export. Agent 2 owns Service Catalog functionality and must review its domain against the
combined candidate. Preserve distinct notification identities, the closed realtime registry, all
API operation IDs and the canonical baseline checksum registry when resolving shared files. Final
readiness requires that exact combined validation; an open PR alone is not completion evidence.
