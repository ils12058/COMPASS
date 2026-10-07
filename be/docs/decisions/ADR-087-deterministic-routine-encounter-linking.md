# ADR-087: Deterministic Routine Interview and Counseling Encounter linking

## Status

Accepted. Refines the "Encounter matching and finalization" section of
[ADR-023](ADR-023-routine-interview.md). ADR-023's rule that a Counseling Encounter is
independently recordable without a Routine Interview remains authoritative, as does its
Individual Inventory prerequisite.

## Context

ADR-023 linked a Routine Interview to its Counseling Encounter only at evaluation finalization.
Until then `RoutineInterview.counseling_encounter` stayed NULL, even when COMPASS already knew the
relationship:

- an Appointment-backed Routine Interview and an Encounter recorded for the same Appointment
  share one anchor, and an Appointment admits at most one Encounter;
- an Encounter recorded from a direct Routine Interview's Counseling workspace
  (`/portal/counseling/workspace/routine-interview/{id}`) was created with no reference to that
  Routine Interview, so the Counselor later picked it again from radio buttons while finalizing;
- the workspace inferred "Counseling Encounter: Recorded" from a similarity search while the
  database held no link.

Students also opened each Appointment's Routine Interview through a "Start Routine Interview"
action whose only effect was to create the record the Appointment already implied.

## Decision

### Invariant

Counseling Encounters may exist independently of Routine Interviews. When COMPASS has
deterministic Routine Interview provenance, it creates or associates the relationship itself;
users are not asked to link records COMPASS already knows belong together. COMPASS never links
by similarity (same Student, Counselor, entry mode, or nearby times).

### Appointment-backed Routine Interviews

A scheduled Counseling Appointment remains the anchor, and the existing idempotent
`ensure_for_appointment` remains the only way it gets its Routine Interview (one per Appointment,
enforced by the one-to-one constraint and the Appointment row lock). The Student interface
presents "Complete Routine Interview" and runs that ensure while opening the form; there is no
separate start step and no second creation endpoint.

COMPASS does not create the Routine Interview when the Appointment is booked: ADR-057 blocks
reassignment of an Appointment that has a Routine Interview and rewrites no downstream Counselor
record, so creating it at booking would make every Counseling Appointment unreassignable. The
Inventory prerequisite would also skip creation for Students who book before submitting their
Inventory. Ensuring on open keeps both rules and the existing reassignment window intact.

### Automatic linking

The link is persisted in the same transaction that makes the relationship deterministic:

| Moment | Link source |
| --- | --- |
| An Encounter is recorded for an Appointment that has a Routine Interview | `APPOINTMENT` |
| A Routine Interview is ensured for an Appointment that already has an Encounter | `APPOINTMENT` |
| An Encounter correction attaches it to an Appointment, or makes it satisfy that Appointment's Routine Interview | `APPOINTMENT` |
| An Encounter is recorded from a Routine Interview's Counseling context (`routine_interview_id` on `POST /counseling/encounters`) | `ROUTINE_INTERVIEW_CONTEXT` |

Every link revalidates the ADR-023 matching rules on the server; a client-supplied Routine
Interview is never trusted. Recording from a Routine Interview context requires the actor to be
its assigned Counselor (otherwise it is not found) and the `routine_interviews.manage_assigned`
capability in addition to `counseling.manage_assigned`. A mismatched Student, entry mode,
delivery mode, or Appointment, or an existing link, rejects the whole recording, so no unlinked
Encounter is left behind. A plain recording outside any Routine context is unaffected.

An Appointment Encounter that fails the matching rules (for example a non-APPOINTMENT entry mode)
is still recorded and stays independent; finalization keeps reporting the mismatch, and a later
correction that fixes it links it.

Linking the link that already exists is a no-op. A different existing link is never replaced, and
an Encounter linked to one Routine Interview is never taken by another; both are rejected
(`routine_interview_encounter_conflict`, `counseling_routine_interview_already_linked`). The
one-to-one constraint on `counseling_encounter` stays authoritative under concurrency.

Once linked, an Encounter correction that would break the match is rejected whether or not the
Evaluation is finalized (`counseling_linked_routine_conflict`; finalized records keep
`counseling_finalized_routine_conflict`). Links are never removed.

### Locking

Every Routine mutation locks the Routine Interview before its Appointment. Encounter recording
and correction now lock the Routine Interview they may link first, identified by unlocked
lookups that are safe because a Routine Interview's Appointment never changes and a link is
never removed. Ensuring a Routine Interview holds the Appointment lock and takes the
Appointment's Encounter with `SKIP LOCKED`; a correction holding that Encounter waits on the
Appointment and links it itself afterwards. A Routine Interview created in the instant between a
recording's lookup and its Appointment lock is locked after the Appointment; PostgreSQL resolves
the residual deadlock risk by aborting one transaction.

### Finalization

- Linked: finalization validates the persisted Encounter and needs no selection. Naming a
  different Encounter is rejected.
- Appointment-backed but unlinked (records from before this decision): the Appointment's single
  Encounter is reconciled and linked (`APPOINTMENT_RECONCILIATION`).
- Direct and unlinked (an Encounter recorded outside the Routine context, or before this
  decision): the Counselor must name the Encounter (`COUNSELOR_RECOVERY`). COMPASS never picks one
  of several candidates. The frontend shows this choice only in this case, labelled as Encounters
  recorded outside the Routine Interview, and otherwise directs the Counselor to record from the
  Routine Interview's workspace.

A missing Encounter still blocks finalization.

### Workspace consistency

The Counseling context overview reports the Routine Interview's persisted Encounter whenever one
exists, with `matching_encounter.routine_interview_linked`. The similarity search that extends a
direct context's access window now runs only for unlinked Routine Interviews and only considers
unlinked Encounters; the workspace labels its result "Recorded outside this Routine Interview"
rather than "Recorded". Access windows are otherwise unchanged.

Students continue to see a Routine Interview's Encounter only once it backs a finalized
Evaluation, exactly as before; linking earlier does not widen Student-visible data.

### Audit

`routine_interview.encounter_linked` records `link_source`, `entry_mode`, `appointment_id`, and
`encounter_id` only, distinguishing automatic links from reconciliation and Counselor recovery.
It never carries Intake or Evaluation content. Existing creation, Intake, finalization, and
Encounter audit events are unchanged; Encounter correction metadata adds
`linked_routine_dependency_checked`.

### Data

No schema change or migration. Historical records are not bulk-linked: Appointment-backed ones
reconcile deterministically at finalization, and direct ones keep explicit Counselor recovery.

## Not changed

The Individual Inventory prerequisite for creating a Routine Interview is unchanged:
`RoutineInterview.inventory` stays required, `require_current_submitted_inventory()` still gates
creation, and there are no pending or Inventory-less Routine Interviews. When the prerequisite is
unmet, ensuring still fails with `routine_interview_inventory_required` and the Encounter is still
recordable. Reconsidering that relationship is a separate decision.

Direct entry modes (`WALK_IN`, `CALLED_IN`, `REFERRED`) keep their meaning; no Call Slip or
Referral provenance is added to Routine Interviews.
