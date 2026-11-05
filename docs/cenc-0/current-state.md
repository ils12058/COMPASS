# CENC-0 — Current state at the audit base

**Status:** read-only static audit. **Audit base:** `integration/ux15-modernization`
`04d2581baae3350eb25cc301ea36755775c1b98a`, 2026-11-05. Every claim is labeled
**Verified**, **Inferred** or **Unknown**. No runtime behavior was executed.

This file describes what exists at HEAD. Proposal #9's intended behavior is not described here as if
it exists; proposal assumptions are separated in [`README.md`](README.md) and evaluated in
[`action-matrix.md`](action-matrix.md).

---

## 1. Layer map

| Layer | Appointment | Counseling Encounter |
|---|---|---|
| Model owner | `be/compass/appointments/` | `be/compass/counseling/` |
| Canonical record | `Appointment` — reservation + administrative outcome | `CounselingEncounter` — actual completed interaction facts |
| Status | 4-state terminal consistency constraint | No status field; completeness is derived from creation + actual times |
| Mutation entry | `appointments/services.py` | `counseling/services.py` |
| Public API | `be/compass/appointments/api.py` | `be/compass/counseling/api.py` |
| Frontend feature | `fe/src/features/appointments/` | `fe/src/features/counseling/`, `fe/src/features/ecounseling/` |
| Audit action family | `appointment.*` | `counseling.encounter.*` |
| Downstream side effects | cancellation notification (student + provider); no completion notification | Feedback opportunity + `FEEDBACK_INVITATION` notification |
| Relationship | One Appointment may have zero or one Encounter | One Encounter may link to zero or one Appointment |

**Verified** by module layout and imports listed below. The two domains do not call each other's
mutation services in either direction: `appointments/services.py` has no `CounselingEncounter`
import except in the advisory projection at `:1820,1857` and no-show guard at `:1661-1666`; the
Counseling creation service imports `Appointment` only to read and validate the link
(`counseling/services.py:400-500`).

---

## 2. Appointment domain

### 2.1 Model and statuses

| Item | Value / field | Evidence |
|---|---|---|
| Statuses | `SCHEDULED`, `CANCELLED`, `COMPLETED`, `NO_SHOW` | `be/compass/appointments/models.py:13-17` |
| Identity | UUID `id`, unique `reference_code` | `appointments/models.py:40-41` |
| Participants | `student`, `provider` (Counselor), canonical `service` | `appointments/models.py:42-57` |
| Service snapshot | `service_name_snapshot` | `appointments/models.py:52` |
| Schedule facts | `delivery_mode`, `starts_at`, `ends_at` | `appointments/models.py:58-60` |
| Lifecycle status | `status` (default `SCHEDULED`) | `appointments/models.py:61-65` |
| Cancellation provenance | `cancelled_at`, `cancelled_by` | `appointments/models.py:76-83` |
| Completion provenance | `completed_at`, `completed_by` | `appointments/models.py:84-91` |
| No-show provenance | `no_show_at`, `no_show_by` | `appointments/models.py:92-99` |
| Creation provenance | `created_by`, `created_at`, `updated_at` | `appointments/models.py:69-75,100-101` |
| Default permissions | disabled | `appointments/models.py:108-109` |

**Verified** constraints (`appointments/models.py:122-163`):

- `appointments_time_order`: `starts_at < ends_at`.
- `appointments_cancellation_cutoff_nonnegative`.
- `appointments_status_terminal_consistent`: exactly one status and its matching provenance field
  must be present; the other provenance fields must be null.

The terminal-consistency constraint is the database guarantee that a `COMPLETED` Appointment has
`completed_at` and no cancellation/no-show timestamp, and vice versa. It does **not** require a
Counseling Encounter.

### 2.2 Lifecycle services

| Service | Preconditions | Writes | Side effects | Evidence |
|---|---|---|---|---|
| `create_student_appointment` | active current Student, canonical/eligible Service, availability | `Appointment` (`SCHEDULED`) | audit, confirmation notification | `appointments/services.py:885-1011` |
| `cancel_appointment(administrative=…)` | actor management access (administrative) or owning Student; status `SCHEDULED`; not after start; E-Counseling access not started; no E-Counseling room; student cutoff | `CANCELLED`, `cancelled_at/by` | audit; `APPOINTMENT_CANCELLED` to Student and provider | `appointments/services.py:1042-1124` |
| `reschedule_appointment` | management or Student; `SCHEDULED` before start; relationships clear; availability | `starts_at/ends_at`, change event | audit, notification | `appointments/services.py:1200-1375` (guard at `:807-813`) |
| `reassign_appointment` | management access; `SCHEDULED` before start; no Routine Interview, Encounter or E-Counseling room; new provider eligible; availability | `provider`, change event | audit, notification | `appointments/services.py:1377-1393,1396-1500` |
| `complete_appointment` | management access; idempotent when already `COMPLETED`; otherwise `SCHEDULED`; at/after `starts_at`; E-Counseling access not `OPEN` | `COMPLETED`, `completed_at/by` | **audit only** | `appointments/services.py:1566-1618` |
| `mark_appointment_no_show` | management access; idempotent when already `NO_SHOW`; otherwise `SCHEDULED`; at/after `ends_at`; E-Counseling access not `OPEN`; **no linked Encounter** | `NO_SHOW`, `no_show_at/by` | audit only | `appointments/services.py:1621-1687` |

**Verified**: `complete_appointment` contains no Encounter check, no Encounter creation and no
notification call (`appointments/services.py:1566-1618`). The only audit action is
`APPOINTMENT_COMPLETED` (`:1607-1617`). `mark_appointment_no_show` is the only Appointment mutation
that consults `CounselingEncounter` (`:1661-1666`).

**Verified**: cancellation does not check `CounselingEncounter`
(`appointments/services.py:1042-1124`). It blocks on E-Counseling access/room and on start time, but
a linked Encounter is otherwise irrelevant. This makes a cancelled Appointment with a linked
Encounter reachable when the Encounter was recorded before the Appointment started (see
[`action-matrix.md`](action-matrix.md)).

### 2.3 Appointment access policy

`appointment_access_policy_for_service` returns `RELATIONSHIP_ONLY` for the canonical Counseling
Service and `ORGANIZATIONAL` otherwise
(`be/compass/appointments/access.py:24-27`). Management access requires an active actor with
`appointments.manage`, then:

1. the provider relationship for that Appointment (`:30-36,57-58`); or
2. for organizational Services only, operational College responsibility (`:66-72`).

Head Guidance is explicitly refused for another provider's Appointment (`:60-64`). For Counseling,
the relationship-only branch refuses everyone except the provider (`:66-70`).

**Verified consequences** (`be/tests/test_appointment_management_scope.py`):

- `test_counseling_appointment_is_relationship_only_across_list_get_filters_and_cancel` (`:365-440`):
  provider list/detail/cancel work; other Counselor, Head and GSS get 404 or empty lists.
- `test_head_sees_counseling_appointment_only_when_head_is_selected_provider` (`:444-476`).

**Verified**: GSS receives `appointments.manage` (`accounts/policy.py:711-712`) but no
`counseling.*` capability (`:698-723`); regardless, the relationship-only policy prevents GSS from
managing a Counseling Appointment. The proposal's administrative-completion premise for Counseling
therefore does not hold at HEAD.

### 2.4 Detail projection

`GET /api/v1/appointments/{id}` returns the Appointment plus:

- `counseling_context_available` — computed by `counseling_context_available(...)` at request time;
- `actions` — the advisory action projection.

**Verified** at `be/compass/appointments/api.py:909-940`. The projection
(`appointment_actions_for`, `appointments/services.py:1808-1923`) uses server time and linked
records, and is explicitly advisory: mutations revalidate under locks (`:1814-1818`).

Projection blockers relevant to CENC:

- `complete` = `NOT_SCHEDULED`, `NOT_STARTED` before `starts_at`, or `ECOUNSELING_ACCESS_OPEN`
  (`appointments/services.py:1911-1915`). There is **no** `COUNSELING_ENCOUNTER_LINKED` blocker.
- `mark_no_show` = `NOT_SCHEDULED`, `NOT_ENDED`, `ECOUNSELING_ACCESS_OPEN` or
  `COUNSELING_ENCOUNTER_LINKED` (`:1916-1922`).
- `cancel` = `NOT_SCHEDULED`, E-Counseling access started, room linked, already started, Student
  cutoff (`:1886-1893`).
- `reassign` includes Routine, Encounter and room blockers (`:1908-1910`).

---

## 3. Counseling domain

### 3.1 Model and statuses

| Item | Value / field | Evidence |
|---|---|---|
| Entry modes | `APPOINTMENT`, `WALK_IN`, `CALLED_IN`, `REFERRED` | `be/compass/counseling/models.py:14-18` |
| Identity | UUID `id` | `counseling/models.py:22` |
| Participants | `student`, `counselor`, canonical `service` | `counseling/models.py:23-37` |
| Service snapshot | `service_name_snapshot` | `counseling/models.py:38` |
| Appointment link | optional one-to-one `appointment` | `counseling/models.py:39-45` |
| Source facts | `entry_mode`, `delivery_mode` | `counseling/models.py:46-47` |
| Actual times | `started_at`, `ended_at` | `counseling/models.py:48-49` |
| Authorship | `created_by`, `created_at`, `updated_at` | `counseling/models.py:50-58` |
| Default permissions | disabled | `counseling/models.py:65-66` |

**Verified** constraints (`counseling/models.py:78-90`):

- `counseling_time_order`: `started_at < ended_at`.
- `counseling_appointment_mode_requires_link`: `entry_mode != APPOINTMENT OR appointment is not null`.

The second constraint is one-directional. It does not require `entry_mode=APPOINTMENT` when
`appointment_id` is present. **Verified** by the constraint expression and by
`be/tests/test_counseling.py:831-862` (constraint tests) and `:794-827` (a `REFERRED` Encounter
retains its Appointment link and entry mode after correction).

`StudentSessionSummary` is a separate one-to-one Counselor-authored, encrypted, optionally published
record (`counseling/models.py:93-115`). It is not created by Encounter creation and is outside CENC-1.

### 3.2 Actual-time rules

`_normalize_actual_times` (`counseling/services.py:172-188`):

- both values must be datetimes;
- both must be timezone-aware;
- both are converted to the institution timezone;
- `started_at < ended_at`;
- `ended_at` must not be in the future.

**Verified** by code and by `be/tests/test_counseling.py:557-600,650-681`. There is **no** check that
the actual interval overlaps or fits the Appointment's scheduled interval, and no maximum age.

### 3.3 Encounter creation

`create_encounter` (`counseling/services.py:452-605`) has two branches.

**Appointment branch** (`appointment_id` present):

1. Normalize entry mode and actual times (`:476-477`).
2. Open an atomic block and call `lock_routine_for_encounter_recording` before locking the
   Appointment (`:481-486`), preserving Routine → Appointment order.
3. Lock the Appointment (`:487`, plain `select_for_update()`), lock Counselor and Student in sorted
   order (`:490-492,225-236`), validate both are active (`:493-494`).
4. Load the canonical Counseling Service `FOR UPDATE` (`:495`).
5. Derive delivery mode from the Appointment and validate canonical Service, Service identity,
   Student identity and delivery consistency (`:496-514`).
6. `_validate_appointment_link` (`:285-319`): Appointment must be `SCHEDULED` or `COMPLETED`,
   provider must equal the caller, Student/Service/delivery must match, and no other Encounter may
   already be linked.
7. If Routine context was supplied, validate the Routine match (`:522-532`).
8. `_create_row` (`:322-382`) creates the Encounter with `created_by=counselor`, records
   `COUNSELING_ENCOUNTER_CREATED`, calls `ensure_feedback_opportunity(...)`, and creates the
   `FEEDBACK_INVITATION` notification.
9. Link the Routine Interview if applicable (`:544-549`).

The branch does **not** require `entry_mode=APPOINTMENT`. A caller may supply `WALK_IN`, `CALLED_IN`
or `REFERRED` together with an `appointment_id` and the link is accepted as long as the identity
checks pass (`:505-532`; no entry-mode check in `_validate_appointment_link`).

**Direct branch** (no `appointment_id`):

- rejects `entry_mode=APPOINTMENT` (`:552-553`);
- requires `student_id` and `delivery_mode` (`:554-557`);
- locks Routine context (if any), users sorted, Service `FOR UPDATE` (`:560-571`);
- validates the canonical Service, Counselor eligibility and delivery mode
  (`:572-576,254-265`);
- creates the row; no Appointment is involved (`:588-604`).

**Authorization boundary**: the HTTP route requires an active `COUNSELOR` with
`counseling.manage_assigned` (`counseling/api.py:573-605,239-244`), plus
`routine_interviews.manage_assigned` when a Routine context is supplied (`:588-590`). There is no
relationship check for a direct Encounter: the Student may be any active `STUDENT` returned by the
unscoped lookup (`counseling/services.py:796-812`; `counseling/api.py:443-473`).

### 3.4 Encounter candidates and reads

- `list_appointment_candidates` (`counseling/services.py:640-690`) returns the caller's own
  canonical Counseling Appointments in `SCHEDULED` or `COMPLETED` with no Encounter yet (`:664-672`).
  It deliberately does not re-check current Service delivery/provider coverage (`:651-653`).
- `list_encounter_appointment_candidates` (`:693-739`) returns the caller's Appointments for the same
  Student/Service with no other Encounter linked.
- `list_my_encounters` filters `counselor_id=actor.pk` (`:742-784`).
- `get_encounter_for_actor` requires the caller to be the Encounter's Counselor and an active
  `COUNSELOR` (`:787-793`).
- `list_students` filters only `is_active=True` and role `STUDENT`; it has no College, lifecycle or
  relationship scope (`:796-812`). **Verified** by
  `be/tests/test_counseling.py:1196-1265` (returns a graduated Student outside the Counselor's
  College responsibility).

### 3.5 Encounter correction

`update_encounter` (`counseling/services.py:857-1046`):

- accepts only `entry_mode`, `appointment_id`, `delivery_mode`, `started_at`, `ended_at`
  (`:865-870`);
- locks the linked Routine and the Appointment's Routine first (`:872-873,815-854`), then the
  Encounter, then the actor, then both old/new Appointments sorted, then the Service
  (`:874-925`);
- validates the proposed Appointment link with `require_unused_by=item.pk` (`:944-951`);
- recomputes actual times and rejects future/invalid values (`:890-896`);
- validates the linked Routine match; a mismatch is a conflict, and if the Routine is finalized the
  conflict is a finalized-Routine conflict (`:966-1004`);
- reconciles the Feedback opportunity's completion timestamp, refusing chronology violations
  (`:1006-1015`);
- writes only changed fields, records `COUNSELING_ENCOUNTER_UPDATED`, and may attach the Encounter
  to an Appointment's Routine afterwards (`:1017-1045`).

**Verified**: changing `entry_mode` does not clear an existing `appointment_id`, and attaching an
Appointment does not force `entry_mode=APPOINTMENT`
(`be/tests/test_counseling.py:794-827`; form behavior in
`fe/src/features/counseling/encounter-correction-form.tsx:55-56,141-160`).

### 3.6 Counseling Context

`resolve_counseling_context` accepts an Appointment or Routine Interview anchor. For an Appointment
anchor (`context_access.py:85-144`):

- actor must be an active `COUNSELOR` with `counseling.view_assigned` (`:50-57`);
- Appointment must be canonical Counseling, belong to the actor as provider, and be `SCHEDULED` or
  `COMPLETED` (`:91-106`);
- the access window starts before the scheduled start and ends after the scheduled end, extended
  when a **matching** Encounter exists (`:108-124`);
- the matching Encounter requires `entry_mode=APPOINTMENT`, matching Student/Counselor/Service/
  delivery, completed `ended_at`, and an actual start no later than the base window
  (`context_access.py:60-82`).

`counseling_context_available` is a boolean projection of that resolver
(`context_access.py:284-306`), used by Appointment Detail.

**Verified consequence**: a linked Encounter with `entry_mode != APPOINTMENT` is invisible to the
Appointment's Counseling Context even though it is linked to the Appointment.

---

## 4. Routine Interview linkage

- Matching is deterministic: Student, Counselor, canonical Service, delivery mode, completed, then
  either `entry_mode=APPOINTMENT` + exact Appointment identity, or direct entry mode
  (`routine_interviews/matching.py:39-68`). No Student/date-similarity matching exists.
- `ensure_for_appointment` is Student-initiated, requires a `SCHEDULED` Appointment and current
  Student status, and creates/locates the one Routine Interview (`routine_interviews/services.py:464-555`).
  It can link an already-recorded Encounter using `skip_locked` (`:543-554`).
- `_link_encounter` refuses to replace a different link, checks one-to-one ownership, and uses the
  DB constraint as the final race safeguard (`:1200-1252`).
- `lock_routine_for_encounter_recording` documents and implements Routine-before-Appointment order
  (`:1255-1288`).
- `finalize_assigned_evaluation` requires a submitted Student Intake and a linked completed
  Encounter; it locks the Routine and Encounters and preserves finalized content
  (`:1365-1456`).

**Verified**: `link_appointment_encounter` silently declines to link when the Encounter does not
match the Routine (`:1324-1357`); it does not raise. Encounter creation therefore succeeds even when
no deterministic Routine link is possible. `create_encounter`'s explicit Routine-context branch is
stricter: `_validate_routine_context` fails the recording if the facts do not match
(`counseling/services.py:406-432`).

---

## 5. E-Counseling constraints

- Appointment eligibility for joining is `SCHEDULED` only (`ecounseling/services.py:127-154`).
- Workspace loading accepts a saved room for a `COMPLETED` Appointment (`:157-163`).
- Participant relationship checks are Student-self or assigned Counselor (`:166-191`).
- The access window is derived from scheduled start/end and settings:
  `TOO_EARLY`, `OPEN`, `CLOSED` (`:88-93,194-239`).
- Provider readiness and the access window are separate; provider state does not change the window
  (`:269-287`).

Appointment mutations consume the window:

- completion is blocked while `OPEN` (`appointments/services.py:1595-1602`);
- no-show is blocked while `OPEN` (`:1652-1659`);
- cancellation is blocked once the window is not `TOO_EARLY`, and when a room is linked
  (`:1071-1083`);
- reassignment is blocked when a room is linked (`:1377-1393`).

**Verified**: Encounter creation itself does not consult E-Counseling
(`counseling/services.py:452-605`). A composed Finish operation must call the Appointment mutation to
inherit these checks; it must not reimplement or bypass them.

---

## 6. Feedback and notifications

- Feedback source type `COUNSELING_ENCOUNTER` (`feedback/models.py:28-30`) with a unique
  `(source_type, source_id)` constraint (`:59-64`).
- `ensure_feedback_opportunity` uses `get_or_create`, recovers from an IntegrityError by fetching the
  existing row, and validates provenance (`feedback/services.py:217-285`).
- `reconcile_counseling_feedback_opportunity` locks the opportunity, validates provenance and
  chronology, and updates only `service_completed_at` (`:288-339`).
- Encounter creation invokes `ensure_feedback_opportunity` and
  `create_notification_for_event(FEEDBACK_INVITATION)` inside `_create_row`
  (`counseling/services.py:322-382,378-381`).
- `create_notification_for_event` uses `get_or_create` for the in-app notification and schedules
  push/email delivery on commit; transport setup failures do not undo the notification
  (`notifications/services.py:92-150`).
- `FEEDBACK_INVITATION` is optional informational email (`notifications/policy.py:328-339`).
- There is **no** `APPOINTMENT_COMPLETED` notification event; events cover scheduled, cancelled,
  rescheduled, reassigned and reminders (`notifications/policy.py:46-52`).

**Verified** by code and by `be/tests/test_counseling.py:284-324`: a synthetic notification
persistence failure rolls back the Encounter, its audit event, the notification and the Feedback
opportunity.

---

## 7. Audit events

| Action | Constant / string | Evidence |
|---|---|---|
| Appointment cancelled | `appointment.cancelled` | `be/compass/audit/actions.py:80` |
| Appointment completed | `appointment.completed` | `audit/actions.py:83` |
| Appointment no-show | `appointment.no_show` | `audit/actions.py:84` |
| Encounter created | `counseling.encounter.created` | `audit/actions.py:87` |
| Encounter updated | `counseling.encounter.updated` | `audit/actions.py:88` |
| Routine Encounter linked | `routine_interview.encounter_linked` | `audit/actions.py:119` |

Completion metadata records the reference code and transition (`SCHEDULED -> COMPLETED`) only
(`appointments/services.py:1613-1616`). Encounter creation metadata records entry mode, delivery mode
and Appointment id (`counseling/services.py:354-358`). No clinical narrative, Evaluation content or
diagnosis is written to these events.

There is no audit action that identifies a composed Finish operation as such. Whether one is
required is D-CENC-20.

---

## 8. API inventory

### 8.1 Counseling module (13 operations)

| Operation | Path | Authorization | Relevance |
|---|---|---|---|
| `counselingCreateEncounter` | `POST /api/v1/counseling/encounters` | active Counselor + `counseling.manage_assigned`; + Routine capability when anchoring | The only Encounter write path |
| `counselingGetEncounter` | `GET /api/v1/counseling/encounters/{id}` | owning Counselor | Read |
| `counselingUpdateEncounter` | `PATCH /api/v1/counseling/encounters/{id}` | owning Counselor | Correction |
| `counselingListMyEncounters` | `GET /api/v1/counseling/me/encounters` | owning Counselor | Read |
| `counselingListAppointmentCandidates` | `GET /api/v1/counseling/appointment-candidates` | active Counselor | Appointment-origin picker |
| `counselingListEncounterAppointmentCandidates` | `GET /api/v1/counseling/encounters/{id}/appointment-candidates` | owning Counselor | Correction picker |
| `counselingListStudents` | `GET /api/v1/counseling/students` | active Counselor | Unscoped direct picker |
| `counselingGetEncounterCreationOptions` | `GET /api/v1/counseling/encounter-options` | active Counselor | Direct-origin options |
| Context overview/sections | `/api/v1/counseling/context/...` | active Counselor + `counseling.view_assigned` | Time-bounded context |
| Student Session Summary operations | `/api/v1/counseling/...summaries...` | Student or owning Counselor | Separate feature |

**Verified** operation ids and paths in `be/compass/counseling/api.py:391-746`. There is no
`POST .../appointments/{id}/finish`.

### 8.2 Appointment module (19 operations)

Lifecycle-relevant operations:

| Operation | Path | Authorization | Evidence |
|---|---|---|---|
| `appointmentsGet` | `GET /api/v1/appointments/{id}` | self/provider or management | `appointments/api.py:909-940` |
| `appointmentsCancel` | `POST /api/v1/appointments/{id}/cancel` | Student self or management | `appointments/api.py` cancel route |
| `appointmentsReschedule` | `POST /api/v1/appointments/{id}/reschedule` | Student self or management | `appointments/api.py` reschedule route |
| `appointmentsReassign` | `POST /api/v1/appointments/{id}/reassign` | management | `appointments/api.py` reassign route |
| `appointmentsComplete` | `POST /api/v1/appointments/{id}/complete` | `appointments.manage` + record access | `appointments/api.py:1105-1121` |
| `appointmentsMarkNoShow` | `POST /api/v1/appointments/{id}/no-show` | `appointments.manage` + record access | `appointments/api.py:1124-1140` |

The remaining operations cover booking, slots, lists, history, candidates and reminders.

---

## 9. Frontend inventory

| Surface | Current behavior | Evidence |
|---|---|---|
| Appointment Detail | Shows Appointment status, schedule and actions. `Complete appointment` opens a generic confirmation: "This appointment will be marked completed and will no longer be scheduled." No Encounter state is displayed. `Open Counseling` appears only when `counseling_context_available`. | `fe/src/features/appointments/appointment-detail-page.tsx:161-182,211-235,592-627,690-747` |
| Counseling page | Heading "Counseling"; page action "Record"; section "My counseling encounters"; list shows Appointment reference. | `fe/src/features/counseling/counselor-encounters.tsx:95-113,140` |
| Record Encounter form | Appointment origin presets identity and **reference-only** scheduled times; actual times start blank; submit sends only actual times; helper says "Recording this encounter does not complete the Appointment." | `fe/src/features/counseling/record-encounter-form.tsx:47-61,87-109,333-358` |
| Record Encounter dialog | Title "Record counseling encounter"; uncertain save stays open with "Check again"/"View encounters", never blind retry. | `record-encounter-form.tsx:333-371` |
| Encounter correction | Only changed facts are sent; identity is immutable; choosing an Appointment sets entry mode `APPOINTMENT`, clearing it sets `WALK_IN`; the backend does not enforce the inverse. | `encounter-correction-form.tsx:42-61,138-160` |
| Counseling Workspace (Appointment/Routine anchor) | Shows whether a matching Encounter exists, offers `Record encounter` when authorized; after context expiry shows an unavailable notice; only a non-expired context offers `View encounter`. | `counseling-workspace.tsx:264-371` |
| E-Counseling Workspace | Separate "Counseling Encounter" section with `Record encounter`; uncertain result offers "Check again"; no attendance inference from media. | `ecounseling-workspace.tsx:375-434` |
| Help copy | "Recording it does not complete an Appointment and does not start audio/video recording." | `counseling-help.tsx:7` |
| Counseling access helper | Counselor workspaces require role `COUNSELOR` plus Counseling capability. | `counseling-access.ts:17-32` |

**Verified**: there is no Finish action, no combined confirmation, no Encounter status on Appointment
Detail, no Needs-documentation segment and no reconciliation action. Searching `fe/src` for
`finish`/`already_finished`/`requires_documentation` returns no matches.

---

## 10. Transaction and lock map

| Operation | Lock acquisition order | Notes |
|---|---|---|
| `create_encounter` (Appointment) | Routine (if any) → Appointment → Users sorted by pk → Service → insert Encounter → Feedback `get_or_create` → notification `get_or_create` | `counseling/services.py:480-549,225-236`; Routine-first documented at `routine_interviews/services.py:1255-1288` |
| `create_encounter` (direct) | Routine context → Users sorted → Service → insert → Feedback → notification | `counseling/services.py:560-604` |
| `update_encounter` | linked Routine + anchored Routine → Encounter → actor User → Appointments sorted → Service → Feedback opportunity | `counseling/services.py:872-1015` |
| `cancel_appointment` | Appointment → notification recipients (no user locks) | `appointments/services.py:1051-1123` |
| `reassign_appointment` | Appointment → Users sorted → Service → availability/overlap | `appointments/services.py:1396-1500,610-615` |
| `complete_appointment` | Appointment | `appointments/services.py:1576-1618` |
| `mark_appointment_no_show` | Appointment → Encounter existence query (unlocked) | `appointments/services.py:1631-1666` |
| `ensure_for_appointment` | Appointment → create Routine → Encounter `skip_locked` → link/audit | `routine_interviews/services.py:471-555` |
| `finalize_assigned_evaluation` | Routine → Encounters → write/audit | `routine_interviews/services.py:1365-1456` |

**Verified**: the existing creation path already documents Routine-before-Appointment ordering.
A composed Finish operation must acquire the Routine lock first, then delegate to paths that lock the
same Appointment and users; any new operation that locks the Appointment before the Routine would
risk a deadlock with Encounter creation/finalization.

---

## 11. Caller and process inventory

| Service | Production callers | Staging seed | Background job / command |
|---|---|---|---|
| `complete_appointment` | `appointments/api.py:1114` via `POST /appointments/{id}/complete` | `staging_seed/workflows.py:107` | none |
| `create_encounter` | `counseling/api.py:592` via `POST /counseling/encounters` | `staging_seed/workflows.py:135` | none |
| `ensure_for_appointment` | `routine_interviews/api.py:637` via Student route | `staging_seed/workflows.py:235` | none |

**Verified** by repository search for the service symbols. Management commands under
`be/compass/*/management/commands/` cover account creation, OpenAPI export, policy sync, catalog
sync, encryption/key rotation, seed data and operational checks; none completes Appointments or
creates Encounters. No task queue worker in this repository invokes these services.

**Inferred**: the only current ways to reach the two writes are the HTTP APIs, the staging-seed
workflow, or direct ORM/admin access outside this repository. CENC-0 found no hidden automated
Encounter producer, scheduled-time inference, E-Counseling disconnect handler or reminder path that
creates an Encounter.

---

## 12. Static counts and coverage summary

| Metric | Value |
|---|---:|
| Appointment lifecycle services inspected | 6 (`create`, `cancel`, `reschedule`, `reassign`, `complete`, `no-show`) |
| Counseling public services inspected | 10 (create, update, get, list mine, candidates ×2, options, students, context, summaries) |
| Routine linking services inspected | 6 (`ensure`, `link`, `lock`, `validate`, finalize, reconciliation helpers) |
| Primary backend CENC test functions | 116 static across 10 files |
| Composed Finish tests | 0 |
| Needs-documentation tests | 0 |
| Concurrency tests for Finish | 0 |
| Frontend tests covering actual-time integrity | `fe/tests/counseling-encounter-consistency.test.mjs`, `.browser.mjs` |
| Frontend tests covering context confidentiality | `fe/tests/counseling-context-confidentiality.test.mjs`, `.browser.mjs` |
| Frontend tests covering Routine linking | `fe/tests/routine-encounter-linking.test.mjs` |

All test counts are static function counts, not execution results. No test was run.

## 13. Verified gaps relative to CENC

1. No composed transaction or endpoint (`Verified`, absence searches).
2. No state-based reconciliation for `SCHEDULED`+Encounter or `COMPLETED`+no Encounter
   (`Verified`).
3. No idempotency key or replay contract for Encounter creation (`Verified`,
   `be/tests/test_counseling.py:866-917` and absence in `counseling/api.py:77-94`).
4. No derived Needs-documentation projection or scoped worklist (`Verified`, absence searches).
5. No Appointment-detail Encounter state or Finish/Reconcile action (`Verified`, frontend inventory).
6. No cross-domain concurrency tests for a Finish operation (`Verified`, test inventory).
7. No authorization path for GSS to complete a Counseling Appointment; the proposal's
   administrative-completion premise is false at HEAD (`Verified`).
8. No enforcement that an Appointment-linked Encounter uses `entry_mode=APPOINTMENT` (`Verified`,
   model constraint + service code + test).
9. No check that actual times relate to the Appointment's scheduled window (`Verified`,
   `_normalize_actual_times` and `_validate_appointment_link`).
10. No notification for Appointment completion, so a composed operation must not invent one without
    GCO approval (`Verified`, notification policy).
