# Risk register — FUP-0

**Audit base:** `integration/ux15-modernization` at `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`,
2026-11-05.
**Claim labels:** **Verified** = static evidence with `path:line`; **Inferred** = reasoned from verified
code; **Unknown** = evidence or command still required. No test, database query, dev server or
deployment was executed.
**Likelihood and impact are audit judgments, not measurements.** No population data, incident history
or live task volume was inspected. Frequencies are **Unknown**.

This register covers two risk classes:

- **Current-state risk** — the behavior exists at HEAD and can affect staff or Students today.
- **Implementation risk** — a foreseeable failure mode of FUP-1/FUP-2/FUP-3 if the decisions in
  [`decisions.md`](decisions.md) are skipped or misapplied.

## Heat summary

| ID | Risk | Class | Likelihood | Impact | Owner | Primary decision |
|---|---|---|---|---|---|---|
| R-FUP-01 | Operational task survives Referral void with no recorded review | Current | High (deterministic) | Medium | GCO | D-FUP-01 |
| R-FUP-02 | Confidential task becomes an inaccessible, unclosable orphan | Current | Medium | High | GCO + privacy | D-FUP-02 |
| R-FUP-03 | Source UUID/filter treated as authorization | Current + implementation | Medium | High | Engineering + privacy | D-FUP-01/02 |
| R-FUP-04 | Head designation mistaken for global Follow-Up authority | Current + implementation | Medium | Medium | GCO | — |
| R-FUP-05 | "Further action" implemented as auto-created or duplicated task | Implementation | Medium | Medium-High | GCO + engineering | D-FUP-03/04 |
| R-FUP-06 | Completion read as case or Referral resolution | Current | High | Medium | GCO | D-FUP-05 |
| R-FUP-07 | Referral void assumed to close the Follow-Up | Current | Medium | Medium | GCO | D-FUP-01/05 |
| R-FUP-08 | Stale or misleading notification after source loss/reassignment | Current | Medium | Medium | GCO + engineering | D-FUP-06 |
| R-FUP-09 | Follow-Up encryption key loss or bad rotation | Current | Low | High | Engineering + records | — |
| R-FUP-10 | Premature schema expansion before decisions | Implementation | Medium | High | Engineering | D-FUP-01/03 |
| R-FUP-11 | Stale SAR documentation drives a duplicate or wrong migration | Current | Medium | Medium | Engineering + SAR owner | — |
| R-FUP-12 | Unexecuted UAT journeys reported as validation | Current | High | Medium | FUP-4 owner | D-FUP-07 |
| R-FUP-13 | Source-filter 404 and silently disappearing context panel | Current | Low-Medium | Low-Medium | Engineering | D-FUP-01 |
| R-FUP-14 | Source change races with completion/reassignment | Current + implementation | Low | Medium | Engineering | D-FUP-01 |

---

## R-FUP-01 — Operational task survives Referral void with no recorded review

**Class:** current-state. **Likelihood:** High — the behavior is deterministic for every voided
Referral with a live operational task. **Impact:** Medium — pending work loses its visible anchor but
remains actionable; nobody is told, and no review is recorded.

**Evidence (Verified):** operational authorization does not recheck the source
(`be/compass/guidance_followups/policy.py:167-168`); detail returns `source: null` and
`source_unavailable: true` (`be/compass/guidance_followups/api.py:253-263`); mutations still pass
`_lock_for_mutation` (`be/compass/guidance_followups/services.py:268-283`); Referral void writes no
Follow-Up event or audit (`be/compass/referrals/services.py:896-940`); the only test asserts detail
source absence (`be/tests/test_guidance_followups.py:252-275`). Finding #1 in
[`README.md`](README.md).

**Mitigation (proposed, not adopted):** D-FUP-01 Option A — preserve the task, make source
unavailability truthful and consistent on detail, and add regression tests for list/report/My Work/
mutation after void. Do **not** auto-cancel, auto-hide or auto-complete. If GCO requires proof of
review, choose D-FUP-01 Option B and add an explicit review record rather than an activity-note
convention.

**Rollback / review trigger:** review before FUP-1 closes and before any release note that mentions
Referral void. If a projection change is approved and later rejected, revert the copy/indicator only;
the domain state was never changed. No data rollback is required because FUP-0 and the proposed FUP-1
add no persistence.

---

## R-FUP-02 — Confidential task becomes an inaccessible, unclosable orphan

**Class:** current-state. **Likelihood:** Medium — requires the source Counselor to lose source access,
the source to be voided/unavailable, or the Counselor account to become unavailable. **Impact:** High —
the task remains `PENDING` and invisible to everyone, cannot be completed, cancelled or reassigned, and
there is no approved coverage path.

**Evidence (Verified):** confidential detail/mutation requires the assignee to remain a `COUNSELOR`
with the live source relationship (`be/compass/guidance_followups/policy.py:162-183`,
`policy.py:144-156`); list/report SQL mirrors that relationship (`policy.py:212-245`); recovery is
`OPERATIONAL` only (`be/compass/guidance_followups/recovery.py:51-56`); the Head designation adds no
Follow-Up capability and no confidential source access (`be/compass/accounts/policy.py:761-788`);
Continuity runtime policy returns `None` and denies (`be/compass/counseling/continuity_policy.py:99-109`).
Finding #3 in [`README.md`](README.md); detail in
[`source-lifecycle.md`](source-lifecycle.md).

**Mitigation (proposed, not adopted):** D-FUP-02 must decide whether a confidential task may be
covered, by whom, with what source-level authorization and what audit. Do not solve it by broadening
`recovery_queryset` or by letting Head Guidance read confidential tasks. A Continuity adapter is
acceptable only after CONT institutional approval; a read grant must not silently become a manage
grant. Until then, treat the orphan as a known limitation and monitor it through an authorized,
metadata-only report.

**Rollback / review trigger:** review when CONT runtime policy is approved, when the first orphan is
reported, or before FUP-3B. Any stopgap confidential bypass must be removed if the institutional
decision rejects it.

---

## R-FUP-03 — Source UUID/filter treated as authorization

**Class:** current + implementation. **Likelihood:** Medium — source identifiers appear in URLs and
query parameters, which invites the assumption that supplying an ID grants context. **Impact:** High —
a leak would expose Student identity, source existence or confidential record metadata across
Counselors.

**Evidence (Verified):** the source context endpoint re-authorizes the actor with
`policy.require_source` (`be/compass/guidance_followups/workspace.py:50-69`); the list source filter
calls the same function and raises `FollowUpNotFound` for an unreadable source
(`be/compass/guidance_followups/services.py:244-248`); operational detail exposes a source only when
the actor currently has source access (`be/compass/guidance_followups/policy.py:248-266`,
`api.py:253-263`); confidential scope is computed in SQL, not by client filter
(`policy.py:212-245`).

**Mitigation:** keep authorization derived from the actor, never from a supplied `source_id`; never add
raw source fields to `FollowUpSummary`; test 404/403 parity for the context endpoint and filtered list;
treat any proposed client-supplied `visibility`, `student_scope` or `source_name` as a security change.

**Rollback / review trigger:** review any PR that adds source data to a list payload, accepts a scope
parameter, or removes the `require_source` call. If a leak is found, disable the affected endpoint at
the router rather than trying to filter in the frontend.

---

## R-FUP-04 — Head designation mistaken for global Follow-Up authority

**Class:** current + implementation. **Likelihood:** Medium — "Head Guidance" reads as oversight, and
the designation already permits operational recovery and assignment scope. **Impact:** Medium —
incorrect copy or expectation; an attempted bypass would either fail (confusing) or, if implemented,
grant broad access to confidential work.

**Evidence (Verified):** the Head designation grants no `guidance_followups.*` capability
(`be/compass/accounts/policy.py:761-788`); Head receives an operational-only bypass in
`in_operational_scope` (`be/compass/guidance_followups/policy.py:42-48`); ordinary list remains
assignment-scoped (`policy.py:194-210`); recovery is operational only
(`be/compass/guidance_followups/recovery.py:49-64`).

**Mitigation:** state the operational-only boundary in help copy and UAT; if GCO wants a Head
operational oversight list, specify it as a separate endpoint/scope decision with tests — do not widen
the ordinary list by implication.

**Rollback / review trigger:** review during FUP-1 copy approval and whenever a Head Guidance user
reports missing tasks.

---

## R-FUP-05 — "Further action" implemented as auto-created or duplicated task

**Class:** implementation. **Likelihood:** Medium if FUP-2 proceeds without D-FUP-03/D-FUP-04.
**Impact:** Medium-High — duplicate or wrongly owned tasks, hidden delegation, and a second
confidentiality classification derived incorrectly from the predecessor.

**Evidence (Verified):** there is no predecessor/next-action field, endpoint or control; completion is
terminal (`be/compass/guidance_followups/models.py:45-94`,
`be/compass/guidance_followups/services.py:391-417`); the current create endpoint requires an explicit
student, assignee, category and due date, and derives visibility only from a live source
(`services.py:127-208`).

**Mitigation:** require an explicit user action with a preview; create a new task through the existing
create contract; carry source/visibility only by re-derivation, never by copying a confidential
classification; use an idempotency key and expected-version semantics; do not auto-create on
completion; if a predecessor link is added, make it immutable and auditable. D-FUP-03 must define
whether "further action" is a new task, an activity note, or simply guidance copy.

**Rollback / review trigger:** block FUP-2 merge until D-FUP-03 and D-FUP-04 are approved. If an
auto-creation behavior ships and is rejected, remove the trigger and keep already-created tasks (do
not delete records).

---

## R-FUP-06 — Completion read as case or Referral resolution

**Class:** current-state. **Likelihood:** High — the word "complete" naturally implies the underlying
concern is resolved. **Impact:** Medium — staff may stop monitoring the Referral/Encounter, or GCO may
treat Follow-Up counts as case closure.

**Evidence (Verified):** `complete_followup` mutates only the Follow-Up and appends its own event
(`be/compass/guidance_followups/services.py:391-417`); no Referral/Encounter/Routine write exists in
the Follow-Up service module; the detail copy says the related record keeps its own access rules and
progress (`fe/src/features/guidance-followups/followups-detail.tsx:108`); reports count tasks only
(`be/compass/guidance_followups/workspace.py:150-187`).

**Mitigation:** D-FUP-05 — approved copy at completion and in reports that completion closes the task,
not the case; UAT journey for a completed task whose Referral stays open; never auto-close a Referral
from a Follow-Up completion.

**Rollback / review trigger:** review when report definitions or dashboard labels are next changed;
if a downstream consumer treats completed tasks as case closure, correct the consumer, not the domain.

---

## R-FUP-07 — Referral void assumed to close the Follow-Up

**Class:** current-state. **Likelihood:** Medium — voiding is an administrative correction and staff
may assume it cascades. **Impact:** Medium — a task is either abandoned while pending or, if a future
auto-close is added, independent work is silently terminated.

**Evidence (Verified):** `void_referral` updates only the Referral and its administrative fields
(`be/compass/referrals/services.py:896-940`); no Follow-Up event, audit or state change is written;
the Follow-Up test asserts the task remains readable after void
(`be/tests/test_guidance_followups.py:252-275`).

**Mitigation:** D-FUP-01/D-FUP-05; explicit copy in the Referral void confirmation that Follow-Ups are
independent; optional review prompt on the task (not an automatic state change).

**Rollback / review trigger:** review before any Referral void UX change; if cascading behavior is ever
proposed, require an explicit institutional decision and a reversible migration plan.

---

## R-FUP-08 — Stale or misleading notification after source loss/reassignment

**Class:** current-state. **Likelihood:** Medium. **Impact:** Medium — an assignee may act on a notice
whose task has since been reassigned or whose source is gone; repeated notices train staff to ignore
them.

**Evidence (Verified):** notification event types are only `assigned`, `reassigned` and `due_changed`
(`be/compass/notifications/policy.py:42-44`); currentness is computed from the latest material event
(`be/compass/guidance_followups/integration.py:47-84`); source loss is not a material event; delivery is
gated by `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED`, default `False`
(`be/config/settings.py:719`); reassignment writes an event and invalidates prior notices
through currentness, but source loss writes nothing.

**Mitigation:** D-FUP-06 — decide whether source invalidation should suppress or annotate a pending
notice; test currentness after reassignment and after void; do not add email/push until approved. Keep
in-app notices free of protected descriptions/outcomes.

**Rollback / review trigger:** review before enabling the notification flag in any environment and
before FUP-1 changes notification copy.

---

## R-FUP-09 — Follow-Up encryption key loss or bad rotation

**Class:** current-state. **Likelihood:** Low. **Impact:** High — descriptions, outcomes and event
remarks become permanently unreadable; fail-closed reads return service errors rather than leaking.

**Evidence (Verified):** Fernet encryption with record/section/event AAD binding and a fail-closed
keyring (`be/compass/guidance_followups/content.py:18-86`); rotation is a management command
(`be/compass/guidance_followups/management/commands/rotate_guidance_followup_encryption.py`); the
decision is recorded in `be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md`; operations
guidance is in `be/docs/guidance-followups-operations.md`.

**Mitigation:** maintain key custody and backup outside the repository; run rotation only with the
documented staged procedure and a verified backup; monitor 503/decryption failures; never log
ciphertext or keys; do not rotate during FUP-1/FUP-2 without a rehearsed rollback.

**Rollback / review trigger:** review before any key rotation or environment restore. Rotation is
resumable; if a key is suspected lost, stop writes and follow the operations runbook rather than
re-encrypting blindly.

---

## R-FUP-10 — Premature schema expansion before decisions

**Class:** implementation. **Likelihood:** Medium — the natural implementation of "review" or "further
action" is a new column/table. **Impact:** High — policy is baked into the schema; later reversal
requires a migration and data backfill on an encrypted domain, and may conflict with FUP-3A/3B.

**Evidence (Verified):** current model has no review, predecessor, next-action or resolution field
(`be/compass/guidance_followups/models.py:45-144`); two migrations exist; DB constraints enforce
terminal-state provenance (`models.py:108-135`). D-FUP-01/03 are **Open**
([`decisions.md`](decisions.md)).

**Mitigation:** FUP-1 must be schema-free. Require a decision ID in any PR that adds a migration under
`be/compass/guidance_followups/migrations/`; review the migration against D-FUP-01/03/05; avoid
nullable flags that encode an undecided policy.

**Rollback / review trigger:** any proposed migration before D-FUP-01/D-FUP-03 approval is a stop
condition. If one ships, do not write data until the decision is recorded; prefer reverting the
migration before release.

---

## R-FUP-11 — Stale SAR documentation drives a duplicate or wrong migration

**Class:** current-state. **Likelihood:** Medium. **Impact:** Medium — an engineer following
`docs/sar-0` or the proposal may attempt to migrate `StudentAffiliation` again or "fix" code that
already uses `student_academics`.

**Evidence (Verified):** SAR removed the model
(`be/compass/organization/migrations/0005_delete_studentaffiliation.py:13-15`); live Follow-Up code uses
`student_academics` (`policy.py:200-208`, `workspace.py:6-7,113-114`, `recovery.py:57-64`);
`docs/sar-0/README.md:37-38,55-58` and proposal lines 5748/6227 still describe the old baseline;
`docs/sar-3-4/implementation.md:37,41` and `docs/sar-5/validation.md:265,274-275` record the change.

**Mitigation:** FUP-3C is verification-only (see
[`cross-proposal-readiness.md`](cross-proposal-readiness.md)); cite the migration evidence in every
FUP-3C work item; correct the stale SAR-0/proposal text in a separate documentation change after GCO
approval — FUP-0 must not edit outside `docs/fup-0/`.

**Rollback / review trigger:** review at FUP-3C kickoff and before any organization migration is
created.

---

## R-FUP-12 — Unexecuted UAT journeys reported as validation

**Class:** current-state. **Likelihood:** High if this package is quoted without its labels.
**Impact:** Medium — false confidence in behavior; institutional approval based on unexecuted steps.

**Evidence (Verified):** this audit executed no test, browser, server or database command; the 20
journeys in [`ux-journeys.md`](ux-journeys.md) are **Proposed / Not executed**; the proposal's 45 UAT
scenarios (lines 6417-6467) are unexecuted at HEAD; the cited cross-domain test contains no Follow-Up
reference (proposal line 6619; divergence D4).

**Mitigation:** every journey carries a status; FUP-4 executes the approved subset and records
pass/fail with evidence; release notes must say "proposed" until FUP-4 signs off. D-FUP-07 is the
institutional gate.

**Rollback / review trigger:** review at FUP-4 entry and before any UAT result is cited in a release or
approval memo.

---

## R-FUP-13 — Source-filter 404 and silently disappearing context panel

**Class:** current-state. **Likelihood:** Low-Medium — requires a source-filtered request or a source
page viewed after the source becomes unavailable. **Impact:** Low-Medium — confusing but fail-closed;
the caller learns only that the record is unavailable.

**Evidence (Verified):** `source_context` raises `FollowUpNotFound` when the source is missing or
unreadable (`be/compass/guidance_followups/workspace.py:66-69`); the list filter calls it before
filtering (`be/compass/guidance_followups/services.py:244-248`); the source-page context panel returns
`null` on a context error, so the panel and its "add follow-up" link disappear
(`fe/src/features/guidance-followups/followups-context.tsx:18-21`). This is not a data leak.

**Mitigation:** FUP-1 may show a truthful, non-leaking unavailable state **on the Follow-Up detail**,
where the actor is already authorized for the task. Do not add a source-existence oracle to source
pages or lists. Test 404 parity for the context endpoint and filtered list.

**Rollback / review trigger:** review during FUP-1 copy approval; if support reports confusion,
prioritize the detail copy over any new endpoint.

---

## R-FUP-14 — Source change races with completion/reassignment

**Class:** current + implementation. **Likelihood:** Low. **Impact:** Medium — a task can be completed
or reassigned in the window between a source becoming invalid and the next read; with mandatory review
(D-FUP-01 Option B), the review could be bypassed by a concurrent completion.

**Evidence (Inferred from Verified code):** Follow-Up concurrency is guarded by `expected_version` and
row locks (`be/compass/guidance_followups/services.py:268-283`), but the Follow-Up row does not share a
lock or version with the Referral/Encounter; operational authorization never rechecks the source
(`policy.py:167-168`); Referral void locks the Referral, not Follow-Ups
(`be/compass/referrals/services.py:896-940`). No test covers interleaving.

**Mitigation:** if D-FUP-01 Option A is chosen, accept and document the race; if Option B is chosen,
enforce the review and source check inside the same transaction as the completion/cancellation, and add
a test that simulates source invalidation before the mutation. Do not claim serializability across
domains.

**Rollback / review trigger:** review when D-FUP-01 is decided; re-review if the institution requires
"review before completion" as a hard gate.

---

## Controls that reduce the above risks

These are **Verified** strengths, not open risks:

- Strict request schemas reject unknown fields (`be/compass/guidance_followups/api.py:46-47`); the
  detail contract exposes no source when unavailable (`api.py:253-263`).
- Scope is applied in SQL before pagination (`services.py:258-265`); recovery is metadata-only
  (`recovery.py:122-135`).
- All state changes write an event and an audit record through one path
  (`services.py:79-123`); idempotency is actor-scoped with a request fingerprint
  (`replay.py:12-59`).
- Protected text is encrypted with AAD binding and fail-closed reads (`content.py:40-86`).
- Notifications are disabled by default (`be/config/settings.py:719`) and currentness follows material events
  (`integration.py:47-84`).
- Recovery never exposes protected descriptions (`recovery.py:122-135`;
  `fe/src/features/guidance-followups/followups-reassignment.tsx:29`).

## Risk acceptance and review

| Item | Owner role | Status |
|---|---|---|
| Accept current operational-void behavior until D-FUP-01 | GCO | Pending |
| Accept confidential-orphan limitation until D-FUP-02 | GCO + privacy | Pending |
| Accept notification currentness until D-FUP-06 | GCO | Pending |
| Approve FUP-1 risk treatment | GCO + engineering | Pending |
| Approve FUP-2 risk treatment | GCO + privacy | Pending |

**Review cadence:** re-check this register at FUP-1 start, FUP-2 start, FUP-3A/3B entry, and FUP-4
entry. Re-validate every `path:line` against the then-current HEAD; this register is frozen at
`5224256a`.

**Rollback of this audit:** the package is documentation-only under `docs/fup-0/`. Deleting or
reverting these files has no runtime, schema, data or Git-history effect beyond the documentation
change itself. No application rollback is needed.
