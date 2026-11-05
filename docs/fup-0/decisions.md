# Decision register — D-FUP-01 through D-FUP-07

**Status of every decision: Open.**
No GCO, UCN, privacy, records, FAC, CONT or SAR authority has approved any option below. Technical
behavior described here is current implementation evidence, not an institutional decision. The
provisional recommendations are audit proposals only.

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.

## 1. How to read this register

Each decision records:

- the policy question;
- why the current code cannot answer it;
- viable options and consequences;
- a **provisional** recommendation (not adopted);
- accountable owner role;
- what the decision blocks;
- current status.

The proposal contains 22 broader open questions (proposal lines 6493-6518). They are not adopted here.
D-FUP-01..07 are the narrower decisions that block FUP-1/FUP-2 or the cross-proposal slices. Where a
proposal question maps to a D-FUP item, the mapping is noted.

---

## D-FUP-01 — Pending operational task when its Referral is voided

**Question:** When a live Referral is voided, what must happen to an independently owned,
`OPERATIONAL`, `PENDING` Follow-Up that references it?

**Current behavior (Verified):** the task survives unchanged. It remains in the assignee's list,
report and My Work; it can be updated, reassigned, completed and cancelled. Only the related-record
panel changes: `source` becomes `null`, `source_unavailable` is `true`, and the copy says the related
record is no longer available (`policy.py:162-168`; `services.py:268-283`; `api.py:253-263`;
`followups-detail.tsx:108`). No review is recorded, and no Follow-Up event or audit is written when the
Referral is voided (`referrals/services.py:896-940`). The source-page context panel disappears
(`followups-context.tsx:18-21`).

**Options:**

| Option | Meaning | Consequence | Assessment |
|---|---|---|---|
| A. Preserve + truthful projection, review encouraged | Keep the task; show source unavailable consistently; no mandatory gate | Minimal change; relies on staff judgment; cannot prove review occurred | **Provisional recommendation for FUP-1** |
| B. Preserve + mandatory server-enforced review | Add a review decision (actor/time/outcome) that must exist before completion/cancel or before further work | Stronger evidence; needs new state/event/API or a defined existing-event convention; more UX | Recommended **only if GCO requires proof of review** |
| C. Auto-cancel on void | Referral void terminates the task | Violates "no silent auto-closure"; destroys independent work; historical task becomes terminal without human decision | **Not recommended** |
| D. Auto-hide from list/report | Task remains in database but disappears | Conceals pending work; still blocks reporting; worse than current | **Not recommended** |
| E. Relink to a replacement Referral | Move source identity | Rewrites provenance; needs source-validation and audit; no replacement workflow exists | **Out of FUP-1**; separate decision if needed |

**Provisional recommendation (not adopted): Option A**, with a visible but non-alarming review prompt
and a test proving list/report/My Work/mutation behavior. If GCO requires a mandatory gate, choose B
and add persistence deliberately; do not fake a review with an activity note.

**Why the code cannot answer it:** operational authorization intentionally does not recheck the source
(`policy.py:167-168`). This is a policy choice, not an oversight; changing it would change who can
complete tasks.

**Owner:** GCO (operational workflow); privacy/records for retention implications of the source link.

**Blocks:** FUP-1; UAT-FUP-10/11/13.

**Status:** **Open**. Evidence needed: GCO decision on review timing and authority, plus the approved
list/detail wording.

---

## D-FUP-02 — Confidential task when the source Counselor is unavailable

**Question:** A `COUNSELOR_CONFIDENTIAL` task exists, but its original Counselor is unavailable or no
longer meets source access. Who, if anyone, may read, own, reassign, complete or cancel it?

**Current behavior (Verified):**

- Confidential detail/mutation requires the current assignee to be a `COUNSELOR` with the relevant
  source capability and the source relationship (`policy.py:162-183`).
- A different Counselor cannot pass `require_assignee` because the source's `counselor_id` must equal
  the candidate (`policy.py:144-156`; `policy.py:51-97`).
- `recovery_queryset` is `OPERATIONAL` only (`recovery.py:51-56`).
- Head designation adds no Follow-Up capability and no confidential source access
  (`accounts/policy.py:761-795`; test `:705-730`).
- There is no continuity adapter (`policy.py` has no grant branch; static search of
  `be/compass/counseling` for `guidance_followup` found nothing).

**Consequence (Inferred):** a confidential task can become an inaccessible `PENDING` orphan. It
remains in the database, but nobody can list, reassign, complete or cancel it. The assignee cannot
dispose of it, and no admin route exists.

**Options:**

| Option | Meaning | Consequence | Assessment |
|---|---|---|---|
| A. No transfer; await the original Counselor or a separate administrative disposition | Current behavior | Safest confidentiality; hidden pending work; no resolution path | Current state, not sufficient long-term |
| B. CONT-approved, source-scoped, time-bound coverage **plus** a separate task-ownership authority | Receiving Counselor can read selected records and optionally accept/own tasks under an explicit grant | Aligns with CONT; requires real provider, source adapter, task authority, revocation, audit | **Provisional recommendation after CONT approval** |
| C. Downgrade to operational | Make it visible to GSS/other staff | Leaks professional context; explicitly forbidden by current classification | **Reject** |
| D. Head/acting-Head blanket override | Designation grants access | Bypasses clinical confidentiality; violates CONT boundary | **Reject** |
| E. Operational recovery of confidential rows | Reassign without source access | Grants task control without source context; leaks existence/assignment | **Reject** |

**Provisional recommendation (not adopted):** keep the current deny as the interim rule. If GCO and
CONT approve coverage, implement **B** with separate authorities for read, accept/own, create and
reassign. A read grant alone must not permit mutation (`docs/cont-0/source-record-policy.md:21`;
`docs/cont-0/README.md:24`).

**Owner:** GCO, CONT/privacy owners, source-domain owners (Counseling/Routine).

**Blocks:** FUP-3B; UAT-FUP-15. It does **not** need to block a projection-only FUP-1.

**Status:** **Open**. Evidence needed: CONT D01–D18 disposition, a real provider, a source-read
adapter, a task-coverage policy, revocation/expiry tests, and a decision on retained orphan tasks.

---

## D-FUP-03 — Meaning and persistence of "further action"

**Question:** After completing one Follow-Up, how should staff record that another action is needed,
and does that decision need durable structure?

**Current behavior (Verified):** completion takes only an encrypted outcome; it is terminal. There is
no next-action classification, no predecessor/successor link, no automatic creation, and no UI control
(`services.py:391-417`; `models.py:45-94`; `followups-detail.tsx:86-104`).

**Options:**

| Option | Meaning | Consequence | Assessment |
|---|---|---|---|
| A. UI-only prompt + explicit "Create another follow-up" | After completion, show a question/affordance; reuse the existing create form with Student/source prefilled; user confirms a new task | No schema; preserves independence; no searchable further-action metric | **Provisional recommendation** |
| B. UI-only three-choice Yes/No/To be determined, not persisted | Capture intent in the interaction only | No audit/report evidence; may imply a decision that is not stored | Acceptable if GCO does not need reporting |
| C. Persist a small disposition enum on completion | Searchable `NO_FURTHER_ACTION` / `FURTHER_ACTION_RECOMMENDED` / `MONITORING_ONGOING` | New field/migration; must not imply effectiveness; needs reporting rules | Only if GCO has a real decision/report use |
| D. Add `predecessor_followup_id` | Durable chain between tasks | Same-Student/source validation, cycle prevention, audit, permissions; more complexity | Only if traceability is required |
| E. Effectiveness/outcome score | Clinical judgment | Outside this domain; unsafe | **Reject** |

**Provisional recommendation (not adopted): Option A.** If GCO needs a metric, use C; if it needs
chain traceability, use D as a separate change. Do not bundle C/D into FUP-2 by default.

**Owner:** GCO.

**Blocks:** FUP-2; UAT-FUP-16.

**Status:** **Open**. Evidence needed: GCO answer to proposal questions 8–10 (lines 6500-6504),
including whether completion should offer a next-task action and whether a durable link is required.

---

## D-FUP-04 — Who may initiate a next Follow-Up

**Question:** After a task is completed (or while one is pending), who may create the next task?

**Current behavior (Verified):** creation requires `guidance_followups.manage`; a linked source
requires manage-level source access; a source-free task requires operational scope; confidential
creation requires the assignee to be the creating source Counselor (`services.py:127-208`;
`policy.py:138-159`). There is no "create from completed task" route, so this authority is only
exercised through the ordinary create form.

**Options:**

| Option | Meaning | Consequence | Assessment |
|---|---|---|---|
| A. Current assignee with manage + current source/Student access | The person who did the work can plan the next step | Aligns with existing permissions; no new authority | **Provisional recommendation** |
| B. Any manager in scope | Any eligible staff member can create a next task for the Student | Wider coordination; may duplicate or reassign responsibility | Acceptable only with explicit GCO rule |
| C. Head only | Head controls continuation | Slows routine work; Head is not always the clinician | **Not recommended for all tasks** |
| D. Source owner only for confidential | Preserve professional continuity | Consistent with confidentiality; may block legitimate handoff | Correct for confidential; CONT still governs transfer |
| E. Faculty/Student/creator outside scope | External initiation | Privacy/authority violation | **Reject** |

**Provisional recommendation (not adopted):** **A** for operational tasks; **D** for confidential
tasks (the source-authorized Counselor), with CONT-approved coverage only when D-FUP-02 is decided.
Do not let a completed task's former assignee create a confidential successor after losing source
access.

**Owner:** GCO.

**Blocks:** FUP-2; UAT-FUP-16.

**Status:** **Open**. Evidence needed: GCO confirmation of initiation authority and whether the
completing assignee can always create the next task.

---

## D-FUP-05 — Completion never closes a Referral; voiding never silently closes a Follow-Up

**Question:** Confirm the two cross-domain invariants:

1. A Follow-Up completion/cancellation must not change Referral status, administrative state or
   actions.
2. A Referral void/administrative closure must not silently complete, cancel or delete a Follow-Up.

**Current behavior (Verified):**

- Follow-Up services never write Referral rows; `complete_followup` and `cancel_followup` update only
  the Follow-Up and event (`services.py:391-463`).
- Referral `void_referral` never calls Follow-Up services (`referrals/services.py:896-940`); no
  `guidance_followup` reference exists in `be/compass/referrals`.
- Referral-linked tasks store only source kind/id; no Referral status is copied into the task.
- Administrative closure fields and state exist (`referrals/models.py:109-125`;
  `administrative_state.py:7-19`), but no Follow-Up code reads them.

**Options:** confirm both invariants, or authorize a specific exception. An exception must name the
event, actor, timing, evidence and reversal path; a generic "auto-close" is not acceptable.

**Provisional recommendation (not adopted):** **affirm both invariants** and require any future
closure automation to be a separately approved deterministic policy with its own audit. If GCO wants
to warn on Referral closure while tasks remain pending, make it a read-only warning, not a mutation.

**Owner:** GCO and Referral domain owner; UCN/QMS if the Referral form/closure meaning is affected.

**Blocks:** FUP-1 (review design), FUP-3A (FAC closure), UAT-FUP-17.

**Status:** **Open**, but high-confidence invariant; no code change is needed to preserve it.

---

## D-FUP-06 — Notification behavior for continued or source-invalidated work

**Question:** When a task is completed and a next task is created, or when a source becomes
unavailable, who should be notified and through which channel?

**Current behavior (Verified):**

- Notification events exist only for `FOLLOWUP_ASSIGNED`, `FOLLOWUP_REASSIGNED` and
  `FOLLOWUP_DUE_CHANGED` (`notifications/policy.py:42-44`).
- Only the latest material event per current authorized pending task is current
  (`integration.py:57-84`).
- Activity, completion, cancellation and source changes emit no Follow-Up notification.
- External email/push is disabled by default (`be/config/settings.py:719`); in-app remains.
- Realtime hints go to current and old assignee; notification only to current assignee
  (`integration.py:96-123`).
- No Student/Faculty notification exists.

**Options:**

| Option | Meaning | Consequence | Assessment |
|---|---|---|---|
| A. No new notification | Rely on list/My Work | Quiet; staff may miss a created next task | Acceptable only if creation is an explicit user action with immediate UI feedback |
| B. In-app notification on next-task assignment | Reuse existing assignment event | Consistent; no new event type; respects current policy | **Provisional recommendation** |
| C. Email/push for next-task assignment | External delivery | Depends on the flag and NOTIF policy; content must stay minimal | Only after NOTIF/GCO approval |
| D. Notify on source invalidation | Tell the assignee the source changed | New event/trigger; must not leak source content | Separate decision; useful with D-FUP-01 Option B |
| E. Notify Student/Faculty | Externalize task status | Privacy violation | **Reject** |

**Provisional recommendation (not adopted):** **B** for a newly created successor task, using the
existing assignment event and currentness rules. No source-change notification in FUP-1 unless GCO
chooses D-FUP-01 Option B. Keep email off until the NOTIF proposal and GCO approve.

**Owner:** GCO with NOTIF/notifications owner.

**Blocks:** FUP-2 notification scope; UAT-FUP-16/19.

**Status:** **Open**. Evidence needed: GCO channel decision and approved wording; no new event should
be added before that.

---

## D-FUP-07 — GCO sign-off of task meanings and UAT journeys

**Question:** Does GCO approve the proposed meaning table, user-facing copy and UAT journeys that
define what staff are attesting when they create, complete or cancel a Follow-Up?

**Current state:** no approval exists. The current UI already uses "complete", "cancel", "outcome" and
"reason", but the institutional meaning of those words and the accepted UAT evidence are not recorded
in this repository. The proposal's 45 scenarios are suggestions (proposal lines 6417-6467), not
approved tests.

**What must be approved:**

1. The term table in `ux-journeys.md` §3 (Follow-Up, Completed, Cancelled, Source unavailable, Review,
   Further action, Referral administratively closed).
2. Which UAT journeys are current behavior and which are blocked/future (FAC/CONT/SAR).
3. The exact completion/cancellation/recovery copy and the "no Student contact" statement.
4. The authority to review and dispose of invalid-source tasks (D-FUP-01/D-FUP-04).
5. Whether completion alone is accepted as the documented action, or category-specific evidence is
   required.
6. The evidence GCO will retain: task ID, event history, audit, source state, UAT screenshots, and
   approvals.

**Provisional recommendation (not adopted):** approve the meanings and current-behavior journeys
before FUP-1, record named accountable owners and dates, and mark FAC/CONT/SAR journeys as
**blocked/future** until their own approvals. Do not treat a code-path demonstration as UAT.

**Owner:** GCO; UCN/QMS or privacy/records where the wording affects institutional records.

**Blocks:** FUP-0 closure; FUP-1; FUP-2; any claim that a UAT journey passed.

**Status:** **Open**.

---

## 2. Decision-to-slice map

| Decision | FUP-1 | FUP-2 | FUP-3A | FUP-3B | FUP-3C |
|---|---|---|---|---|---|
| D-FUP-01 | **Blocks** | — | — | — | — |
| D-FUP-02 | Not required (must not bypass) | — | — | **Blocks** | — |
| D-FUP-03 | — | **Blocks** | — | — | — |
| D-FUP-04 | — | **Blocks** | — | — | — |
| D-FUP-05 | **Blocks** review/closure rules | — | **Blocks** closure claims | — | — |
| D-FUP-06 | — | **Blocks** notification scope | — | — | — |
| D-FUP-07 | **Blocks** | **Blocks** | — | — | — |

## 3. Proposal decisions not adopted by FUP-0

The proposal lists 22 questions (lines 6493-6518). None is answered here. The most relevant groupings:

| Proposal questions | FUP-0 treatment |
|---|---|
| 1–4: what a Follow-Up is, creation trigger, Referral-to-task convention, void timing | D-FUP-01/07; new GCO policy needed |
| 5–7: review responsibility, automatic cancellation, completion evidence | D-FUP-01/04/07 |
| 8–10: further-action classification, effectiveness, continued monitoring | D-FUP-03 |
| 11–13: recurrence, seven-day threshold, external reminders | D-FUP-06; FUP-2 only if approved |
| 14–15: Referral administrative closure and Faculty labels | FAC-D6/FAC-D7; D-FUP-05 |
| 16–18: continuity delegation, Head authority, staff role naming | D-FUP-02; CONT |
| 19: SAR transfer reassessment | FUP-3C verification; UAT-FUP-20 |
| 20–21: reporting and retention | GCO/privacy/records; not FUP-1 |
| 22: implementation minimum | Confirmed technically: FUP-1/FUP-2 can be projection/UX/service-policy without schema if D-FUP-01/03 choose the minimal options; any persistence is a separate decision |

## 4. Sign-off block (to be completed by the institution)

| Field | Value |
|---|---|
| Decision ID | |
| Approved option | |
| Accountable owner (name/role) | |
| Approval evidence/reference | |
| Effective date | |
| Review/expiry date | |
| Scope/conditions | |
| Withdrawal procedure | |
| Signature/attestation | |

**The table is intentionally blank.** No typed name, inserted Audit row, capability grant, passing
test or environment switch is a substitute for an actual institutional approval.
