# UX journeys and proposed GCO task meanings

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.
**Approval status:** every task meaning, copy change and UAT journey below is **Pending** GCO approval.
Nothing in this document is institutional policy. Current behavior is **Verified** statically; no
browser session or UAT was executed.

## 1. What a Follow-Up is today

The proposal's operational definition (proposal lines 5627-5634, 5786-5799) matches the code:

| Record | Meaning | Owner | Current behavior |
|---|---|---|---|
| Referral | Documented request/concern and its administrative record | `referrals` | Voiding is Referral-owned; no Follow-Up write |
| Referral Action | What GCO did on a Referral | `referrals` | Not a Follow-Up |
| Guidance Follow-Up | One assigned responsibility with due time, assignee, activity and disposition | `guidance_followups` | Independent lifecycle |
| Appointment | Scheduled encounter | `appointments` | Not created or changed by a Follow-Up |
| Counseling Encounter / Routine Interview | Professional documentation | `counseling` / `routine_interviews` | Can be an optional source |

A Follow-Up is not a Student case, not a clinical outcome, and not a Referral status. **Verified** by
model ownership and the absence of cross-domain writes.

## 2. Current screens and copy

### 2.1 List — `/portal/follow-ups`

- Pending is the default status filter (`followups-list.tsx:145`).
- Workload counts: Pending, Overdue, Due soon; due soon is the next 7 days
  (`followups-list.tsx:30,65-69`).
- Filters: status, due window, responsibility; table shows Student, category, due/overdue/due-soon,
  assignee, status (`followups-list.tsx:87-96,158`).
- Empty copy distinguishes no assignments, no pending, no page matches, and filtered no-match
  (`:38-39`).
- **No source column or source-unavailable indicator.** A task with a voided Referral looks like any
  other pending task. **Verified** by `api.py:227-250` (no source in summary) and UI table.

### 2.2 Create — `/portal/follow-ups/new`

- Staff-only copy: "Follow-Ups are for staff. Creating one does not contact the Student or send a
  Student notification." (`followups-create.tsx:81`).
- From a source, category is locked and Student is derived; a confidential source says only the
  authorized Counselor can be assigned (`:84-94`).
- Without a source, only `ADMINISTRATIVE`, `STUDENT_CONTACT`, `REFERRAL_ACTION` are offered; counseling
  requires opening the Encounter/Routine and using its panel (`:85-88`).
- Due date is institutional time; a past date is rejected by the backend (`services.py:43-46`).
- Retry uses a stable idempotency key (`followups-create.tsx:68`).
- No "next action" or predecessor field. **Verified.**

### 2.3 Detail — `/portal/follow-ups/[id]`

- Actions render only when `access.manage && status === "PENDING"` (`followups-detail.tsx:86`).
- Current actions: Record activity, Mark complete, Edit task details, Change due date, Reassign,
  Cancel follow-up (`:88-99`).
- Completed panel shows outcome, completer and time (`:81`).
- Cancelled panel shows canceller/time and cancellation remarks (`:81-84`).
- Related-record panel has three states: linked and openable; linked but unavailable; independently
  created (`:108`). The unavailable copy is: "The related record is no longer available to your
  account. This follow-up keeps its own status."
- Completion confirmation: "This follow-up will be completed with the outcome you recorded. Related
  Counseling records, Referrals and Appointments keep their own status." (`:177`).
- Cancellation confirmation: "This follow-up will be cancelled with the reason you recorded. Related
  Counseling records, Referrals and Appointments keep their own status." (`:177`).
- Reassignment confirmation warns: "Responsibility transfers to the selected staff member. You may
  lose access after reassignment." (`:177`).
- **No "Create next follow-up", "Another action needed", or predecessor/successor display.**
  **Verified** by the absence of any such control in the file.

### 2.4 Context panel

- Embedded in Referral, Encounter and Routine detail pages (`followups-context.tsx`).
- Shows linked tasks, status, due date, and a create link when `can_create` (`:27-28`).
- If the context request fails — including because a Referral is voided — the whole panel returns
  `null` (`:20-21`). A task that still appears in the main list therefore disappears from the source
  page. **Verified.**

### 2.5 Report and recovery

- Report: "Counts cover only follow-ups you can currently access. Descriptions and outcomes are
  excluded." (`followups-report.tsx:23`); workload and category counts only; default due-soon horizon 7
  (`:18,26-27`).
- Recovery: "Restore responsibility for operational follow-ups whose original staff member no longer
  meets eligibility. Counselor-confidential follow-ups are excluded."
  (`followups-reassignment.tsx:29`). Confirmation says protected descriptions and source records are
  not shown during recovery (`:55`).

### 2.6 Help

`followups-help.tsx:6-11` explains next actions, 7-day due soon, progress/completion/cancellation,
confidentiality, and notifications. It does **not** explain source voiding, confidential orphan work,
or continuation.

## 3. Proposed task meanings for GCO approval

These are proposed, not current copy. GCO must approve or replace each one (D-FUP-07).

| Term | Proposed meaning | Explicitly not |
|---|---|---|
| Follow-Up | One assigned responsibility with an owner and due time | A case, diagnosis, or resolution of the Student's concern |
| Pending | Work is still assigned and open | Evidence that the Student needs counseling |
| Completed | The specific assigned action has a documented outcome | Proof of intervention effectiveness, Referral closure, or Appointment attendance |
| Cancelled | The task was stopped or is no longer applicable, with a reason | A judgment that the intervention failed |
| Overdue | The due time passed while the task remained pending | An emergency or automatic escalation |
| Due soon | Due within the next 7 days | A scheduled reminder message |
| Source unavailable | The linked record cannot be read by this account; the task keeps its own status | The source was deleted, the concern was resolved, or the task is invalid |
| Review needed (proposed) | A human should confirm whether the task still has a legitimate basis | A new task status or automatic cancellation |
| Further action (proposed) | A human explicitly decides to create another responsibility | Automatic recurrence, case closure, or treatment plan |
| Referral administratively closed (future FAC) | A separate Referral-owner decision | A Follow-Up completion or counseling outcome |

**7-day definition:** `DUE_SOON_HORIZON_DAYS = 7` (`integration.py:16`); shared by My Work, list
counts, report and work queue (`integration.py:19-22`; `workspace.py:150-154`). **Verified.** GCO may
change the threshold only by changing both code and policy.

## 4. Current gaps that UAT must expose

| Gap | Current behavior | Why it matters | Evidence |
|---|---|---|---|
| G1 — Silent source loss in list/report/My Work | Operational task remains, but no source indicator; report includes it | Staff cannot tell which tasks have an invalid source without opening each detail | `api.py:227-250`; `workspace.py:150-187` |
| G2 — Context panel disappears | Panel returns `null` on source error | A task visible in the list is absent from the source page; staff may think it does not exist | `followups-context.tsx:18-21` |
| G3 — No review contract | No review status/event/endpoint | GCO cannot prove a human decided to continue or cancel after a void | `services.py:288-334` (no review fields); no `review` symbols |
| G4 — No further-action path | Completion is terminal; no successor control | Staff must manually recreate a task and may duplicate/lose context | `services.py:391-417`; `followups-detail.tsx:86-104` |
| G5 — Confidential orphan | Inaccessible confidential pending task cannot be listed, reassigned or cancelled | Hidden pending work and no disposition path | `policy.py:162-183`; `recovery.py:49-56` |
| G6 — Head misconception | Head cannot see others' tasks or confidential tasks | A Head may believe designation grants oversight it does not | `policy.py:194-210`; `accounts/policy.py:761-795` |
| G7 — Source-filter 404 | Filtering the list by a voided source returns not-found | Looks like an error rather than "source unavailable" | `services.py:244-248` |
| G8 — No source-change notification | Assignee is not told the source was voided | Stale tasks may be completed without reviewing the change | `integration.py:47-54` (only assignment/reassignment/due-change are material) |
| G9 — Completion copy may still be misread | Copy says the Follow-Up is complete, not that the concern is resolved | Staff may use it as a resolution signal in external communication | `followups-detail.tsx:177`; report labels |

## 5. Proposed UAT journeys

Each journey states the actor, precondition, steps, expected result, unauthorized variant and the
evidence GCO/UAT must capture. "Current" means the behavior can be tested at HEAD; "Proposed" requires
FUP-1/FUP-2 approval and code. No journey was executed.

### UAT-FUP-01 — Standalone operational task, end to end (Current)

- **Actor:** Counselor or GSS with `guidance_followups.manage`.
- **Precondition:** Active Student in actor's operational scope, no source.
- **Steps:** Create with `ADMINISTRATIVE` or `STUDENT_CONTACT`, another eligible assignee, future due;
  assignee opens detail; records activity; completes with outcome.
- **Expected:** One pending task; one `CREATED` event; activity appends an event without status change;
  completion is terminal with outcome/actor/time; Referral/Encounter/Appointment unchanged.
- **Unauthorized variant:** GSS targets a Student outside their College scope → 404/422, no row.
- **Evidence:** task ID, event revisions, audit action names, before/after source-domain states; no
  Student message is sent.
- **Claim:** Current behavior **Verified** by code and test definitions; not executed.

### UAT-FUP-02 — Due-time semantics (Current)

- **Actor:** Assignee with manage.
- **Precondition:** Pending task due more than 7 days away.
- **Steps:** View My Work/report; advance time into 7-day window; advance past due.
- **Expected:** Not due soon at first; due soon within 7 days; overdue after due but still pending;
  no automatic completion/cancellation; no deadline email by default.
- **Unauthorized variant:** Actor without view cannot see the card or report count.
- **Evidence:** timestamps, My Work priority transitions, report counts, notification flag state.
- **Claim:** Current behavior **Verified** by code; time simulation not executed.

### UAT-FUP-03 — Referral-linked operational creation (Current)

- **Actor:** GSS/Counselor with `referrals.manage` and Follow-Up manage.
- **Precondition:** Live Referral for an in-scope Student.
- **Steps:** Open Referral detail; choose "Create referral follow-up"; select assignee and future due;
  confirm.
- **Expected:** `REFERRAL_ACTION` / `OPERATIONAL` task; source pair recorded; task appears in list and
  source context panel; Referral status/actions unchanged.
- **Unauthorized variant:** Counselor B (not source-authorized) cannot create from the Referral;
  GSS outside scope cannot see the Student.
- **Evidence:** source kind/id, derived category/visibility, Referral before/after, audit row.
- **Claim:** Current **Verified**.

### UAT-FUP-04 — Encounter-linked confidential creation (Current)

- **Actor:** Original Counselor with `counseling.manage_assigned`.
- **Precondition:** Encounter for an active Student, actor is the Encounter Counselor, Follow-Up manage.
- **Steps:** Open Encounter; choose "Create counseling follow-up"; confirm self as assignee and future
  due.
- **Expected:** `COUNSELING` / `COUNSELOR_CONFIDENTIAL`; only the actor appears as an eligible
  assignee; task visible only to that Counselor.
- **Unauthorized variant:** GSS cannot create; another Counselor cannot be selected; direct API with
  another Student/source fails.
- **Evidence:** visibility, eligible-assignee response, denial responses.
- **Claim:** Current **Verified**; browser and API not executed.

### UAT-FUP-05 — Routine Interview-linked confidential creation (Current)

- **Actor:** Original Counselor.
- **Precondition:** Routine Interview with no Appointment or a `SCHEDULED`/`COMPLETED` Appointment.
- **Steps:** Create from the Routine detail; complete and view history.
- **Expected:** Confidential task; source link opens only for the source Counselor; if the Appointment
  moves to an unaccepted state, list/detail access is lost (G5).
- **Unauthorized variant:** GSS/other Counselor cannot create or read.
- **Evidence:** Appointment state, task visibility, source denial.
- **Claim:** Current **Verified**; state transition not executed.

### UAT-FUP-06 — Confirmation of confidentiality cannot be downgraded (Current)

- **Actor:** Caller with create capability.
- **Precondition:** Counseling Encounter or Routine source.
- **Steps:** Submit `visibility=OPERATIONAL` or a non-counseling category.
- **Expected:** 422; no row; no source disclosure.
- **Unauthorized variant:** No manage capability → 403 at entry.
- **Evidence:** HTTP status/code, absence of row, no source data in response.
- **Claim:** Current **Verified**; test `:168-210`.

### UAT-FUP-07 — Source/Student/actor mismatch (Current)

- **Actor:** Any authenticated staff caller.
- **Precondition:** Source UUID belongs to another Student or another Counselor.
- **Steps:** Attempt create.
- **Expected:** 404 with no confirmation of existence; no row.
- **Unauthorized variant:** Voided Referral also rejected.
- **Evidence:** status/code, row count, response body.
- **Claim:** Current **Verified**; test `:211-251,252-275`.

### UAT-FUP-08 — Activity, completion and immutable history (Current)

- **Actor:** Current assignee with manage.
- **Precondition:** Pending task.
- **Steps:** Record activity; complete with outcome; open history; attempt update/complete again.
- **Expected:** Events `ACTIVITY_RECORDED`, `COMPLETED`; version increments; second mutation 409; no
  status resurrection.
- **Unauthorized variant:** View-only actor sees history but no action controls; direct mutation 404.
- **Evidence:** event revisions, version, 409 response, audit.
- **Claim:** Current **Verified**; tests `:98-137,343-367`.

### UAT-FUP-09 — Concurrent completion (Current; PostgreSQL)

- **Actor:** Two authorized sessions for the same assignee.
- **Precondition:** Same `expected_version`.
- **Steps:** Submit completion concurrently.
- **Expected:** Exactly one completion/event/audit; the other gets a conflict; no contradictory outcome.
- **Unauthorized variant:** Non-assignee gets 404.
- **Evidence:** database event count, version, both HTTP responses.
- **Claim:** Defined test `:399-428`; **not run** in FUP-0; requires PostgreSQL.

### UAT-FUP-10 — Referral voided after task creation (Current)

- **Actor:** Referral owner voids; task assignee remains.
- **Precondition:** Pending operational task linked to a live Referral.
- **Steps:** Void Referral through Referral service; assignee opens list, detail, report, My Work;
  completes or cancels task.
- **Expected:** Task remains pending; list/report/My Work include it; detail source is `null` and
  `source_unavailable=true`; source panel shows the unavailable copy; completion/cancellation still
  works; no automatic Referral change.
- **Unauthorized variant:** Another Counselor/GSS without operational scope cannot see the task;
  someone who knows the Referral UUID still needs Referral authorization.
- **Evidence:** task/source IDs, list/report/My Work inclusion, detail response, event history.
- **Claim:** Current **Verified** by code and test `:252-275` (detail only); list/report/My Work/mutation
  after void **not tested**.

### UAT-FUP-11 — Voided Referral context panel (Current gap)

- **Actor:** Staff viewing the Referral detail page after void.
- **Precondition:** Same as UAT-FUP-10.
- **Steps:** Open Referral detail; look for the linked-follow-ups panel.
- **Expected current:** Panel is absent (context request fails), even though the task remains in the
  list. **This is the G2 gap.**
- **Proposed:** An approved, non-leaking "related tasks unavailable for this record" state, without
  enumerating hidden tasks.
- **Unauthorized variant:** No view capability → no panel.
- **Evidence:** screenshot, network status, list/detail consistency.
- **Claim:** Current behavior **Verified** by `followups-context.tsx:18-21`.

### UAT-FUP-12 — Reassignment and former-owner loss (Current)

- **Actor:** Current assignee with manage.
- **Precondition:** Pending operational task in shared scope.
- **Steps:** Reassign to another eligible staff member; old owner refreshes list/detail; new owner
  opens task.
- **Expected:** Old owner loses task access; new owner gains it; `REASSIGNED` event; notification to
  new owner; old owner may receive only a cache-eviction hint.
- **Unauthorized variant:** Target outside scope is rejected; non-manage actor cannot reassign.
- **Evidence:** both users' lists, event, notification rows, old-owner 404.
- **Claim:** Current **Verified**; test `:138-167`.

### UAT-FUP-13 — Recovery of an operational orphan (Current)

- **Actor:** Head Guidance or scoped Counselor/GSS with manage.
- **Precondition:** Pending operational task whose current owner is inactive, out of scope, or has lost
  capability.
- **Steps:** Open recovery; preview metadata; reassign to an eligible owner.
- **Expected:** Task appears only if the current owner is ineligible; no description/outcome shown;
  reassignment succeeds; `REASSIGNED` event; new owner sees it.
- **Unauthorized variant:** Non-Head sees only own College; confidential tasks never appear.
- **Evidence:** recovery list contents, metadata fields, resulting owner, event.
- **Claim:** Current **Verified**; tests `:659-704`.

### UAT-FUP-14 — Head recovery excludes confidential (Current)

- **Actor:** Head Guidance Counselor with manage.
- **Precondition:** Confidential task whose source Counselor is unavailable/ineligible.
- **Steps:** Open recovery; search for the task; attempt direct reassignment.
- **Expected:** Task is absent from recovery; direct reassignment fails 404; Head cannot see detail.
  The task remains pending and unresolved (G5).
- **Unauthorized variant:** Head cannot use designation as a source grant.
- **Evidence:** recovery list, direct request status, task row status.
- **Claim:** Current **Verified**; test `:705-730`.

### UAT-FUP-15 — Confidential source loss (Current gap)

- **Actor:** Original Counselor, then a substitute/Head.
- **Precondition:** Confidential task; source access is removed (capability/role/source predicate).
- **Steps:** Original owner opens list/detail; substitute/Head attempts list/detail/reassign; operator
  inspects row.
- **Expected current:** Original and substitute cannot read; task remains `PENDING`; recovery excludes
  it; no notification; no disposition path. **This is the G5 gap and must not be "fixed" by a Head
  bypass.**
- **Proposed:** Only after CONT approval, a source-scoped coverage/task-transfer contract.
- **Unauthorized variant:** Any unrelated Counselor/Head is denied.
- **Evidence:** both users' responses, row status, recovery absence, no content in logs.
- **Claim:** Current access denial **Verified**; population impact **Unknown**.

### UAT-FUP-16 — Further action after completion (Proposed)

- **Actor:** Completing assignee with manage and current source access.
- **Precondition:** Pending task completed with an outcome that indicates another action is needed.
- **Steps:** Complete; choose "Create another follow-up" (proposed); review prefilled Student/source;
  choose a new assignee and future due; confirm.
- **Expected proposed:** One new independent task with a new ID and idempotency key; original stays
  completed; no automatic creation; no confidentiality downgrade; source revalidated at creation;
  optional predecessor link only if D-FUP-03 approves.
- **Unauthorized variant:** Actor cannot create for the selected Student/source → no task; no silent
  inheritance of stale access.
- **Evidence:** two task IDs, original completion event, new `CREATED` event, source pair, assignee,
  idempotency behavior.
- **Claim:** **Proposed**; not implemented at HEAD.

### UAT-FUP-17 — Referral completion does not close Referral (Current invariant)

- **Actor:** Task assignee with manage.
- **Precondition:** Operational task linked to a Referral.
- **Steps:** Complete task; view Referral status/actions.
- **Expected:** Referral status, administrative fields, actions and void state unchanged; no Faculty
  projection changes; no automatic Referral close.
- **Unauthorized variant:** Faculty cannot see the task at all.
- **Evidence:** Referral before/after, Follow-Up event, absence of Referral audit.
- **Claim:** Current **Verified**; future FAC still pending.

### UAT-FUP-18 — Missing keyring fails closed (Current)

- **Actor:** Any authorized reader/writer.
- **Precondition:** No usable `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS`.
- **Steps:** Read detail or create/complete with protected text.
- **Expected:** 503 `followup_content_unavailable`; no plaintext; no partial status transition.
- **Unauthorized variant:** Any actor gets the same content-unavailable behavior; authorization is not
  bypassed.
- **Evidence:** HTTP status, logs, database state.
- **Claim:** Current **Verified**; test `:876-889`; not run.

### UAT-FUP-19 — External email off by default (Current)

- **Actor:** Assignee and a former assignee.
- **Precondition:** Flag `GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED=False` (default).
- **Steps:** Create, reassign, change due; inspect in-app notifications and email outbox.
- **Expected:** In-app current notification; no external email; former assignee's old occurrence is not
  current; no protected free text in notification copy.
- **Unauthorized variant:** Unrelated staff receives no notification.
- **Evidence:** notification rows, outbox, flag value, event currentness.
- **Claim:** Current **Verified** by code/tests `:548-658`; not executed.

### UAT-FUP-20 — SAR College transfer and recovery (Current)

- **Actor:** Head or scoped staff; Student placement changes through SAR.
- **Precondition:** Pending operational task assigned to staff whose new College scope no longer
  includes the Student.
- **Steps:** Change placement through the SAR writer (outside this UAT); refresh list/recovery.
- **Expected:** Old assignee loses list/detail; task appears in recovery (if owner ineligible); a Head
  or newly responsible staff member can recover; confidential tasks unaffected by College scope and
  still subject to source checks.
- **Unauthorized variant:** Staff outside the new College cannot recover.
- **Evidence:** placement revision, old/new list, recovery list, task row unchanged, no source rewrite.
- **Claim:** Current **Verified** by scope/recovery code and SAR migration; not executed end to end.

## 6. What GCO must approve before UAT is meaningful

1. The meaning table in §3, especially "Completed" and "Source unavailable" (D-FUP-07).
2. What staff should do after a source is voided, and whether review must be mandatory (D-FUP-01).
3. Who may decide to continue, cancel or create a next task (D-FUP-04).
4. Whether "further action" is UI-only or needs a durable classification/link (D-FUP-03).
5. Whether any continued task should notify anyone, and through which channel (D-FUP-06).
6. That completion never closes a Referral and voiding never silently closes a Follow-Up (D-FUP-05).
7. Which UAT journeys are "current behavior" and which remain blocked by FAC/CONT/SAR (D-FUP-07).

**Do not mark FAC-, CONT- or SAR-dependent journeys as passed because the code path exists.** The
proposal itself requires them to be recorded as blocked/future (proposal lines 6464-6467).

## 7. Copy that must not ship without approval

| Avoid | Why | Safer proposed wording |
|---|---|---|
| "Case resolved" | Completion is one task, not a case outcome | "This follow-up is complete" |
| "Student successfully treated" | Clinical judgment not in this domain | "Contact task completed with documented outcome" |
| "Referral closed" after task completion | Referral owns its status | "This follow-up is complete; the Referral keeps its own status" |
| "Source invalid" | Implies the source is objectively invalid and may leak cause | "Related record unavailable to your account" |
| "Automatically notify Student" | No Student message is sent | "Creating this task does not contact the Student" |
| "Recovered assignment means the task is valid" | Recovery only changes ownership | "Responsibility transferred; review the task on its own merits" |
| "Due soon" as a reminder | It is a projection, not a scheduled message | "Due within 7 days" |

The last three are already close to current copy (`followups-create.tsx:81`;
`followups-reassignment.tsx:55`; `followups-help.tsx:7-10`). **Verified** for the quoted current text;
any replacement requires GCO approval.
