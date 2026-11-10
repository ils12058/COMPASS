> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-2B + FUP-3A decision record

**Every entry in this file is Provisional — pending GCO/FAC.**
No decision below is adopted, approved or ratified by GCO, UCN, FAC, privacy, records or any
institutional authority. D-FUP-03, D-FUP-04, D-FUP-05 and D-FUP-07 remain **Open** in
[`../fup-0/decisions.md`](../fup-0/decisions.md). FAC-D1–D8 remain unresolved in
[`../fac-5/institutional-decisions.md`](../fac-5/institutional-decisions.md). This file records the
engineering defaults used for review; it does not convert them into institutional decisions.

## D-FUP-03 — Meaning and persistence of "further action"

**Status:** **Provisional — pending GCO.**
**Implemented default:** **UI-only prompt and explicit navigation to the existing create form.**
**Not implemented:** a persisted `NO_FURTHER_ACTION` / `FURTHER_ACTION_RECOMMENDED` /
`MONITORING_ONGOING` disposition; a predecessor/successor link; automatic creation; an
effectiveness score.

### What FUP-2B does

- Shows one `What happens next` panel on a completed, manageable Follow-Up.
- Explains that a new task is separate, has its own responsible staff member and due date, and does
  not reopen the completed task or change the related record.
- Offers one secondary navigation link, `Create next follow-up`, to the existing create page.
- Carries only the readable source kind/id or the standalone Student identity; the user completes
  the ordinary create form and chooses the assignee and due date.

### What FUP-2B deliberately does not do

- It does not record that further action is needed, recommended or declined.
- It does not link the completed task to the new task as predecessor/successor.
- It does not create, assign, schedule or reopen anything by itself.
- It does not measure whether further action occurred or was effective.
- It does not claim that the new task is required.

### Why this is provisional

Option A remains the smallest reversible default consistent with existing behavior. The completion
and create services already exist; the new link is a shortcut, not a new workflow or authority.
GCO has not decided whether a durable further-action record or a formal chain is required.

**Owner:** GCO.
**Evidence needed before adoption:** GCO answer on whether completion should offer a next-task
action and whether a durable link or disposition is required; if yes, a separate approved
schema/workflow slice.
**Rollback:** remove the detail panel, Help section and URL helper; the tests are additive and no
data or contract change is involved.

## D-FUP-04 — Who may initiate a next Follow-Up

**Status:** **Provisional — pending GCO.**
**Implemented default:** **existing create authorization, unchanged.**
**Not implemented:** a new "create from completed task" authority, any manager-only rule, any
source-owner-only rule beyond the existing source checks, or any Faculty/Student initiation.

### What FUP-2B does

- Shows the link only when `followupAccess(user).manage` is true and the task is `COMPLETED`.
- Sends the user to the ordinary create page, which re-checks authorization server-side.
- Does not preselect, hide or lock an assignee.
- With a readable source, the existing create context derives the category and confidentiality from
  the live source and enforces the existing confidential-assignee rule.
- Without a readable source, the create page starts a standalone operational task; it does not
  inherit `COUNSELOR_CONFIDENTIAL`.

### What FUP-2B deliberately does not do

- It does not widen who may create, assign or read a Follow-Up.
- It does not let a former assignee retain confidential access after the source becomes
  unreadable; the confidential classification is not carried through the standalone link.
- It does not let Faculty or Students create or see Follow-Ups.

### Why this is provisional

The existing create authority is already the narrowest coherent default. Linking from a completed
task does not change it. GCO has not confirmed whether the completing assignee must always be the
initiator or whether another manager in scope may continue the work.

**Owner:** GCO.
**Evidence needed before adoption:** GCO confirmation of initiation authority for operational and
confidential tasks, including handoff/coverage rules.
**Rollback:** remove the link; no authorization code changed.

## D-FUP-05 — Completion never closes a Referral; voiding never silently closes a Follow-Up

**Status:** **Provisional — pending GCO.**
**Implemented default:** **affirm both invariants; no automatic action in either direction.**

### What FUP-3A proves

- Completing a Referral-linked Follow-Up updates only that Follow-Up; the Referral's state,
  administrative fields, timestamps and Referral-targeted Audit events are unchanged.
- Voiding a Referral leaves linked Follow-Ups open, assigned and independently owned; their status,
  assignee, source storage, version and timestamps are unchanged.
- The Follow-Up detail then returns `source: null` and `source_unavailable: true`; the assigned user
  still sees the task in their list.
- No ReferralAction is created in either direction.

### What FUP-3A deliberately does not do

- It does not add a warning, prompt or review gate before completion or cancellation (FUP-1D is not
  implemented).
- It does not automatically complete, cancel, relink or delete a Follow-Up when a Referral is
  voided or closed.
- It does not automatically close a Referral when its linked Follow-Ups are completed.

### Why this is provisional

The invariants are the high-confidence default recorded in D-FUP-05, but GCO and the Referral
domain owner have not formally confirmed them or decided whether a read-only closure warning is
wanted.

**Owner:** GCO and Referral domain owner; UCN/QMS if Referral meaning is affected.
**Evidence needed before adoption:** confirmation of both invariants and any approved read-only
warning, with no mutation.
**Rollback:** no production behavior changed; the journey test is additive.

## FAC-D1–FAC-D8 — provisional provider exposure

All eight institutional decisions remain **pending**. The code-owned provisional policies make the
journey available by default, but they answer none of the institutional questions below.

| Decision | Provisional behavior in FUP-3A | Remains pending |
|---|---|---|
| FAC-D1 — digital form and signature authority | Submission uses the existing canonical `UCN-OP-GCO-01F3` revision `1` schema `1` and `UCN_F3_DIGITAL_CAPTURE_V1`; no typed name is treated as a signature | Whether the digital form is an authorized institutional Referral Slip; exact capture, signature/attestation and rendering; source PDF treatment |
| FAC-D2 — eligible Faculty identity | Scope is all active `FACULTY` accounts; the existing submission service still requires an active managed home | Temporary, dual-capacity, delegated and College-less Faculty; the authoritative eligibility source and removal rules |
| FAC-D3 — exact Student confirmation and disclosure | Exact normalized institutional identifier, 300-second ticket, 10 actor / 30 IP attempts per 300 seconds, display name only | Approved identifier/display fields, signed-reference metadata disclosure, abuse response and incident ownership |
| FAC-D4 — Student placement and intake routing | Student College scope is the current active Colleges; the existing placement resolver is unchanged | Authoritative placement source, conflict/transfer handling and approved triage ownership; no second placement writer |
| FAC-D5 — GCO acknowledgment | Explicit receipt by an eligible Counselor or Guidance Services Staff member in current Student College scope; existing server time/actor and Audit | Whether the receipt meaning and `received_at` use are approved; exact responsible actors/Colleges and Faculty wording |
| FAC-D6 — administrative closure | Explicit closure by an eligible Counselor or Guidance Services Staff member with `obligations_reviewed=true`; linked Follow-Ups retain their lifecycles | Actual completion criteria, closer eligibility, attestation wording, linked-task exceptions and retention |
| FAC-D7 — tracking, exceptions and retention | Three-stage disclosure for acknowledged submissions only; existing minimal own projection; voided Referral returns 404 | Exact field/exception allowlist, retention/custody, continued eligibility and any separate Faculty PDF authority |
| FAC-D8 — notifications | **Inactive.** `get_approved_faculty_notice_policy()` returns `None`; no producer, catalog entry, channel or delivery | Event/recipient/channel approval, minimum content, currentness, deduplication and withdrawal semantics |

The provisional metadata records `decision=PROVISIONAL` and
`authority=CODE_OWNED_PENDING_INSTITUTIONAL_APPROVAL`. It is not an approval reference, signature,
official policy or UAT result. A future approved adapter must resolve actual institutional evidence
and its matching `APPROVED` Audit decision; it cannot reuse the provisional rows.

## D-FUP-07 — GCO sign-off of task meanings and UAT journeys

**Status:** **Provisional — pending GCO.**
**Approved copy:** none. The strings below are **proposed wording**, implemented for review.

### Proposed wording implemented in this slice

Completed detail panel title:

> What happens next

Completed detail panel body:

> Create a new task when more work is needed. It gets its own responsible staff member and due date.
> It does not reopen this follow-up or change the related record.

Completed detail action label:

> Create next follow-up

Help heading:

> Creating the next follow-up

Help content:

> The next follow-up is a separate task with its own responsible staff member and due date. When
> the related record is still available, the new task is linked to it and takes its classification
> from that record. When the related record is unavailable, the new task is created without a link
> and does not inherit the earlier task's confidential classification.

### What remains unapproved

- The meaning table and UAT journeys in [`../fup-0/ux-journeys.md`](../fup-0/ux-journeys.md).
- Whether "Create next follow-up" is the institutionally preferred action label.
- Whether the action should be limited to the completing assignee rather than every manager whose
  scope includes the task (the current provisional default is `manage` plus `COMPLETED`).
- Whether completion alone is accepted as the documented action or category-specific evidence is
  required.
- Which UAT journeys are current, blocked or future, and the evidence GCO will retain.
- Any statement that a UAT journey passed.

The backend and browser checks in this package are engineering regression evidence, not UAT or
institutional acceptance.

**Owner:** GCO; UCN/QMS or privacy/records where wording affects institutional records.
**Evidence needed before adoption:** named GCO approver, decision date, approved wording and mapping
of approved UAT journeys.

## Decisions not touched

No other D-FUP item is decided, narrowed or implied by this slice. D-FUP-01 (review gate), D-FUP-02
(coverage), D-FUP-06 (notification behavior), FUP-1D, FUP-2C, FUP-3B, FUP-3C and FUP-4 were not
implemented. The existing Follow-Up assignment notifications are unchanged and are not a Referral
notice.
