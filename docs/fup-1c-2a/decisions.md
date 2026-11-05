# FUP-1C + FUP-2A decision record

**Every entry in this file is Provisional — pending GCO.**
No decision below is adopted, approved or ratified by GCO, UCN, privacy, records or any institutional
authority. D-FUP-01, D-FUP-03 and D-FUP-07 remain **Open** in
[`../fup-0/decisions.md`](../fup-0/decisions.md). This file records the engineering defaults and
proposed wording used for review; it does not convert them into institutional decisions.

## D-FUP-01 — Pending operational task when its source becomes unavailable

**Status:** **Provisional — pending GCO.**
**Implemented default:** **Option A — preserve the task, project availability truthfully, guide review
through copy.**
**Not implemented:** Option B (server-enforced review before completion, cancellation or further work).

### What FUP-1C does

- Keeps the operational Follow-Up open, assigned and independently owned when its Referral is voided.
- Adds `source_unavailable: bool` to the list summary so the task can show that its related record is
  no longer readable without exposing source identity.
- Shows the same value on detail and list for the same actor and task, computed through one shared
  visibility rule.
- Renders a muted `Related record unavailable` line in the list Status cell.
- Leaves the row fully actionable: no new button, filter or automatic action.
- Keeps the report aggregate-only and adds explanatory copy rather than a source counter.

### What FUP-1C deliberately does not do

- It does not record that a reviewer considered whether the work is still needed.
- It does not require a review before completion, cancellation or further work.
- It does not prove that review occurred; it only keeps the state legible.
- It does not add a review state, event, API field beyond the boolean projection, or migration.

### Why this is provisional

Option A remains the smallest reversible default consistent with existing behavior. The new boolean is
a projection of an existing authorization outcome, not a new policy or authority. GCO has not decided
whether proof of review is required.

**Owner:** GCO.
**Evidence needed before adoption:** GCO decision between Option A and Option B; if Option B, an
approved review record, enforcement point, retention rule and UAT evidence.
**Rollback:** remove the list/report copy and the boolean projection; the four tests are additive.

## D-FUP-03 — Meaning and persistence of "further action"

**Status:** **Provisional — pending GCO.**
**Implemented default:** **guidance-only copy; no persistence.**
**Not implemented:** a Yes/No/To-be-determined disposition; a persisted
`NO_FURTHER_ACTION`/`FURTHER_ACTION_RECOMMENDED`/`MONITORING_ONGOING` field; a predecessor/successor
link; an automatic next-task creation; a "Create next follow-up" control.

### What FUP-2A does

- Explains that completing a follow-up ends that task and does not close the related record.
- Explains that if more work is needed, a new follow-up should be created.
- Places the detail copy after the recorded completion outcome and the Help copy in a dedicated
  section.
- Adds no field, endpoint, event, action, link or schema.

### What FUP-2A deliberately does not do

- It does not ask for or store a further-action decision.
- It does not create or link a successor follow-up.
- It does not measure further action or effectiveness.
- It does not imply that a new follow-up is required or that completion closes the related record.

### Why this is provisional

Guidance-only copy is the minimal default that does not invent persistence or a workflow before GCO
decides whether a durable further-action record is needed. The copy is proposed wording for review,
not an approved policy statement.

**Owner:** GCO.
**Evidence needed before adoption:** GCO answer on whether completion should offer a next-task action
and whether a durable link or disposition is required; if yes, a separate approved schema/workflow
slice.
**Rollback:** remove the two copy additions; no data or contract change is involved.

## D-FUP-07 — GCO sign-off of task meanings and UAT journeys

**Status:** **Provisional — pending GCO.**
**Approved copy:** none. The strings below are **proposed wording**, implemented for review.

### Proposed wording implemented in this slice

List indicator, Status cell:

> Related record unavailable

Report, under Workload:

> Source availability is shown on each follow-up. This report counts only follow-ups you can access
> and does not include related-record details.

Detail, Completion outcome:

> Completing this follow-up ends this task. It does not close the related record. If more work is
> needed, create a new follow-up.

Help section heading:

> Completion and further action

Help section content:

> Completing a follow-up ends that task. It does not close the related record. If more work is needed,
> create a new follow-up.

### What remains unapproved

- The meaning table and UAT journeys in [`../fup-0/ux-journeys.md`](../fup-0/ux-journeys.md).
- Whether the list indicator wording is the institutionally preferred description of an unavailable
  related record.
- Whether completion alone is accepted as the documented action or category-specific evidence is
  required.
- Which UAT journeys are current, blocked or future, and the evidence GCO will retain.
- Any statement that a UAT journey passed.

The backend and browser checks in this package are engineering regression evidence, not UAT or
institutional acceptance.

**Owner:** GCO; UCN/QMS or privacy/records where wording affects institutional records.
**Evidence needed before adoption:** named GCO approver, decision date, approved wording and mapping of
approved UAT journeys.

## Decisions not touched

No other D-FUP item is decided, narrowed or implied by this slice. FUP-1D, FUP-2B, FUP-2C and FUP-3
were not implemented.
