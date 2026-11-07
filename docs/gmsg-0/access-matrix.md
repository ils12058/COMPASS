# GMSG-0 — Six-kind relationship, access and negative-privacy matrix

Labels: **Existing** = implemented at `de690220`; **Proposed** = design target only, no code.
Every Existing row's `path:line` refers to `be/compass/guidance_messages/` unless stated. Nothing in a
**Proposed** row is implemented, reachable or enforced.

## 1. Kind-by-kind matrix

### 1.1 `OFFICE` — Student ↔ Guidance Office institutional endpoint — **Existing**

| Dimension | Verified current state |
|---|---|
| Initiator / counterpart | Student for themselves, or staff acting for a scoped Student (`services.py:216-220`), against the institutional Office |
| Source binding | `routing_college` required; no counselor, no appointment (`models.py:80-87`) |
| Participant identity | `student` (non-null `PROTECT`, `models.py:27-29`) + every staff whose College scope covers `routing_college` (`policy.py:48-49,65-67`) |
| Creation / routing | `open_office_thread` (`:216`): placement via `student_academics.reads.get_current_placement` (`:253`), default counselor via `organization.services.resolve_default_counselor_for_student` (`:254`), refusing if that counselor lacks `guidance_messages.manage` or the College is outside its operational scope (`:255-262`) → `MessagesConflict` |
| Required role + capability + resource authority | role ∈ {STUDENT, COUNSELOR, GSS} (`policy.py:33-38`) **and** `view_self`/`manage_self` or `view`/`manage` (`:39-40`) **and** `student_id=actor` or College-scope membership (`:46-49,60-67`) |
| Uniqueness / lifecycle | one open thread per Student (`models.py:110-114`); reopen re-checks it under the Student lock (`services.py:390-399`); `OPEN`/`RESOLVED` only (`models.py:16-18,98-106`) |
| Handler | `assigned_to` set at creation (`services.py:267`), assignable for OFFICE only (`services.py:414-415`), candidates from `office_staff_candidates` + per-candidate revalidation (`policy.py:99-146`) |
| DTO projection | `GuidanceThreadResponse` with `student`, `routing_college` (hidden from Student viewers, `api.py:240-246`) and `assigned_to` (**visible to all authorized readers**, `api.py:247`) |
| Realtime recipients | `recipient_ids`: the Student ∪ `office_staff_candidates`, each passed through `require_thread` (`policy.py:151-164`) |
| Notifications | none (`notifications/policy.py:42-71`; verified absence in `current-state.md` §9) |
| Work indicator | `kind=OFFICE AND assigned_to_id=actor AND latest_sender=student AND status=OPEN` (`work.py:30-36`); unread via `_directory` annotations (`services.py:80-99`) |

**Never sees or infers it:** IT Admin and Institutional Officer (role gate `policy.py:33-38`);
Faculty (`accounts/policy.py:79` ceiling — no messages capability, and the role gate would deny even
if overridden); a Counselor outside the College scope (`policy.py:49`); another Student
(`policy.py:47,61`).

### 1.2 `COUNSELING` — Student ↔ exact original Appointment Counselor — **Existing**

| Dimension | Verified current state |
|---|---|
| Initiator / counterpart | the exact `appointment.student` or the exact `appointment.provider` (`policy.py:84-88`) |
| Source binding | `relationship_appointment` OneToOne `PROTECT` (`models.py:40-46`), `counselor` required, `routing_college` forbidden, `assigned_to` forbidden (`models.py:88-94`) |
| Eligibility | `eligible_relationship`: counseling service code, status ∈ {SCHEDULED, COMPLETED}, active Student with STUDENT role, active provider with COUNSELOR role holding `guidance_messages.view` (`policy.py:72-81`) |
| Lifecycle | `open_counseling_thread` locks the appointment then the thread and reuses by appointment (`services.py:284-325`); `appointment_context` (`:328-360`) resolves the thread or `can_start`, and its docstring states the boundary: an existing thread is authorized **only** by persisted participants, so "cancellation keeps and reassignment never transfers it" |
| Reassignment | `appointments/services.py:1377-1393` blocks reassignment when an Encounter/RoutineInterview/ECounselingRoom exists and swaps `provider` at `:1483`; it never queries `GuidanceThread`. **Verified: access is not recomputed — it is frozen by `counselor_id` (`policy.py:51,63`)** |
| DTO projection | `student` + `counselor` + `relationship_appointment_id`; `routing_college` null by constraint |
| Realtime recipients | exactly `{student, counselor}` through `require_thread` (`policy.py:152-153`) |
| Work indicator | `kind=COUNSELING AND counselor_id=actor AND latest_sender=student` (`work.py:32-36`) |
| Notifications | none |
| Staff (GSS) access | **denied** — `authorized_threads` adds COUNSELING rows only for role COUNSELOR (`:50-51`) and `require_thread` demands `role.code=="COUNSELOR" AND counselor_id==actor` (`:63`) |

**Never sees or infers it:** GSS, IT Admin, Institutional Officer, Faculty, another Counselor, another
Student, and — for the *other* direction — the Clinical domain: counseling content policy stays
Counselor-only (`counseling/api.py:294-299`, `accounts/policy.py:698-724`).

### 1.3 `REFERRAL_COORDINATION` — submitting Faculty ↔ Guidance Office, one Referral — **Proposed**

| Dimension | Design position (provisional) |
|---|---|
| Initiator / counterpart | the original authenticated `FACULTY` submitter ↔ the institutional GCO endpoint |
| Source binding | exactly one `Referral` whose `submission_channel=FACULTY_PORTAL` and whose immutable `submitted_by` equals the requester (`referrals/models.py:13-16,54-61,227-253`) |
| Student identity | **subject only**, never a participant. The Student's College may drive routing; the Student's UUID must never be written into `GuidanceThread.student` for this kind |
| Routing | Student's College from the Referral (placement read `student_academics/reads.py:46-73`), **not** the Faculty home College (proposal line 8379) |
| Required authority | role `FACULTY` **and** a new narrow self capability (proposal §8.2 line 8230) **and** `submitted_by_id == actor` — the exact predicate already used by `referrals/faculty_services.py:307-313`; typed `referrer_name` never proves authorization (proposal line 8279) |
| Lifecycle | one thread per Referral; `OPEN`/`RESOLVED` must not move any Faculty-visible Referral state (`administrative_state.py:6-19`) |
| DTO projection | requester = Faculty person; `student` field must be absent/null in the contract; subject surfaced only to staff already entitled to the Referral detail |
| Realtime recipients | `{original submitter} ∪ {GCO staff passing current Referral/College authority}`, each re-checked with the HTTP predicate |
| Notifications | none today; any future notice must be content-free and deep-link validated (`email_links.py:57-132`) |
| Work indicator | requester-side "awaiting Office" must key on the Faculty requester, not `student_id` (`work.py:36` cannot express this today) |

**Negative rule (mandatory):** the referred Student must never list, open, mark read, receive typing
from or be notified about this thread — the exact hazard at proposal lines 8074 and 8948. Also denied:
Faculty other than the submitter, IT Admin, Institutional Officer, and any GSS/Counselor whose College
scope does not cover the Referral. Faculty must not obtain ReferralActions, staff `status_note`,
Evaluations, Follow-Ups, handoff summaries or counseling history through Messages — the concealment
already enforced for the Faculty projection (`faculty_services.py:294-304`,
`tracking_disclosure.py:7-21`) must hold at the Messages layer too.

### 1.4 `FACULTY_INQUIRY` — Faculty ↔ Guidance Office, no Student, no Referral — **Proposed**

| Dimension | Design position (provisional) |
|---|---|
| Initiator / counterpart | any `FACULTY` account ↔ institutional GCO general-intake queue |
| Source binding | none — no Student, no Referral, no Appointment |
| Routing | an approved institution-wide GCO intake responsibility; **must not** invent a College or silently use the Faculty's home College (proposal line 8263); refuse safely when routing is unavailable, mirroring `services.py:255-262` |
| Required authority | role `FACULTY` **and** new self capability **and** requester identity for reads; staff side requires an approved intake capability narrower than blanket `guidance_messages.manage` (proposal line 8233) |
| Uniqueness | deliberately **not** one-per-Faculty: separate topics stay separate inquiries (proposal §9.4 line 8267); idempotency is per first message via `(sender, client_message_id)` (`models.py:137-139`) |
| DTO / realtime / notification / work | same institutional-endpoint shape as 1.3, requester = Faculty |

**Negative rule:** no Student may be attached, so no Student can ever be a reader; Faculty peers may
not browse one another's inquiries; GSS participation is limited to approved intake responsibilities
(proposal §26 item 11); IT Admin/Institutional Officer denied by role. Copy must steer a
Student-specific concern to Referral rather than letting an inquiry become a covert case record
(proposal §9.5 line 8271).

### 1.5 `COUNSELOR_DIRECT` — exactly two eligible active Counselors, cross-College — **Proposed**

| Dimension | Design position (provisional) |
|---|---|
| Initiator / counterpart | Counselor A ↔ Counselor B, two **different** active COUNSELOR accounts (proposal §11.1 line 8315) |
| Source binding | none: no Student, no case, no Referral, no Appointment; **never an Office queue**, so `assigned_to` must stay null exactly as COUNSELING does (`models.py:93`) |
| College | irrelevant — College coverage must not block peer coordination (proposal line 8315); this is a deliberate departure from `policy.py:48-49` |
| Required authority | role COUNSELOR **and** a narrow peer capability (proposal line 8231) **and** membership `actor ∈ {a, b}` |
| Uniqueness | canonical unordered pair (`min(uuid), max(uuid)`) so A→B and B→A cannot race into two threads (proposal §11.4 line 8332); resolved-then-new semantics undecided (D-GMSG-05/06) |
| DTO | two participant persons; `student` null → contract change required (`api.py:53`) |
| Realtime | exactly `{a, b}`, re-derived at commit through the same authorization pattern as `policy.py:149-165` |
| Notifications | none today |
| Work indicator | must **not** enter the GCO Office workload or response metrics (proposal §18.3 line 8524) |

**Negative rule:** GSS must never be a participant or an inferred reader (today `policy.py:49` grants
GSS every Office thread and `:51,63` keeps it out of COUNSELING — a peer thread must land in the
second category); IT Admin/Institutional Officer denied; no College-wide audience; and a direct chat
grants no source-record read (proposal §11.3 line 8328, §23 line 8707).

### 1.6 `COUNSELOR_CASE_COORDINATION` — authorized pair + one valid grant + one Student subject — **Implemented (GMSG-5), dormant pending D-GMSG-08**

| Dimension | Design position (provisional) |
|---|---|
| Initiator / counterpart | exactly the `original_counselor` and `receiving_counselor` of one `CounselorCaseContinuityGrant` (`continuity_models.py:49,56`) |
| Source binding | one grant (`:44`) + one Student subject (`:46`) |
| Communication authority (implemented) | explicit `communication_purpose=CASE_COORDINATION` + `communication_policy_digest`, guarded by `counseling_grant_communication_scope` (`continuity_models.py:206-214`); source-read scope is never reused as write authority. The production provider returns `None`, so no grant can carry a purpose until D-GMSG-08 institutional approval |
| Required authority (implemented) | role COUNSELOR **and** case capability **and** exact grant participation **and** live window `starts_at <= now < expires_at` with `decision=APPROVED`, no revocation, matching policy digests and `ACTIVE` effective status — one predicate, `authorize_case_coordination` (`case_communication.py:96-106`) |
| Lifecycle | expiry/revocation stop new sends, history reads and resolve/reopen at the authorization boundary even with no background job; tested in `test_guidance_messages_case.py` |
| Post-invalidity reads | D-GMSG-07 provisional (a) implemented: deny both participants; institutional question remains open |
| DTO / realtime | pair only; Student surfaced as subject to the two authorized Counselors; never to an Office queue |

**Negative rule:** GSS never joins (its `guidance_messages.view/manage` must not reach this kind);
no College-wide audience; no third participant; a grant approval must not retroactively reveal earlier
general direct-chat correspondence (proposal §12.2 line 8344); messaging never grants source-record
reads and never becomes a professional record (proposal §12.4 lines 8355-8357); when the originating
Counselor is absent, the system must not forge their reply or mark them Seen (proposal §12.5 line
8361).

## 2. Role × kind access grid (proposed target; Existing rows are today's Verified behavior)

`✓` allowed · `—` denied · `✓*` allowed only with the exact resource relationship named in §1.

| Role | OFFICE (own) | COUNSELING | REFERRAL_COORD | FACULTY_INQ | COUNSELOR_DIRECT | CASE_COORD |
|---|---|---|---|---|---|---|
| `STUDENT` | ✓ own (`policy.py:47,61`) — Existing | ✓* exact Student (`:60-63`) — Existing | — | — | — | — |
| `FACULTY` | — | — | ✓* original submitter | ✓ own inquiries | — | — |
| `COUNSELOR` | ✓* College scope (`:48-49`) — Existing | ✓* persisted `counselor_id` (`:51,63`) — Existing | ✓* authorized GCO Referral scope | ✓* approved intake | ✓* one of the two | ✓* grant participant + live window |
| `GUIDANCE_SERVICES_STAFF` | ✓* College scope — Existing | — (`:63`) | ✓* approved GCO operational work only | ✓* approved intake only | — | — |
| `IT_ADMIN` | — | — | — | — | — | — |
| `INSTITUTIONAL_OFFICER` | — | — | — | — | — | — |
| Head designation (`HEAD_GUIDANCE_COUNSELOR`) | widens **College scope** only (`organization/access_scope.py:143-151`) | no effect (`:51,63`) | no effect | no effect | no effect | no effect |
| `DPO` designation | no messaging effect (`accounts/policy.py:65-76`) | no effect | no effect | no effect | no effect | no effect |

**Verified structural guarantee:** the deny for the last two roles is a role check that runs *before*
the capability check (`policy.py:33-40`), so an accidental `UserCapabilityOverride`
(`accounts/models.py:337`, consulted via `has_capability` `:260-263`) does not open Messages. Keeping
that order is a non-negotiable requirement for every new kind (proposal §8.1 line 8222).

## 3. Negative-privacy matrix across every access surface

For each surface: the verified current enforcement point and the rule any new kind must satisfy.
Surfaces are those enumerated at proposal line 8239.

| # | Surface | Current enforcement (Verified) | Rule for proposed kinds |
|---|---|---|---|
| 1 | List / search | `services.list_threads:102-108` → `authorized_threads` (`policy.py:43-52`), no unfiltered table | Kind must be an explicit clause in the same queryset; a Faculty list query must be `requester_id=actor` |
| 2 | Create / open | `open_office_thread:216-281`, `open_counseling_thread:284-325`; unauthorized targets → `ThreadNotFound` | Creation must revalidate the *source* (Referral/Grant/Pair) at the moment of write, mirroring `policy.py:72-88` |
| 3 | Detail | `get_thread:126-132` (fetch, then `require_thread`) | Same two-step; never serialize before authorization |
| 4 | Message page | `list_messages:135-144` (read-only, no cursor side effect) | Must stay read-only: no implicit mark-read |
| 5 | Send | `_send_locked:169-198` (auth → idempotency → `OPEN` → limit → encrypt → sequence → audit) | Add source-liveness check before `OPEN` check (void Referral / expired grant → refuse new sends) |
| 6 | Mark-read | `mark_read:363-376` under `_lock_thread`; explicit `PATCH …/read` (`api.py:586-596`) | Same path is the *only* legitimate Seen producer |
| 7 | Response DTO | `GuidanceThreadResponse` `api.py:49-63`, `_thread:229-253`, `Cache-Control: no-store, private` `:193-227` | Drop required `student`; suppress `assigned_to` person name from non-staff requesters (D-GMSG-22) |
| 8 | Unread counter | `count_unread_conversations:111-123`; `unread_threads` (`student_actions.py:11-34`) | Kind-scoped; a peer/case thread must not inflate GCO workload metrics |
| 9 | Work summary | `work.py:19-66` | Replace `latest_sender=student_id` (`:36`) with a per-kind requester-side predicate; fix the unassigned-Office blind spot |
| 10 | Handler selection | `eligible_handlers:439-467` + `assign_handler:410-433`; `policy.eligible_handler:123-135` | Office kinds only; the eligible set must come from the approved intake responsibility, not College alone |
| 11 | Resolve / reopen | `set_status:379-407`, `staff_only=True` | Direct/case kinds resolve under their own rules (D-GMSG-06); never allow one kind's reopen to violate another's uniqueness |
| 12 | Notification link | no message notification exists (verified §9 of `current-state.md`); deep-link machinery `email_links.py:40-153` | Any future link must be route-table, strict-UUID, origin-validated and currentness-checked |
| 13 | Realtime delivery | `policy.recipient_ids:149-165` → `publish_to_user_on_commit` (`realtime/publish.py:57-65`) | Recompute recipients per event through the same predicate; never widen to a room channel (none exists, `protocol.py:141-146`) |
| 14 | Realtime subscription | per-user channel from the ticket only (`realtime_service/app.py:260-262`); no client-named channel (`:334-348`) | Preserve: no thread/room subscribe API, ever |
| 15 | Typing start | does not exist | Inbound path must derive actor from the session, never the frame (proposal line 8494); the current transport accepts **no** client frames at all |
| 16 | Typing stop/receive | does not exist | Recipients re-derived from current authorization; revoked grant fails closed |
| 17 | Case context | `appointment_context:328-360` returns structure only (`api.py:125-129`) | A case thread context endpoint must 404 exactly like `continuity_access.py:59-65` |
| 18 | Administrative tools | `default_permissions = ()` on all four models (`models.py:71,131,156,205`) | Keep: no Django admin CRUD as a back door |

## 4. Fail-closed inventory (what must stop access, and where it is proven today)

| Trigger | Current behavior | Verified evidence |
|---|---|---|
| Account deactivated | every service call reloads `is_active=True`; failure → 403 before any row | `policy.py:21-28` |
| Role changed away from allowlist | next `require_actor` denies by role | `policy.py:33-38` |
| Capability removed | next `require_actor` denies by capability | `policy.py:39-40` |
| Staff leaves College scope | `authorized_threads` and `require_thread` re-resolve scope per request | `policy.py:48-49,65-67` |
| Counselor no longer the persisted thread counselor | still denied/granted strictly by `counselor_id`; reassignment does not transfer | `policy.py:51,63`; `services.py:331-334`; `appointments/services.py:1377-1393,1483` |
| Student lifecycle leaves CURRENT | `current_student` gate at creation | `policy.py:91-96`, `services.py:235-236` |
| Student placement changes | **new** Office threads route to the new College; existing `routing_college` is frozen (PROTECT FK) | `services.py:253,266`; `models.py:30-32` |
| Referral voided / administratively closed | **no messaging effect today — no such thread exists**; derived state returns `None` for voided | `administrative_state.py:12-19` |
| Grant expired / revoked | **no messaging surface exists**; the continuity read path 404s | `continuity_access.py:59-65,191,219,255` |
| Thread `RESOLVED` | `send_message` refuses with `MessagesConflict` | `services.py:175-176` |
| Handler deactivated | `assign_handler` requires active + `eligible_handler` | `services.py:417-419` |
| Keyring unavailable | 503, never a plaintext fallback | `content.py:31-37,61-76`; `api.py:212-217` |
| Foreign/unknown UUID | 404 `guidance_thread_not_found`, indistinguishable from missing | `policy.py:55-69`; `api.py:196-201` |

## 5. Slice readiness verdict

| Kind | Ready now? | Blocking requirement |
|---|---|---|
| `OFFICE` | **Existing** — unchanged behavior must be preserved | none |
| `COUNSELING` | **Existing** | none |
| `FACULTY_INQUIRY` | **Blocked on policy, not on code** | needs GCO intake routing decision (D-GMSG-01) and a requester field that §1.4 requires; role/capability substrate exists (`accounts/policy.py:31,79`) |
| `REFERRAL_COORDINATION` | **Ready conditionally** | provenance substrate verified (`referrals/models.py:13-16,54-61,227-253`, `faculty_services.py:307-313`); needs a Referral link + unique constraint and the D-GMSG-09 closure policy |
| `COUNSELOR_DIRECT` | **Ready** | needs pair columns + canonical-pair unique index and one narrow capability; no external domain dependency |
| `COUNSELOR_CASE_COORDINATION` | **Implemented (GMSG-5), dormant** | live grant predicate shipped (`case_communication.py:96`); D-GMSG-08 institutional approval remains **Open — GCO/DPO**, and the production provider returns `None`, so no case conversation can exist. GSS, IT Admin, Institutional Officer, Head and DPO excluded; the Student is a subject, never a participant |
