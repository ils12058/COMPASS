> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# Access matrix — actors, visibility, operations and recovery

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.
**Claim labels:** entries are **Verified** by static authorization code unless labeled **Inferred**.
No authorization test, API call or database query was executed.

## 1. Capability foundation

| Fact | Evidence |
|---|---|
| Follow-Up capabilities are `guidance_followups.view` and `guidance_followups.manage` | `be/compass/accounts/policy.py:142-150` |
| `COUNSELOR` role is granted both | `accounts/policy.py:654-657` |
| `GUIDANCE_SERVICES_STAFF` role is granted both | `accounts/policy.py:698-701` |
| `manage` implies `view` in capability compatibility | `accounts/policy.py:818` |
| `FACULTY` is capped at `referrals.submit_self` / `referrals.view_submitted_self`; it has no Follow-Up capability | `accounts/policy.py:79,82-85,635` |
| `HEAD_GUIDANCE_COUNSELOR` designation grants many operational capabilities but **none** for Follow-Ups | `accounts/policy.py:761-788` |
| Head designation is compatible only with `COUNSELOR` | `accounts/policy.py:795` |
| `policy.ROLES` is exactly `COUNSELOR`, `GUIDANCE_SERVICES_STAFF` | `policy.py:18` |
| Entry requires active account, allowed role and capability | `policy.py:21-29` |

**Key consequence — Verified:** a Head Guidance Counselor's Follow-Up authority comes from being a
`COUNSELOR`, not from the designation. The designation adds **operational Student scope**, not
Follow-Up capability and not confidential access.

## 2. Visibility classes

| Class | Source | Who may own | Read requirement | Mutation requirement |
|---|---|---|---|---|
| `OPERATIONAL` | none, or `REFERRAL`; derived by `classify` | Active `COUNSELOR` or `GUIDANCE_SERVICES_STAFF` with `guidance_followups.manage` | Current assignee + active Student + operational scope | Current assignee + manage capability + operational scope |
| `COUNSELOR_CONFIDENTIAL` | `COUNSELING_ENCOUNTER` or `ROUTINE_INTERVIEW`; derived by `classify` | Active `COUNSELOR` with `guidance_followups.manage` **and** source manage access | Current assignee + active Student + `COUNSELOR` + source view/manage + source relationship | Current assignee + manage + source **manage** + source relationship |

Evidence: `policy.py:117-183`; `require_assignee` at `:138-159`; classification cannot be overridden at
`services.py:150-151` and category changes cannot alter it at `:314-319`.

## 3. Actor-by-actor matrix

Legend: **Y** = allowed when all resource/scope predicates pass; **N** = no path; **Cond** = conditional
on source/Student/assignment facts; **—** = not applicable.

| Actor | List/report own assignments | Detail/history | Create | Update/activity/complete/cancel | Reassign | Recover operational orphans | See confidential task | See source content |
|---|---|---|---|---|---|---|---|---|
| `COUNSELOR` (source owner) | Y (operational + own-source confidential) | Y | Y | Y | Y (confidential recipient must also pass source manage; effectively no transfer) | Y | Y for own assigned confidential tasks | Only if separately source-authorized |
| `COUNSELOR` (not source owner) | Y for own operational tasks only | Y for own operational tasks; N for another Counselor's confidential task | Y for operational; N for another Counselor's confidential source | Y for own operational; N for other confidential | Cannot assign a confidential task to themselves | Y for operational orphans | N | N for another Counselor's confidential source |
| `GUIDANCE_SERVICES_STAFF` | Y (operational only) | Y (operational only) | Y (operational only) | Y (operational only) | Y (operational only) | Y (operational only) | N | Referral links only if `referrals.view`; no confidential source |
| `HEAD_GUIDANCE_COUNSELOR` | Y, but still **only tasks assigned to them** | Y for own tasks | Y; operational Student scope is any active Student | Y for own tasks | Y for own tasks; confidential transfer still blocked | Y for **all** operational orphans | N unless they are the source Counselor and assignee | No blanket access |
| Former assignee | N; tasks disappear from list | N | Y as a general creator if capability and scope | N | N (unless recovery applies) | Y if otherwise eligible | N | N via task |
| Creator who is not assignee | N for that task | N; create response is a minimized receipt only | Y | N | N | N via creation | N | N via task |
| `FACULTY` | N | N | N | N | N | N | N | N (own Referral via Referral API only) |
| Student | N | N | N | N | N | N | N | N via Follow-Up |
| `DPO` / IT administrator | N merely from role | N | N | N | N | N | N | N merely from role |
| Anonymous / unauthenticated | N (session auth required) | N | N | N | N | N | N | N |

Evidence for the actor columns: `policy.py:18-29,42-48,138-183,186-245,248-251`; `recovery.py:49-119`;
`accounts/policy.py:79,761-795`; `api.py:42` (session auth on the router). "Former assignee" and
"creator" are **Verified** by the assignment predicate; the realtime eviction hint is at
`integration.py:96-100`.

## 4. Operation-by-operation rules

### 4.1 List, report, history

- All three begin with `policy.current_actor` requiring `guidance_followups.view` (`services.py:230`;
  `workspace.py:151`; `api.py:717-734`).
- SQL scope filters `assigned_to_id=actor`, active Student and role `STUDENT` before pagination
  (`policy.py:194-196`).
- Head Guidance replaces the College predicate with all operational tasks **but still keeps the
  assignment filter** (`policy.py:197-210`). Head is not a global task-list role.
- Non-Counselor roles receive operational rows only (`policy.py:209-210`).
- Counselors receive operational plus confidential rows whose source matches the actor and the
  relevant source capability (`policy.py:212-245`).
- `report` aggregates the same scope and returns no free text (`workspace.py:150-187`).
- History uses the same detail authorization (`api.py:717-734`).

### 4.2 Create

| Step | Rule | Evidence |
|---|---|---|
| Capability | `guidance_followups.manage` | `services.py:144` |
| Source | Complete pair required; manage-level source access for linked sources | `services.py:147-148,170-177` |
| No source | Operational scope required | `services.py:178-179` |
| Assignee | Active allowed role + manage + operational scope or source manage | `policy.py:138-159` |
| Confidential owner | Must be the creating/source Counselor | `services.py:187-188` |
| Due | Aware future time | `services.py:43-46,168` |
| Visibility | Derived; supplied mismatch rejected | `services.py:149-151` |
| Replay | Creation key + fingerprint; same request returns existing | `services.py:152-167` |

A GSS user can create an operational task for any eligible assignee in their Student scope. A
Counselor can create a confidential task only for themselves, from their own source. **Verified.**

### 4.3 Update / activity / complete / cancel

- `_lock_for_mutation` requires `manage=True`, expected version, row lock, and `status=PENDING`
  (`services.py:268-283`).
- Operational: the actor must be the current assignee and in operational scope; source validity is
  **not** rechecked (`policy.py:167-168`).
- Confidential: the actor must be the current assignee, a Counselor, and pass source **manage** access
  (`policy.py:169-182`).
- A task with only `view` capability can be read but not mutated; the UI hides actions behind
  `access.manage` (`followups-detail.tsx:86`).
- Update cannot change source, visibility, assignee or status; reassign is separate; completion and
  cancellation are separate terminal routes (`services.py:288-334,339-369,391-463`).

### 4.4 Reassign

- Normal reassignment requires current manage access and a `PENDING` task (`services.py:339-369`).
- New assignee must pass `require_assignee` for the task's existing visibility/source.
- Operational: new assignee may be another Counselor or GSS in the Student's operational scope.
- Confidential: the only candidate who can pass source manage is the original source Counselor; a
  different Counselor fails. A no-op to the same owner returns without a new event
  (`services.py:355-356`).
- Recovery path (`allow_recovery=True`) can operate on an operational task whose current owner is
  ineligible, but only if the task appears in `recoverable_queryset` (`services.py:272-276`).

### 4.5 Recovery

| Rule | Evidence |
|---|---|
| Actor must have `manage` | `recovery.py:50` |
| Only `OPERATIONAL`, `PENDING`, active Student | `recovery.py:51-56` |
| Non-Head limited to SAR college scope and active College/campus | `recovery.py:57-64` |
| Current owner eligibility computed in SQL, including role/designation/responsibility/capability overrides | `recovery.py:65-119` |
| Confidential never included | `recovery.py:52` (visibility filter) |
| Preview returns metadata-only summaries | `recovery.py:122-135`; `api.py:343-355` |
| Reassignment through recovery uses the same predicate | `services.py:272-276` |

Recovery is not a confidentiality bypass. It does not decrypt descriptions/outcomes and cannot grant
source access. A Head can recover operational tasks across Colleges; that is the actual Head
"oversight" power in this domain.

### 4.6 Source context and eligible selectors

| Operation | Authorization | Evidence |
|---|---|---|
| `GET /context` | `view` capability at entry; source `view` access; `can_create` requires manage + source manage | `workspace.py:50-91`; `api.py:436-448` |
| `GET /eligible-students` | `manage`; Head all active Students, otherwise College scope | `workspace.py:36-47` |
| `GET /eligible-assignees` | `manage`; Student valid; source manage if linked; operational scope otherwise; confidential candidate list reduced to the actor | `workspace.py:94-147` |
| `GET /report` | `view`; same assignment scope | `workspace.py:150-187` |
| `GET /recoverable` | `manage`; operational only | `recovery.py:122-135` |

## 5. Source access is independent of task access

| Situation | Task access | Source link | Claim |
|---|---|---|---|
| Assignee with operational task, no `referrals.view` | Yes | No; `source_unavailable` | **Verified** |
| Assignee with confidential task, source capability revoked | No (detail/mutation); list may drop | No | **Verified** code path |
| Source-authorized Counselor who is not the assignee | No | Yes via source domain, not via task | **Verified** |
| Creator with manage but not assignee | Minimized receipt only on create; later reads denied | No | **Verified** |
| Former assignee after reassignment | No | No | **Verified** |
| Head with no source relationship | No confidential task; operational only if assigned/recovering | No blanket | **Verified** |
| Anyone who knows a source UUID | Still requires source-domain authorization | Not a bearer token | **Verified** |

## 6. HTTP behavior and disclosure minimization

| Case | Response | Evidence |
|---|---|---|
| Wrong role/capability at entry | 403 `followup_access_denied` | `policy.py:21-29`; `api.py:212-215` |
| Task not assigned / out of scope / source invalid | 404 `followup_not_found` | `policy.py:248-251`; `api.py:216-217` |
| Invalid source/student/category/page | 422 `invalid_followup` | `api.py:220-221` |
| Stale version or terminal mutation | 409 `followup_conflict` | `services.py:279-282`; `api.py:218-219` |
| Missing/tampered encryption key | 503 `followup_content_unavailable` | `content.py:18-25,67-86`; `api.py:208-211` |
| Unknown query parameter | 422 | `api.py:198-200,479-481` |
| Missing recent MFA on write | Step-up rejection (existing auth contract) | `api.py:203-205`; `authentication/step_up.py` |
| Non-assignee creator on create | Minimized receipt, no source/description/outcome/events | `api.py:266-281` |

**Inferred:** a user who can infer existence from timing or from source pages may still learn that a
task exists, but the Follow-Up API does not confirm inaccessible object existence. No timing or
side-channel analysis was performed.

## 7. What is deliberately absent

- No `HEAD_GUIDANCE_COUNSELOR` override for confidential tasks.
- No `GUIDANCE_SERVICES_STAFF` confidential access.
- No Faculty/Student Follow-Up route.
- No global admin/DPO content access.
- No recovery of confidential tasks.
- No creator backdoor after creation.
- No direct `source_id` authorization.
- No "view all Follow-Ups" capability.
- No ability to change source/visibility after creation.
- No ability to reopen a terminal task.

All **Verified** by route/capability/service inventory. These absences are security properties to
preserve in FUP-1/FUP-2, not gaps to "fix" without an institutional decision.
