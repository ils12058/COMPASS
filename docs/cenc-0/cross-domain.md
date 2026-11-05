# CENC-0 — Cross-domain boundaries

**Status:** read-only static audit at `04d2581b` (2026-11-05). Claims are **Verified**,
**Inferred** or **Unknown**. The proposal's core architectural rule is "integrate domain actions,
**not** domain ownership" (proposal line 6677). This file maps the ownership that a composed Finish
operation must respect.

---

## 1. Ownership table

| Domain | Owns | A Finish operation may | A Finish operation must not |
|---|---|---|---|
| Appointments | Appointment row, status, terminal provenance, change events, cancellation/no-show | Request the existing completion transition through its service; read schedule and status | Write `status`/`completed_at`/`completed_by` directly; infer attendance; bypass E-Counseling or no-show guards |
| Counseling | `CounselingEncounter`, actual session facts, Encounter audit, Student Session Summary | Create the single Encounter through the existing creation service; read existing facts; route corrections to the correction service | Create a second Encounter; overwrite actual times on replay; accept a client-supplied Counselor identity; mark a session attended without attestation |
| Routine Interviews | Routine Interview, Intake, Counselor Evaluation, deterministic linkage, finalization | Use the existing deterministic linker and lock order; report link state | Match by Student/date similarity; finalize Evaluation; create Intake; replace a link; mutate finalized content |
| Feedback | Feedback opportunity identity and invitation policy | Let Encounter creation invoke the existing `ensure_feedback_opportunity` exactly once | Create a second producer or a Finish-specific feedback source; reissue invitations on replay |
| Notifications | Events, policies, in-app records, durable delivery | Preserve existing Encounter-invitation intent and delivery semantics | Invent an Appointment-completed notification without approval; include clinical content |
| E-Counseling | Access window, rooms, media/capture lifecycle | Read eligibility through the Appointment mutation; surface a safe blocker | Treat a room/join/media event as attendance; bypass an `OPEN` window |
| Audit | Append-only events and metadata policy | Record existing domain events; optionally add minimal correlation if approved | Log clinical content, reasons, transcripts, Evaluation answers or summary text |
| Guidance Follow-Ups (FUP) | Tasks and their source lifecycle | Nothing on the normal Finish path | Auto-create, complete, reassign or close a Follow-Up |
| Faculty/Referrals (FAC) | Referral origin and administrative status | Nothing | Report Counseling to Faculty; auto-close a Referral; infer Counseling from a Referral |
| Case Continuity (CONT) | Read-only grants, handoff summaries | Nothing on the normal Finish path | Convert a read grant into Encounter-authoring authority; rewrite original Counselor ownership |

**Verified** by service ownership and imports described below.

---

## 2. Appointment ↔ Counseling

### 2.1 Current coupling points

| Coupling | Direction | Behavior | Evidence |
|---|---|---|---|
| Appointment link validation | Counseling reads Appointment | Accepts `SCHEDULED`/`COMPLETED`; verifies provider, Student, Service, delivery; refuses if another Encounter is linked | `counseling/services.py:285-319` |
| Encounter candidate list | Counseling reads Appointment | Provider's own `SCHEDULED`/`COMPLETED` Appointments with no Encounter | `counseling/services.py:640-690` |
| Reassignment guard | Appointment reads Counseling | Refuses reassignment when an Encounter exists | `appointments/services.py:1377-1393` |
| No-show guard | Appointment reads Counseling | Refuses no-show when an Encounter exists | `appointments/services.py:1661-1666` |
| Action projection | Appointment reads Counseling | Computes `encounter_linked` for manager actions | `appointments/services.py:1851-1858` |
| Counseling Context matching | Counseling reads Appointment | Requires `entry_mode=APPOINTMENT` plus identity/time match | `counseling/context_access.py:60-82` |
| Appointment detail availability | Appointment calls Counseling | `counseling_context_available` boolean | `appointments/api.py:920-932` |
| Completion | **No coupling** | `complete_appointment` does not write or read Encounter | `appointments/services.py:1566-1618` |

### 2.2 Transaction boundary

The two writes are separate transactions today. There is no caller that opens one transaction around
both, and no endpoint accepts both intents. **Verified** by caller inventory in
[`current-state.md`](current-state.md) §11.

A composed Finish operation changes only **transaction ownership**, not domain ownership: it opens
the transaction at the Counseling integration boundary and calls
`create_encounter(...)` and `complete_appointment(...)`. It must not use
`Appointment.objects.update(...)` or direct status assignment.

### 2.3 Provenance invariant

`appointments_status_terminal_consistent` guarantees that a `COMPLETED` Appointment has exactly
`completed_at` and no other terminal timestamp (`appointments/models.py:134-162`). The completion
service writes exactly those fields (`appointments/services.py:1603-1606`). When the Appointment is
already `COMPLETED`, the service returns before writing
(`appointments/services.py:1586-1587`), so a later Encounter cannot rewrite the original actor/time.

CENC-1 must preserve that early return. It must not implement its own `SCHEDULED → COMPLETED` update
for an already-completed Appointment because that would either falsify a second transition or
incorrectly require `completed_at` to change.

---

## 3. Counseling ↔ Routine Interviews

### 3.1 Matching contract

`routine_interview_encounter_match_issue_for_facts` requires, in order
(`routine_interviews/matching.py:39-68`):

1. same Student;
2. same Counselor;
3. canonical Counseling Service;
4. same delivery mode;
5. Encounter ended in the past;
6. for an Appointment-anchored Routine: Encounter `entry_mode=APPOINTMENT` and identical
   Appointment id;
7. for a direct Routine: Encounter must have no Appointment and the same entry mode.

There is no similarity matcher. This is the only permitted way for Finish to link a Routine.

### 3.2 Link invariants

- One Routine per Appointment; one Encounter per Routine (`routine_interviews/models.py:124-155`).
- A Routine cannot point at a different Encounter after a link; replacement is rejected
  (`routine_interviews/services.py:1200-1252`).
- A finalized Routine requires a linked Encounter (`routine_interviews/models.py:138-144`) and its
  Evaluation cannot be invalidated by an Encounter correction
  (`counseling/services.py:966-1004`).
- `link_appointment_encounter` silently declines a mismatch and never replaces a link
  (`routine_interviews/services.py:1324-1357`).

### 3.3 What Finish may do

- For a new Encounter, `create_encounter` already discovers the Appointment's Routine, locks it
  first and attempts a deterministic link (`counseling/services.py:480-549`).
- For an existing Encounter, Finish may attempt the same deterministic link if it is absent. It must
  not force a link when matching fails, and must not finalize the Evaluation.
- If a finalized/conflicting Routine makes truthful completion impossible, Finish should return a
  stable conflict and write nothing. The proposal requires this (proposal lines 6878, 6938).

### 3.4 Intake and Evaluation are independent

`finalize_assigned_evaluation` requires a submitted Student Intake and a linked completed Encounter
(`routine_interviews/services.py:1365-1456`). Encounter creation does not require Intake or
Evaluation. Finish must not add either as a hidden gate. **Verified** by the absence of Routine
imports in `counseling/services.py` other than linking helpers
(`counseling/services.py:441-449,474`).

---

## 4. Counseling ↔ Feedback

### 4.1 Canonical producer

`_create_row` creates the Encounter, records `COUNSELING_ENCOUNTER_CREATED`, calls
`ensure_feedback_opportunity(...)` with the Encounter as source, then creates the
`FEEDBACK_INVITATION` notification (`counseling/services.py:322-382`). The Feedback source type is
`COUNSELING_ENCOUNTER` (`feedback/models.py:28-30`), and the unique constraint on
`(source_type, source_id)` makes a duplicate opportunity impossible for the same Encounter
(`feedback/models.py:59-64`).

### 4.2 Idempotency and replay

- `ensure_feedback_opportunity` is `get_or_create` with an IntegrityError fetch fallback
  (`feedback/services.py:256-267`).
- `create_notification_for_event` is `get_or_create` on recipient/event/source
  (`notifications/services.py:104-116`).
- On replay of an existing Encounter, Finish must not call `_create_row`, so it cannot create another
  opportunity or invitation.
- If a legacy Encounter is missing its opportunity, Finish must not invent one implicitly as part of
  "already finished"; the existing Feedback reconciliation contract is the only repair path
  (`feedback/services.py:288-339`). The proposal says the same (lines 7441–7443).

### 4.3 Correction chronology

Encounter correction can change `ended_at`, and `reconcile_counseling_feedback_opportunity` refuses a
completion time after Feedback was made available or submitted (`feedback/services.py:325-333`).
Finish must route time corrections to `update_encounter`, never silently update the Encounter times
as part of a replay.

**Verified** by `be/tests/test_counseling_downstream_lifecycle.py:104-359` (finalized Routine
protections, Feedback survival, chronology rollback, provenance fail-closed, no-op correction).

---

## 5. Counseling ↔ Notifications

| Event | Producer | Policy | Evidence |
|---|---|---|---|
| `feedback.invitation` | Encounter creation | optional informational email; in-app | `notifications/policy.py:328-339`; `counseling/services.py:378-381` |
| `appointment.cancelled` | Appointment cancellation | student + provider | `appointments/services.py:1115-1123` |
| `appointment.scheduled/rescheduled/reassigned/reminders` | Appointment flows | existing policies | `notifications/policy.py:46-52` |
| `appointment.completed` | **none** | **no event definition** | `notifications/policy.py:46-52`; `complete_appointment` audit only |
| `student_session_summary.published` | Summary publish | student | `student_session_summaries.py:149-156` |

**Verified**: a composed Finish operation that calls `complete_appointment` will not emit a
completion notification. Adding one would be a new product/privacy decision, not a mechanical
consequence (D-CENC-20/D-CENC-13). The proposal explicitly warns not to assume every completed
Appointment sends email (lines 7445–7447).

`create_notification_for_event` makes the in-app notification durable in the transaction and defers
push/email delivery to `on_commit`; transport setup failure is logged and does not undo the
notification or the Encounter (`notifications/services.py:118-150`). This matches the proposal's
atomicity rule for mandatory versus optional work (line 6894).

---

## 6. Counseling ↔ E-Counseling

| State | Behavior | Evidence |
|---|---|---|
| Appointment eligible for join | `SCHEDULED` only | `ecounseling/services.py:127-154` |
| Saved room for completed Appointment | Workspace can load it | `ecounseling/services.py:157-163` |
| Access window | `TOO_EARLY` / `OPEN` / `CLOSED` from scheduled start/end and settings | `ecounseling/services.py:194-239` |
| Provider readiness | Separate from window; does not move it | `ecounseling/services.py:269-287` |
| Completion | Blocked while `OPEN` | `appointments/services.py:1595-1602` |
| No-show | Blocked while `OPEN` | `appointments/services.py:1652-1659` |
| Cancellation | Blocked once access not `TOO_EARLY`; blocked with room | `appointments/services.py:1071-1083` |
| Reassignment | Blocked with room | `appointments/services.py:1377-1393` |
| Encounter creation | **No E-Counseling check** | `counseling/services.py:452-605` |

**Verified**: E-Counseling state is an Appointment-lifecycle constraint, not a Counseling one.
Finish must obtain the `OPEN` block by calling the existing completion service. If Finish created the
Encounter first and then hit the `OPEN` block, the enclosing transaction must roll the Encounter back;
CENC-1 must test that sequence, because today no caller composes them.

Media capture, recording and consent are not attendance facts. `ecounseling-workspace.tsx:394-432`
documents the Encounter separately from media; nothing in the backend creates an Encounter from a
room, join or disconnect event (`Verified` by caller inventory).

---

## 7. Audit

- Existing events are domain-specific and append-only.
- Appointment completion records `appointment.completed` with reference and transition only
  (`appointments/services.py:1607-1617`).
- Encounter creation records `counseling.encounter.created` with entry/delivery/Appointment id only
  (`counseling/services.py:348-359`).
- Encounter correction records changed field names, not values (`counseling/services.py:1021-1033`).
- Routine linking records `routine_interview.encounter_linked` with link source and ids
  (`routine_interviews/services.py:1239-1251`).

**Verified**: none of these events contains Counseling narrative, Evaluation answers, diagnoses,
transcripts or Student Session Summary text. A Finish operation can reuse these two events; adding a
distinct "Counselor-confirmed finish" event is D-CENC-20. If added, it must follow the same
minimal-metadata rule (`docs/` audit policy; proposal lines 6917–6919).

---

## 8. Guidance Follow-Ups (FUP)

**Verified absence**: no `guidance_followups`/`GuidanceFollowUp` references under
`be/compass/counseling/` or `be/compass/appointments/`. FUP is an independent domain with its own
source policy. Encounter creation/correction does not create, complete, reassign or close a
Follow-Up. The proposal explicitly keeps Follow-Up creation optional and outside Finish
(proposal lines 6828–6835, 7738–7739).

**Implication**: CENC-1 must not add FUP side effects. If a future CENC slice offers a contextual
"Create Follow-Up" link, it is a separate explicit user action, not part of the composed transaction.

---

## 9. Faculty / Referrals (FAC)

**Verified**: no Referral writes from Counseling or Appointments. Counseling Context history reads
Referral rows for display as administrative history
(`counseling/context_services.py:19,309-327`), with statuses `RECORDED`, `RECEIVED`, `VOIDED`. The
Referral domain owns Faculty origin and administrative status
(`referrals/models.py:13-19,45-99`).

**Implication**: Finish must not close, acknowledge or otherwise change a Referral, and must not
send Faculty any session progress. The proposal's out-of-scope list forbids exactly that
(proposal line 7829). No Fac operation is needed in CENC-1.

---

## 10. Case Continuity (CONT)

**Verified**: the continuity policy provider deliberately returns `None` with no settings-based
activation (`counseling/continuity_policy.py:1-8,107-109`), and Counseling Context authorization
requires an active assigned Counselor rather than a continuity grant
(`counseling/context_access.py:50-57`). No continuity grant is consulted by context access
(no matches under `context_access.py`).

**Implication**: a continuity read grant cannot be treated as Encounter-authoring authority. CENC-1
must remain provider-only; the proposal says the same (lines 7407, 7431). Future CONT integration is
separate.

---

## 11. Student Session Summary

**Verified**: `StudentSessionSummary` is one-to-one with an Encounter, encrypted, Counselor-authored,
and published separately (`counseling/models.py:93-115`). It is created only by an explicit
`put_assigned_student_session_summary` (`student_session_summaries.py:93-115`), never by Encounter
creation. Publishing notifies the Student and records an audit event
(`student_session_summaries.py:118-157`).

**Implication**: Finish must not create, draft, publish or link a Student Session Summary. A
post-Finish link to an authoring page may be a CENC-2 UX decision (D-CENC-13), but no automatic
content.

---

## 12. Boundary checklist for CENC-1

A composed Finish implementation is boundary-safe only if all answers are "yes":

1. Does it call Appointment-owned completion rather than writing status fields? **Required**
2. Does it call Counseling-owned Encounter creation rather than inserting rows? **Required**
3. Does it preserve the existing Routine-first lock order? **Required**
4. Does it use only deterministic Routine matching, with no similarity? **Required**
5. Does it create Feedback only through `ensure_feedback_opportunity`? **Required**
6. Does it avoid a new Feedback source or a Finish-specific invitation? **Required**
7. Does it avoid inventing a completion notification? **Required**
8. Does it preserve the E-Counseling `OPEN` block by delegating to completion? **Required**
9. Does it avoid creating/finalizing Routine Intake/Evaluation? **Required**
10. Does it avoid FUP/FAC/CONT/Summary side effects? **Required**
11. Does it log no clinical content? **Required**
12. Does it remain provider-only with no GSS/IT Admin/Head override? **Required**
