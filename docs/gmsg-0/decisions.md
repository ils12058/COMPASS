# GMSG-0 — Decision register

`D-GMSG-01..18` map 1:1 to Proposal #10 §26 (lines 8855–8878). `D-GMSG-19..30` are decisions this
audit surfaced; they are engineering-owned unless marked otherwise.

**Status vocabulary.** `Provisional — engineering default, not GCO/DPO/UCN-approved` means an
engineer chose a safe default so a later slice can proceed; it is **not** institutional approval.
`Open — institutional approval required` means no slice may implement the behavior until GCO/DPO/UCN
answer. No decision here introduces a feature flag or toggle (ground rule 4); where a phased rollout
is needed it is a code-owned provisional policy in the
`be/compass/referrals/provisional_activation.py:5-11,52-133,206-224` style (fixed synthetic audit
event UUIDs, code-owned digests, no env/DB switch, PROVISIONAL never cross-validating APPROVED).

| ID | Proposal §26 item | Topic |
|---|---|---|
| 01 | 1 | General Faculty intake authority |
| 02 | 2 | Faculty Inquiry topic separation |
| 03 | 3 | Office read semantics ("Seen by Guidance Office") |
| 04 | 4 | Office sender receipts |
| 05 | 5 | Counselor-pair conversation uniqueness |
| 06 | 6 | Direct-thread resolution |
| 07 | 7 | Case-grant history after expiry |
| 08 | 8 | Grant source scope / communication purpose |
| 09 | 9 | Faculty Referral closure and void |
| 10 | 10 | Student notification of Faculty submission |
| 11 | 11 | GSS operational eligibility |
| 12 | 12 | Message notification channels |
| 13 | 13 | Typing defaults |
| 14 | 14 | Read-receipt expectations |
| 15 | 15 | Confidentiality guidance copy |
| 16 | 16 | Retention and record access |
| 17 | 17 | Dual-capacity roles |
| 18 | 18 | Rollout dependencies |

## Institutional-scope decisions

### D-GMSG-01 — General Faculty intake authority
**Context:** a Faculty inquiry needs an institutional recipient. Today Office routing resolves a
**Student's** College placement plus that College's default Counselor
(`services.py:253-262`) and visibility is College scope (`policy.py:48-49`). A Faculty inquiry has no
Student, so no College, so no route exists.
**Options:** (a) route to a Head-designated institution-wide intake responsibility; (b) fan out to
every COUNSELOR with `guidance_messages.manage` across all Colleges; (c) refuse creation until GCO
names an intake team.
**Provisional recommendation:** (a) with (c) as the runtime behavior — create only when an intake
responsibility resolves, else `MessagesConflict`, mirroring the existing refuse-when-unroutable branch.
Never reuse the Faculty's home College as the boundary (proposal line 8263).
**Rationale:** option (b) makes an institution-wide inbox out of a College-scope mechanism and would
expose a Faculty thread to every scoped staff member on earth.
**Status:** `Open — institutional approval required` (which staff/designation, queue, fallback).
**Owner:** GCO. **Impact:** blocks GMSG-2; a `routing_intake_responsibility`-style field or an
`organization` scope is new work, not a tweak.

### D-GMSG-02 — Faculty Inquiry topic separation
**Context:** proposal §9.4 (line 8267) wants separate inquiries for separate topics and explicitly not
the one-open-thread-per-Student rule (`models.py:110-114`).
**Options:** (a) unlimited concurrent inquiries per Faculty with a rate limit; (b) soft concurrency
cap plus a deliberate reopen; (c) one open inquiry per Faculty.
**Provisional recommendation:** (b) — a bounded number of open inquiries plus the existing
`(sender, client_message_id)` idempotency (`models.py:137-139`) so a retried first message cannot
duplicate an inquiry.
**Rationale:** (c) reproduces an invariant that exists to protect Student/Office workload identity, and
(a) with no cap invites a queue-flooding DoS against GCO.
**Status:** `Provisional — engineering default, not GCO/DPO/UCN-approved`.
**Owner:** GCO (concurrency number), Engineering (mechanism). **Impact:** GMSG-2; needs a partial
unique/count guard, no new table.

### D-GMSG-03 — Office read semantics
**Context:** "Seen by Guidance Office" could mean the assigned handler or any authorized reader. Today
there is one per-(thread,user) cursor (`models.py:146-162`) advanced only by `mark_read`
(`services.py:363-376`); nothing distinguishes handler from reader, and College-scoped staff can read a
thread without being assigned (`policy.py:48-49`).
**Options:** (a) designated handler's cursor; (b) any authorized Office reader's cursor; (c) no Office
Seen at all.
**Provisional recommendation:** (b) — any authorized reader who performs the genuine mark-read action,
because (a) silently loses the fact that a scoped colleague already read the message and would let an
assignment change un-see content.
**Rationale:** the requester addressed the Office, not a person (proposal line 8438).
**Status:** `Open — institutional approval required` (proposal line 8861 recommends an
"appropriate handler/intake authority" — that is *not* what (b) does; the divergence must be
explicitly resolved rather than quietly implemented).
**Owner:** GCO. **Impact:** GMSG-6; if (a) is chosen, an `office_watermark` row plus handler-change
revalidation is required (see D-GMSG-23).

### D-GMSG-04 — Office sender receipts
**Context:** should staff see a Student's/Faculty's personal Seen on Office replies?
**Options:** (a) yes within the requester-facing side of an authorized Office thread; (b) no.
**Provisional recommendation:** (a) for Student Office only; withheld for `REFERRAL_COORDINATION` and
`FACULTY_INQUIRY` until D-GMSG-03 and D-GMSG-22 land, because the same DTO field set that would show
it also carries staff identity today (`api.py:247`).
**Rationale:** asymmetric receipts are already the reality — `mark_read` publishes to the reader only
(`services.py:375`), so nothing today tells a peer the cursor moved.
**Status:** `Open — institutional approval required`. **Owner:** GCO/DPO.
**Impact:** GMSG-6 response DTO addition.

### D-GMSG-05 — Counselor-pair conversation uniqueness
**Context:** proposal §11.4 (line 8332) requires canonical unordered-pair identity; no pair concept
exists in code (the thread has `student`, `counselor`, `assigned_to`, `created_by` —
`models.py:27-56`).
**Options:** (a) one persistent direct thread per pair; (b) bounded episodic direct threads.
**Provisional recommendation:** (a) — one discoverable direct thread per canonical pair, with a
partial unique index on the canonicalized pair (D-GMSG-21).
**Rationale:** (b) needs a definition of "episode" that the schema cannot derive, and duplicate
pairwise history is exactly what makes "which chat was about the logistics question" unanswerable.
**Status:** `Open — institutional approval required` (UX outcome), engineering able to implement
either. **Owner:** GCO/UCN. **Impact:** GMSG-4.

### D-GMSG-06 — Direct-thread resolution
**Context:** `set_status` is staff-only today (`services.py:384,386`) and would be a category error for
a peer chat.
**Options:** (a) either counselor may resolve/reopen; (b) direct threads never resolve; (c) archive-
style dismissal per participant.
**Provisional recommendation:** (b) — keep `OPEN` for direct kinds and let each counselor filter it out
personally; avoid converting casual office chat into a fake case outcome (proposal line 8864).
**Rationale:** `RESOLVED` today carries institutional meaning (`resolved_by` provenance,
`models.py:61-68,98-106`) that a peer chat has no right to borrow.
**Status:** `Open — institutional approval required`. **Owner:** GCO. **Impact:** GMSG-4 + GMSG-8 copy.

### D-GMSG-07 — Case-grant history after expiry
**Context:** proposal §12.6 (line 8365) recommends denying new sends **and** confidential history reads
after invalidity. Code today has no message↔grant link at all, so nothing to preserve or revoke.
**Options:** (a) immediate total denial for both parties; (b) receiving Counselor loses reads,
originating Counselor keeps them; (c) time-boxed read tail.
**Provisional recommendation:** (a) — deny new sends and history reads for both participants on
`REVOKED`; treat normal `expires_at` passage identically until GCO says otherwise.
**Rationale:** (b)/(c) require a rule engine over "who was authorized for what when", which does not
exist (`continuity_services.py:230-248` is grant-local); a default that reads nothing is the only
implementable fail-closed position today.
**Status:** `Open — institutional approval required`. **Owner:** GCO/DPO. **Impact:** GMSG-5.

### D-GMSG-08 — Grant source scope / communication purpose — **the blocking one**
**Context:** the audit searched for any communication authority in the continuity contract:
`ContinuitySourceKind` is `{ENCOUNTER, ROUTINE_EVALUATION}`
(`continuity_models.py:34-36`), the capability map enumerates only those two reads
(`continuity_access.py:41-44`), and the module docstring says "Metadata-only professional continuity
provenance; no content authority." (`continuity_models.py:1`).
**Options:** (a) treat an approved grant as implicitly authorizing case-coordination messaging;
(b) require an explicit additional approved communication scope on the grant; (c) ship the kind with
no authority (never).
**Provisional recommendation:** (b). Option (a) is **rejected**: messaging is content authority and the
shipped contract disclaims exactly that. (c) is prohibited by ground rules and by proposal line 8896.
**Rationale:** reusing a source-read grant as a write-side communication right would let an
`ENCOUNTER`-scope coverage grant open an unbounded confidential channel.
**Status:** `Open — institutional approval required` **and** a code prerequisite: GMSG-5 is blocked
until (i) a communication scope exists on the grant and (ii) a single
"is this pair authorized for this Student now" service exists (see D-GMSG-29 / risks).
**Owner:** GCO (+ Engineering to build the scope). **Impact:** gates GMSG-5 entirely.

### D-GMSG-09 — Faculty Referral closure and void
**Context:** Faculty-visible state is derived and void-aware
(`administrative_state.py:6-19`), closure/void fields are real
(`referrals/models.py:109-132,227-253`), and no Referral↔message coupling exists today.
**Options:** (a) closure stops new sends, keeps reads; (b) closure stops both; (c) void stops both,
closure stops nothing; (d) staff-only continued send.
**Provisional recommendation:** (c) as the engineering floor — an **administrative closure alone does
not** break the conversation (proposal line 8303 agrees), a **void** stops new sends for the Faculty
side and keeps encrypted history for authorized staff; and never let message `OPEN`/`RESOLVED` write
back to Referral state (proposal line 8301).
**Rationale:** voiding is the only state in the code that already nullifies the Faculty projection
(`administrative_state.py:12-19`), so it is the natural send boundary.
**Status:** `Open — institutional approval required` (how long, who may still send).
**Owner:** GCO. **Impact:** GMSG-3 send path plus a documented rule; encrypted history untouched.

### D-GMSG-10 — Student notification of Faculty submission
**Context:** no message notification exists at all (`current-state.md` §9), and Referral notification
contract re-checks active FACULTY (`referrals/notification_contract.py:46`).
**Provisional recommendation:** no automatic Student notification and no inferred Student access —
message-side and Referral-side (proposal line 8868, §10.4 line 8297).
**Status:** `Provisional — engineering default, not GCO/DPO/UCN-approved` (negative rule; the separate
Referral-policy question stays with GCO). **Owner:** GCO. **Impact:** GMSG-3; a tested negative.

### D-GMSG-11 — GSS operational eligibility
**Context:** GSS holds `guidance_messages.view/manage/templates.manage`
(`accounts/policy.py:702-704`) and reaches every College-scoped Office thread
(`policy.py:48-49`), but no counseling capability at all (`accounts/policy.py:698-724`,
`counseling/api.py:294-299`).
**Provisional recommendation:** GSS may work Student Office, and — only if GCO names an intake
responsibility (D-GMSG-01) — Faculty Inquiry and Referral Coordination queues; GSS may **never**
appear in `COUNSELOR_DIRECT` or `COUNSELOR_CASE_COORDINATION`.
**Rationale:** the two existing boundaries already encode this split; generalizing it is safer than
inventing a new role concept.
**Status:** `Open — institutional approval required` (eligibility detail), negative rule engineering-
fixed. **Owner:** GCO. **Impact:** GMSG-2/3/4/5 negative tests.

### D-GMSG-12 — Message notification channels
**Context:** zero message events; adding one costs five coordinated changes (enum member, catalog
entry, target type, route, FE mapping) because `NotificationTargetType` (`policy.py:24-38`) and
`_RECORD_ROUTES` (`email_links.py:40-51`) are closed sets, and in-app currentness is opt-in per event
(`notifications/api.py:129-135`, `current.py:12-30`).
**Options:** (a) realtime/in-app only; (b) coalesced background email for Office kinds; (c) per-message
email.
**Provisional recommendation:** (a) until GCO asks for more; (c) rejected outright.
**Rationale:** currentness would have to be registered per event or every stale message link claims
"is current"; body-free links are the only safe email content
(`email_links.py:109-153`).
**Status:** `Open — institutional approval required`. **Owner:** GCO/DPO. **Impact:** GMSG-8.

### D-GMSG-13 — Typing defaults
**Context:** no inbound realtime path exists (see D-GMSG-24).
**Provisional recommendation:** heartbeat at most once per ~3–4s, TTL ~6–10s with local expiry on
receipt, never displayed for `RESOLVED`, unauthorized or hidden conversations, suppressed entirely if
the thread's kind is case-coordination once D-GMSG-07 is decided.
**Rationale:** values chosen to be conservative against the 512-byte frame cap and exact-field registry
(`protocol.py:36,216-223`), not from load testing — **Unknown** until measured.
**Status:** `Provisional — engineering default, not GCO/DPO/UCN-approved` (proposal line 8871 wants
agreement, including reduced-motion behavior). **Owner:** GCO + Engineering. **Impact:** GMSG-7.

### D-GMSG-14 — Read-receipt expectations
**Provisional recommendation:** receipts are advisory and never mandatory-per-kind; per the strict
definition in §3.1 of `ux-journeys.md`, no kind may display Seen without a real authorized view, and
nothing may display "Delivered".
**Status:** `Open — institutional approval required`. **Owner:** GCO/DPO. **Impact:** GMSG-6.

### D-GMSG-15 — Confidentiality guidance copy
**Provisional recommendation:** ship the composer notice pointing case topics to Case Coordination
(proposal line 8328) and the "not 24/7 / emergency" line (line 8392) as **placeholder text pending
GCO-approved wording**; do not invent institutional commitments.
**Status:** `Open — institutional approval required`. **Owner:** GCO. **Impact:** GMSG-4/8 copy.

### D-GMSG-16 — Retention and record access
**Context:** no retention/export/disposition code exists; messages are append-only
(`services.py:185`) and every FK `PROTECT`.
**Provisional recommendation:** **defer entirely** — build no purge, export or legal-access path in
GMSG-1..8; records governance owns that (proposal lines 8414-8416, 8895).
**Status:** `Open — institutional approval required`. **Owner:** DPO + records governance.
**Impact:** none in this family; a stated non-goal.

### D-GMSG-17 — Dual-capacity roles
**Context:** one primary role per account (`User.role`, and `policy.py:33-38` branches on
`actor.role.code` exactly once). A person who is both Faculty and Counselor can only hold one.
**Provisional recommendation:** do **not** merge privileges; a dual-capacity person uses the single
role on their account, and Messages must not offer the other role's kinds. If both are genuinely
needed, that is a formal identity-policy change, not a messaging change.
**Rationale:** capability-union hacks would silently give a Faculty account peer Counselor access.
**Status:** `Open — institutional approval required`. **Owner:** GCO/UCN. **Impact:** all kinds; a
documented limitation plus a negative test.

### D-GMSG-18 — Rollout dependencies
**Verified answer to the proposal's question (line 8876):** #7 Faculty identity + provenance
**shipped**; #6 continuity grants **shipped but without communication scope**; #1 SAR placement
**shipped and already consumed** by Messages creation (`services.py:31,253`); #5 notification deep
links **shipped and unused** by Messages. `StudentAffiliation` is gone. So GMSG-2/3/4 are unblocked
modulo D-GMSG-01/08, and GMSG-5 is blocked on CONT, not on scheduling.
**Status:** `Provisional — engineering default, not GCO/DPO/UCN-approved` (facts verified; the release
sequencing remains a GCO/UCN call). **Owner:** Engineering + GCO. **Impact:** sequencing of all slices.

## Engineering decisions surfaced by this audit

### D-GMSG-19 — Participant representation and migration style
**Options** — the full comparison (Student-nullability, per-kind cardinality, unique indexes, locking,
old-thread compatibility, DTO compatibility, encryption binding, backfill, fresh vs upgrade, rollback)
is in [`implementation-plan.md`](implementation-plan.md) §1.
**Provisional recommendation:** **Option 1 — expand `GuidanceThread` with typed, kind-constrained
participant/source columns**, staged so that GMSG-1 keeps `student` NOT NULL and adds new kinds'
columns without permitting any new kind; nullability arrives only in the slice that needs it, with a
CHECK that forbids `student` on non-legacy kinds.
**Rejected:** Option 2 (participant table) — per-kind cardinality cannot be CHECKed across rows, pair
races need advisory locks, and a membership table is precisely the "client-supplied arbitrary
participant list" surface proposal line 8176 forbids; Option 3 (compat layer, keep `student` as an
authorization input) — that is the disclosure hazard at proposal line 8656.
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-1.

### D-GMSG-20 — Canonical kind codes and capability names
**Provisional recommendation:** keep the existing two verbatim and add
`FACULTY_INQUIRY`, `REFERRAL_COORDINATION`, `COUNSELOR_DIRECT`, `COUNSELOR_CASE_COORDINATION`
(`models.py:11-13` precedent, `max_length=16` must be widened —
the longest proposed code is 26 characters, `models.py:23`). Capabilities:
`guidance_messages.faculty_inquiry.view_self` / `.manage_self`,
`guidance_messages.referral.view_self` / `.manage_self`,
`guidance_messages.counselor_direct.view` / `.manage`,
`guidance_messages.case_coordination.view` / `.manage`, plus
`guidance_messages.office_intake.manage` for scoped staff work — **not** a widened
`guidance_messages.manage` (proposal lines 8230-8233; the current `manage` implies `view`
per `accounts/policy.py:820-822`, so reusing it would silently grant every College Office thread).
**Status:** `Provisional — engineering default` (names need GCO/UCN blessing with the copy).
**Owner:** Engineering. **Impact:** GMSG-1 (catalog + implications), GMSG-2..5 (grants).

### D-GMSG-21 — Counselor-pair canonicalization and uniqueness mechanics
**Provisional recommendation:** two columns `direct_first_user`, `direct_second_user` with a DB CHECK
`first < second` (canonical by UUID order) plus a partial unique index
`(direct_first_user, direct_second_user) WHERE kind = COUNSELOR_DIRECT` (open threads only if
D-GMSG-05 resolves to one-persistent). Service canonicalizes before insert; `select_for_update` on the
second user then the first (a consistent global order) prevents the A→B / B→A race, with the unique
index as the independent final guard — the same belt-and-braces logic already documented for send
(`services.py:203-206`).
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-4.

### D-GMSG-22 — Staff identity in the requester-facing DTO
**Verified finding:** `api.py:247` returns `assigned_to` (a `GuidancePerson` with full name,
`api.py:225-227`) to **every** authorized reader, including the Student; `routing_college` is already
conditionally suppressed for Students (`api.py:240-246`) but `assigned_to` is not. The FE never renders
it (`guidance-messages-presentation.ts:50,55`).
**Provisional recommendation:** suppress `assigned_to` for non-staff requesters (mirror the
`routing_college` treatment) in the same slice that introduces a Faculty requester, and keep it for
staff. If any existing consumer needs it, prefer surfacing `GuidanceRecipientOptions.office_label`
(`api.py:117-118`) instead.
**Rationale:** proposal lines 8373 and 8442 forbid exposing staff identity/group membership to the
requester; the field already crosses that boundary today even though no screen shows it.
**Status:** `Provisional — engineering default` (a **behavior change** needing GCO awareness because it
alters an existing Student-visible contract). **Owner:** Engineering + GCO. **Impact:** contract change
→ generated client; belongs to the slice that changes the API.

### D-GMSG-23 — Office Seen watermark necessity
**Provisional recommendation:** derive Office Seen from existing per-user cursors where D-GMSG-03
chooses "any authorized reader" (no new table needed: the max cursor among currently-authorized readers
is computable from `models.py:146-162`); add a durable monotonic watermark row **only** if GCO chooses
handler-scoped semantics or promises Seen that survives reassignment.
**Rationale:** proposal line 8440 and line 8174 make the watermark conditional; §15.6 (line 8454)
forbids fabricating historical Seen, so the derived version must show an honest "not yet seen" for
legacy threads.
**Status:** `Provisional — engineering default`, contingent on D-GMSG-03. **Owner:** Engineering.
**Impact:** GMSG-6.

### D-GMSG-24 — Typing transport
**Verified constraint:** the realtime layer is server→client only — the public registry is a closed
5-event exact-field map (`protocol.py:46-54`), channels are per-user and derived from the ticket
(`:141-146`, `app.py:260-262`), and the only permitted post-auth client frame is a policy violation
that closes the socket (`app.py:334-336,343-348`). **There is no client→server signal at all.**
**Provisional recommendation:** typing start/stop travels as an **authenticated HTTP call** (a narrow
`POST /threads/{id}/typing`, authorization = the same `require_thread(manage=True)`), the server then
publishes a new registered event `messages.typing_changed {thread_id}` to the recomputed recipients
through the existing content-free path; a TTL is carried in the payload only if the registry gains a
bounded non-UUID field — **which the registry currently forbids** (`:219-223` requires canonical UUIDs),
so TTL must live in the receiver, or the validator must be intentionally widened. That widening is a
real design decision, not a detail.
**Rejected:** a presence/room channel (does not exist, would break per-user authorization) and a
WebSocket command frame (does not exist, and `app.py:343-348` deliberately closes on it).
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-7 touches
`be/realtime_service/protocol.py`, `be/realtime_service/app.py` policy, a new endpoint and the FE
mirror `realtime-protocol.ts:28-34`.

### D-GMSG-25 — Per-kind work indicators (and the unassigned-Office fix)
**Provisional recommendation:** replace `latest_sender_id = student_id` (`work.py:35-36`) with a
kind-specific "requester side vs office side" predicate: a thread is reply-needed when the last message
was authored by someone **outside** the reader's side of that kind, and include
`assigned_to IS NULL` open Office threads in the queue.
**Rationale:** both halves are existing defects for today's two kinds (Verified, `work.py:32`), and the
Student-identity equality cannot be reused for Faculty/peer kinds at all.
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-1 (structure)
→ GMSG-8 (surfacing); existing FE/queue tests must be re-checked, not assumed.

### D-GMSG-26 — Mark-read integrity and monotonicity enforcement
**Verified:** monotonicity is Python-only under the thread lock (`services.py:363-376`) with no DB
constraint beyond `>= 0` (`models.py:159-161`), and no audit event.
**Provisional recommendation:** before Seen becomes user-visible, enforce it in the database too (a
`CHECK` cannot reference another row, so a trigger is wrong here — instead add a conditional update
`… WHERE last_read_sequence < :new` and assert the affected row count, keeping the thread lock), and
keep audit off by default (proposal §20.7 line 8610 warns against routine seen telemetry; if staff-
performance visibility is ever requested it is a DPO question).
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-6.

### D-GMSG-27 — DTO and generated-client compatibility
**Provisional recommendation:** add `participant`/`purpose` projections additively, and make `student`
optional in the same release that first returns a non-Student thread; never let an old client interpret
a Faculty thread as a Student record (proposal line 8626). Hand-editing
`contracts/openapi.json` or `fe/src/lib/api/generated/**` is prohibited
(`fe/AGENTS.md` §4, §57) — the client changes in the slice that changes the API.
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-2..5 contracts.

### D-GMSG-28 — Rate limits
**Verified:** a Redis limiter with fail-closed defaults already exists
(`be/compass/common/rate_limit.py`, used at `referrals/faculty_api.py:110` and
`faculty_services.py:180-198`, `settings.py:188-192` with `RATE_LIMITER_FAIL_OPEN` default `False`),
while Messages declares no 429 (`api.py:285`) even though the FE already maps one
(`guidance-messages-errors.ts:28`).
**Provisional recommendation:** reuse that limiter for inquiry creation and typing heartbeats
(proposal §20.6 line 8606) and only then keep the existing 429 copy honest.
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-2, GMSG-7.

### D-GMSG-29 — Authorization centralization
**Verified:** two facts make this necessary. (1) `require_thread` uses an **else-branch** meaning
"anything not COUNSELING is Office-by-College" (`policy.py:62-67`), so a new kind carrying
`routing_college` becomes instantly visible to all College-scoped staff — the single most dangerous
line in this audit. (2) Continuity authorization is duplicated across ≥7 call sites with
grant-local logic (`continuity_services.py:230-248` and the sites listed in `source-lifecycle.md` §4).
**Provisional recommendation:** rewrite `authorized_threads`/`require_thread`/`recipient_ids` as an
explicit per-kind matrix with **deny for any unlisted kind**, land it in GMSG-1 while only two kinds
exist (so the legacy behavior is provably unchanged), and require GMSG-5 to consume one CONT predicate
service rather than writing an eighth copy.
**Status:** `Provisional — engineering default`. **Owner:** Engineering. **Impact:** GMSG-1 (blocker for
everything after it).

### D-GMSG-30 — Records governance owner
**Provisional recommendation:** name DPO + records governance as the owner of retention/disposition and
keep GMSG-1..8 free of any deletion or export path (see D-GMSG-16). Encryption is a safeguard, not a
retention authority.
**Status:** `Open — institutional approval required`. **Owner:** DPO. **Impact:** none now; blocks any
future "records access" feature.

## Institutional approval gate (explicit, separate from the above)

Nothing in this package is GCO-, DPO- or UCN-approved. Before GMSG-2, GCO must answer D-GMSG-01 (and
with it D-GMSG-11); before GMSG-5, GCO/DPO must answer D-GMSG-07 and **both approve and see built** the
communication scope in D-GMSG-08; before GMSG-6, D-GMSG-03/04/14; before GMSG-7, D-GMSG-13; before
GMSG-8, D-GMSG-12/15/16. Engineering-provisional defaults may be implemented only where the row above
says `Provisional`, and each such implementation must carry the provisional label in its own slice doc,
never a claim of approval.
