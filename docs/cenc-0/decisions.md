# CENC-0 — Decisions requiring GCO / team / privacy confirmation

**Status:** all decisions are **Open**. Nothing in this file is approved institutional policy. The
"provisional recommendation" is the audit's engineering recommendation for CENC-1 scoping, not a GCO
decision. Proposal §25 is lines 7789–7812; D-CENC-01..20 map 1:1 to proposal items D01–D20.
D-CENC-21 and D-CENC-22 are additional findings from this audit.

**Owners used below:** **GCO** — Guidance and Counseling Office; **Team** — COMPASS engineering;
**Privacy** — DPO/Privacy Governance; **GSS** — Guidance Services Staff leadership; **UX** —
Counselor workflow owners with Team.

---

## D-CENC-01 — Attestation language

- **Proposal:** D01 (line 7793).
- **Question:** What exact text must the assigned Counselor confirm to record a Counseling session?
- **Options:** (A) a required checkbox with explicit "Counseling actually took place" language;
  (B) a typed confirmation; (C) no separate flag, submit implies attestation.
- **Provisional recommendation:** A — required positive confirmation plus actual times; server
  rejects a false/missing flag. The proposal's request concept includes `counseling_occurred`
  (line 7279).
- **Owner:** GCO.
- **Blocker:** approved wording and accessibility review. Until approved, CENC-1 can implement the
  mechanics with provisional copy, but must not claim GCO approval.
- **Status:** **Open**.

## D-CENC-02 — Who may finish

- **Proposal:** D02 (line 7794).
- **Question:** Is only the personally assigned Counselor allowed to attest, or is there a formally
  approved coverage/delegation path?
- **Options:** (A) assigned provider only; (B) assigned provider plus an approved coverage actor;
  (C) broader delegated professional role.
- **Provisional recommendation:** A for CENC-1. B/C require a separate authorization design and
  must not be approximated by the Head designation or GSS Appointment management.
- **Owner:** GCO; Team for enforceability.
- **Blocker:** GCO coverage policy; no approved continuity/coverage authoring contract exists at HEAD
  (`counseling/continuity_policy.py:107-109`; `context_access.py:50-57`).
- **Status:** **Open**.

## D-CENC-03 — Administrative completion for Counseling

- **Proposal:** D03 (line 7795).
- **Question:** Should authorized GSS/office staff retain an administrative Complete action for
  Counseling Appointments, and how is it distinguished from clinical attestation?
- **Options:** (A) keep current relationship-only policy (provider only); (B) grant GSS a narrowly
  labeled administrative completion without Encounter authority; (C) remove administrative
  completion for Counseling entirely.
- **Provisional recommendation:** A for CENC-1. At HEAD GSS cannot see or complete a canonical
  Counseling Appointment (`appointments/access.py:47-72`;
  `be/tests/test_appointment_management_scope.py:365-440`). Expanding this is a separate policy
  change with its own tests and audit semantics; CENC-1 must not do it silently.
- **Owner:** GCO; GSS; Team.
- **Blocker:** GCO decision. The proposal assumes GSS administrative completion is possible
  (lines 6702, 7702), which is **not** true at HEAD.
- **Status:** **Open**.

## D-CENC-04 — Retrospective documentation after administrative completion

- **Proposal:** D04 (line 7796).
- **Question:** May a Counselor retrospectively document a genuinely held session after an
  administrative completion?
- **Options:** (A) yes, preserving completion provenance; (B) yes only within a window; (C) no.
- **Provisional recommendation:** A, exactly as proposal recommends. The existing completion service
  already preserves provenance by returning early on `COMPLETED`
  (`appointments/services.py:1586-1587`); Encounter creation accepts `COMPLETED`
  (`counseling/services.py:294-298`).
- **Owner:** GCO.
- **Blocker:** GCO approval; interaction with D-CENC-03 (if GSS never completes Counseling at HEAD,
  the scenario is narrower).
- **Status:** **Open**.

## D-CENC-05 — Action label and reconciliation model

- **Proposal:** D05 (line 7797).
- **Question:** Is the action "Finish Counseling", "Complete Counseling Appointment", or an
  automatically recognized reconciliation inside one button?
- **Options:** (A) one primary `Finish Counseling`, with a separate reconciliation outcome for
  existing Encounter; (B) separate `Complete Counseling Appointment`; (C) no new label, fold into
  existing Complete.
- **Provisional recommendation:** A. It matches the proposal's confirmed direction (line 6659) and
  lets one endpoint return `CREATED`/`EXISTING`/`ALREADY_FINISHED`.
- **Owner:** GCO; UX.
- **Blocker:** copy approval.
- **Status:** **Open**.

## D-CENC-06 — Actual timing and backdating

- **Proposal:** D06 (line 7798).
- **Question:** Are retrospective sessions permitted indefinitely while the original assigned
  Counselor remains authorized? Are there accuracy/attestation limits?
- **Options:** (A) no age limit; (B) a GCO-defined maximum backdate; (C) case-by-case approval.
- **Provisional recommendation:** A for CENC-1, matching current Encounter rules: aware,
  chronological, not future, no maximum age (`counseling/services.py:172-188`;
  `be/tests/test_counseling.py:557-600`). Adding a limit without GCO policy would be an unverified
  restriction.
- **Owner:** GCO.
- **Blocker:** GCO policy.
- **Status:** **Open**.

## D-CENC-07 — Time suggestions

- **Proposal:** D07 (line 7799).
- **Question:** Should actual times always start blank, or may the UI offer a clearly labeled opt-in
  suggestion from reliable session metadata?
- **Options:** (A) always blank; (B) opt-in suggestion from E-Counseling join/leave, clearly labeled
  and confirmed; (C) automatic prefill.
- **Provisional recommendation:** A for CENC-1 and CENC-2. Current UI/back-end treat scheduled times
  as reference only (`record-encounter-form.tsx:47-61,87-109`). C is forbidden by the proposal.
- **Owner:** GCO; Team; UX.
- **Blocker:** If B is ever desired, media/join provenance must be verified as reliable; no such
  contract exists.
- **Status:** **Open**.

## D-CENC-08 — Overdue documentation indicators

- **Proposal:** D08 (line 7800).
- **Question:** When should a completed Appointment with no Encounter appear for review? May staff
  record an administrative "No Counseling occurred" reason without fabricating attendance?
- **Options:** (A) no indicator in CENC-1; (B) derived per-Appointment hint; (C) scoped worklist plus
  optional reason.
- **Provisional recommendation:** A for CENC-1; B/C belong to CENC-4 after GCO defines eligibility
  and overdue rules. No persisted state and no automatic Encounter. Current code has no such
  projection (absence searches; `appointments/services.py:1808-1923`).
- **Owner:** GCO; GSS.
- **Blocker:** GCO definitions of "overdue", "administratively completed", and whether a
  no-session reason is allowed.
- **Status:** **Open**.

## D-CENC-09 — Wrong administrative completion

- **Proposal:** D09 (line 7801).
- **Question:** Who may review/amend a mistakenly completed Appointment without erasing audit
  history?
- **Options:** (A) separate incident/correction workflow with audit; (B) allow reopening with
  reason; (C) delete the completion.
- **Provisional recommendation:** A. C is explicitly out of scope (proposal line 7836). CENC-1
  performs no correction of administrative completion; a correction workflow is a later authorized
  slice.
- **Owner:** GCO; Privacy; Team.
- **Blocker:** no approved correction workflow; `CANCELLED`+Encounter legacy states need the same
  policy.
- **Status:** **Open**.

## D-CENC-10 — E-Counseling sequencing

- **Proposal:** D10 (line 7802).
- **Question:** Which actual provider room/access/capture states must finish before the business
  operation may safely complete?
- **Options:** (A) preserve the existing `OPEN` block and complete only after the access window
  closes; (B) also require room closure/capture reconciliation; (C) allow Finish while `OPEN`.
- **Provisional recommendation:** A for CENC-1. It reuses the verified Appointments rule
  (`appointments/services.py:1595-1602`). B needs a separately verified capture-state contract;
  C would bypass an existing safeguard and is forbidden by the proposal (line 6877).
- **Owner:** GCO; Team; E-Counseling operator.
- **Blocker:** GCO decision on whether B is required.
- **Status:** **Open**.

## D-CENC-11 — Existing conflicting Routine Interview

- **Proposal:** D11 (line 7803).
- **Question:** How should conflicting historical Routine links be presented and escalated, and who
  may approve corrections?
- **Options:** (A) reject Finish with a stable conflict and preserve the Routine; (B) allow Finish
  without linkage and surface the conflict separately; (C) auto-relink.
- **Provisional recommendation:** A for a finalized/conflicting Routine; otherwise Finish may record
  the Encounter without a link when no deterministic match exists. Never replace a link or finalize
  an Evaluation. The existing linker refuses replacement
  (`routine_interviews/services.py:1200-1252`) and silent mismatch skipping
  (`:1324-1357`) must not be misinterpreted as conflict resolution.
- **Owner:** GCO; Team.
- **Blocker:** GCO escalation path; no approved correction authority.
- **Status:** **Open**.

## D-CENC-12 — Feedback invitation timing

- **Proposal:** D12 (line 7804).
- **Question:** Is the existing immediate Encounter-generated feedback invitation acceptable when
  documentation is late, or are currentness/age constraints required?
- **Options:** (A) preserve current immediate invitation; (B) suppress or delay invitations for late
  documentation; (C) add an age limit.
- **Provisional recommendation:** A for CENC-1. It reuses the canonical producer once
  (`counseling/services.py:322-382`). B/C change Feedback policy and need GCO + Privacy approval.
- **Owner:** GCO; Privacy.
- **Blocker:** GCO decision; no existing age/currentness setting.
- **Status:** **Open**.

## D-CENC-13 — Post-Finish next steps

- **Proposal:** D13 (line 7805).
- **Question:** Should the UI invite Counselor Evaluation, Student Session Summary or Follow-Up
  actions contextually, and in what order?
- **Options:** (A) Encounter link only in CENC-1; (B) contextual links in CENC-2; (C) guided sequence
  including FUP.
- **Provisional recommendation:** A for CENC-1, B for CENC-2. C must remain optional and outside the
  transaction; FUP/FAC/CONT integration is a later slice.
- **Owner:** GCO; UX.
- **Blocker:** workflow approval.
- **Status:** **Open**.

## D-CENC-14 — Workload visibility

- **Proposal:** D14 (line 7806).
- **Question:** Should a scoped Needs Documentation view appear in Counseling, My Work or Appointment
  management, or is a contextual indicator enough?
- **Options:** (A) none in CENC-1; (B) contextual Appointment badge; (C) scoped worklist in CENC-4.
- **Provisional recommendation:** A for CENC-1; C eventually, scoped to the provider's own
  Appointments. No global Student listing.
- **Owner:** GCO; GSS; UX.
- **Blocker:** D-CENC-08 definitions.
- **Status:** **Open**.

## D-CENC-15 — Reporting

- **Proposal:** D15 (line 7807).
- **Question:** Does GCO need separate metrics for administrative completion, confirmed sessions and
  late documentation?
- **Options:** (A) no new metrics in CENC-1/2; (B) add aggregate metrics later; (C) per-Counselor
  dashboards.
- **Provisional recommendation:** A for the composed slice. Any later metric must avoid clinical
  content and must not label administrative completion as attendance.
- **Owner:** GCO; Team.
- **Blocker:** metric definitions and privacy review.
- **Status:** **Open**.

## D-CENC-16 — Authorization sufficiency

- **Proposal:** D16 (line 7808).
- **Question:** Are current Counselor/Appointment capabilities sufficient, or is one narrow new
  attestation capability justified?
- **Options:** (A) reuse `counseling.manage_assigned` + `appointments.manage` + provider identity;
  (B) add `counseling.finish_assigned`; (C) broaden to GSS.
- **Provisional recommendation:** A. The COUNSELOR grant already contains both capabilities
  (`accounts/policy.py:654-696`) and the Appointment provider check is record-level
  (`appointments/services.py:816-818`; `appointments/access.py:47-72`). B adds policy surface without
  a verified distinction; C contradicts D-CENC-02.
- **Owner:** Team; GCO security.
- **Blocker:** GCO confirmation that provider identity alone expresses the attestation rule.
- **Status:** **Open**.

## D-CENC-17 — Retention and corrections

- **Proposal:** D17 (line 7809).
- **Question:** What GCO/UCN policy applies to correction or retention of professionally documented
  Encounter times, especially after a finalized Evaluation or submitted Feedback?
- **Options:** (A) preserve current correction rules indefinitely; (B) add a correction window;
  (C) immutable after finalization/feedback.
- **Provisional recommendation:** A for CENC-1; Finish routes corrections to the existing
  `update_encounter`, which preserves finalized Routine/Feedback chronology constraints
  (`counseling/services.py:857-1046`; `feedback/services.py:288-339`). Any stricter policy is
  separate.
- **Owner:** GCO; Privacy.
- **Blocker:** retention schedule/approval.
- **Status:** **Open**.

## D-CENC-18 — User-copy approval

- **Proposal:** D18 (line 7810).
- **Question:** Is "Finish Counseling" the preferred label across in-person and Online sessions,
  including already-administratively-completed cases?
- **Options:** (A) `Finish Counseling` everywhere; (B) `Complete Counseling Appointment` for the
  reconciliation case; (C) different copy for Online.
- **Provisional recommendation:** A for the new action, with truthful branching confirmation text.
  Existing copy remains until CENC-2.
- **Owner:** GCO; UX.
- **Blocker:** copy review and accessibility.
- **Status:** **Open**.

## D-CENC-19 — Priority and UAT

- **Proposal:** D19 (line 7811).
- **Question:** Should core Finish ship before all CENC reconciliation/worklist enhancements?
- **Options:** (A) CENC-1 backend first, then CENC-2; (B) wait for the full worklist; (C) ship UI
  first.
- **Provisional recommendation:** A, matching the proposal's recommendation. C is unsafe because a
  frontend chain reproduces the partial-failure problem (proposal lines 7263–7265).
- **Owner:** Team; GCO.
- **Blocker:** GCO UAT scheduling; decisions D-CENC-01..16 for the specific path.
- **Status:** **Open**.

## D-CENC-20 — Audit interpretation

- **Proposal:** D20 (line 7812).
- **Question:** Does the office require explicit distinct audit wording for "Counselor-confirmed
  session" versus "Appointment administratively completed", beyond existing domain actions?
- **Options:** (A) reuse `appointment.completed` + `counseling.encounter.created` with minimal
  metadata; (B) add a `counseling.finish` correlation event; (C) add a separate completion reason
  field.
- **Provisional recommendation:** A for CENC-1; evaluate B if audit cannot distinguish a Finish
  completion from a legacy administrative completion. A `reason` field would be schema change and is
  not justified by the current audit.
- **Owner:** GCO; Privacy; Team.
- **Blocker:** GCO audit interpretation; CENC-1 must not claim distinct semantics without approval.
- **Status:** **Open**.

---

## Additional audit decisions

## D-CENC-21 — Appointment-linked Encounter with non-`APPOINTMENT` entry mode

- **Source:** CENC-0 finding; not in proposal §25.
- **Question:** Should an Appointment-linked Encounter be required to use
  `entry_mode=APPOINTMENT`, or is a `WALK_IN`/`CALLED_IN`/`REFERRED` Encounter legitimately linked
  to an Appointment?
- **Options:** (A) enforce `appointment_id → entry_mode=APPOINTMENT` in CENC-1 validation and
  correction; (B) keep the current one-directional rule and teach Counseling Context to accept any
  linked Encounter; (C) leave the state but reject Finish on it and route to correction.
- **Provisional recommendation:** C for CENC-1: Finish requires an exactly matching
  `entry_mode=APPOINTMENT` Encounter; existing mismatched records are not silently rewritten and are
  directed to the correction workflow. A/C differ on whether to tighten the correction API; a
  database check change would be a migration and needs separate approval.
- **Owner:** GCO; Team.
- **Blocker:** GCO meaning of entry mode; migration decision.
- **Status:** **Open**.

**Verified evidence:** `counseling/models.py:83-89`; `counseling/services.py:480-532,857-951`;
`context_access.py:60-82`; `routine_interviews/matching.py:57-62`;
`be/tests/test_counseling.py:794-827,831-862`.

## D-CENC-22 — Direct Student lookup scope

- **Source:** CENC-0 finding; not in proposal §25.
- **Question:** Should direct Encounter recording remain available for any active Student, or be
  scoped to the Counselor's College responsibility/current lifecycle?
- **Options:** (A) keep current unscoped lookup; (B) scope to operational College responsibility;
  (C) scope to current students only; (D) require an existing Appointment/Routine context for all
  Encounter creation.
- **Provisional recommendation:** Do **not** change in CENC-1. Record the gap, and schedule a
  separate privacy/authorization slice because changing direct access affects Walk-in/Called-in/
  Referred workflows and the proposal explicitly preserves them (line 6673). Any future scope must
  be verified against GCO policy rather than guessed.
- **Owner:** GCO; Privacy; Team.
- **Blocker:** GCO policy for direct Counseling and Student search.
- **Status:** **Open**.

**Verified evidence:** `counseling/services.py:796-812`; `counseling/api.py:443-473`;
`be/tests/test_counseling.py:1196-1265`.
