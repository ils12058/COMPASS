# CENC-0 — Current journeys, truthful copy and proposed UAT

**Status:** read-only static audit at `04d2581b` (2026-11-05). Claims are **Verified**,
**Inferred** or **Unknown**. Everything in §3 is **Proposed** and was **not executed**. No browser,
dev server or test was run.

---

## 1. Current staff journeys

### 1.1 Complete an attended Appointment (the double operation)

**Verified** from frontend/backend code:

1. Counselor opens Appointment Detail (`fe/src/features/appointments/appointment-detail-page.tsx`).
2. If the Counseling Context is currently available, the page shows `Open Counseling` linking to
   `/portal/counseling/workspace/appointment/{id}` (`:592,622-624`).
3. The Actions panel offers `Complete appointment` when the server projection allows it
   (`:690-700`).
4. The confirmation says: "This appointment will be marked completed and will no longer be
   scheduled." (`:221-227`).
5. The backend sets `COMPLETED`/`completed_at`/`completed_by` and records an audit event; it does
   **not** create an Encounter (`be/compass/appointments/services.py:1566-1618`).
6. The page reloads the Appointment and shows the new status. It does **not** show whether an
   Encounter exists or offer to record one.

The reverse order is equally supported:

1. Counselor opens the Counseling Workspace from the Appointment.
2. Records the Encounter with actual times.
3. The backend leaves the Appointment `SCHEDULED` (`counseling/services.py:452-605`).
4. The form explicitly says: "Recording this encounter does not complete the Appointment."
   (`record-encounter-form.tsx:358`).
5. The Counselor must return to Appointment Detail and complete it separately.

Neither order is composed. Both can be left half-finished.

### 1.2 Record an Encounter from Counseling

**Verified**:

- Counseling page action `Record` opens an inline `RecordEncounterForm`
  (`counselor-encounters.tsx:95-113`).
- The form supports an Appointment origin or a direct Student origin
  (`record-encounter-form.tsx:45-61,87-109`).
- Appointment origin presets Student/Service/delivery and shows scheduled times **for reference
  only**; those times are never sent (`:47-61,93-100`).
- Actual times start blank and are required (`:321-330`).
- The provenance note is: "The Appointment sets the student, Service, and delivery mode. You are
  recorded as the counselor." (`:81-85`).
- The dialog title is "Record counseling encounter" (`:367-371`); the submit label is
  "Record encounter" (`:356`).
- An uncertain save shows "We couldn't confirm whether the encounter was recorded." plus
  `Check again`/`View encounters`; it never automatically re-submits (`:333-358`).

### 1.3 Record an Encounter from the contextual workspace

**Verified**:

- The Appointment/Routine workspace shows `Record encounter` when the actor can manage the context
  (`counseling-workspace.tsx:270-275,350-352`).
- It displays `Not yet recorded`, `Recorded`, or `Recorded outside this Routine Interview`
  (`counseling-shared.tsx:68-88`).
- After a successful record, the action becomes `View encounter` and query caches are invalidated
  (`counseling-workspace.tsx:277-300,343-345`).
- When the time-bounded context expires, the page shows "Counseling workspace is no longer
  available"; the `Open Counseling` link on Appointment Detail disappears because
  `counseling_context_available` becomes false (`context_access.py:284-306`;
  `appointment-detail-page.tsx:592`).

### 1.4 Record an Encounter from E-Counseling

**Verified**:

- The E-Counseling workspace has a separate "Counseling Encounter" disclosure
  (`ecounseling-workspace.tsx:394-432`).
- It says "Record the encounter after the counseling conversation." (`:392`).
- It uses the same `RecordEncounterDialog` and the same uncertain-save behavior (`:405-430`).
- Recording is explicitly separate from media capture (`:394-395`); no room/join/disconnect state
  creates an Encounter.

### 1.5 Correct an Encounter

**Verified**:

- Encounter Detail offers correction (`encounter-detail-page.tsx:55-70`).
- Only changed facts are sent (`encounter-correction-form.tsx:42-61`).
- Identity is immutable: "Student, Counselor, Service, creator, and creation time cannot be
  changed." (`:138`).
- The Appointment select and entry-mode select interact in the UI: choosing an Appointment sets
  `APPOINTMENT`, clearing it sets `WALK_IN` (`:146-160`).
- The backend does not enforce the inverse (`counseling/services.py:857-951`), so the API can create
  a linked Encounter whose entry mode is not `APPOINTMENT`; Counseling Context then ignores it
  (`context_access.py:60-82`).

### 1.6 Observe the result today

| Question | Current answer | Evidence |
|---|---|---|
| Does Appointment Detail show the Encounter? | No | no Encounter field in `appointment-detail-page.tsx`; only `counseling_context_available` |
| Does completion warn if no Encounter exists? | No | `appointments/services.py:1911-1915`; complete copy `appointment-detail-page.tsx:221-227` |
| Does the Counseling workspace show Appointment completion? | No | it shows only Encounter state (`counseling-workspace.tsx:333-352`) |
| Is there a "Needs documentation" list? | No | absence searches |
| After context expiry, can the Counselor still record for that Appointment? | Yes, through the general Record form's Appointment search, which includes `COMPLETED` records | `counseling/services.py:664-672` |
| Is the path discoverable? | **Inferred** no: the contextual link is gone and no prompt points to the general search | `appointment-detail-page.tsx:592`; `counselor-encounters.tsx:95-113` |

---

## 2. Truthful copy inventory

These are current strings. They are factual and must not be replaced with copy implying attendance
from administrative status.

| Surface | Copy | Evidence | Assessment |
|---|---|---|---|
| Complete confirmation | "This appointment will be marked completed and will no longer be scheduled." | `appointment-detail-page.tsx:221-227` | **Verified truthful**; it does not claim an Encounter |
| No-show confirmation | "This appointment will be marked no-show and will no longer be scheduled." | `:228-234` | Truthful |
| Record form (scheduled Appointment) | "Recording this encounter does not complete the Appointment." | `record-encounter-form.tsx:358` | Truthful; this is the gap CENC intends to remove |
| Help | "Recording it does not complete an Appointment and does not start audio/video recording." | `counseling-help.tsx:7` | Truthful |
| Provenance | "The Appointment sets the student, Service, and delivery mode. You are recorded as the counselor." | `record-encounter-form.tsx:81-85` | Truthful |
| Uncertain save | "We couldn't confirm whether the encounter was recorded." | `counseling-shared.tsx:59` | Truthful; no false success |
| Already recorded | "An encounter was already recorded for this Appointment. The latest details are now shown." | `counseling-workspace.tsx:295-299` | Truthful |
| Workspace recorded | "Completed interaction recorded {start} – {end}." | `counseling-workspace.tsx:343-345` | Truthful; uses actual times |
| Routine mismatch | "A matching interaction recorded {start} – {end} is not linked to this Routine Interview. If it is this interaction, choose it when finalizing the Counselor Evaluation." | `counseling-workspace.tsx:345-346` | Truthful and specific |
| E-Counseling | "Record the encounter after the counseling conversation." | `ecounseling-workspace.tsx:390-392` | Truthful |
| Context expiry | "These interaction details can no longer be reviewed here." | `counseling-workspace.tsx:328-329` | Truthful |
| Encounter correction | "Student, Counselor, Service, creator, and creation time cannot be changed." | `encounter-correction-form.tsx:138` | Truthful |

**Verified absence**: no string anywhere says "Needs documentation", "Finish Counseling", "already
finished", or that a completed Appointment necessarily had a session.

---

## 3. Proposed UAT journeys (not executed)

All scenarios below are **Proposed**. They require GCO-approved fixtures and must not be reported as
passed until executed. Proposal scenario numbers refer to §23 (lines 7678–7759).

### 3.1 Core finish journeys

| # | Proposed preconditions | Proposed expected result | Proposal ref |
|---|---|---|---|
| P-01 | In-person Counseling Appointment `SCHEDULED`, after start, no Encounter, E-Counseling not `OPEN` | One submission with actual start/end creates exactly one Encounter, links it to the Appointment, completes the Appointment, creates one Feedback opportunity and one invitation, records both domain audits, returns authoritative result | A1–A3; D38–39 |
| P-02 | Same, but dialog cancelled before submit | No Encounter, no Feedback, Appointment unchanged | A8 |
| P-03 | Actual end equal to start / earlier / future / naive | Rejected with field-specific error; Appointment and Encounter unchanged | A4–A7 |
| P-04 | Actual times different from scheduled times | Actual values retained; scheduled window unchanged; no substitution | A3 |
| P-05 | `CANCELLED` or `NO_SHOW` Appointment | Rejected; cancellation/no-show history unchanged; no Encounter, no Feedback | A10–A11 |
| P-06 | Non-Counseling Service, Group Session or non-canonical record | Rejected; no Encounter | A12–A14 |
| P-07 | Online Appointment while E-Counseling access is `OPEN` | Rejected; no Encounter; Appointment remains `SCHEDULED`; Counselor sees the existing safe reason | D38 |
| P-08 | Online Appointment after access closes | Finish succeeds without requiring recording/transcription | D39 |

### 3.2 Existing state and replay

| # | Proposed preconditions | Proposed expected result | Proposal ref |
|---|---|---|---|
| P-09 | `SCHEDULED` Appointment already has a matching `APPOINTMENT` Encounter | Finish completes only; Encounter and Feedback unchanged; `encounter_result=EXISTING` | B15 |
| P-10 | `COMPLETED` Appointment, no Encounter, Counselor attests a real session | Encounter created; original `completed_by`/`completed_at` unchanged; no second completion audit | B16; §14.8 |
| P-11 | `COMPLETED` Appointment, no Encounter, no session occurred | Review indicator must not force creation; no Encounter without explicit attestation | B17 |
| P-12 | `COMPLETED` + matching Encounter | Idempotent already-finished result; no new writes | B18 |
| P-13 | Double-click / retried request | One Encounter, one Feedback, one completion transition; second request returns existing result | B19 |
| P-14 | Two concurrent Finish requests | One terminal result; no duplicate Encounter/Feedback/audit | B20 |
| P-15 | Finish races with legacy Record Encounter | Exactly one Encounter; loser gets a stable conflict or existing result | B21 |
| P-16 | Finish races with legacy Complete | One completion; provenance truthful; one Encounter | B22 |
| P-17 | Finish races with cancel/no-show | No mutually inconsistent status + Encounter newly committed | B23 |
| P-18 | Network timeout after commit, then retry | Check-again path reveals the existing result; no blind replay or duplicate | B24 |
| P-19 | Contradictory actual times on replay | Rejected/conflict; recorded times not overwritten; directed to correction | B25; §6.3 |

### 3.3 Routine and direct interaction

| # | Proposed preconditions | Proposed expected result | Proposal ref |
|---|---|---|---|
| P-20 | Matching Routine Interview pre-exists | Finish links it deterministically; Evaluation remains unfinalized and Intake unchanged | C27 |
| P-21 | Routine created after Encounter | Later deterministic reconciliation links it; no similarity matching | C28 |
| P-22 | Routine has pending Intake | Finish still records the session; finalization still requires Intake | C29 |
| P-23 | Finalized Routine with incompatible reassociation attempt | Rejected; finalized Evaluation unchanged | C30 |
| P-24 | Direct Walk-in/Called-in/Referred Encounter | Still works without an Appointment; no fake Appointment is created | C32–C34 |
| P-25 | Direct encounter from Routine context | Transactionally linked by existing rules | C35 |
| P-26 | Two same-day direct Encounters | Not auto-joined to one Routine by similarity | C36 |

### 3.4 Authorization, privacy and access

| # | Proposed preconditions | Proposed expected result | Proposal ref |
|---|---|---|---|
| P-27 | Unrelated Counselor guesses the Appointment UUID | Not-found semantics; no protected facts; no Finish permission | E51 |
| P-28 | Head Guidance not selected as provider | Not-found/denied; designation alone does not authorize | E52 |
| P-29 | GSS with Appointment management capability | Cannot call Finish; cannot create a professional Encounter | E53 |
| P-30 | IT Admin | Cannot impersonate the Counselor | E54 |
| P-31 | Stale browser after assignment change | Fresh authorization under lock rejects; no old-client success | E55 |
| P-32 | Continuity read grant | Does not authorize Finish or Encounter authoring | E56 |
| P-33 | Needs-documentation worklist | Only scope-permitted Appointments; administrative completion is not labeled confirmed attendance | E57 |
| P-34 | Audit inspection | Correct actor, separate domain events, original completion provenance preserved | E61 |
| P-35 | Failure injected after Encounter before Appointment transition | Full rollback; no false success; no outbound false-success notification | E62 |

### 3.5 Downstream effects

| # | Proposed preconditions | Proposed expected result | Proposal ref |
|---|---|---|---|
| P-36 | New Encounter through Finish | Exactly one canonical Feedback opportunity and permitted invitation | D43 |
| P-37 | Replay of Finish | No second invitation | D44 |
| P-38 | Student submits Feedback then Encounter is validly corrected | Submitted Feedback survives; chronology rules hold | D45 |
| P-39 | Counselor does not create a Follow-Up | Finish still succeeds; no Follow-Up created | D47 |
| P-40 | Routine Evaluation or Student Session Summary not authored | Finish still succeeds; neither is auto-created/published | D48–49 |
| P-41 | Faculty Referral linked to the Student | Referral administrative status unchanged; no Faculty disclosure | D50 |
| P-42 | Media capture pending/failed/disabled | Documentation follows E-Counseling rules; no artifact claimed ready; no attendance inference | D41–42 |

---

## 4. Journey design constraints for CENC-2

These are constraints derived from verified current behavior, not GCO decisions:

1. **One primary action per context.** Do not keep equally prominent Complete and Record controls
   for the same attended session (proposal lines 7168–7169). Current Appointment Detail and
   Counseling Workspace are separate pages with separate actions
   (`appointment-detail-page.tsx:690-747`; `counseling-workspace.tsx:350-352`).
2. **Actual times remain blank and are never pre-filled from the schedule.** The current form already
   guarantees this (`record-encounter-form.tsx:47-61,321-330`). A Finish dialog must preserve it.
3. **Read-only source facts.** Student/Counselor/Service/delivery/Appointment reference come from
   the Appointment (`counseling/services.py:496-521`), not from inputs.
4. **Uncertain save is checked, not replayed.** The existing pattern must be reused
   (`record-encounter-form.tsx:333-358`; `counseling-workspace.tsx:347-349`).
5. **No clinical content in success or notification copy.** The proposal's copy is aspirational
   (lines 7231–7245); GCO approval is D-CENC-18.
6. **Do not hide documentation gaps.** If Appointment Detail says "Completed", it must not imply a
   session was documented. A derived indicator belongs to CENC-4, not to a persisted status.
7. **Context expiry remains honest.** A Finish success page or link must not extend Counseling
   Context access (proposal lines 7413–7415).
8. **Direct recording stays available.** Walk-in/called-in/referred flows must remain; CENC-1
   changes no direct path.
9. **No new attendance inference from E-Counseling.** The Encounter section stays separate from call
   controls (`ecounseling-workspace.tsx:394-395`).
10. **Admin completion is not clinical attestation.** If D-CENC-03 ever grants GSS completion for
    Counseling, the UI and API must still refuse Finish without the assigned Counselor.

---

## 5. Copy decisions still open

| Copy question | Current text | Decision |
|---|---|---|
| Primary action label | none (`Complete appointment`, `Record encounter`) | D-CENC-05/D-CENC-18 |
| Confirmation that Counseling occurred | none | D-CENC-01 |
| Success message | none | D-CENC-18 |
| Existing Encounter + still scheduled | none | D-CENC-05 |
| Administratively completed, no Encounter | none | D-CENC-08 |
| Online blocked | E-Counseling-specific existing messages | D-CENC-10 |
| Needs documentation | none | D-CENC-08/D-CENC-14 |
