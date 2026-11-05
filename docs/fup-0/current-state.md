# Current state — Guidance Follow-Up domain at FUP-0

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9` (2026-11-05).
**Claim labels:** every substantive statement is **Verified**, **Inferred** or **Unknown**. Unless a row
is explicitly labeled otherwise, the statements and tables in this document are **Verified** against
the files cited. No runtime behavior was executed.

## 1. Where the domain lives

| Layer | Path | Role |
|---|---|---|
| Models | `be/compass/guidance_followups/models.py` | Three tables, enum choices, integrity constraints, indexes |
| Services | `be/compass/guidance_followups/services.py` | Creation, read, list, mutation and detail orchestration |
| Policy | `be/compass/guidance_followups/policy.py` | Actor, source, operational scope, confidential scope, assignee eligibility |
| API | `be/compass/guidance_followups/api.py` | 14 strict authenticated HTTP operations |
| Workspace | `be/compass/guidance_followups/workspace.py` | Eligible Students, source context, eligible assignees, aggregate reporting |
| Integration | `be/compass/guidance_followups/integration.py` | My Work projection, notification currentness, realtime hints |
| Recovery | `be/compass/guidance_followups/recovery.py` | Operational orphan detection and reassignment support |
| Replay | `be/compass/guidance_followups/replay.py` | Durable mutation receipts and retry identity |
| Content | `be/compass/guidance_followups/content.py` | Authenticated encryption, AAD binding, fail-closed keyring, rotation |
| Errors | `be/compass/guidance_followups/errors.py` | Five private error classes mapped to HTTP |
| Migrations | `be/compass/guidance_followups/migrations/0001_initial.py`, `0002_guidancefollowupmutation.py` | Three tables and constraints |
| Rotation command | `be/compass/guidance_followups/management/commands/rotate_guidance_followup_encryption.py` | Batched verify/re-encrypt, resumable |
| Tests | `be/tests/test_guidance_followups.py` | 29 test functions / 33 static cases |
| Operational docs | `be/docs/guidance-followups-operations.md`; `be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md` | Authority matrix, flags, rotation, rollout, ADR |
| Frontend | `fe/src/features/guidance-followups/`; `fe/src/app/(portal)/portal/follow-ups/` | List, create, detail, report, recovery, context panel, help |

The router is mounted under `/api/v1/guidance-followups`
(`be/compass/api/v1/router.py:30`; router construction at
`be/compass/guidance_followups/api.py:42`).

## 2. Models

### 2.1 `GuidanceFollowUp` — `models.py:45-144`

| Field | Definition | Notes |
|---|---|---|
| `id` | UUID primary key, generated | `:46` |
| `student` | FK to `AUTH_USER_MODEL`, `PROTECT` | Not restricted to role at database level; policy checks role/active |
| `source_kind` | nullable 32-char choice | `COUNSELING_ENCOUNTER`, `REFERRAL`, `ROUTINE_INTERVIEW` |
| `source_id` | nullable UUID, **not a ForeignKey** | Source identity is a loose reference; no database referential integrity |
| `visibility` | 32-char choice | `OPERATIONAL`, `COUNSELOR_CONFIDENTIAL` |
| `category` | 32-char choice | `ADMINISTRATIVE`, `STUDENT_CONTACT`, `COUNSELING`, `REFERRAL_ACTION` |
| `assigned_to` | FK to `AUTH_USER_MODEL`, `PROTECT` | Current owner; policy requires active staff role + capability |
| `due_at` | `DateTimeField`, required | Creation requires an aware **future** time |
| `status` | 16-char choice, default `PENDING` | `PENDING`, `COMPLETED`, `CANCELLED` |
| `description_ciphertext` | nullable text, `editable=False` | Encrypted free text |
| `outcome_ciphertext` | nullable text, `editable=False` | Encrypted completion outcome |
| `created_by` | FK, `PROTECT` | Creation provenance |
| `completed_by`, `completed_at` | nullable FK/time | Completion provenance |
| `cancelled_by`, `cancelled_at` | nullable FK/time | Cancellation provenance |
| `version` | positive integer, default 1 | Optimistic concurrency and event revision |
| `creation_key_digest` | 64-char **unique** | Actor-scoped SHA-256 of the idempotency key |
| `creation_request_fingerprint` | 64-char | Request identity; changed fingerprint on replay conflicts |
| `created_at`, `updated_at` | automatic timestamps | |

**Integrity constraints** (`models.py:99-136`):

1. `fup_source_pair_consistent` — both source fields null or both non-null (`:100-106`).
2. `fup_version_positive` — version ≥ 1 (`:107`).
3. `fup_terminal_state_consistent` — `PENDING` has no completion/cancellation/outcome; `COMPLETED`
   has completion actor/time and outcome, no cancellation; `CANCELLED` has cancellation actor/time,
   no completion or outcome (`:108-135`).

**Indexes** (`:138-144`): assignment/status/due/id; student/created/id; source kind/id.

`default_permissions = ()` (`:97`) removes Django's generic model permissions; the domain is reached
only through its API and services.

**Not enforced by the model:** source-kind/category coherence and source/student match are service
policy, not a database check. A direct ORM write could create a row the policy would never create.
**Verified** by absence of such constraints in `models.py`.

### 2.2 `GuidanceFollowUpEvent` — `models.py:147-176`

| Field | Definition | Notes |
|---|---|---|
| `id` | UUID primary key | |
| `followup` | FK `PROTECT`, related name `events` | |
| `kind` | 24-char choice | `CREATED`, `UPDATED`, `REASSIGNED`, `ACTIVITY_RECORDED`, `COMPLETED`, `CANCELLED` |
| `actor` | FK `PROTECT` | Who performed the change |
| `revision` | positive integer | Matches the task version at the event |
| `old_assignee`, `new_assignee` | nullable FKs | Reassignment provenance |
| `old_due_at`, `new_due_at` | nullable datetimes | Due-change provenance |
| `remarks_ciphertext` | nullable text, `editable=False` | Encrypted activity/cancellation text |
| `created_at` | automatic | |

Unique `(followup, revision)` (`:171-174`) and revision ≥ 1 (`:175`). `default_permissions = ()`.
There is **no application update/delete operation** for events, and no database trigger. The
"immutable history" is an application convention plus the absence of mutation routes, not a
database-enforced append-only guarantee. **Verified** by service/API inventory; **Inferred** that an
ORM-level writer outside the domain could update rows.

### 2.3 `GuidanceFollowUpMutation` — `models.py:179-198`

Durable request identity only: `followup` FK, `actor` FK, unique `key_digest`, request fingerprint,
`action`, `revision`, timestamp. No free text and no second business lifecycle. `default_permissions =
()`.

## 3. Enumerations and classification

`models.py:12-42`:

| Enum | Values |
|---|---|
| `FollowUpSource` | `COUNSELING_ENCOUNTER`, `REFERRAL`, `ROUTINE_INTERVIEW` |
| `FollowUpVisibility` | `OPERATIONAL`, `COUNSELOR_CONFIDENTIAL` |
| `FollowUpCategory` | `ADMINISTRATIVE`, `STUDENT_CONTACT`, `COUNSELING`, `REFERRAL_ACTION` |
| `FollowUpStatus` | `PENDING`, `COMPLETED`, `CANCELLED` |
| `FollowUpEventType` | `CREATED`, `UPDATED`, `REASSIGNED`, `ACTIVITY_RECORDED`, `COMPLETED`, `CANCELLED` |

`policy.classify` (`policy.py:117-135`) is the only source-of-truth mapping:

| Source | Required category | Result | Server override of supplied visibility |
|---|---|---|---|
| `COUNSELING_ENCOUNTER` | `COUNSELING` | `COUNSELOR_CONFIDENTIAL` | Rejected if different (`services.py:150-151`) |
| `ROUTINE_INTERVIEW` | `COUNSELING` | `COUNSELOR_CONFIDENTIAL` | Rejected if different |
| `REFERRAL` | `REFERRAL_ACTION` | `OPERATIONAL` | Rejected if different |
| none | `ADMINISTRATIVE`, `STUDENT_CONTACT`, `REFERRAL_ACTION` | `OPERATIONAL` | Rejected if different |
| none | `COUNSELING` | Invalid | No source-free counseling task |

A task's visibility cannot be changed later: `update_followup` has no source/visibility parameter, and
a category change that would alter the classification is rejected (`services.py:314-319`). **Verified.**

## 4. Lifecycle

### 4.1 States and transitions

```
create ──> PENDING ── complete ──> COMPLETED
              │
              ├── cancel ────────> CANCELLED
              │
              ├── update / reassign / record activity (stays PENDING)
              │
              └── time passes (stays PENDING; may become overdue)
```

- `PENDING` is the default and the only state that `_lock_for_mutation` accepts
  (`services.py:281-282`).
- `COMPLETED` and `CANCELLED` are terminal. No normal service reopens, resumes or edits them.
- Overdue is derived (`due_at < now`), not a status (`api.py:246`; `workspace.py:170`).
- Completion writes encrypted outcome, actor and time in one transaction (`services.py:391-417`).
- Cancellation writes encrypted reason as the event's remarks and cancellation provenance
  (`services.py:422-463`).
- `record_activity` does not change status; it appends an event and increments version
  (`services.py:374-386`).

**Verified.** The database constraint enforces the same terminal/provenance combinations
(`models.py:108-136`).

### 4.2 Version and event rules

Every business mutation increments `version` and writes an event at the new revision:

| Operation | Version | Event | Audit | Notification intent |
|---|---:|---|---|---|
| Create | 1 (default) | `CREATED` | `guidance_followup.created` | Material → assignment notification |
| Update due/category/description | +1 if changed | `UPDATED` | `guidance_followup.updated` | Material only when old due exists and changes |
| Reassign | +1 | `REASSIGNED` | `guidance_followup.reassigned` | Material → reassignment notification |
| Record activity | +1 | `ACTIVITY_RECORDED` | `guidance_followup.activity_recorded` | Not material; realtime hint only |
| Complete | +1 | `COMPLETED` | `guidance_followup.completed` | Not material |
| Cancel | +1 | `CANCELLED` | `guidance_followup.cancelled` | Not material |

Evidence: `services.py:326-333,358-368,382-385,400-415,431-462`; `integration.py:47-54`;
`audit/actions.py:255-260`. A no-op update/reassign returns without a new version or event
(`services.py:324-325,355-356`).

### 4.3 Creation validation sequence

`services.py:127-208` executes, in order:

1. `policy.current_actor(actor, manage=True)` — active, allowed role, capability (`:144`).
2. Idempotency key format and actor-scoped digest; request fingerprint (`:145-146,59-62`).
3. Source-pair completeness (`:147-148`).
4. `policy.classify` and refusal to override visibility (`:149-151`).
5. Transaction, actor row lock (`:152-154`).
6. Creation-key replay: same fingerprint returns the existing task if the actor is still authorized;
   a different fingerprint conflicts (`:155-167`).
7. Future, aware due time (`:168`).
8. Student existence and active `STUDENT` role, row-locked (`:169`; `policy.py:32-39`).
9. If a source exists: **manage**-level source authorization (`:170-177`).
10. If no source: operational scope (`:178-179`).
11. Assignee eligibility for the derived visibility (`:180-186`).
12. Confidential creation requires the assignee to be the creating actor (`:187-188`).
13. Encrypt description, insert row, append `CREATED` event, write audit (`:189-207`).

The `GuidanceFollowUp` row is inserted with `force_insert=True`; the encrypted description is set
before save. The event references `item.version` (1). A failure at any point rolls back the transaction.

### 4.4 Durable mutation replay

`replay.py:12-59`:

- HTTP mutation callers supply `Idempotency-Key` (`api.py` write routes).
- The digest is actor-scoped; the fingerprint is a request hash.
- A replay with the same action/follow-up/fingerprint returns the existing task, or the existing
  event for `record_activity`, without creating a second mutation.
- A changed fingerprint, action or follow-up raises conflict.
- A receipt row is written after the mutation in the same transaction; receipts contain no content.

The creation path uses its own `creation_key_digest` / `creation_request_fingerprint` columns rather
than the mutation table (`models.py:91-92`; `services.py:145-167`).

### 4.5 Concurrency

- Creation locks the actor row (`select_for_update`) before replay lookup and student/source checks
  (`services.py:152-154`).
- Mutations lock only the Follow-Up row with `select_for_update(of=("self",))` (`services.py:65-76`),
  then check expected version and `PENDING` status.
- Concurrent completion is covered by a PostgreSQL test (`test_guidance_followups.py:399-428`), but
  that test was **not run** in FUP-0.
- **Inferred risk:** a source-domain mutation (e.g. Referral void) does not share a lock or
  transaction with Follow-Up completion, so a completion and a source invalidation can interleave.
  No cross-domain locking exists.

## 5. Encryption and protected content

`content.py`:

- Keyring from `settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS` (`:18-25`); missing/invalid keyring raises
  `FollowUpContentUnavailable` (HTTP 503, `api.py:207-211`).
- Fernet keyring parsing via `compass.confidential_data.crypto`.
- Bound JSON with AAD `{followup_id, section, event_id?}` (`:40-44`); sections are `description`,
  `outcome`, `remarks`.
- Maximum 4,000 characters per protected text (`:13-15`); NUL/encoding validation (`:28-37`).
- Decryption failures, tamper, wrong record or wrong section all become 503; plaintext is not returned
  in the error (`:67-86`).
- `rotate_text` verifies before re-encrypting with the primary key (`:89-91`).
- Detail reads decrypt description, outcome and each event's remarks in Python; one failure aborts the
  detail response with 503 (`services.py:487-504`). **Verified** by code; no runtime test executed.

The rotation command is documented in `be/docs/guidance-followups-operations.md`; it changes only
ciphertext, not lifecycle, revisions, actors or source identity.

## 6. Read, list, report and workspace behavior

### 6.1 List

`services.list_followups` (`services.py:216-265`):

- Actor must be active, allowed role and have `guidance_followups.view` (`policy.current_actor`).
- SQL scope (`policy.scope`) is applied **before** offset/limit.
- Filters: `status`, `student_id`, `assigned_to_id`, `source_kind`+`source_id`, `due_window`
  (`OVERDUE`/`UPCOMING`), `ordering` (`EARLIEST_DUE`/`LATEST_DUE`), `page` 1–100, `page_size` 1–50.
- `source_kind`/`source_id` filtering calls `workspace.source_context` first, so an inaccessible or
  voided source rejects the whole query with a not-found response rather than returning an empty page
  (`services.py:244-248`; `workspace.py:50-69`).
- A fixed-size page plus one row proves `has_next`; no unbounded fetch (`services.py:258-265`).
- `FollowUpPage` returns summaries only. **The list schema has no source fields**; it cannot show a
  source-unavailable indicator (`api.py:134-157,227-250,474-492`).

### 6.2 Detail and history

`services.followup_detail` (`services.py:466-508`):

- Rechecks `require_followup` (assignment + scope + source for confidential).
- Decrypts description/outcome; decrypts event remarks for the latest 20 events.
- Calls `policy.visible_source`; returns `None` when source authorization fails.
- The API adds `source_unavailable = source_id is not None and source is None`
  (`api.py:253-263`).
- History route pages 20 events; same authorization (`api.py:717-734`).

A non-assignee creator receives a minimized receipt on the **create response only** (`api.py:266-281`),
with description/outcome/source/events removed. It is not a lasting read grant.

### 6.3 Report

`workspace.reporting` (`workspace.py:150-187`):

- Uses the same `policy.scope` as list (assignment-scoped).
- Defaults: last 30 days; completion period max 366 days; due-soon horizon 1–90 days.
- Aggregates pending/completed/cancelled/overdue/due_soon/completed_in_period and category counts.
- No free text, Student names or source payloads.
- `overdue` and `due_soon` are pending-only; `due_soon` is `now <= due_at <= now + horizon`.
- `followup_is_time_sensitive` uses the same 7-day default (`integration.py:16-22`).

### 6.4 Eligible Students and assignees

- `eligible_students` uses `compass.operational_students.list_scoped_operational_students`, with
  `college_ids=None` for Head Guidance, otherwise the SAR-backed operational responsibility colleges
  (`workspace.py:36-47`).
- `source_context` loads the source row, validates the Student, requires source access, and computes
  `can_create` from `guidance_followups.manage` plus **manage**-level source access
  (`workspace.py:50-91`).
- `eligible_assignees` derives classification first, requires source/operational scope, then filters
  active staff by capability, role and scope. Confidential candidates are limited to the actor
  (`workspace.py:94-147`).
- The final list is rechecked with `policy.require_assignee` before the page boundary
  (`workspace.py:126-147`).

### 6.5 Student and source projections

- `policy.valid_student` requires an existing, active account with role `STUDENT`
  (`policy.py:32-39`).
- Operational scope is Head Guidance (any active Student) or the actor's resolved responsibility
  colleges checked against the Student's canonical `student_academic_profile` placement
  (`policy.py:42-48`).
- `list_scoped_operational_students` is the SAR-era Student selector; it is not a second placement
  writer.

## 7. API surface

All operations use session authentication (`api.py:42`); all writes call
`require_recent_mfa_for_request` (`api.py:203-205`). Schemas are `extra="forbid"` (`api.py:46-47`);
unknown query parameters are rejected by `_strict_query` or an explicit field-set check
(`api.py:198-200,479-481`).

| # | Method and path | Operation ID | Purpose |
|---:|---|---|---|
| 1 | `GET /api/v1/guidance-followups` | `guidanceFollowupsList` | Assignment-scoped list |
| 2 | `POST /api/v1/guidance-followups` | `guidanceFollowupsCreate` | Create; requires `Idempotency-Key` |
| 3 | `GET /api/v1/guidance-followups/{id}` | `guidanceFollowupsGet` | Detail |
| 4 | `PATCH /api/v1/guidance-followups/{id}` | `guidanceFollowupsUpdate` | Due/category/description |
| 5 | `POST /api/v1/guidance-followups/{id}/reassign` | `guidanceFollowupsReassign` | Change assignee |
| 6 | `POST /api/v1/guidance-followups/{id}/activities` | `guidanceFollowupsRecordActivity` | Append encrypted activity |
| 7 | `POST /api/v1/guidance-followups/{id}/complete` | `guidanceFollowupsComplete` | Terminal completion |
| 8 | `POST /api/v1/guidance-followups/{id}/cancel` | `guidanceFollowupsCancel` | Terminal cancellation |
| 9 | `GET /api/v1/guidance-followups/{id}/history` | `guidanceFollowupsHistory` | Event history |
| 10 | `GET /api/v1/guidance-followups/context` | `guidanceFollowupsGetContext` | Source-derived create context |
| 11 | `GET /api/v1/guidance-followups/eligible-students` | `guidanceFollowupsEligibleStudents` | Scoped Student selector |
| 12 | `GET /api/v1/guidance-followups/eligible-assignees` | `guidanceFollowupsEligibleAssignees` | Scoped staff selector |
| 13 | `GET /api/v1/guidance-followups/recoverable` | `guidanceFollowupsRecoverable` | Operational orphan preview |
| 14 | `GET /api/v1/guidance-followups/report` | `guidanceFollowupsReport` | Aggregate workload |

**OpenAPI consistency:** all 14 operation IDs are present in `contracts/openapi.json`, and the Orval
client exports the corresponding 14 functions under
`fe/src/lib/api/generated/guidance-followups/guidance-followups.ts`. **Verified** statically; no
export/regeneration check was run.

**Error contract** (`api.py:207-224`):

| Condition | HTTP | Code |
|---|---:|---|
| Protected content/keyring unavailable | 503 | `followup_content_unavailable` |
| Capability/actor denied at entry | 403 | `followup_access_denied` |
| Object not found or not authorized by resource/source | 404 | `followup_not_found` |
| Stale version, already terminal, replay mismatch | 409 | `followup_conflict` |
| Invalid input/source pair/category/page | 422 | `invalid_followup` |
| Unexpected | 500 | `internal_error` |

The API deliberately uses 404 for inaccessible objects to avoid confirming existence
(`policy.py:248-251`).

## 8. Frontend surface

| Route | File | What it shows |
|---|---|---|
| `/portal/follow-ups` | `fe/src/app/(portal)/portal/follow-ups/page.tsx` | Pending-by-default list, workload counts, filters, links |
| `/portal/follow-ups/new` | `.../new/page.tsx` | Create form; optional source context from query parameters |
| `/portal/follow-ups/[followupId]` | `.../[followupId]/page.tsx` | Detail, actions, history, source panel, completion/cancellation |
| `/portal/follow-ups/report` | `.../report/page.tsx` | Aggregate report |
| `/portal/follow-ups/reassignment` | `.../reassignment/page.tsx` | Operational orphan recovery |

Feature files:

| File | Behavior |
|---|---|
| `followups-access.ts` | Role + capability UI gate |
| `followups-data.ts` | Realtime `followups.changed` invalidation; 60-second visible-tab poll; focus/reconnect refetch (`:13-18`) |
| `followups-list.tsx` | Pending default; Pending/Overdue/Due soon counts; filters; due/assignee/status table; no source indicator |
| `followups-create.tsx` | Source context, category locked to source, Student/assignee selectors, future due, idempotent retry; staff-only copy at `:81` |
| `followups-detail.tsx` | Actions only when `access.manage && status === "PENDING"` (`:86`); source panel at `:108`; consequence copy at `:177` |
| `followups-context.tsx` | Embedded linked-follow-ups panel on Referral/Encounter/Routine detail; returns `null` on context error, so a voided source removes the panel (`:20-21`) |
| `followups-reassignment.tsx` | Recovery preview and reassignment, operational only |
| `followups-report.tsx` | Aggregate counts and category table, 7-day default |
| `followups-shared.tsx` | Labels, source destinations, error copy |
| `followups-help.tsx` | Staff-only, 7-day due-soon, confidentiality, notification explanation |

The generated client is the only API path used by these components; no handwritten fetch layer was
found. **Verified** by imports in the feature files.

## 9. Notifications, My Work and audit

### 9.1 Notification events

- Three Follow-Up event codes: `FOLLOWUP_ASSIGNED`, `FOLLOWUP_REASSIGNED`, `FOLLOWUP_DUE_CHANGED`
  (`notifications/policy.py:42-44`).
- Target type `GUIDANCE_FOLLOW_UP` (`notifications/policy.py:27`).
- Event catalog: `MANDATORY_OPERATIONAL`, channels in-app + email (`notifications/policy.py:89-108`).
- External email/push is gated by `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED`, default **False**
  (`be/config/settings.py:719`); in-app remains.
- Only the **latest material event** per current authorized pending task is current
  (`integration.py:57-84`). Material events are `CREATED`, `REASSIGNED`, or `UPDATED` with a changed
  non-null due (`:47-54`). Activity, completion and cancellation do not generate Follow-Up
  notifications.
- Realtime hint `followups.changed` is sent to the current and old assignee; only the current assignee
  gets a notification (`integration.py:96-123`).
- A former assignee can receive the cache eviction hint but not a notification.

### 9.2 My Work

- `pending_followups` uses `policy.scope(manage=True)` and returns pending tasks only
  (`integration.py:25-44`).
- Work Queue priority is `TIME_SENSITIVE` when overdue or within 7 days, otherwise `ACTION_REQUIRED`
  (`be/compass/work_queue/services.py:42-50`; card creation at `:82`).
- The card uses due date and Student display data, not protected free text.

### 9.3 Audit

Six actions (`audit/actions.py:255-260`), each with target type
`guidancefollowups.guidancefollowup` and metadata `{version, ...}` (`services.py:115-123`). Metadata
does not include description, outcome or remarks. **Verified** for the inspected calls; no runtime
audit emission was executed.

## 10. Recovery

`recovery.recoverable_queryset` (`recovery.py:49-119`):

- Actor must be active, allowed role and have `guidance_followups.manage`.
- Rows: `visibility="OPERATIONAL"`, `status="PENDING"`, active Student role.
- Non-Head actors are restricted to their SAR college scope and active College/campus.
- The **current owner's** eligibility is computed in SQL, including role, designation, responsibility
  and capability overrides; rows with an eligible owner are excluded.
- Confidential rows are excluded unconditionally.
- Head Guidance sees all operational orphans; no confidential rows are ever included.
- `list_recoverable` returns metadata-only summaries, 1–100 page, 1–50 size (`recovery.py:122-135`).
- Reassignment through `reassign_followup(allow_recovery=True)` uses the same recoverable predicate
  (`services.py:268-283,339-369`).

## 11. Operational documentation and flags

`be/docs/guidance-followups-operations.md` documents:

- Staff-only workspace, authority matrix, source types.
- Durable lifecycle and idempotency.
- Notification matrix and external-delivery flag.
- Encryption keyring and rotation.
- Rollout and operational checks.

`be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md` records the original secure-domain
decision. Both are documentation, not institutional approval. `be/config/settings.py` registers the
app (`:85`) and defaults external Follow-Up notifications off (`:719`). No deployment or staging state
was inspected.

## 12. What is not true at HEAD

The following common assumptions are **false** or unsupported by the code:

| Assumption | Actual state | Claim |
|---|---|---|
| Follow-Up scoping still uses `StudentAffiliation`. | Uses canonical `student_academics`; retired model only in historical migrations. | **Verified false** |
| A voided Referral hides or cancels its operational task. | Task remains visible/mutable; only source link is unavailable. | **Verified false** |
| A Head Guidance Counselor can always see confidential Follow-Ups. | No Follow-Up capabilities from designation; confidential source access still required. | **Verified false** |
| A source read grant can transfer a confidential task. | No grant reader; manage source access is required, and a confidential task can only be owned by its source Counselor. | **Verified false** |
| Completing a task closes or updates the Referral. | No cross-domain write; completion is Follow-Up-only. | **Verified false** |
| Follow-Up has automatic recurrence or a next-task chain. | No scheduler, predecessor field or auto-creation. | **Verified false** |
| Activity/completion sends email. | Only assignment/reassignment/due change are notification events; external delivery is off by default. | **Verified false** |
| The proposal's cited cross-domain test covers Follow-Up. | That file has no Follow-Up reference. | **Verified false** |
| SAR-0 describes current placement. | SAR-0 describes the pre-SAR baseline; HEAD uses `student_academics`. | **Verified stale** |
