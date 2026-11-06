# GMSG-0 — Source, participant and lifecycle truth at `de690220`

Question answered: when a *source* (Referral, continuity grant, Appointment, placement) or a
*participant* (role, activity, College) changes, what actually happens to a conversation — and what
would each proposed kind need. Every "today" statement is Verified with `path:line`; every "would
need" statement is a provisional design position.

## 1. Dependency readiness verdict (work package 4.3)

| Dep | Shipped? | Exact contract available to Guidance Messages | Evidence |
|---|---|---|---|
| **FAC** (Faculty identity + Referral provenance, docs/fac-5) | **Yes** | role `FACULTY` exists in the catalog; ceiling = exactly `referrals.submit_self` + `referrals.view_submitted_self`; `submitted_by`/`submitted_at` are persisted and DB-enforced for `FACULTY_PORTAL`; a 7-field owned projection is the only Faculty read path | `accounts/policy.py:31,79,82-85,635`; `referrals/models.py:13-16,54-61,227-253`; `referrals/faculty_services.py:294-313` |
| **CONT** (continuity grants, docs/cont-4) | **Partially — and not for messaging** | grant row with `student`, `original_counselor` (nullable), `receiving_counselor`, `decision`, `starts_at`, `expires_at`, `revoked_at`; scope kinds closed to `ENCOUNTER`/`ROUTINE_EVALUATION`; fail-closed read predicate inside `continuity_access` | `counseling/continuity_models.py:1,20-25,34-41,44-190,193-220`; `continuity_services.py:230-248`; `continuity_access.py:41-44,47,59-65,191,219,255,268` |
| **SAR** (canonical placement, docs/sar-7) | **Yes** | `student_academics.reads.get_current_placement` + `student_is_placed_in_colleges`; one mutable current row per Student + `revision`; term history in `StudentAcademicPeriodRecord` | `student_academics/models.py:18-68,82-156`; `reads.py:46-73,76-90`; consumed today at `guidance_messages/services.py:31,253` |
| **NOTIF** (authenticated deep links, docs/notif-04) | **Yes, but unused by Messages** | closed route table, strict-UUID record ids, canonical origin validation, `EmailLinkReason` enum, source-owned currentness at delivery/push/in-app | `notifications/email_links.py:40-51,57-106,109-132,135-153`; `current.py:12-30`; `delivery.py:98,372`; `push.py:237,266` |
| **CENC** (Encounter/Finish, docs/cenc-4) | **Yes, and cleanly isolated** | zero references to Guidance Threads anywhere in the counseling app | `grep -rn "GuidanceThread|GuidanceMessage|guidance_messages" be/compass/counseling/` → **0 matches** |
| **FUP** (Follow-Up boundaries, docs/fup-2b-3a) | **Yes** | `OPERATIONAL` / `COUNSELOR_CONFIDENTIAL` only; non-Counselors SQL-scoped; source-pair consistency constraint; **no Faculty visibility concept at all** | `guidance_followups/models.py:18-20,100-106`; `policy.py:117-135,169-182,209-210`; `grep -i faculty be/compass/guidance_followups/*.py` → **0 matches** |

**Consequence:** the proposal's ordering premise ("Faculty role/provenance… not yet", "academic
College placement is still resolved through legacy `StudentAffiliation`", proposal lines 8102-8106,
8104) is **false at this base**: `FACULTY` and `FACULTY_PORTAL` provenance exist, and
`grep -rn "class StudentAffiliation" be/` finds nothing — placement is already canonical SAR. Only
the CONT communication-scope assumption remains genuinely unbuilt.

## 2. Proposal assumption register — then vs `de690220`

| Proposal claim (line) | Status now | Evidence |
|---|---|---|
| Role catalog does not include `FACULTY` (8104) | **False — it exists** | `accounts/policy.py:31` |
| Faculty provisioning is proposed by #7 (8104) | **False — shipped** | `accounts/policy.py:79,82-85,635` |
| Referral submitter provenance is proposed (8104) | **False — shipped + DB-enforced** | `referrals/models.py:54-61,227-253` |
| Case continuity grants "not yet a verified installed source of authorization" (8104) | **Half true — grants exist, but carry no content/messaging authority** | `continuity_models.py:1,34-41` |
| Placement resolved through legacy `StudentAffiliation` (8104) | **False — retired; SAR is canonical** | `student_academics/reads.py:46-73`; used at `guidance_messages/services.py:31,253` |
| Two thread kinds, required Student, one open Office per Student (8061-8063) | **True — unchanged** | `models.py:11-13,27-29,110-114` |
| Read cursor table already suitable for receipts (8065) | **True for direct kinds; no institutional watermark exists** | `models.py:146-162` |
| Encryption bound to thread/message/sequence/sender (8086) | **True** | `content.py:40-46` |
| Office handler candidates = College Counselors + Heads + supervised staff (8078) | **True** | `policy.py:99-120` |
| Reassignment never transfers an existing Counseling thread (8082) | **True** | `services.py:331-334` |
| `work.py` assumes Student-last-sender (8092) | **True** | `work.py:35-36` |
| FE recognizes Student/Guidance staff only (8098) | **True** | `guidance-messages-access.ts:28-29` |
| Messages does not create an email per message; #5 not claimed (8100) | **True — zero notification surface** | verified greps, `current-state.md` §9 |
| Six kinds / participant table / typing event / office watermark exist in code (8155-8205, §15, §16) | **False — all Proposed** | no matching code anywhere |

## 3. Referral lifecycle → coordination thread

- Faculty-visible state is derived, three-valued (`SUBMITTED`, `RECEIVED_BY_GCO`,
  `ADMINISTRATIVELY_CLOSED`) and returns `None` for non-`FACULTY_PORTAL` or voided referrals —
  `referrals/administrative_state.py:6-9,12-19`. **Verified: there is no Referral status enum**; void
  (`voided_at:131`, `voided_by:132`) and closure (`administratively_closed_at/by:109-116`, digests
  `:117-124`, `administrative_version:125`) are separate facts.
- **No coupling exists in either direction today**: nothing in `be/compass/referrals/` imports
  `guidance_messages`, and message `OPEN`/`RESOLVED` cannot touch Referral state
  (`services.py:379-407` writes only thread columns). Proposal §10.5 (line 8301) and §19 (8558-8561)
  require that this stays true.
- A thread may bind only to a Referral whose `submitted_by` equals the actor and whose channel is
  `FACULTY_PORTAL` — the exact predicate already used for Faculty reads
  (`faculty_services.py:307-313`). Stable bind target = `Referral.id` UUID PK
  (`referrals/models.py:46`); `reference_code` (`:47`) is unique but **must not** be the link —
  proposal line 8168 forbids a free-text Reference Number, and `models.py` keeps the typed FK pattern
  (`relationship_appointment_id`) as precedent (`:40-46`).
- Required revalidation at each boundary (proposed): create (submitter + channel + non-void), send
  (same, plus grant-window rules of D-GMSG-09), read (submitter or current Referral authority),
  realtime recipient selection (same predicate as HTTP), and notification (recipient still entitled +
  source current, `current.py:12-30` pattern).
- Read-history vs new-send: proposal §10.5 (8303) recommends preserving authorized history and
  stopping new interaction after invalidation. Provisional position in
  [`decisions.md`](decisions.md) D-GMSG-09; **institutional confirmation required**.

## 4. Continuity grant lifecycle → case-coordination thread

- Decision values `REQUESTED, APPROVED, DECLINED, CANCELLED, REVOKED`
  (`continuity_models.py:20-25`); `decision` defaults to `REQUESTED` (`:69`); revocation is provenanced
  (`revoked_at:87`, constraint `:166-182`); interval finiteness/order enforced (`:122-152`).
- Effective-state logic exists but is grant-object-local: `_effective(grant, scopes, users, policy,
  now)` returns ACTIVE/SCHEDULED/EXPIRED/REVOKED/UNAVAILABLE/PENDING
  (`continuity_services.py:230-248`). **Verified: no callable answers "is Counselor X authorized about
  Student Y right now" without the caller already holding a grant row and its scope set** — the
  pattern is duplicated across at least seven sites (`continuity_access.py:47,59-65`;
  `continuity_services.py:251,299`; `coverage_selection.py:105`; `continuity_sources.py:81`;
  `handoff_services.py:87`; `context_access.py:50,99`).
- The proven fail-closed rule to copy: non-APPROVED, wrong receiver, or outside
  `starts_at <= now < expires_at` → `not_found` 404, re-checked after decryption
  (`continuity_access.py:59-65,191,219,255`).
- **Verified: no communication purpose is expressible** — source kinds are `ENCOUNTER` and
  `ROUTINE_EVALUATION` (`:34-36`) and the capability map enumerates only those reads
  (`continuity_access.py:41-44`). Granting GSS or any non-participant anything is out of the question:
  GSS holds no `counseling.*` capability at all (`accounts/policy.py:698-724`) and the counseling API
  hard-gates `role.code != "COUNSELOR"` → 403 (`counseling/api.py:294-299`).
- Handoff summary is a separate encrypted resource OneToOne to the grant
  (`handoff_models.py:9-23`) — proposal §12.4 (8355-8357) requires Messages never to publish or
  substitute for it. **Verified: no code path connects them today.**
- Grant expiry/revocation must stop access **without a background job** (proposal line 8404): the
  only sound mechanism is per-request revalidation of the grant at read/send/realtime, exactly as
  `continuity_access` does.

## 5. Appointment lifecycle → Counseling thread (existing behavior to preserve)

| Event | Verified effect on an existing COUNSELING thread | Evidence |
|---|---|---|
| Status → CANCELLED/RESCHEDULED | none: `appointment_context` authorizes existing threads purely by persisted participants; `eligible_relationship` is checked only when *creating* | `services.py:301-307,331-334`; `policy.py:72-81` |
| Provider reassignment | thread keeps the original `counselor_id`; the new provider gains nothing. Reassignment itself is blocked once an Encounter/RoutineInterview/E-Counseling room exists and otherwise just swaps `Appointment.provider` | `policy.py:51,63`; `appointments/services.py:1377-1393,1483` |
| Finish counseling (CENC) | no messaging side effect — zero references in `be/compass/counseling/` | verified grep |
| Student renamed / College transfer | thread keeps `student` (PROTECT) and `routing_college` (frozen at creation) | `models.py:27-32`; `services.py:266` |
| Counselor account deactivated | loses `current_actor` (`is_active=True`) → cannot read or write; thread row survives (PROTECT) | `policy.py:21-28` |

**Verified hazard to keep out of GMSG-2..5:** an existing COUNSELING thread bound to a SCHEDULED
appointment with no Encounter can outlive a provider change while remaining owned by the old
counselor — correct for confidentiality, but it means "who is the Counselor for this Student" and
"who may read this thread" are different questions that must never be merged.

## 6. Placement and organizational change → Office routing

- Placement is read only at creation (`services.py:253-266`); `routing_college` is immutable
  afterwards, and visibility is evaluated against it (`policy.py:48-49,65-67`).
- Scope is re-resolved per request from `organization/access_scope.py:109-154` (Counselor
  responsibility, staff supervision, Head → all active Colleges).
- **Verified:** `student_academics.reads.get_current_placement` does not consult
  `placement_effective_at` (`models.py:44` vs `reads.py:46-73`) and there is no date-ranged placement
  history, so "which College owned this Student when this thread was created" is unrecoverable from
  placement alone — the thread's own `routing_college` is the only historical record. Any future
  re-routing rule must not rewrite it (proposal §14.4 line 8412).

## 7. Messaging-lifecycle mechanics that already exist (and their edges)

- Resolve/reopen (`services.py:379-407`) is staff-only (`:384`), audited (`:404`), publishes to
  recipients (`:406`) and re-checks one-open-Office on reopen (`:390-399`). `set_status` locks
  actor → student → thread, matching `open_office_thread`'s order — **Inferred: consistent ordering is
  what prevents the create/reopen deadlock; any new kind with its own uniqueness rule must join the
  same lock order.**
- Send on `RESOLVED` is refused (`services.py:175-176`) with `MessagesConflict` → 409
  (`api.py:206-208`).
- Idempotency: `_replay` (`:160-166`) returns the prior message for the same
  `(sender, client_message_id)`, and cross-thread reuse is a conflict; first-send replay in
  `open_office_thread` additionally verifies the prior thread's kind and Student (`:237-246`) —
  **Verified pattern to generalize: the replay check must name the new kind and its source object.**
- Handler assignment never grants access (`policy.py:123-135`, `services.py:410-433`); a stale
  candidate is refused at save time (`:416-419`) and the FE refetches rather than auto-retrying
  (`guidance-handler-assignment.tsx:141-143`).
- **Verified lifecycle gaps for GMSG-6/7:**
  1. `mark_read` writes no audit event (`services.py:363-376`) — fine for privacy (proposal §20.7 line
     8610 discourages routine seen auditing), but it means an institutional Seen watermark cannot be
     reconstructed from audit if it is ever promised retrospectively.
  2. No office-level read row exists (`models.py` has 4 models), so "Seen by Guidance Office" would
     survive a handler change only if a new durable watermark is added (D-GMSG-04).
  3. Deleting/deactivating the last eligible staff member of a College leaves the thread's
     `assigned_to` pointing at them (PROTECT keeps the row; `eligible_handler` would refuse a *new*
     assignment) — the queue keeps being visible to scope-holders, so no orphaning, but reply-needed
     hides it (`work.py:32`).

## 8. Retention, records and deletion

- **Verified:** no retention, export, disposition or deletion code exists for Guidance Messages —
  messages are append-only (`services.py:185` `force_insert=True`) and every FK is `PROTECT`.
- Proposal §14.5 (8414-8416) and §27 (8895) make actual retention a GCO/DPO/records decision
  (D-GMSG-16), explicitly **out of scope** for engineering to invent. This audit therefore defers it
  and records the deferral rather than proposing a purge job.
