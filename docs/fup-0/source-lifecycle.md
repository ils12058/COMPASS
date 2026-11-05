# Source lifecycle — authorization, invalidation and reconciliation

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.
**Question answered:** what happens to a Follow-Up when its Referral, Counseling Encounter or Routine
Interview changes, becomes unreadable, is voided, is deleted or is reassigned?

Unless labeled otherwise, statements are **Verified** by static code inspection. No source-domain
mutation and no Follow-Up runtime call was executed.

## 1. Source references are loose, policy-checked references

`GuidanceFollowUp.source_kind` and `source_id` are a nullable choice plus a plain `UUIDField`, **not a
ForeignKey** (`models.py:52-55`). Consequences:

- There is no database referential integrity between a Follow-Up and its source.
- A source row can be deleted (subject to that domain's own rules) without the database preventing it;
  the Follow-Up would retain a dangling reference. **Verified** model shape; source deletion paths are
  **Unknown** / domain-specific.
- The source UUID is **not a bearer credential**. Every source resolve goes through the source domain's
  current authorization (`policy.py:51-114,254-266`).
- Source identity is immutable after creation: no service or API accepts a source change
  (`services.py:288-334`).

## 2. Source authorization at creation and at read/mutation

### 2.1 Creation-time `require_source` (`policy.py:51-114`, `manage=True`)

| Source | Required actor | Required capability | Required source/Student facts | Delegated service recheck |
|---|---|---|---|---|
| `COUNSELING_ENCOUNTER` | `COUNSELOR` | `counseling.manage_assigned` | Encounter exists with matching `student_id` and `counselor_id == actor` | `get_encounter_for_actor` (`counseling/services.py:787-793`) |
| `ROUTINE_INTERVIEW` | `COUNSELOR` | `routine_interviews.manage_assigned` | Routine exists with matching Student/Counselor; linked Appointment is null or `SCHEDULED`/`COMPLETED` | `get_assigned` (`routine_interviews/services.py:979-984`) |
| `REFERRAL` | any allowed Follow-Up actor | `referrals.manage` | Referral exists with matching Student and `voided_at IS NULL` | `get_referral` (`referrals/services.py:605-611`) |

On failure, `require_source` raises the private `FollowUpNotFound`, which becomes HTTP 404. The
caller is not told whether the source is missing, belongs to another Student, is voided, or is outside
the caller's authority (`errors.py`; `api.py:216-217`).

For **read** (`manage=False`), the same shapes apply with `counseling.view_assigned`,
`routine_interviews.view_assigned` and `referrals.view`.

### 2.2 Source checks on each path

| Path | Source check | Evidence |
|---|---|---|
| Create | `require_source(manage=True)` for source-linked tasks | `services.py:170-177` |
| Detail | `followup_detail` → `require_followup` → `authorized`; confidential rechecks source; then `visible_source` resolves the link | `services.py:466-508`; `policy.py:162-183,254-266` |
| List/report/My Work | SQL scope only; operational has no source predicate; confidential mirrors the source relationship | `policy.py:186-245`; `integration.py:25-44` |
| Update/activity/complete/cancel | `_lock_for_mutation` → `require_followup(manage=True)`; confidential rechecks source | `services.py:268-283` |
| Reassign | Same, with recovery fallback for operational only | `services.py:339-369` |
| Recovery | Operational rows only; no source check at all | `recovery.py:49-119` |
| Notification currentness | `policy.scope(manage=True)` | `integration.py:57-84` |
| Source context panel | `workspace.source_context` → `require_source`; then `require_source(manage=True)` for `can_create` | `workspace.py:50-91` |
| List filtered by source | `workspace.source_context` first; inaccessible source rejects the query | `services.py:244-248` |

**Critical asymmetry — Verified:** for an `OPERATIONAL` task, `authorized()` checks the current
assignee, active Student and operational Student scope, but **does not** call `require_source`
(`policy.py:167-168`). For a `COUNSELOR_CONFIDENTIAL` task, it does (`:169-182`). This is the root of
the operational/confidential divergence below.

## 3. Referral void — the verified operational behavior

A Referral is voided only through the Referral domain (`referrals/services.py:896-940`), which sets
`voided_at`/`voided_by` and encrypted void reason (`referrals/models.py:131-138`). It checks for an
active linked Call Slip (`:926-930`) but contains **no Follow-Up check, cancellation, event or
notification**. **Verified** by the absence of any `guidance_followup` reference in
`be/compass/referrals`.

### 3.1 Post-creation effect on an operational task

| Surface | Effect after Referral void | Claim | Evidence |
|---|---|---|---|
| Task row | Unchanged: same status, assignee, due date, source `kind`/`id` | **Verified** | No source-change writer; `models.py:52-55` |
| Detail read | Still authorized; `source` becomes `null`; `source_unavailable` becomes `true` | **Verified** | `policy.py:162-168`; `api.py:253-263`; test `:252-275` |
| Source link | Not rendered; safe copy says the related record is no longer available | **Verified** UI code | `followups-detail.tsx:108` |
| List | Still included if assigned and in scope; no source column/indicator | **Verified** | `policy.py:186-210`; `api.py:227-250` |
| Report | Still counted in pending/overdue/category totals | **Verified** | `workspace.py:150-187` |
| My Work | Still projected; priority unchanged | **Verified** | `integration.py:25-44` |
| Notifications | Existing material event remains current; no new notification | **Verified** code path | `integration.py:57-84` |
| Update due/category/description | Still allowed | **Verified** | `services.py:288-334` |
| Reassign | Still allowed (new assignee must meet operational scope); the voided link transfers with the task | **Verified** code path | `services.py:339-369`; `policy.py:138-159` |
| Record activity | Still allowed | **Verified** | `services.py:374-386` |
| Complete | Still allowed | **Verified** | `services.py:391-417` |
| Cancel | Still allowed | **Verified** | `services.py:422-463` |
| Context panel on the Referral detail | Context request fails (voided filter), so the component returns `null`; linked tasks disappear from that panel | **Verified** | `policy.py:104-107`; `followups-context.tsx:18-21` |
| List filtered by that source | `source_context` rejects the voided source, so the request returns not-found rather than an empty list | **Verified** | `services.py:244-248`; `workspace.py:66-69` |
| Audit | Only the Referral's own void audit; no Follow-Up audit row | **Verified** | no Follow-Up call in `void_referral` |
| Recovery | Task is not recoverable merely because the source is void; owner eligibility is unrelated | **Verified** | `recovery.py:49-119` |

**Proposal claim confirmed:** a pending operational task may remain accessible when its linked
Referral deep link becomes unavailable (proposal lines 5726-5734). The current UI explains this on
detail but not in the list, report or My Work. There is no server-side review requirement.

### 3.2 Creation after void

`require_source` filters `voided_at__isnull=True` (`policy.py:104-106`), so creating a new Referral-linked
task from a voided Referral is rejected. `source_context` also rejects it (`workspace.py:50-69`).
`test_referral_source_keeps_operational_scope` covers the foreign-Counselor creation denial and the
post-void detail source absence (`:252-275`). **Verified** static test reading; test not run.

### 3.3 What does **not** happen

- No automatic cancellation, hide, reassignment or status change.
- No `SOURCE_INVALID`/`SOURCE_REVIEW_PENDING` status.
- No source-review event, actor, timestamp or decision.
- No relink to a replacement Referral.
- No notification to the assignee that the source changed.
- No source-invalidation audit entry in the Follow-Up domain.
- No cross-domain transaction or lock between voiding and task mutation.

All **Verified** by code absence and the service/event inventory; operational consequence is
**Inferred**.

## 4. Confidential source loss — the harder behavior

For a `COUNSELOR_CONFIDENTIAL` task (only Counseling Encounter or Routine Interview sources), access
requires all of:

1. Current assignee.
2. Active Student with role `STUDENT`.
3. Actor role `COUNSELOR`.
4. `counseling.view_assigned` / `routine_interviews.view_assigned` for detail, or the `manage`
   variants for mutation.
5. Source row matching the task's Student and `counselor_id == actor`.
6. The source domain's own resolver (`get_encounter_for_actor` / `get_assigned`).
7. For Routine Interview, a null Appointment or one in `SCHEDULED`/`COMPLETED`.

Evidence: `policy.py:162-183,186-245,51-97`.

### 4.1 If any of those stop being true

| Surface | Effect | Claim |
|---|---|---|
| Detail | 404; the task is indistinguishable from absent | **Verified** code path |
| List/report | SQL scope may still include it only while the mirrored source predicate matches; if the predicate fails, it disappears | **Verified** code path; exact divergence cases **Inferred** |
| Mutations (update/reassign/activity/complete/cancel) | 404; the task cannot be disposed through normal means | **Verified** code path |
| Recovery | Excluded unconditionally (`visibility="OPERATIONAL"` filter) | **Verified** |
| Head Guidance | No bypass: Head only expands operational scope; confidential still requires source | **Verified**; test `:705-730` |
| Notifications/My Work | Drop out when scope no longer matches; no reassignment/notice to anyone | **Verified** code path |
| Audit | No source-loss event | **Verified** |
| Row | Remains `PENDING`; no automatic terminal transition or deletion | **Verified** |

The result is an **operational orphan**: a real pending task with no authorized owner and no UI path
to resolve it. Whether any given deployment has such rows is **Unknown**; a population query was not
run and is outside FUP-0.

### 4.2 Why ordinary reassignment does not solve it

`require_assignee` for a confidential task requires the **candidate** to pass `require_source(...,
manage=True)` (`policy.py:144-156`). `require_source` requires the source's `counselor_id` to equal the
candidate. Since the source has one original Counselor, the only eligible confidential owner is that
Counselor. A different Counselor fails; GSS fails the role requirement. Therefore:

- A confidential task cannot be transferred to a substitute through the normal reassign route.
- The recovery route is explicitly operational-only.
- A Head designation adds no Follow-Up capability and no source access
  (`accounts/policy.py:761-795`).

**Verified** by the predicates. This is the exact boundary CONT is intended to address, not a bug to
paper over with a Head override.

### 4.3 Routine Interview appointment-state edge

`require_source` accepts a Routine only when its Appointment is null or `SCHEDULED`/`COMPLETED`
(`policy.py:79-97`), and `scope` mirrors that (`policy.py:232-243`). If the linked Appointment moves to
another state, both list scope and detail fail. If the Appointment is later restored to an accepted
state, access returns, because no Follow-Up state changed. **Verified** predicate; lifecycle
transitions of Appointment are outside this audit.

### 4.4 Encounter access changes

`get_encounter_for_actor` requires the actor to still be the Encounter's Counselor and an active
`COUNSELOR` (`counseling/services.py:787-793`). Capability revocation is checked before it
(`policy.py:52-56`). An active-account, role or capability change can therefore orphan the task even
if the source row remains unchanged. **Verified**; whether such changes occur operationally is
**Unknown**.

## 5. Other source changes

| Change | Operational task | Confidential task | Claim |
|---|---|---|---|
| Referral voided | Task survives; link unavailable; still mutable | Not applicable (Referral cannot be confidential source) | **Verified** |
| Referral becomes unreadable to actor (scope/capability) | Task survives; link unavailable; still mutable | Not applicable | **Verified** code path |
| Referral deleted | Task survives with dangling source; link unavailable | Not applicable | **Inferred** from plain UUID reference; deletion path **Unknown** |
| Referral Student changed (malformed/other writer) | Task remains for its Student; source link likely unavailable due to Student mismatch | Not applicable | **Inferred**; Referral Student is normally immutable |
| Encounter/Routine source deleted | Not applicable | Detail/list/mutation fail; orphan | **Inferred** from no FK and source checks |
| Source Counselor identity changed | Not applicable | Old owner may lose; new owner may gain only if all predicates match | **Inferred**; historical counselor immutability is domain-specific |
| Actor loses source capability | Task survives; link unavailable | Task becomes inaccessible/orphan | **Verified** code path |
| Student deactivated or role changed | Detail/list deny; row remains; recovery excludes | Same | **Verified** for access; **Verified** test `:430-437` for deactivation; retention inferred |
| Student College transfer | Operational scope changes; owner may become ineligible; recovery may surface it | Confidential unaffected by College scope | **Verified** scope code; recovery behavior **Verified** SQL |
| Task reassigned | Old owner loses; new owner must satisfy scope | Only original source Counselor can be candidate, so no effective transfer | **Verified** |

## 6. Reconciliation contracts that do **not** exist

Static search over `be/compass/guidance_followups`, `be/compass/referrals`, and
`be/compass/counseling` found no source-event subscription, no source-change callback and no
Follow-Up write from another domain. **Verified**:

| Missing contract | Consequence |
|---|---|
| Source validity/state projection beyond `source_unavailable` | No list/report/My Work indication; no reason or review hint |
| Source-review state and authorized decision | No way to record "reviewed — continue" or "reviewed — cancel" as a distinct decision |
| Source-invalidation event kind | No immutable proof that a human reviewed the change |
| Relink/replacement-source operation | A task cannot be pointed at a corrected/alternate source without creating a new task |
| Confidential orphan recovery/admin disposition | No approved path to cancel, reassign or archive an inaccessible confidential task |
| Cross-domain notification | Assignee may not learn that the source was voided |
| Cross-domain audit correlation | Referral void audit does not reference linked tasks; Follow-Up audit does not record source state |
| Bulk reconciliation command/report | Operators cannot enumerate affected tasks safely from the Follow-Up domain |
| Deletion detection | No FK, no tombstone, no periodic checker |

## 7. What FUP-1 can and cannot fix

**Can fix without schema or new authorization:**

- Make the existing detail `source_unavailable` state more explicit and consistent.
- Add list/report-safe presentation derived from existing fields, if GCO approves the disclosure.
- Add tests for the current operational behavior after void and for confidential source loss.
- Improve source-page context behavior without exposing hidden tasks.
- Add help/copy explaining that a task has its own status and that a source link is not a case status.

**Cannot fix without D-FUP-01/D-FUP-02 and, for confidential work, CONT:**

- Mandatory review before completion.
- Recording an authorized disposition.
- Automatically cancelling or hiding tasks.
- Relinking a task.
- Transferring a confidential task to a substitute.
- Guaranteeing that no confidential orphan exists.

**Verified** that no current code supports these; **Inferred** that adding them is a policy and schema
decision, not a copy change.

## 8. Unknowns and evidence still needed

| Unknown | Evidence required |
|---|---|
| Actual frequency of voided-Referral tasks and confidential orphans | Authorized read-only aggregate query; not run |
| Whether Referral rows are ever hard-deleted in production | Referral deletion policy/inventory; not inspected |
| Whether Encounter/Routine counselor identity is mutable | Domain migration/service audit; not fully inspected here |
| Whether deployed staging matches HEAD | Deployment SHA/data check; no access |
| Whether any external job/consumer writes Follow-Up rows directly | Repository-wide search found none; database/runtime check not run |
| Whether source changes are routinely accompanied by manual staff communication | GCO process evidence; not available |
| Whether users understand the current "related record unavailable" copy | UAT/usability evidence; not executed |
