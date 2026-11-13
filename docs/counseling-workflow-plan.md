# COMPASS counseling workflow: decisions and implementation plan

**Date:** 12 November 2026 · Philippine Time  
**Status:** Decided planning baseline. CW-1 is implemented and verified locally, in review as pull request #360 ([CW-1 record](cw-1/README.md)). CW-2 is implemented and verified locally on `codex/counseling-cw2-next-actions`, stacked on CW-1 ([CW-2 record](cw-2/README.md)). CW-3a transfer is implemented and verified locally, stacked on CW-2 ([CW-3 record](cw-3/README.md)). CW-3b, CW-3c and CW-4 to CW-7 remain open.
**Purpose:** Turn the related counseling features into one understandable student-care workflow, and capture the related Referral, Counselor About, and Guidance Messages improvements.

The owner has asked us to make the remaining product decisions using the Guidance Head's insights and the discussions in both chats. The decisions below are the team's chosen implementation direction. Statements attributed to the Guidance Head are the owner's recollection, not a verbatim institutional specification. In particular, a ten-session closure rule was never established.

## 1. The idea in plain language

**Isang case = isang folder para sa isang magkakaugnay na concern o episode ng counseling ng student.**

Inside that folder, the counselor should understand: who is responsible, what has happened, what needs to happen next, and whether the work is ongoing or concluded.

| Term | Plain meaning |
|---|---|
| Referral | Someone asks Guidance to attend to a student's concern. |
| Case | The continuing episode of support that connects relevant sessions and next actions. |
| Appointment | A scheduled meeting. |
| Session / Counseling Encounter | A meeting that actually happened and was recorded. |
| Follow-up | A specific next action with a responsible person and a deadline. |
| Temporary coverage | Another counselor helps for a defined period; the primary counselor remains responsible. |
| Transfer | Another counselor accepts ongoing responsibility for the same case. |
| Handoff | The relevant information and pending work communicated to that counselor. |
| Case closure | A counselor records that the current episode of support has concluded, with a reason and outcome. |

Example: a student comes to Guidance, meets a counselor, has a follow-up task, attends another session, and eventually finishes the planned support. If a different counselor takes over midway, the case continues. A completed session or task does not mean the whole case is closed.

The existing separate workspaces still have useful purposes. Appointments shows the schedule across students; Follow-ups shows tasks across students; Messages shows conversations. The case workspace connects the same underlying records for one episode. It must not create duplicate appointments, tasks, sessions, or conversations.

## 2. What led to this plan

| Discussion | Insight or request carried forward | Decision in this plan |
|---|---|---|
| Earlier chat: Counselor About and Messages | Backend changes are now allowed. About means where the counselor is assigned: colleges and campus. Messages lacks equivalent identity/context data. | Add a shared authorized counselor summary and useful appointment context. Do not start a biography-management project. |
| Earlier chat: panel proposals and Guidance Head discussion | Handoff/continuity also supports transfers where a potential conflict of interest could affect impartiality; it is not limited to emergencies or absence. | Separate temporary coverage from ongoing case transfer. |
| Earlier chat: approval | Ordinary counselor transfers go through the Head. The Head also needs a workable route to transfer her own cases. | Head approval for ordinary transfers; direct authorization for the Head's own outgoing case; receiving-counselor acceptance. |
| Earlier chat: faculty referrals | Counselors need suggested days/times when a referred student can be contacted or called in. | Add scheduling information that distinguishes known student availability from permission to leave the referrer's class. |
| Current chat: limited handoff information | Selected data, handoff text, and ownership are being confused. | Show exactly what is shared and what responsibility changes. Improve the handoff structure. |
| Current chat: Follow-ups | Tasks look like a separate feature, and their relation to sessions and transfers is unclear. | Integrate next actions into the case and coordinate their ownership during transfer. |
| Current chat: closing after several sessions | The Head may be describing case closure after an episode of counseling. Ten sessions may only have been an example. | Add deliberate case closure, with no automatic session-count threshold. |
| Current chat: frontend coherence | The screens make the user connect the process mentally. | Make the case overview and next action the main counseling experience. |

This covers the relevant parts of the fifteen-proposal discussion, particularly counselor continuity and faculty referral handling. It does not claim to re-audit, implement, or approve all fifteen proposals.

## 3. Current implementation and actual gaps

These are source findings, not claims about a live deployment. Reviewed checkout: `codex/remove-privacy-designation-retention`, commit `6814bdbe30fc0591de690c474b931456a7c5501b`. The locally available `origin/staging` reference was `751f31ea4778afe04b2c153a92a733846cf95a56`. The counseling and Follow-ups areas examined did not differ between those references. No fresh runtime, hosted CI, or deployment verification was performed for this document.

| Area | Existing behavior | Work needed |
|---|---|---|
| Counseling | Individual completed Encounters, appointment completion, and separately published Student Session Summaries. | A persistent case/episode connecting related work, with current responsibility and lifecycle. |
| Case Coverage | Requests for selected records, independent Head approval, start/expiry, and revocation. Coverage lasts at most 30 days and may start at most 14 days ahead. | Clear temporary-support semantics; receiver acceptance for new requests; connection to a real case. |
| Transfer | Coverage approval does not establish ongoing case ownership. | An explicit request, authorization, acceptance, and effective ownership transition. |
| Head's outgoing case | The requester cannot approve the same request. | A narrow direct-authorization route when the Head is the outgoing responsible counselor. |
| Selected records | Encounter reference, start/end, entry/delivery mode, and original counselor; finalized Routine Evaluation academic adjustment rating and recommendations. | Honest disclosure previews and links; do not imply that all case history or narrative is shared. |
| Handoff | Optional confidential text, up to 12,000 characters; original counselor drafts/submits; submitted text is read-only. | Structured preparation, clear review/receipt states, and an unavailable-author route. |
| Follow-ups | Tasks with category, assignee, due date, activity, outcome, and Pending/Completed/Cancelled status. | Case linkage and explicit handling of pending tasks during coverage, transfer, and closure. |
| Confidential Follow-ups | Authorization depends on the counselor of the original Encounter/Interview. Ordinary coverage does not supply that management authority. | Deliberate case/task authorization for accepted transfers and selected temporary assignments. |
| Follow-ups UI | List emphasizes student, category, due date, staff, and status. The actual action description is inside the detail page. | Make the next action visible without opening every row. |
| Referral closure | Administrative closure exists and is separate from counseling completion. | Preserve that distinction when case closure is introduced. |
| Case closure | No dedicated counseling case with Active/Closed state exists. | Case-level close/reopen actions and history. |
| Referral timing | Faculty submission contains confirmation, course/year/block, and reason; no scheduling windows. | Add timing information and staff verification. |
| Counselor About | Booking provides name, photo, and default-assignment indication. Organization records already contain college/campus responsibilities. | A scoped summary usable in booking and Messages. |
| Guidance Messages | Counselor identity is name/ID; thread has appointment ID but no appointment date/service summary. Seen receipts and typing already exist. | Photo/About and authorized appointment context; preserve the completed messaging work. |

The provisional policy-object layer was removed under ADR-119. Historical CONT documents describe earlier activation conditions and are not instructions to restore policy digests, activation records, DPO designations, or the removed Retention interface.

## 4. Decisions: what a case is and who owns it

**CASE-01 — One episode, not the student's entire lifetime record.** A student may have more than one case over time and, when justified, more than one active case. Do not automatically group every session for the student into a single case. Show existing accessible active cases when opening another, so the counselor can avoid accidental duplicates.

**CASE-02 — One primary responsible counselor per active case.** A covering counselor may have explicitly assigned work, but primary responsibility changes only through an accepted transfer. College assignment, case responsibility, historical session authorship, appointment provider, and individual task assignee remain distinct facts.

**CASE-03 — Open a case deliberately.** A counselor opens it from an authorized counseling intake, appointment, encounter, or routine-interview context. A referral can lead to counseling, but faculty submission alone does not create a clinical case or assign a counselor. Walk-in/called-in intake uses the existing authorized student-selection route. Case creation must not turn the Accounts directory into a professional-record discovery mechanism.

**CASE-04 — Keep the initial lifecycle small.** The main states are **Active** and **Closed**. Pending transfer, scheduled coverage, overdue work, and awaiting acceptance are separate workflow indicators; they do not replace the case state. Do not add a large status taxonomy in the first implementation.

**CASE-05 — Preserve history.** Linking or transferring a case never rewrites the author of an old Encounter, Evaluation, Student Session Summary, or Handoff. A correction to an incorrect link is explicit and audited; it does not erase the underlying record.

**CASE-06 — Count actual linked sessions.** The case's session count uses linked completed Encounters, without double-counting their associated appointments or Routine Interviews. Scheduled, cancelled, and missed appointments do not count as completed sessions. The student's total sessions across other cases is a different measure.

**CASE-07 — Separate case access from access to source content.** A case link, Head designation, or task assignment does not grant unrestricted access to the student's other records. New case-level permissions must explicitly define which historical records and pending tasks the current counselor may read or manage.

## 5. Decisions: coverage, transfer, and handoff

### 5.1 Two clear actions

**CONT-01 — Offer “Arrange temporary coverage” and “Transfer case” as separate actions.** Both identify the case, proposed counselor, purpose, information to share, and pending work. The screen must state whether primary responsibility will remain or change.

Temporary coverage retains the current 30-day duration and 14-day advance limits for the first version. Extending it requires a new deliberate request. A transfer has no automatic 30-day reversal: the new counselor remains responsible until another transfer or closure.

**CONT-02 — Receiving-counselor acceptance is required for new transfers and new coverage requests.** This extends current coverage behavior intentionally. Authorization confirms that the arrangement is appropriate; acceptance confirms that the receiver can take the specified work and has reviewed the information available. Silence is not acceptance.

### 5.2 Authority and exceptional situations

| Situation | Request / authorization | Acceptance and effect |
|---|---|---|
| Counselor A transfers to Counselor C | A requests; an uninvolved Head approves. | C accepts; responsibility changes atomically. |
| Head transfers her own case to C | The Head directly authorizes her own outgoing transfer. | C accepts; responsibility changes atomically. |
| A requests temporary coverage from C | A requests; an uninvolved Head approves. | C accepts; selected coverage starts at the approved start time. A remains primary. |
| Head requests temporary coverage for her own case | Direct outgoing-Head authorization, confined to her own case. | C accepts; Head remains primary. |
| Original counselor is unavailable or should not be required to initiate a conflict-related move | An eligible office staff member prepares the scoped request; an independent Head authorizes. No original-counselor signature or impersonation is required. | Receiver reviews available information and explicitly accepts. |
| Head is the proposed receiver | Use an eligible Head other than requester and receiver when one exists. When none exists, only the current primary Counselor's personal request may go directly to the receiving Head; office-prepared incoming requests are blocked. This is the owner's decision on 13 November 2026 for an office with one Head. | Receiving Head accepts explicitly. The personal-request route records `independent_authorization = false` in continuity history, audit metadata and Privacy governance activity. |
| Requester/receiver is the only possible approver, or the Head is implicated as reviewer of another counselor's case | Do not self-approve. Show the blocked reason and retain the existing owner. | An independent authorized arrangement is required before the system can execute it. |

**CONT-03 — Keep the Head exceptions narrow.** The Head may directly authorize only her own outgoing case, never an incoming arrangement or her own request for somebody else's case. By the owner's decision on 13 November 2026 for an office with one Head, when no eligible authorizer other than requester and receiver exists, the current primary Counselor may personally request the Head as receiver with a neutral reason; the Head must accept explicitly and the arrangement records `independent_authorization = false`. Office-prepared incoming requests remain blocked as “No independent approver is available.” If another eligible Head exists, ordinary independent authorization applies. Do not create a generic self-approval bypass, an automatic Acting Head, or a new delegated-approver role.

**CONT-04 — Use neutral reasons.** Include potential conflict of interest / impartiality concern, planned absence, unexpected absence, temporary support, and an appropriate change in service responsibility. A conflict reason does not label the outgoing counselor “biased” or establish misconduct. Sensitive explanation belongs in restricted content, not list rows, notifications, or reports.

### 5.3 Progress and effective ownership

**CONT-05 — Use an explicit workflow:** prepare → authorize → receiver reviews/accepts → effective. Show who must act next. The Head's own outgoing route goes directly from preparation to authorization, with a separate recorded authorization event.

For the first transfer version, acceptance makes the transfer effective immediately. Future-dated transfers are deferred. Coverage may be accepted ahead of time and becomes active only within its approved interval. A changed recipient, purpose, disclosure scope, task plan, or interval invalidates previous authorization/acceptance and requires a new review.

**CONT-06 — Define the pending-review boundary.** After authorization, the receiver may open a narrowly scoped review package containing the selected handoff and records, without case-management rights. For new transfer offers, the review offer expires seven calendar days after authorization. For coverage, it expires at the earlier of seven days or the approved coverage expiry. This is a chosen product expiry, not an institutional response-time or treatment rule. An expired offer needs fresh authorization; it does not change the owner.

Declining, cancelling, or letting an offer expire leaves primary responsibility unchanged. Store the decision and a bounded reason. The requester's workspace must show that another arrangement is needed. A completed transfer is reversed only through a new authorized transfer, never by deleting its history.

**CONT-07 — Protect concurrent changes.** Recheck the current owner, case status, recipient eligibility, disclosure scope, and affected tasks when accepting. Two receivers cannot both become primary. A stale acceptance must fail clearly, without a half-transferred case. Do not transfer a case while conflicting coverage remains active; end it explicitly or wait for expiry first. Preserve the current overlap restriction in the first coverage version.

**CONT-08 — Record student communication.** Include whether the student has been informed, when, and by whom. If informing is deferred, require a recorded reason and a named next action. This tracks communication; it does not invent a consent attestation or automatically send a message to the student.

### 5.4 The information being handed over

**HAND-01 — Make the shared package understandable.** Show selected records by useful type/date labels, their original authors, and an accurate explanation of the fields available. Keep the existing limited Encounter and Evaluation projections unless a later explicit field-inventory change is implemented and tested. “Shared records” must never imply the whole student file.

**HAND-02 — Structure the handoff around continuation of work:**

- Relevant context for the current concern and the handoff's purpose.
- Support already provided and current progress, as recorded by the author.
- Pending actions, upcoming appointments, and who will handle each one.
- Relevant considerations for continuing support.
- What the receiving counselor needs to review or do next.

Use separate structured sections while retaining a 12,000-character aggregate narrative bound initially. Keep operational approval explanations separate from confidential counseling narrative. A submitted handoff remains immutable; further information is an attributed, dated addendum, not an overwrite.

**HAND-03 — Planned transfer normally includes a submitted handoff.** If the original counselor is unavailable or a summary cannot appropriately be obtained, an independent Head may authorize an explicit “handoff unavailable” exception with a reason. Office staff may record operational facts; they cannot write clinical content under the outgoing counselor's identity. The receiver must see the missing-information warning and accept the available package. Temporary coverage may omit narrative where selected records and a clear task plan are sufficient.

**HAND-04 — Acceptance and receipt are not the same as professional endorsement.** Record who reviewed/accepted and when. Opening a handoff does not automatically accept a case, certify the accuracy of another author's narrative, or complete any task.

**HAND-05 — Set access after the change.** Temporary coverage/review access ends at expiry, revocation, decline, or cancellation. After an effective transfer, the new primary counselor keeps case access and the explicitly transferred source/task permissions until the next authorized ownership/lifecycle change. The outgoing counselor retains their ordinary historical-author access, but gains no access to the new counselor's later confidential work. Approved handoff records must remain reviewable by the authorized case owner after closure; closure alone does not destroy the documentation. Source-specific and account-access checks still apply.

## 6. Decisions: Follow-ups and appointments

**FUP-01 — Present a Follow-up as a next action.** Show an authorized action label, student, responsible staff member, due date, and status in the list and case overview. Do not copy confidential task text into notifications, office-wide dashboards, or unauthorized summaries. In narrow layouts, prioritize the action and deadline over secondary metadata.

**FUP-02 — Add an optional case relationship while preserving existing source links.** Counseling case tasks can still point to the relevant Encounter or Routine Interview. Referral and standalone administrative tasks remain valid without a case. From a case, “Add next action” preselects its context; from a source, show the eligible existing case connection without silently choosing a different case.

**FUP-03 — Preserve task meaning.** Pending → Completed requires an outcome; Pending → Cancelled requires a reason. An activity update keeps the task pending. Completing a task does not close a case/referral or create an appointment. A due date is a work deadline, not a booked meeting time. Further work gets a new task, with an explicit predecessor link when created through “Create next action.”

**FUP-04 — Review pending work before transfer.** Each pending case task must have an explicit disposition: transfer it, finish/cancel it through its normal workflow, or retain it with a named eligible person for a defined remaining action. Unallocated work blocks acceptance. Retaining work with an outgoing counselor is unavailable when the recorded conflict makes that participation inappropriate.

Selected task ownership changes with the effective transfer, preserving the original creator, source, due date, prior activity, and outcome history. The receiver's authority to the selected task must be implemented explicitly; changing an assignee ID alone is insufficient. Where old confidential history cannot be shared, prepare a safe successor task and explicitly resolve the original instead of downgrading confidentiality.

**FUP-05 — Coverage only delegates selected tasks.** Do not reassign every pending task automatically. Each temporarily delegated task has a named owner, deadline, and return plan. At coverage end, unfinished delegated tasks return to the primary counselor with an attributed event; if that counselor is ineligible, flag them for authorized recovery. Expiry never completes or cancels the work. Confidential recovery must use the case-continuity authority added here; the current operational-only “Recover assignments” screen must not become a broad confidential-access shortcut.

**APT-01 — Explicitly review future appointments.** A transfer does not rewrite old providers or silently change scheduled meetings. For every upcoming case-linked appointment, choose an existing supported reassignment/reschedule/cancellation action, or explicitly retain the meeting with its provider and explain why. A conflict-related move cannot quietly retain an inappropriate provider. Domain booking rules remain authoritative; the case screen opens the existing supported actions.

If an appointment cannot be reassigned because of existing linked records or lifecycle rules, show that constraint and use an explicit supported alternative. Never bypass it by updating database fields. Changing the reviewed appointment/task plan requires a fresh transfer review.

## 7. Decisions: case closure and return to support

**CLOSE-01 — No automatic closure after ten sessions.** Display the count for context. The responsible counselor deliberately closes the case after reviewing the work. Do not manufacture a maximum-session rule or treat a count as proof that a concern is resolved.

**CLOSE-02 — The current responsible counselor performs ordinary closure.** Being Head does not grant access to another counselor's confidential content or permission to assert a counseling outcome. If the responsible counselor is unavailable, arrange legitimate responsibility through the transfer workflow before clinical closure. Closing the Head's own case follows the same responsible-counselor rule and needs no additional routine approval.

**CLOSE-03 — Record a reason, outcome, author, and time.** Initial reasons: planned support concluded; student chose to discontinue; unable to re-establish contact after documented attempts; external service handover confirmed; or institutional service eligibility ended. The counselor documents the actual circumstances. These reasons must not all display as “successfully resolved.” Do not impose an invented number of contact attempts.

**CLOSE-04 — Review outstanding work first.** Show pending case tasks, future linked appointments, pending transfers, and active/scheduled coverage. Resolve them through explicit actions before closing. A continuing clinical action should keep the case active. Necessary post-closure administrative work may remain only with an explicit owner, due date, and post-closure designation. The closure screen never silently cancels appointments, completes tasks, or revokes access arrangements.

**CLOSE-05 — Preserve the record.** Closure ends active case work; it does not delete records, archive the student's account, close every referral, or prevent future access to support. Historical-author and authorized case-review access follow explicit permissions. Student-facing summaries remain separately published resources.

**CLOSE-06 — Support a deliberate return.** Reopen the same case for continuation of the same episode, recording the reason and an event that preserves the previous closure. A different concern/episode gets a new case. The current eligible responsible counselor may reopen; if that person is unavailable, the Head initiates the same independently authorized assignment/acceptance process before reopening. Do not permit a user to gain access merely by clicking Reopen.

**CLOSE-07 — Keep administrative Referral closure separate.** Faculty sees only the existing permitted referral progress. Do not expose case closure reason, session count, clinical outcome, or confidential Follow-ups through the Faculty portal. A closed administrative referral does not imply completed counseling, and vice versa.

## 8. Decisions: one coherent frontend

**UX-01 — Main path: Counseling → My cases → Case overview.** Opening a case should immediately answer: who is responsible, whether it is active/closed, what happened most recently, and what needs to happen next. Keep unlinked legacy sessions available through a clearly labeled session-records view.

The proposed overview emphasizes this information before secondary history:

```text
Student / Case reference                    Active
Responsible counselor: Counselor A
Completed sessions: 3
Next appointment: Tuesday, 10:00 AM
Next action: Check progress — due Friday — Counselor A

[Schedule session] [Record session] [Add next action]
More actions: Arrange coverage · Transfer case · Close case

Sessions and appointments | Next actions | Continuity and history
```

This is an information-layout guide, not a final visual design or an existing screen. Every value and action must come from an authorized backend response. Show only actions available at the current step; do not display every workflow form at once.

**UX-02 — Retain the useful global views.** Appointments remains the cross-student/service calendar; Follow-ups remains the current user's task list; My work remains the consolidated action queue. These views deep-link into the same case or source record and preserve relevant back-navigation/filter state. A mixed-service calendar must not become counseling-only.

**UX-03 — Embed continuity in the case.** Coverage/transfer details, pending approval, receiving acceptance, handoff, and selected tasks belong to the relevant case. Keep a separate approvals/work queue for staff who need to act across cases. Do not require users to discover a detached coverage page to continue a case.

**UX-04 — Explain responsibilities visibly.** Distinguish “Primary counselor,” “Covering counselor until…,” “Waiting for Head approval,” and “Waiting for Counselor C to accept.” Display dates in Philippine Time. Use names and useful record references rather than UUIDs as the primary labels. A transfer pending approval is not shown as already transferred.

**UX-05 — Preserve confidential audience boundaries.** Head/office operational queues show the metadata needed to route and authorize work, not unrestricted counseling narrative. Students and Faculty do not receive the staff case workspace. Sensitive descriptions are absent from general Home cards unless that projection explicitly authorizes them.

**UX-06 — Integrate existing Messages and E-Counseling.** Reuse the authorized contextual conversation rather than creating a second chat for each new case page. Do not automatically add the new counselor to old student conversations or share their history. Access to case-coordination messages follows the applicable review/coverage/transfer permission and participant lifecycle. Navigating or opening Messages must preserve an ongoing E-Counseling call.

**UX-07 — Consolidate the specific destinations that fragment the journey.** A source review on 12 November 2026, at the same checkout revision recorded in section 3, confirmed that Counseling currently opens an Encounter list and links to a separate coverage route. Coverage is not a separate top-level portal menu item. Follow-ups already appears in My work, while the counselor's daily menu also includes the full Follow-ups workspace. Referral details already contain linked Call Slips and Follow-ups, so that connection should be improved rather than recreated.

| Current screen or entry | Selected direction | What remains available |
|---|---|---|
| Counseling opens “My Counseling Encounters” | Make the authorized counselor's case list and case overview the main entry. Show sessions as part of the case journey. | Session-record browsing and existing Encounter detail routes for historical and unlinked records; the student's separately published Session Summaries. |
| Separate coverage request/detail journey | Prepare and review the relevant coverage, transfer, and handoff from the case's continuity section. Show the responsible person and waiting step together. | Authorized approvals and incoming-work queues across cases; the existing legacy coverage view for grants without case linkage. An approver opens the permitted review projection without gaining the clinical case workspace. |
| Follow-ups alongside My work | Put case tasks under “Next actions” in the case. Make My work the daily entry to work requiring attention, with a clear link to the complete Follow-ups workspace. | The global assigned-task list, completed/cancelled history, standalone and Referral tasks, reporting, and authorized assignment recovery. |
| Referral and Call Slip pages | Continue issuing and reviewing linked Call Slips from the Referral, with clear next-action links and a return to that Referral. | Standalone Call Slip issuance and the cross-student Call Slips list. They also serve work without a Referral and remain important to the office assistant and student audiences. |
| Appointments and session recording | Start scheduling or recording from the case when its context is known, using the same appointment and Encounter workflows. Return to the originating case or calendar after the action. | The mixed-service calendar, booking rules, appointment details, and independent session records. A task deadline and a session count keep their existing distinct meanings. |
| Messages, E-Counseling, and Counselor About | Open the existing authorized conversation/call from its context. Show Counselor About through the same focused detail interaction in selection and Messages. | General Guidance Office inquiries, the Messages workspace, and the persistent active-call experience. About does not need a new standalone profile destination. |
| My work and Office workload | Keep the personal action queue and office oversight clearly named for their different purposes. Connect an item to its authorized case or source. | Office-level operational projections and authorized management actions; sensitive task or case descriptions retain their separate disclosure rules. |

“Remove” here means retiring a redundant entry or separate everyday journey once its replacement works. Existing record URLs and independent domain resources remain usable where they still serve authorized work. The current Follow-up report and Recover assignments links are already secondary tools inside Follow-ups; keep them there rather than claiming they are extra top-level destinations to remove.

**UX-08 — Reduce menu overlap when the connected task experience is ready.** In CW-2, move Follow-ups from the counselor's default daily navigation to More, retaining it in authorized destination search and linking to its complete view from My work. Keep the current daily Routine Interviews entry, which serves a separate workflow. The core counselor navigation becomes Home, My work, Appointments, Messages, Counseling, and Routine interviews. The Head retains Office workload and Reports according to existing access; the office assistant retains daily Referrals and Call Slips. Student and Faculty navigation continues to serve their own published records and administrative tasks.

Apply ordering and visibility through the shared portal workspace registry and current access helpers. Preserve authorized additional destinations in More; a role's preferred order does not remove effective grants. Keep creation, handoff, closure, and other case-specific actions with their record context. Preserve the originating list/filter state, unsaved-change handling, and existing record access when navigating between the case and global views.

Implement this in the existing CW order: CW-1 replaces the session-first counseling entry only when genuine case relationships and authorized projections exist; CW-2 connects tasks and scheduling before reducing daily-menu overlap; CW-3 integrates continuity; CW-4 adds closure in the same workspace; CW-6 supplies About and conversation context. A visual regrouping alone cannot establish case ownership, transfer acceptance, or lifecycle behavior. Review any retired page against its replacement for history, permissions, incoming work, and legacy records.

## 9. Decisions: Referral scheduling information

**REF-01 — Add “When can Guidance reach or meet the student?” to referral preparation.** A referrer may provide known student availability, periods when the student may leave the referrer's own class, or choose “Unknown / needs confirmation.” Both kinds of known information may be supplied. Do not require Faculty to guess the student's full timetable.

**REF-02 — Use structured windows with a short note.** Allow up to five windows, each identified as a specific date or recurring weekday, start/end time, and information type. Recurring windows require a validity end date. Use Philippine Time, require end after start, and flag expired windows. A note can explain scheduling constraints; sensitive referral reasons stay in the existing reason field.

**REF-03 — Preserve who supplied the information.** Store the Faculty-submitted scheduling details as part of the immutable submission. Staff may separately record verified/updated availability, with author/time, without rewriting the Faculty's original statement. “Faculty reports availability” must not silently become “Student confirmed.”

**REF-04 — Treat it as scheduling guidance.** Show it to authorized staff in the referral and relevant appointment-preparation context. It neither reserves a slot nor overrides counselor availability, conflicts, or booking eligibility. Creating a referral still does not automatically book an appointment or contact the student.

## 10. Decisions: Counselor About and Guidance Messages

**ABOUT-01 — Share one authorized counselor summary.** Use existing counselor identity/photo and active organization responsibility data. The About action shows assigned colleges and their campuses. Handle Head fallback responsibility accurately rather than pretending every college is a direct assignment. Display an honest empty/unavailable state when assignment details are absent.

**ABOUT-02 — Keep About separate from selection.** Opening About must not change the selected counselor or book an appointment. Reuse it in booking, eligible recipient selection, and an authorized counselor conversation header. Do not expose the general Accounts/Organization administration payload to students just to obtain these fields.

**ABOUT-03 — Keep the scope focused.** Do not add biographies, qualifications, specialties, availability promises, or profile-management forms without an actual source and separate requirement. Distinguish organization assignment from being the responsible counselor for a particular case. Refresh displayed information when assignment or access changes.

**MSG-01 — Supply a safe counselor photo and appointment summary.** Where the viewer is authorized, include appointment reference, service, scheduled date/time, and status so multiple conversations with the same counselor can be distinguished. Recheck appointment/thread authorization; do not disclose context merely because an ID was linked historically.

**MSG-02 — Preserve office identity and completed work.** Shared Guidance Office conversations remain identified as the office. Preserve the existing Seen/typing behavior, identity layout, name wrapping, composer reachability, and contextual-call integration. This package does not rebuild them or start unrelated delivery-status, attachment, AI-summary, or transcript features.

## 11. Backend and migration work

The following are domain responsibilities to implement, not invented endpoint names. Define the canonical OpenAPI contract before the UI consumes each new behavior; regenerate the frontend client normally.

| Workstream | Required backend changes |
|---|---|
| Case foundation | Persistent episode, primary counselor, Active/Closed lifecycle, minimal case metadata, explicit record relationships, ownership/lifecycle history, and authorized projections. |
| Record linking | Validate same student, legitimate source access, unique Encounter-to-case membership, and deliberate corrections. Do not duplicate source rows. |
| Continuity | Separate transfer and coverage semantics; narrow outgoing-Head authorization; review package; receiver decisions; expiry; atomic effective ownership and selected task changes. |
| Handoff | Structured, versioned confidential content; submitted snapshots and addenda; explicit unavailable-author exception and recipient receipt. |
| Follow-ups | Case and predecessor links; separate task/source permissions; selected transfer and temporary delegation; unfinished-task return/recovery behavior. |
| Appointments | Case relationship and explicit coordination plan using existing booking services. Preserve old providers and appointment lifecycle rules. |
| Closure/reopening | Authorized transitions, disposition checks, reason/outcome, chronology, and next-action projections. |
| Referral timing | Versioned confidential content/schema, immutable Faculty submission, staff verification records, and authorized schedule suggestions. |
| Identity and Messages | Shared safe counselor summary, scoped photo/assignment disclosure, and current appointment context. |

### Migration decisions

- Additive, data-preserving migrations are the default for this work. Do not treat ADR-119's earlier reset-only delivery as blanket permission to reset databases or rewrite existing release baselines again. Follow the repository's then-current migration/manifest rules when implementing.
- Keep legacy Encounters, Follow-ups, referrals, and coverage history usable. Do not auto-create one case per student, infer shared clinical concerns, or invent historical acceptance/closure events.
- Provide a deliberate “Link existing session” path for authorized counselors. Linking records owned by other counselors requires the explicit approved disclosure/linking route; a matching student ID is insufficient.
- Existing active coverage retains its documented legacy approval behavior until it expires or is revoked. Clearly identify it as legacy coverage; do not fabricate receiver acceptance. New requests use the acceptance rule in this plan. Do not expand legacy scopes during conversion.
- Case labels/summaries and narrative fields are sensitive. Use existing confidential-data patterns, bounded projections, content-free audit events, and protected record access. Linking case membership does not create universal student-history access.
- Revalidate permissions and versions at mutations. Sensitive data must clear when access expires or changes. Existing source records, published Student Session Summaries, and historical message audiences keep their independent controls.

## 12. Implementation order and concrete deliverables

Each package includes its own API, UI, meaningful tests, and documentation. The labels below are this plan's work packages.

| Package | State on 13 November 2026 |
|---|---|
| CW-1 | Implemented and verified locally (backend, frontend, browser journeys in Chromium and WebKit, upgrade rehearsal). In review as pull request #360; not merged or deployed. See the [CW-1 record](cw-1/README.md). |
| CW-2 | Implemented and verified locally with mocked and real local backends, in Chromium and WebKit, plus an upgrade rehearsal. Stacked on CW-1; not merged or deployed. Staff-side booking remains an open gap. See the [CW-2 record](cw-2/README.md). |
| CW-3a | Transfer implemented and verified locally: backend, frontend, Chromium/WebKit mocked and real-backend journeys, and upgrade rehearsal. Stacked on CW-2; not merged or deployed. See the [CW-3 record](cw-3/README.md). |
| CW-3b / CW-3c | Handoff and case coverage not started. |
| CW-4 to CW-7 | Not started. |

| Order | Package | Deliverable and completion condition |
|---|---|---|
| 1 | **CW-1: Case foundation and overview** | Case creation/linking, primary responsibility, authorized session count, active case list, and usable overview. Existing unlinked records remain accessible. |
| 2 | **CW-2: Next actions and scheduling coherence** | Case-linked Follow-ups, visible action labels, predecessor links, contextual scheduling, and shared navigation with global task/calendar views. This establishes the pending-work model used by transfer. |
| 3 | **CW-3: Coverage, transfer, and handoff** | Approval matrix, Head's own outgoing route, recipient review/acceptance, ownership transitions, selected task handling, appointment review, and bounded access. No unsupported “transferred” success state. |
| 4 | **CW-4: Closure and reopening** | Deliberate close/reopen, reasons/outcomes, pending-work disposition, retained chronology, and accurate distinction from referral/session/task completion. |
| 5 | **CW-5: Referral timing** | Faculty availability/class-release windows, unknown option, immutable submission, staff verification, and useful scheduling display. This can proceed independently once the shared field conventions are settled. |
| 6 | **CW-6: Counselor About and Messages context** | Shared safe counselor summary, assignment/campus About, photos, and authorized appointment summary. Preserve existing messaging improvements. |
| 7 | **CW-7: Integrated verification and handover** | Cross-role browser journeys, access regressions, migration rehearsal, workflow documentation, and an evidence-based review of the exact combined candidate. |

Do not postpone every visible improvement until all backend work is finished. Each package should provide a coherent usable increment, with unavailable future actions omitted or honestly explained. Any implementation task must first inspect the current checkout/branch and changes; the branch used to write this planning document is unrelated to the future feature branch.

## 13. Required acceptance scenarios

These are checks to run during implementation, not claims that tests have already passed.

- [ ] A counselor can explain a case's owner, status, last session, and next action from its overview without opening multiple modules.
- [ ] A referral, self-booked appointment, walk-in, and routine-interview escalation can each reach the appropriate counseling case through authorized actions.
- [ ] Two different concerns for one student can remain separate; legacy sessions are not grouped automatically.
- [ ] Actual sessions are counted once; cancelled/no-show/future appointments do not inflate the count.
- [ ] Completing a session/task or administratively closing a referral does not close the case.
- [ ] Ten completed sessions never trigger automatic closure.
- [ ] A → C transfer requires Head authorization and C's acceptance; A remains responsible while pending or declined.
- [ ] The Head can authorize her own outgoing case without a self-approval deadlock, but cannot use that exception for an incoming case.
- [ ] For an office with one Head, the current primary Counselor's personal request to the Head requires explicit acceptance and records no independent authorization; office-prepared requests to that Head are blocked. With another eligible Head present, ordinary independent authorization applies (owner decision, 13 November 2026).
- [ ] An unavailable original counselor can be handled without impersonation or a fabricated handoff; missing information is visible to the receiver.
- [ ] An implicated/absent independent approver results in a clear blocked arrangement, not silent self-approval.
- [ ] Review access is limited and expires; changing the package invalidates earlier authorization/acceptance.
- [ ] Concurrent accept/close/revoke/eligibility changes cannot produce two primary counselors or partial task transfer.
- [ ] Coverage keeps the primary counselor, limits shared work, and returns unfinished delegated tasks or flags legitimate recovery at its end.
- [ ] The receiver obtains only approved source/task information; Head/GOA approval metadata does not expose confidential narrative.
- [ ] A transferred confidential task is manageable under the new explicit authority, while unrelated historical sources remain inaccessible.
- [ ] Appointment plans respect existing provider/linkage rules; no silent booking, reassignment, reschedule, or cancellation occurs.
- [ ] Closing a case accounts for pending tasks, appointments, transfers, and coverage; a closure reason is not mislabeled as successful resolution.
- [ ] Reopening preserves closure history and checks current authority; new concerns can open a separate case.
- [ ] Faculty can supply availability, class-release periods, or unknown information; an immutable submitted statement stays distinct from later staff verification.
- [ ] Stale timing suggestions do not reserve slots or override current booking rules.
- [ ] About opens without selecting a counselor and shows only authorized current assignment/campus data.
- [ ] Messages identifies the right counselor/appointment, preserves office identity, and does not expose old conversations to a newly assigned counselor.
- [ ] Existing Student Session Summary publication, Faculty visibility, Seen/typing, and active E-Counseling call behavior remain intact.
- [ ] Phone layouts, keyboard navigation, focus after actions, loading/empty/denied/stale states, and back-navigation support the full journey.
- [ ] From My work or the shared calendar, a counselor can open an authorized case, handle the next action, and return to the originating view without creating duplicate tasks, sessions, appointments, or conversations.
- [ ] Moving Follow-ups to More preserves access to the complete task list, completed/cancelled history, reporting, and authorized recovery; standalone tasks remain usable without a case.
- [ ] Integrating coverage into a case preserves legacy grant access and independent approval projections; an approver receives only the review information authorized for that action.
- [ ] Standalone Call Slips, student Session Summaries, Faculty Referrals, and mixed-service appointments remain usable through their existing audience permissions.
- [ ] A migration rehearsal preserves legacy authorship, open tasks, source links, coverage intervals, and historical evidence without inventing events.

Unit/API tests should cover meaningful transitions and authorization boundaries; browser tests should exercise real end-to-end role journeys and recovery. Runtime and deployment claims require fresh evidence on the implementation candidate. This document creates no deployment, database-reset, or external-messaging action.

## 14. Source map and conversation provenance

Use current owning code for implementation. Historical audits explain why limits exist but do not override newer code or the explicit decisions above.

| Evidence | Location |
|---|---|
| Individual Encounters and published summaries | [Counseling models](../be/compass/counseling/models.py) |
| Appointment completion records one Encounter | [Counseling finish service](../be/compass/counseling/finish_service.py) |
| Current coverage kinds, reasons, and grants | [Continuity models](../be/compass/counseling/continuity_models.py) |
| Current limits and source field inventories | [Continuity rules](../be/compass/counseling/continuity_rules.py), [selected-read schemas](../be/compass/counseling/continuity_read_schemas.py) |
| Current approval and effective-state behavior | [Continuity services](../be/compass/counseling/continuity_services.py) |
| Handoff content and lifecycle | [Handoff content](../be/compass/counseling/handoff_content.py), [handoff services](../be/compass/counseling/handoff_services.py) |
| Current coverage and handoff screens | [Coverage page](../fe/src/features/counseling/coverage/coverage-page.tsx), [details](../fe/src/features/counseling/coverage/coverage-detail.tsx), [protected records](../fe/src/features/counseling/coverage/protected-record.tsx) |
| Current portal destinations, role ordering, and session-first Counseling entry | [Workspace registry](../fe/src/features/portal/components/portal-workspaces.ts), [Counseling entry](../fe/src/features/counseling/counseling-entry-page.tsx), [Encounter list](../fe/src/features/counseling/counselor-encounters.tsx) |
| Personal work queue and Follow-up overlap | [My work](../fe/src/features/work-queue/work-queue-page.tsx), [work presentation](../fe/src/features/work-queue/work-queue-presentation.ts) |
| Existing Referral/Call Slip connection and standalone issuance | [Linked Call Slips](../fe/src/features/referrals/referral-call-slip-section.tsx), [direct issuance](../fe/src/features/call-slips/call-slip-create-page.tsx) |
| Follow-up lifecycle, permissions, recovery | [Models](../be/compass/guidance_followups/models.py), [policy](../be/compass/guidance_followups/policy.py), [services](../be/compass/guidance_followups/services.py), [recovery](../be/compass/guidance_followups/recovery.py) |
| Follow-up list and contextual explanation | [List](../fe/src/features/guidance-followups/followups-list.tsx), [context](../fe/src/features/guidance-followups/followups-context.tsx), [help](../fe/src/features/guidance-followups/followups-help.tsx) |
| Faculty submission contract and confidential content | [Faculty API](../be/compass/referrals/faculty_api.py), [Referral content](../be/compass/referrals/confidential_content.py) |
| Administrative Referral closure | [Referral administration UI](../fe/src/features/referrals/referral-administration.tsx) |
| Counselor selection and organization responsibilities | [Appointments API](../be/compass/appointments/api.py), [Organization models](../be/compass/organization/models.py) |
| Message identity/context and completed Seen/typing work | [Messages API](../be/compass/guidance_messages/api.py), [GMSG-6/7 record](gmsg-6-7/README.md) |
| Current replacement of provisional activation rules | [ADR-119](../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) |

Conversation sources:

- Recovered chat **“siguro balikan natin yung mga naiwan natin for improvements…”**, ID `01a1cf0f-8c2e-7a03-b5f8-e7bef273cb5a`: all five turns were read, including the final unanswered question about limited handoff data and confusing pages.
- Current continuation chat, ID `01a1cf28-d9d3-73d1-b75e-bed37098a3da`: Follow-ups, possible case closure, the plain-language journey, frontend coherence, and the owner's instruction to decide and document the work.
- Subsequent continuation chat **“aruy naputol na naman tayo sa kabilang chat, basahin mo daw…”**, ID `01a1cf4d-5104-75a3-bdef-a52324642b4a`: the final unanswered product question asked which pages to simplify or remove because the frontend feels fragmented. Sections UX-07 and UX-08 complete that review after recovering the conversation in chat `01a1cf67-4479-75b3-8465-211bc42bf612` and checking the current owning frontend sources.
- The earlier fifteen-proposal document was consulted for continuity and referral context. Its technical suggestions are not all direct panel requirements, and it does not establish automatic closure after ten sessions.

**Document completion:** the discussions have been consolidated, product decisions selected, and the specific navigation/page consolidation recorded. **Implementation completion:** CW-1, CW-2 and CW-3a are implemented and verified locally but not merged ([CW-1 record](cw-1/README.md), [CW-2 record](cw-2/README.md), [CW-3 record](cw-3/README.md)); CW-3b, CW-3c, CW-4 to CW-7 and every acceptance check in section 13 remain open. No box in section 13 is ticked, because none has been confirmed in a browser on a combined candidate.
