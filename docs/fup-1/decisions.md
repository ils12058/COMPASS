# FUP-1 decision record

**Every entry in this file is Provisional — pending GCO.**
No decision below is adopted, approved or ratified by GCO, UCN, privacy, records or any institutional
authority. D-FUP-01 and D-FUP-07 remain **Open** in [`../fup-0/decisions.md`](../fup-0/decisions.md).
This file records the engineering default used for FUP-1 and the copy proposed for review; it does not
convert either into an institutional decision.

## D-FUP-01 — Pending operational task when its Referral is voided

**Status:** **Provisional — pending GCO.**
**Implemented option:** **Option A — preserve the task and project truthfully; review encouraged.**
**Not implemented:** Option B (server-enforced review before completion/cancellation or further work).

### What FUP-1 does

- Keeps the operational Follow-Up open and independently owned when its Referral is voided.
- Keeps the task in the assignee's ordinary list, report, My Work and notification currentness rules.
- Returns `source: null` and `source_unavailable: true` on detail; the task remains actionable.
- Renders the proposed source-unavailable explanation on detail.
- Writes no Follow-Up event or Follow-Up audit when the source is voided.
- Does not auto-close, auto-hide, relink or reassign the task.

### What FUP-1 deliberately does not do

- It does not record that a reviewer considered whether the work is still needed.
- It does not require a review before completion or cancellation.
- It does not prove that review occurred; it only encourages it in copy.
- It does not add a review state, event, API field or migration.

### Why this is provisional

Option A is the smallest reversible engineering default consistent with current behavior. It avoids
inventing a review record or enforcement rule before GCO decides whether proof of review is required.
The characterization tests lock current behavior so a later Option B decision has a stable baseline.

**Owner:** GCO.
**Evidence needed before adoption:** GCO decision between Option A and Option B; if Option B, a
GCO-approved review record, enforcement point, retention rule and UAT evidence.
**Rollback:** revert the copy and browser-test changes; the six tests are additive.

## D-FUP-07 — GCO sign-off of task meanings and UAT journeys

**Status:** **Provisional — pending GCO.**
**Approved copy:** none. The strings below are **proposed wording**, implemented for review.

### Proposed wording implemented in FUP-1

Detail, `source_unavailable` branch:

> The related record is no longer available to your account. This follow-up remains open and keeps its
> own status. Review whether the work is still needed. Completing or cancelling it records your reason
> but does not change the related record.

Source-page context panel, error branch:

> Linked follow-ups are not available for this record.

Help section, "When a related record becomes unavailable":

> The follow-up keeps its own status and remains independently owned. Only the link to the related
> record becomes unavailable. Completing or cancelling the follow-up records your decision and does
> not change the related record.

### What remains unapproved

- The meaning table and UAT journeys in [`../fup-0/ux-journeys.md`](../fup-0/ux-journeys.md).
- Whether completion alone is accepted as the documented action or category-specific evidence is
  required.
- Which UAT journeys are current, blocked or future.
- The evidence GCO will retain.
- Any statement that a UAT journey passed.

The browser and backend checks in this package are engineering regression evidence, not UAT or
institutional acceptance.

**Owner:** GCO; UCN/QMS or privacy/records where wording affects institutional records.
**Evidence needed before adoption:** named GCO approver, decision date, approved wording and mapping of
approved UAT journeys.

## Decisions not touched

No other D-FUP item is decided, narrowed or implied by FUP-1. FUP-1C, FUP-1D, FUP-2 and FUP-3 were
not implemented.
