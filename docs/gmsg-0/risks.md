# GMSG-0 — Risk register

Audit base `de6902200878f1413bea7a5a90166d30be92bdfc`, branch `integration/ux15-modernization`,
2026-11-06. Documentation only; nothing here is implemented.

Every substantive claim carries **Verified** (read at the cited `path:line`), **Inferred**
(a consequence of verified code, stated as such) or **Unknown**. Proposal text is never evidence
of current behavior. Citations are repo-relative paths under `be/`, `fe/` and `docs/`; the
`path:line` form matches `current-state.md` and `access-matrix.md`.

---

## 1. Scales

| Likelihood | Meaning in this register |
|---|---|
| Near-certain | Happens on the ordinary path unless something is changed first |
| Likely | Happens under a plausible, ordinary implementation choice |
| Possible | Requires a specific, non-default choice or a coincidence |
| Rare | Requires a defect plus an unusual condition |

| Impact | Meaning |
|---|---|
| Critical | Confidential content reaches a role with no authority to it — a reportable privacy breach |
| Severe | Existence, count or identity of a confidential relationship leaks to an unauthorized party |
| Major | Wrong-person write, lost message, broken contract, or a slice that cannot be built safely |
| Minor | Cosmetic, ergonomic, or documentation drift |

Mitigations below are *requirements on later slices*, not actions taken here. Each risk names its
review trigger, so the register can be re-scored rather than re-derived.

---

## 2. The seven named disclosure hazards

These are the hazards the proposal family must not carry into implementation. Each is stated as
mechanism → evidence → what makes it worse → mitigation → acceptance test.

### H-1 The `student` field is the participation switch

**Likelihood Near-certain · Impact Critical · Verified (mechanism) / Inferred (consequence)**

`GuidanceThread.student` is a non-null `PROTECT` foreign key to `User`
(`be/compass/guidance_messages/models.py:27-29`). Today three independent places treat "the
thread's `student`" as "a party to this conversation":

- Student visibility — `authorized_threads` returns `query.filter(student_id=actor.pk)` with no
  kind test at all (`be/compass/guidance_messages/policy.py:46-47`).
- Student write authority — `require_thread` grants a Student access iff
  `thread.student_id == actor.pk` (`policy.py:60-61`).
- Realtime routing — `recipient_ids` seeds its candidate set with `Q(pk=thread.student_id)`
  (`policy.py:151`).

So the moment any new kind writes a *referred* Student into `student`, that Student can list the
thread, open it, send into it and receive its hints — including a `REFERRAL_COORDINATION` or
`COUNSELOR_CASE_COORDINATION` thread whose whole purpose is staff-only discussion *about* them.
Proposal §19's matrix ("No access to Student/case records", "No Faculty content access") is
aspirational text, not a guard. **Inferred** from the three Verified citations.

Aggravating factor: `gm_thread_family_shape` (`models.py:80-97`) currently *forces* a non-null
`student` for every kind, so a new staff-only kind cannot be created without either violating the
constraint or inventing a fake Student. Both are wrong; the constraint itself encodes the
assumption. **Verified.**

**Mitigation (GMSG-1 onward).** Participation must become an explicit, per-kind predicate that no
column accidentally satisfies:
(a) `authorized_threads` and `require_thread` branch on `kind` before any identity comparison;
(b) `recipient_ids` derives candidates from the same predicate;
(c) a kind that is neither `COUNSELING` nor `OFFICE` must never be reachable through
`policy.py:46-47`;
(d) any kind with nullable `student` needs `gm_thread_family_shape` rewritten in the **same**
migration that introduces the kind, not a later one.

**Acceptance test.** A matrix test that, for each kind, asserts that a Student whose id appears in
a thread's `student` column but who is not a declared participant receives 404 on list, get,
messages, send, read and status — and receives no realtime hint. The negative tests must cover the
`recipient_ids` path, not only HTTP.

---

### H-2 `require_thread`'s else-branch: "not Counseling ⇒ College Office"

**Likelihood Near-certain · Impact Critical · Verified**

`be/compass/guidance_messages/policy.py:62-67`:

```
elif thread.kind == ThreadKind.COUNSELING:
    allowed = actor.role.code == "COUNSELOR" and thread.counselor_id == actor.pk
else:
    allowed = (
        thread.routing_college_id in resolve_general_guidance_college_scope(actor).college_ids
    )
```

This is an allowlist-by-exclusion written as a fallback. Any new `ThreadKind` value — added for
`REFERRAL_COORDINATION`, `FACULTY_INQUIRY`, `COUNSELOR_DIRECT` or `COUNSELOR_CASE_COORDINATION` —
falls into `else` and is therefore authorized by **College scope alone**, for every COUNSELOR and
GUIDANCE_SERVICES_STAFF whose `resolve_general_guidance_college_scope` covers the thread's
`routing_college`. Adding a kind and setting `routing_college` for routing convenience is, by
itself, a full-staff disclosure of a confidential thread.

The identical shape exists in `recipient_ids` (`policy.py:152-155`) and in `authorized_threads`
(`policy.py:49-52`), so one new kind leaks through query visibility, per-thread authorization
**and** push routing. Three sites, one missing branch, no error raised. **Verified.**

**Mitigation.** Replace the fallback with an exhaustive, kind-keyed dispatch that *denies* on an
unlisted kind (`ThreadNotFound` on the deny path, never a fallthrough) — one table keyed by
`ThreadKind`, consumed by all three call sites. The audit's position is that this refactor is a
**precondition for GMSG-2**, not part of GMSG-5. See
[implementation-plan.md](implementation-plan.md) (the blocking item) and
[decisions.md](decisions.md) D-GMSG-29.

**Acceptance test.** A test iterating `ThreadKind.choices` asserting every value has an explicit
branch, plus a test that an unrecognized kind cannot reach `require_thread` because the model field
is a closed `TextChoices` (`models.py:11-13`, `models.py:23`).

---

### H-3 Capability breadth outruns thread design

**Likelihood Likely · Impact Severe · Verified (grants and order) / Inferred (consequence)**

`guidance_messages.view` / `.manage` / `.templates.manage` are defined at
`be/compass/accounts/policy.py:162`, `:167`, `:172` and granted to the **COUNSELOR** role (`:654`,
codes at `:658-660`) and the **GUIDANCE_SERVICES_STAFF** role (`:698`, codes at `:702-704`); Students
receive only `…view_self` / `…manage_self` (`:152`, `:157`; granted at `:725`, codes at `:727-728`).
The five definitions span `:151-175`. Crucially, College Heads receive their messages authority from the **COUNSELOR role
grant, not the designation**: `DESIGNATION_CAPABILITY_GRANTS["HEAD_GUIDANCE_COUNSELOR"]`
(`:761-782`) contains **no** `guidance_messages.*` code — it adds `organization.*`,
`student_academics.*`, `appointments.manage`, reporting codes, and nothing messaging-related. A Head's
*reach across several Colleges* therefore comes from `resolve_general_guidance_college_scope`, not
from a wider capability. The FE mirror states the same rule
(`fe/src/features/guidance-messages/guidance-messages-access.ts:3-6`). The check order is
**role before capability**: `require_actor` tests the role set first and only then the capability
(`be/compass/guidance_messages/policy.py:31-40`), so capability is a *narrowing* control and never a
*widening* one.

Two consequences for the proposed kinds:

1. Reusing the existing capability codes cannot grant Faculty access, because `FACULTY` is absent
   from `STAFF_ROLES` (`guidance_messages/policy.py:17`) and `FACULTY_CAPABILITY_CEILING`
   (`accounts/policy.py:79`) contains no `guidance_messages.*` code. That is good, and it must be
   *kept*: any proposal to add a guidance code to the ceiling is an institutional approval item, not
   an engineering one. **Verified** for the current state, **Inferred** for the consequence.
2. Conversely, `UserCapabilityOverride` (`accounts/models.py:337`) can widen *effective* capability
   for one user. Existing code already tolerates that by re-checking `has_capability` at row level
   (`guidance_messages/policy.py:80`, via `eligible_relationship`), and `recipient_options`
   deliberately still pages over the canonical Appointment directory and drops rows whose provider
   capability was revoked (`services.py:495-501`). New kinds must revalidate per-row the same way:
   an earlier discovery list is advisory only. **Verified.**

**Mitigation.** Per-kind capability codes (e.g. `guidance_messages.faculty_inquiry.manage`) are the
only way to keep the four proposed families separately narrowable, but minting them is approval item
**D-GMSG-07**. Engineering default: no new code, no ceiling change, and every new kind requires an
explicit participation predicate **in addition to** a capability.

**Acceptance test.** For each new kind, assert 404 on list and get for each of
{IT_ADMIN, INSTITUTIONAL_OFFICER, HEAD designation, Institutional Officer role, FACULTY, non-participant
STUDENT}; plus one assertion that a `UserCapabilityOverride` granting a guidance code to an
out-of-role user still yields 404 (the role gate fires first).

---

### H-4 The response DTO assumes a Student exists

**Likelihood Near-certain · Impact Severe · Verified**

`GuidanceThreadResponse.student: GuidancePerson` is **required**
(`be/compass/guidance_messages/api.py:53`) and `_thread` builds it unconditionally with
`_person(thread.student)` (`api.py:234`). `assigned_to` is likewise emitted unconditionally
(`api.py:245`) — the handler's name reaches every actor who passes `require_thread`, which today
means every College-scoped staff member. Only `routing_college` is actor-conditional at present,
suppressed for Students at `api.py:236-244`.

Because the schema is `StrictSchema` and the OpenAPI document plus the Orval client are generated,
making `student` nullable is a **breaking** change for every consumer of
`guidanceMessagesListThreads`, `…GetThread`, `…OpenOfficeThread` and the Counseling-open operations
(`api.py:288-668`, 21 operations inventoried in `current-state.md` §5). `contracts/openapi.json` and
`fe/src/lib/api/generated/**` are outside GMSG-0's write scope, so this is a **sequencing** risk,
not a design detail. **Inferred** from the Verified DTO plus the generation rule.

Aggravated on the FE: `fe/src/features/guidance-messages/guidance-messages-access.ts:27-47`
recognizes exactly three roles (STUDENT, COUNSELOR, GUIDANCE_SERVICES_STAFF), and the conversation
surface renders a Student identity from the DTO; a Faculty actor has no representation in that model
at all. **Verified.**

**Mitigation.** Prefer additive, per-kind projection: keep `student` for `OFFICE`/`COUNSELING`,
introduce a discriminated `subject`/`participants` shape only in the slice that introduces the new
kind, and regenerate the contract **in the same commit** as the API change (never separately). Do
not make `student` nullable in GMSG-1. Treat `assigned_to` as a candidate for kind-conditional
suppression, mirroring `routing_college`.

**Acceptance test.** A contract test that a Faculty actor's thread payload contains no Student node
and no Counselor clinical field; an FE type-level test that the generated union is handled
exhaustively.

---

### H-5 The realtime registry cannot carry the proposed presence/typing behavior

**Likelihood Near-certain · Impact Major · Verified**

`PUBLIC_EVENT_FIELDS` is a closed, frozen mapping of **five** event names, one of which is
`messages.thread_changed` with exactly `{"thread_id"}`
(`be/realtime_service/protocol.py:46-54`); hints are validated field-for-field with canonical-UUID
checks (`protocol.py:213-231`). Channels are **per-user only** (`protocol.py:141-146`). The client
may send exactly one frame — the authentication frame — and any further client frame closes the
socket with `POLICY_VIOLATION` (`be/realtime_service/app.py:334-336`, `app.py:343-348`).

Consequences the proposal text does not account for:

- Typing indicators, read-receipt fan-out, presence and per-thread channels are **not** expressible
  without (a) new registered events, (b) a new channel model, and (c) a new inbound frame type —
  three protocol changes, each of which weakens a deliberate restriction. **Inferred.**
- Publishing is best-effort by design: `_publish` swallows transport errors
  (`be/compass/realtime/publish.py:31-40`) and `_changed` resolves recipients **at commit**
  (`guidance_messages/services.py:58-67`). There is no outbox. A dropped hint is repaired only by
  polling, and the FE freshness layer is polling-based
  (`fe/src/features/guidance-messages/guidance-messages-freshness.ts:20-21`, `:115-128`).
  **Verified.**
- Because `recipient_ids` runs at publish time, **H-1 and H-2 are push-path hazards**: a new kind
  that passes `require_thread` will be pushed to people who should never learn the thread exists.
  The hint carries `thread_id`, an opaque UUID — which is exactly enough to probe the API.
  **Inferred** from Verified routing code.

**Mitigation.** Any new event must enter the registry with the smallest possible field set and be
re-audited against the participation predicate. Do not add client→server frames to support typing;
if typing is required it needs its own approval item. Keep `thread_id` opaque — never add kind,
subject or display name to a hint.

**Acceptance test.** A protocol test that an unregistered event name is refused; a service test
that a thread whose participants fail `require_thread` yields an empty `recipient_ids` set.

---

### H-6 Notifications: silence is the current contract

**Likelihood Near-certain · Impact Major · Verified (absence)**

The notification catalog is a closed 30-event set over 12 target types
(`be/compass/notifications/policy.py:24-38`, `:42-71`). **None** of them are Guidance Messages
events, and `guidance_messages/services.py` never calls the notification recorder — the only
outbound signals are `publish_to_user_on_commit` and the audit trail (`services.py:47-67`). Email
deep links are authenticated, UUID-strict and origin-validated
(`be/compass/notifications/email_links.py:57-106`), and "currentness" is source-owned with
`is_current=True` defaulted except for `GROUP_SESSION`
(`be/compass/notifications/api.py:129-135`, `be/compass/notifications/current.py:12-30`).

The risk is asymmetric: adding a "new message" notification introduces a delivery channel whose
content surface (title, body snippet, link target) has never been scoped for confidential threads,
and the deep-link target must not be derivable. Doing so turns a **quiet** confidentiality property
into an **outbound** disclosure path — including into email, which proposal §19 explicitly forbids
("No email body leak"). **Inferred** from the Verified absence plus the link/content contracts.

**Mitigation.** Do not add message notifications in GMSG-1..GMSG-4. When they are added they must
carry no body text, be gated by the same participation predicate, and have their `is_current`
revalidation owned by Guidance Messages rather than defaulted to `True`.

**Acceptance test.** A test that no message mutation enqueues a notification; later, a test that a
notification for a staff-only kind is not delivered to a non-participant and contains zero content
fields.

---

### H-7 The case-continuity grant carries no communication authority

**Likelihood Near-certain · Impact Critical (for GMSG-5) · Verified**

`be/compass/counseling/continuity_models.py:1` opens with its own boundary: "Metadata-only
professional continuity provenance; no content authority." `ContinuitySourceKind` enumerates only
`ENCOUNTER` and `ROUTINE_EVALUATION` (`:34-36`) and `ContinuityProjection` only the two matching
metadata projections (`:39-41`) — there is no message or conversation source kind. The grant binds
`student` (`:46-48`), a **nullable** `original_counselor` (`:49-55`), `receiving_counselor`,
`starts_at`/`expires_at`, `decision` and `revoked_at` (`:44-190`).

Effective-window logic exists for records
(`counseling/continuity_services.py:230-248`, `counseling/continuity_access.py:41-65`), but it is a
**read** grant over **documents**, and it is duplicated across at least seven call sites rather than
exposed as one predicate for "is this Counselor authorized for this Student's case right now?".
**Verified** at the citations; "duplicated" from the call-site list in `access-matrix.md`.

`COUNSELOR_CASE_COORDINATION` therefore has **no existing authority to reuse**. This is why the
audit's verdict is **GMSG-5 blocked** (see [source-lifecycle.md](source-lifecycle.md)): implementing
it means inventing communication authority inside a domain that explicitly disclaims it, or silently
treating a document grant as a chat grant. Either way it needs institutional approval, not an
engineering default.

**Mitigation.** Before GMSG-5 lands:
(a) an explicit messaging-class source kind/projection, or a separate messaging grant, decided by
GCO/DPO/UCN (**D-GMSG-11/12**);
(b) one shared authorization predicate consumed by visibility, per-thread check **and**
`recipient_ids`;
(c) revocation revalidated on the **push** path, since proposal §19 requires "No access by lingering
realtime subscription".

**Acceptance test.** A test that setting `revoked_at` mid-conversation produces 404 on list/get/send
*and* removes the user from `recipient_ids` for the next hint, with no manual refresh or socket
reconnect.

---

## 3. General risk register

| ID | Risk | L | I | Mitigation | Review trigger | Label |
|---|---|---|---|---|---|---|
| R-01 | A new kind is authorized by the `require_thread` else-branch and becomes visible to all College staff | Near-certain | Critical | Exhaustive kind dispatch before GMSG-2 (H-2) | Any `ThreadKind` addition | Verified |
| R-02 | A referred Student written into `student` gains read/write/push on a staff-only thread | Near-certain | Critical | Kind-keyed participation predicate; rewrite `gm_thread_family_shape` in the same migration (H-1) | Any kind reusing `student` as "subject" | Verified |
| R-03 | Making `GuidanceThreadResponse.student` nullable breaks the generated client and every FE consumer | Likely | Major | Additive per-kind projection; contract regenerated in the same commit as the API change (H-4) | Any DTO change at `api.py:49-63` | Verified |
| R-04 | Typing/presence/read-receipt fan-out demands client→server frames the protocol closes on | Near-certain | Major | Cut the requirement, or raise an approval item; do not silently widen `app.py:343-348` | Any UX mock showing typing | Verified |
| R-05 | Adding message notifications creates an unscoped outbound content channel, including email | Likely | Severe | No notifications before GMSG-5; content-free, predicate-gated, source-owned `is_current` (H-6) | Any "notify me" request | Verified |
| R-06 | `COUNSELOR_CASE_COORDINATION` implemented on top of a metadata-only continuity grant | Near-certain | Critical | Block GMSG-5 pending an authority decision (H-7) | Any GMSG-5 ticket | Verified |
| R-07 | Faculty access added by extending `STAFF_ROLES` rather than a separate Faculty path | Likely | Severe | Keep `STAFF_ROLES` (`policy.py:17`) staff-only; Faculty authorization must be its own predicate with its own tests | Any diff touching `policy.py:17` | Inferred |
| R-08 | `FACULTY_CAPABILITY_CEILING` widened to make messaging work, silently widening Faculty reach elsewhere | Possible | Severe | Treat the ceiling (`accounts/policy.py:79`) as an approval item; verify against `:152-172` | Any new Faculty capability code | Inferred |
| R-09 | `client_message_id` reuse across threads returns 409 and confuses a retrying client | Likely | Minor | `_replay` already scopes by sender (`services.py:160-166`); keep per-sender semantics, document the 409 | Any new send path | Verified |
| R-10 | No 429 anywhere in Guidance Messages while Faculty referral surfaces are rate-limited | Near-certain | Major | A Faculty-facing thread API needs a rate-limit decision: `ERRORS = (401,403,404,409,422,503)` at `api.py:285` has no 429, unlike `referrals/faculty_services.py:180-198` | Any Faculty-facing message endpoint | Verified |
| R-11 | Lock-order inversion deadlock between actor → thread → student | Possible | Major | Preserve the documented sender→thread order (`services.py:202-207`) and the `no_key=True` Student locks (`services.py:226`, `services.py:385`); new kinds must not lock `Appointment` and `GuidanceThread` in opposite orders | Any new `select_for_update` | Verified |
| R-12 | Two open threads of a new kind for the same pair/subject — the only "one open" guard is `gm_one_open_office_per_student` | Likely | Major | Design a per-kind partial unique constraint **with** the kind; no cross-kind guard exists (`models.py:110-114`) | Any new kind with a "one open" rule | Verified |
| R-13 | Encryption AAD binds thread/message/sequence/sender, so re-parenting a thread does **not** re-encrypt it | Near-certain | Severe | Never mutate `student`/`counselor`/`routing_college` on an existing thread; treat re-parenting as out of scope. Binding at `content.py:40-46` | Any proposed "move thread" admin action | Verified |
| R-14 | Key rotation (`rotate_guidance_message_encryption`, ADR-105) not exercised against new kinds | Possible | Major | Rotation re-wraps via `QuerySet.update` in batches; a new kind must be covered by the same path; dry-run first | Any new encrypted field | Verified |
| R-15 | `read_body` raises `GuidanceMessageContentUnavailable` on any schema mismatch, so a version bump makes old threads unreadable | Possible | Severe | Keep `SCHEMA_VERSION = 1` (`content.py:11`); any bump is its own slice with a readable migration window | Any change to `content.py` | Verified |
| R-16 | Work queues silently ignore new kinds — `work.py` matches only `OFFICE`/`COUNSELING` and infers "Student spoke last" from `latest_sender_id == student_id` | Near-certain | Major | Extend or explicitly exclude per kind (`work.py:30-36`); a staff-only thread with `student` set would falsely count as "reply needed" | Any new kind | Verified |
| R-17 | `mark_read` monotonicity is enforced in Python only (`services.py:364-377`, guard at `:372`) | Rare | Minor | A DB-side `Greatest`/conditional update would close it; today a higher sequence always wins | Any bulk-import of historical messages | Inferred |
| R-18 | 404-vs-403 mapping **is** the concealment mechanism; a new path returning 403 leaks existence | Possible | Severe | Every operation must route through `_safe` (`api.py:193`) and never bypass `require_thread`'s `raise ThreadNotFound() from None` (`policy.py:58-59`) | Any error-handling change | Verified |
| R-19 | Provisional decisions in `decisions.md` are read as approved policy | Likely | Major | Every entry is labelled **Provisional — engineering default, not GCO/DPO/UCN-approved**; the approval gate is its own section, not a footnote | Any external circulation of this package | Inferred |
| R-20 | Proposal §19 references `StudentAffiliation`, which no longer exists anywhere in `be/` | Near-certain | Minor | SAR-7 `student_academics/reads.py:46-73` (`get_current_placement`) is the live source; do not plan an "adapter to legacy" | Any doc citing `StudentAffiliation` | Verified |
| R-21 | `docs/notif-04/event-channel-matrix.md:43` still documents the **pre-rename** `counseling.shared_summary.published` / `COUNSELING_SHARED_SUMMARY` and the removed module `counseling/shared_summaries.py`; the live codes are `counseling.student_session_summary.published` / `STUDENT_SESSION_SUMMARY` (`notifications/policy.py:31,62`) published from `counseling/student_session_summaries.py:118` | Near-certain | Minor | Pre-existing drift, unrelated to GMSG; flagged so GMSG-0 is not blamed for it and GMSG-6 does not copy a name that only survives as a legacy-detection predicate (`0002_student_session_summary_contract.py:23-25`) | Any new event added to that matrix | Verified |
| R-22 | Appointment reassignment never touches `GuidanceThread`, so a Counseling thread stays with the original Counselor indefinitely | Near-certain | Severe (privacy) / Major (UX) | Intended per `appointment_context` ("cancellation keeps and reassignment never transfers it", `services.py:331-332`); `appointments/services.py:1377-1393` has no thread reference. Any change is an approval item, not a bugfix | Any "handover" request | Verified |
| R-23 | `recipient_options` drops rows whose provider capability was revoked mid-page, so page sizes vary | Possible | Minor | Documented at `services.py:495-501`; acceptable, but a Faculty picker must not inherit it | Any new picker paging | Verified |
| R-24 | The FE role model has three roles; Faculty has no mapping in the access function | Near-certain | Major | `guidance-messages-access.ts:27-47` must be rewritten as a role-before-capability mirror of H-3 before any Faculty surface ships | Any FE messaging change | Verified |
| R-25 | Shipped copy assumes a Student counterpart across 20+ line-verified strings | Near-certain | Minor | Inventory in [ux-journeys.md](ux-journeys.md); every new family needs its own terminology pass | Any new conversation family shipped | Verified |

---

## 4. Cross-cutting: the pattern behind the register

Read together, one structural fact produces most of these risks: **authorization in this domain is
derived from which column holds a person, not from a declared participation relation.** `student`
means "party", `counselor` means "party", `routing_college` means "staff-visible", `assigned_to`
means "handler" — and each is overloaded, with `else` branches as the fallback.

Adding four more conversation families to a two-kind schema that encodes participation in column
identity is what makes R-01, R-02, R-16 and H-5 near-certain rather than possible. That is the
argument for the staged, typed-column migration recommended in
[implementation-plan.md](implementation-plan.md) — and for doing the exhaustive kind dispatch
**first**, while there are only two kinds to enumerate and only existing tests to keep green.

**Inferred**, from the Verified code cited throughout §2 and §3.

---

## 5. Risks accepted by this audit

Explicitly not mitigated here, because GMSG-0 changes nothing:

- All hazards above. This register is the mitigation *plan*, not the mitigation.
- Body length `BODY_LIMIT = 4000` (`content.py:10`) and the template length limits
  (`models.py:170-227`): adequate; nothing carried forward.
- Pagination `MAX_PAGE_SIZE = 50` (`services.py:43-44`) with the +1 over-fetch probe
  (`services.py:70-79`, `:102-109`): correct; accepted.
- Best-effort realtime with no outbox (`publish.py:31-40`): accepted as ADR-101 policy; the
  compensating control is FE polling, which makes this a **latency** risk (see H-5), not a
  correctness one.
- No message notifications (H-6): accepted as the current, safer state.

---

## 6. Stop conditions met / not met

Brief §10 required stopping if any of these occurred. None did.

| Condition | Result |
|---|---|
| Audit base differs from required HEAD | **Not met** — `de6902200878f1413bea7a5a90166d30be92bdfc` exact |
| A claimed dependency contradicts its own docs | **Found and recorded, not blocking**: `docs/notif-04/event-channel-matrix.md:43` (R-21) and proposal §19's `StudentAffiliation` (R-20). Corrected in this register rather than stopped on, because neither changes the audit's conclusions |
| A safe authorization boundary cannot be established | **Not met** for GMSG-1..GMSG-4; **met for GMSG-5**, reported as blocked per H-7 rather than guessed |
| Completing the audit requires code/schema/contract/generated-client/test changes | **Not met** — nine documents only |
| A path would expose Faculty–GCO or confidential content to an unauthorized role | **Not met** — no path was executed |

---

## 7. Re-scoring instructions

For each risk, in order: (1) does the cited line still read as quoted? (2) has the mitigation
landed in the named slice? (3) re-score **likelihood only** — impact is intrinsic to the disclosure
and must not be reduced because a mitigation is planned. Any hazard from H-1 to H-7 still at
Near-certain likelihood at the GMSG-1 review is a stop condition for GMSG-2, not a backlog item.
