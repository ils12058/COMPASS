# Institutional UAT Matrix

## Execution rules

This is a blank handoff for a separately approved staging deployment and human UAT. **No result has
been recorded.** Fill fields only after a tester performs the case with an approved non-production
account and record.

Use existing approved UAT accounts and synthetic or approved non-production records. Do not create
production accounts, change credentials, distribute passwords, extract real Student records, or
create institutional test data without approval. For one-time submissions, use only an approved
test opportunity/record whose lifecycle is suitable for testing; if none is available, mark the
case Blocked and explain why. Confirm the tester's role, capability set, Student lifecycle,
College/supervision scope, browser/OS, viewport, and test-data class in the comments/evidence.

**Per-case execution fields are blank by design:** actual result, status (`Pass / Fail / Blocked /
Not Run`), evidence reference, comments, and defect reference. A blank field does not imply a pass.

## Student

### STU-01 — Home actions and announcements

- **Role:** Current Student.
- **Preconditions:** Approved current Student account with at least one canonical pending action and an announcement visible to that account.
- **Steps:** Sign in; review the first Home action; open and return from the owning workspace; inspect announcements and any count links.
- **Expected:** Pending canonical action is prominent; count meaning is preserved; only authorized Student destinations appear; announcement audience, pinning, and links are correct.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-02 — Lifecycle and self-service eligibility

- **Role:** Current Student, then approved Graduated/Former Student account if available.
- **Preconditions:** Accounts with known lifecycle and only their existing capabilities.
- **Steps:** Compare Home actions and destinations; attempt only documented self-service links; inspect historical Inventory/Tracer access.
- **Expected:** Current-only actions are absent for non-current accounts; authorized historical reading remains available; no action or obligation is inferred from a missing count.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-03 — Individual Inventory draft and review

- **Role:** Current Student.
- **Preconditions:** Approved editable Inventory draft and designated test account.
- **Steps:** Edit one answer; move between sections without saving; use Save progress; trigger a required-field error; follow the error summary; review answers; cancel final confirmation.
- **Expected:** Unsaved answers remain; confirmed save feedback appears only after save; error navigation reaches the owning field; cancel does not submit; no official question or option changes.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-04 — Exit Interview draft and conditional questions

- **Role:** Eligible Student.
- **Preconditions:** Approved Exit Interview opportunity and designated non-production draft.
- **Steps:** Navigate by the section links; answer a conditional question; leave a required rating unanswered; save a partial draft; review and return to the question.
- **Expected:** Official groups and scales remain intact; draft and final validation differ appropriately; error/section links return to the correct question; saving does not submit.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-05 — Graduate Tracer voluntary draft

- **Role:** Eligible Graduate.
- **Preconditions:** Existing voluntary Tracer opportunity or draft; no new eligibility rule is assumed.
- **Steps:** Open without starting a response if none exists; when an approved draft exists, exercise one employment branch and save; review conditional fields and section links.
- **Expected:** Participation stays voluntary; only authorized existing opportunities are shown; inactive conditional answers do not leak into the payload; draft remains distinct from final submission.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-06 — Routine Intake save, submit, and read-only state

- **Role:** Current Student with an authorized Routine Interview.
- **Preconditions:** Approved test Appointment/Interview; approved test record for any final submission.
- **Steps:** Edit an answer; save progress; review “Other” and concern questions; submit through the explicit confirmation; reopen the record.
- **Expected:** Partial draft is allowed; current answers are preserved; success is confirmed only by the server; a submitted Intake is read-only and no duplicate submission is generated.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-07 — Customer Feedback one-time response

- **Role:** Student with an eligible Customer Feedback opportunity.
- **Preconditions:** Dedicated approved test opportunity not used by another UAT case.
- **Steps:** Review required and optional questions; leave optional respondent identity blank; inspect confirmation; submit once; revisit the opportunity.
- **Expected:** Identity remains optional and is not copied from the profile; questions/conditions are unchanged; submission is one-time and reports only confirmed status.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-08 — CSM numeric zero and Not Applicable

- **Role:** Student with a separate eligible CSM opportunity.
- **Preconditions:** Dedicated approved CSM test opportunity.
- **Steps:** Select numeric zero and Not Applicable where appropriate; inspect validation and confirmation; submit once; compare with Customer Feedback state.
- **Expected:** Zero and N/A remain valid source choices; CSM is independently tracked from Customer Feedback; no draft persistence is promised.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### STU-09 — Appointment/service navigation

- **Role:** Student with existing Appointment/service capabilities.
- **Preconditions:** Approved synthetic or non-production schedule state.
- **Steps:** Open Appointment and service destinations from Home; use the owning workspace's booking/navigation path.
- **Expected:** Home only links to existing authorized destinations; availability and booking remain owned by the Appointment workflow; no clinical detail appears in Home.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Guidance Counselor

### COU-01 — Manila agenda and canonical My Work

- **Role:** Counselor.
- **Preconditions:** Counselor account with `appointments.view_self`, one self Appointment today, and known Work Queue ordering.
- **Steps:** Open Home near a UTC/Manila date boundary if feasible; compare agenda date/time and first work items with their owning workspace.
- **Expected:** `Asia/Manila` date is used; agenda is self-scoped, chronological, bounded; My Work retains backend ordering and links.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### COU-02 — Counselor Evaluation save and finalization

- **Role:** Authorized Counselor.
- **Preconditions:** Approved completed eligible Encounter and associated Evaluation draft.
- **Steps:** Review nullable ratings/narratives; save draft; initiate finalization only through the authorized Encounter flow; reopen after confirmation.
- **Expected:** Save and finalization are separate; nullable values and source narratives remain intact; confirmed finalization is read-only; no unauthorized record is shown.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### COU-03 — Routine Evaluation ownership

- **Role:** Counselor.
- **Preconditions:** One assigned and one unassigned/non-authorized Routine Interview test record, if available.
- **Steps:** Open canonical work; inspect the assigned record; attempt the unauthorized deep link through normal app navigation.
- **Expected:** Assigned work opens through the owning route; unassigned/resource-denied content remains concealed; Student intake answers do not appear in Home previews.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### COU-04 — Follow-Ups and Counseling continuation

- **Role:** Counselor with the relevant existing assignment/capabilities.
- **Preconditions:** Approved assigned Follow-Up and Counseling work item.
- **Steps:** Continue from Home/My Work to each owning workspace; inspect only the detail allowed there.
- **Expected:** Work order and destination remain canonical; no private narrative is included in Home; authorization is rechecked by the destination API.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### COU-05 — Agenda and stale/error states

- **Role:** Counselor.
- **Preconditions:** Approved schedule state and a controlled test environment that can safely produce a temporary read failure.
- **Steps:** Review confirmed empty, transient failure/stale, and retry states without changing source data.
- **Expected:** Empty, failed, and stale are distinguishable; stale data is labeled; Retry refreshes the source; no Home mutation occurs.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Head Guidance Counselor

### HEAD-01 — Head retains ordinary Counselor self-work

- **Role:** Head Guidance Counselor.
- **Preconditions:** Head-designated Counselor account with self Appointment and Work Queue access.
- **Steps:** Review Home agenda, My Work, and work destinations; compare with the same account's Counselor responsibilities.
- **Expected:** Self work remains scoped to the current Counselor; designation alone does not expand agenda or work records.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### HEAD-02 — Authorized oversight and absent capability

- **Role:** Head Guidance Counselor with approved test accounts for granted and absent optional capabilities.
- **Preconditions:** Institution-approved role/capability combinations; do not alter live grants for this case.
- **Steps:** Compare oversight destinations in each account; follow only a destination that the existing capability grants.
- **Expected:** Only existing authorized destinations appear; absent capability is not described as empty workload; backend still decides every resource access.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### HEAD-03 — No cross-Counselor confidential access

- **Role:** Head Guidance Counselor.
- **Preconditions:** Approved non-production Counselor A/other-Counselor data with distinct resource scopes.
- **Steps:** Open Home and attempt the ordinary application path to another Counselor's restricted Appointment/Evaluation/Assessment record.
- **Expected:** Head designation grants no override; unauthorized record remains concealed; no clinical narrative is shown in Home.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Guidance Services Staff

### GSS-01 — Canonical work, managed schedule, and Office metrics

- **Role:** Guidance Services Staff with approved operational scope.
- **Preconditions:** Account with `appointments.manage` and known scoped Work Queue/Guidance Operations data.
- **Steps:** Review Home work order, today's managed Appointments, Office workload labels, and destinations.
- **Expected:** Managed and self-Appointments are not conflated; schedule is bounded and Manila-dated; aggregate metrics retain their source meaning; My Work stays canonical.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### GSS-02 — Missing Appointment capability and direct link

- **Role:** GSS account without `appointments.manage`.
- **Preconditions:** Approved account configuration without this capability.
- **Steps:** Open Home; verify managed Appointment area/request is absent; attempt an existing managed Appointment route.
- **Expected:** Home does not claim an empty schedule or request the list; the owning route/backend denies unauthorized access.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### GSS-03 — Good Moral preparation versus issuance

- **Role:** GSS preparer and, where available, view-only GSS.
- **Preconditions:** Approved requests in preparation and Counselor-issuance states.
- **Steps:** Open each request from Home/Work; inspect available actions and status labels.
- **Expected:** Preparation and issuance remain separate; GSS does not receive Counselor issuance action; no certificate is issued from Home.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### GSS-04 — Call Slips, Referrals, Messages, Group Sessions

- **Role:** Guidance Services Staff.
- **Preconditions:** Existing capabilities for only the relevant authorized workspaces.
- **Steps:** Follow authorized links from Home/My Work; verify unavailable destinations remain absent or denied.
- **Expected:** Each domain retains its owner, scope, and lifecycle; Home introduces no new mutation or broad visibility.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### GSS-05 — Scope/account change and stale data

- **Role:** GSS, then a restricted Student or GSS test account with narrower scope.
- **Preconditions:** Approved account-switch or scope-change path.
- **Steps:** Confirm initial data; switch account or revoke scope through the approved process; revisit Home and detail links.
- **Expected:** Prior protected schedule/work/metrics disappear after the new account/scope is confirmed; denied sources do not reuse cached content.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Other roles

### OTH-01 — IT Administrator non-regression

- **Role:** IT Administrator.
- **Preconditions:** Approved account with ordinary Overview access.
- **Steps:** Open Overview; inspect summary, work, and navigation; verify no UX15 Student/Counselor/GSS-only composition appears.
- **Expected:** Existing general Overview behavior remains; no Guidance clinical data is introduced.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### OTH-02 — Institutional Officer non-regression

- **Role:** Institutional Officer without clinical-resource authority.
- **Preconditions:** Approved role/capability state.
- **Steps:** Open Overview and attempt only ordinary authorized destinations.
- **Expected:** Existing Overview remains; no Counselor/Student confidential content is exposed by UX15 Home.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### OTH-03 — DPO-designated Institutional Officer

- **Role:** Institutional Officer with approved DPO designation, where supported.
- **Preconditions:** Institution-approved account and documented DPO-authorized resources.
- **Steps:** Verify privacy oversight destinations and attempt no unrelated clinical access.
- **Expected:** Existing privacy-specific authority remains correctly scoped; designation does not create Guidance clinical access.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Accessibility and interaction

### A11Y-01 — Keyboard-only Portal Shell and Home

- **Role:** Run with Student, Counselor, Head, and GSS accounts.
- **Preconditions:** Supported desktop browser and approved account.
- **Steps:** Use skip link, Tab/Shift+Tab, Enter/Space, command palette, dock/drawer, account menu, and Accessibility controls; close overlays with Escape.
- **Expected:** Logical focus order, visible focus, correct accessible names, focus returns to opener, and content remains available with the dock expanded/collapsed.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### A11Y-02 — Actual browser zoom

- **Role:** Repeat representative Student form, Counselor Home, GSS Home, and shell flows.
- **Preconditions:** Approved Chromium and Safari versions; real 200% browser zoom.
- **Steps:** Test at effective narrow and desktop layouts; exercise actions, dialogs, menus, fields, tables, and horizontal scrolling.
- **Expected:** No clipped primary actions or inaccessible questions; enlarged text remains readable; focus and popovers remain usable.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### A11Y-03 — Screen reader

- **Role:** Repeat representative Student, Counselor, Head, and GSS flows with institution-supported assistive technology.
- **Preconditions:** Supported screen reader/browser combination and approved synthetic/non-production account.
- **Steps:** Inspect landmarks/headings, Home status, form labels/errors, status announcements, navigation, and dialogs.
- **Expected:** Correct role/name/state and reading order; errors and confirmed saves are announced once; focus moves to and returns from dialogs appropriately.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### A11Y-04 — Physical mobile and touch

- **Role:** Student and one Guidance staff role.
- **Preconditions:** Approved phone/tablet and non-production accounts.
- **Steps:** Use Home discovery, mobile navigation, form sections, matrices, confirmation, and recovery at narrow viewport.
- **Expected:** No clipped or overlapping controls; choices and targets are usable; touch navigation preserves answer values and visible context.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### A11Y-05 — Error summary and confirmation focus

- **Role:** Student and Counselor.
- **Preconditions:** Approved draft and authorized finalization scenario.
- **Steps:** Trigger validation; follow summary link; open/cancel/confirm a consequential action; inspect focus after closing.
- **Expected:** Original invalid field is reached and described; cancel preserves input; confirmation uses clear domain-specific consequence; focus returns logically.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

## Staging integration and environment checks

### SYS-01 — Staging API/build compatibility

- **Role:** Approved representative accounts only.
- **Preconditions:** Separately approved promotion and staging deployment; deployment is not authorized by this matrix.
- **Steps:** Verify session/CSRF, Home queries, form reads/writes, route/API contract, and relevant error states against the actual staged backend.
- **Expected:** Existing endpoints/schemas and capabilities behave as reviewed; no missing configuration or migration; all status is recorded with environment SHA.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### SYS-02 — Session, permission, and scope revocation

- **Role:** Approved privileged and restricted account pairs.
- **Preconditions:** Approved test account-switch and capability/scope-change process.
- **Steps:** Confirm privileged data; switch or revoke; revisit Home and an authorized/unauthorized resource.
- **Expected:** Cached private data is removed after new authority is confirmed; backend rejects unauthorized deep links; no stale Home detail remains.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____

### SYS-03 — Controlled uncertain-submission recovery

- **Role:** Student and Counselor.
- **Preconditions:** Approved isolated test data and a controlled non-production fault method; do not simulate a production failure.
- **Steps:** Exercise a lost response/status check for Routine Intake, Feedback/CSM, and Evaluation only where safe; observe recovery before taking another action.
- **Expected:** No false success or automatic duplicate; exact retry is offered only for the same supported intent; canonical state and read-only transition remain correct.
- **Actual result:** ____ · **Status:** ____ · **Evidence:** ____ · **Comments:** ____ · **Defect:** ____
