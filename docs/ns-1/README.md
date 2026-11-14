# NS-1: Counselor-initiated next session and follow-up shortcuts

**Date:** 14 November 2026 · Philippine Time
**Branch:** `claude/counseling-next-session`, cut from `codex/counseling-cw1-case-foundation` at `53c3d704` (the combined CW-1 to CW-6 workflow in [#360](https://github.com/ils12058/COMPASS/pull/360), open when this branch was cut)
**Specification:** the owner's proposal *Counselor-initiated next session and follow-up shortcuts* (14 November 2026), with the section 5 defaults D1 to D5 applied as written
**Builds on:** [CW-2](../cw-2/README.md) (next actions, case Appointments; it recorded the missing staff booking as D5), [CW-3](../cw-3/README.md) (coverage), [CW-6](../cw-6/README.md) (Messages context)
**Status:** Implemented and verified locally with mocked and real backends. Hosted CI has not run, nothing is merged or deployed, and nobody at the Guidance and Counseling Office has tried it. See [Verification](#verification).

## What people can do now

**Counselor, from a case**

- **Propose session** from the case's new **Session proposals** panel, or from a pending next action. The form takes a purpose and 1 to 3 times, each **In person** or **Online**, picked from the Counselor's open times. Nothing is booked or reserved.
- Optionally tick **Also issue a Call Slip** when a time is In person. Nothing is issued then.
- Follow each proposal on the case: waiting, accepted (with its Appointment), declined, withdrawn or expired.
- **Withdraw** a proposal until the Student accepts.
- After the Student accepts an In person time, **Issue Call Slip** for that Appointment. It opens the ordinary Call Slip issuance, prefilled with the Student, the case, the Appointment and its start time, and the Counselor issues it.

**Student**

- Is notified "Your Counselor proposed a session time. Please choose one." and sees a **Proposed session** item in Student actions.
- On the respond page (`/portal/appointments/proposals/<id>`), sees the Counselor, the purpose and the times, and **accepts one** or **declines**. Accepting books the Appointment under the normal booking rules. If the time was taken meanwhile, the page says so and nothing is booked.
- Online sessions keep the existing E-Counseling consent before the session.

**Shortcuts on a pending next action** (Follow-up detail and the case's Next actions panel)

| Shortcut | Opens | Shown when |
|---|---|---|
| Message student | The reader's most recent existing Counseling conversation with the Student | Such a conversation exists |
| Issue Call Slip | Call Slip issuance prefilled with the Student, and the case when the reader may link it | The reader may issue Call Slips for the Student |
| Propose session | The propose page, carrying the task | The reader may propose for the task's case |

Each shortcut carries `return_to`, so the destination's back link returns to the task or case. When a proposal made from a task is accepted, or its session is recorded, the task shows **"Complete this follow-up?"** with a button that opens the reader's own completion form. Nothing is completed for them.

## Rules the implementation enforces

| Rule | Where |
|---|---|
| A proposal never reserves a slot. | `propose_session` only calls the read-only `check_offerable_interval`; no Appointment row exists until acceptance. Tested by listing the same time as still bookable for another Student. |
| Acceptance books only through the existing Appointment service. | `accept_proposal` calls `create_student_appointment` as the Student, with the proposal's Service, provider, delivery mode and start. Availability, overlaps, Fixed Slot and Group Session conflicts, Inventory prerequisite and the cancellation cutoff all apply. |
| Concurrent accepts create at most one Appointment. | The catalog gate, then the case row, then the proposal row are locked before booking. A second accept sees `ACCEPTED` (same option: returns the same result; other option: `409 session_proposal_closed`). `appointment` is a one-to-one column. Tested with real threads, including an accept racing another Student's booking of the same time. |
| One open proposal per case. | Partial unique constraint `ns_proposal_one_pending_per_case` plus the case lock. |
| Closed cases refuse proposals. | `proposer_authority` gives nobody authority on a closed case (`409 counseling_case_closed` for the owner). A pending proposal on a case closed later reads as expired and cannot be accepted. |
| D1 authority. | The case's primary Counselor, or the receiving Counselor of an **accepted, in-interval** case coverage. Both need `counseling.manage_assigned` and `appointments.view_self`. The proposer is the provider of the offered times. |
| D2 expiry. | `expires_at = min(earliest offered time, created + 7 days)`. Expiry is computed on read; no job runs. An expired row is stored as `EXPIRED` when the next proposal is made for the case. |
| D3 withdrawal. | The proposer or the case's primary Counselor, while the proposal is still pending, with `expected_version`. |
| D4 notifications are content-free. | `counseling.session_proposal.received` (Student) and `.decided` (Counselors), in-app only and excluded from lock-screen push. The text names no case, purpose, time or task. |
| A Call Slip is issued only after acceptance, and only by hand. | The tick stores `call_slip_requested` only. `can_issue_call_slip` turns on after acceptance for a scheduled, future In person Appointment with no active case Call Slip, and the Counselor issues through `POST /call-slips`. |
| Case Call Slips. | New optional `counseling_case_id` and `appointment_id` on `CallSlipCreateRequest`. Counselor-only, always a live issuance, never together with a Referral. The Appointment must be currently linked to the case, scheduled, In person and for the same Student; at most one non-voided case Call Slip per Appointment. The link lives in a new table, so the Call Slip table is untouched. The link is shown only to the case's primary Counselor. |
| Session recorded ends the linked Call Slip. | When a session for that Appointment is added to the case (`case_services._link`), the case Call Slip gets `interview_ended_at` = the session's end. Voided or already ended Call Slips are untouched. |
| Standalone and Referral Call Slips are unchanged. | They take the original code path; the new path is entered only with `counseling_case_id`. |
| No second conversation, no participant added. | Message student only reads `authorized_threads` for an existing COUNSELING thread where the reader is the Counselor. Tested: no thread exists before or after. |
| Follow-up confidentiality is unchanged. | Shortcuts are computed only for readers who may manage the task (`policy.authorized(..., manage=True)`) and carry identifiers only. The task title and description never reach the propose page, the Student, notifications or audit. |
| The Student sees only their own proposals and no case details. | `/me` endpoints filter by Student; the Student projection has no case, Call Slip or task fields. Another Student gets 404; staff endpoints refuse Students. |
| Audit carries no narrative. | `counseling.session_proposal.created/.withdrawn/.accepted/.declined` and `counseling.case.call_slip_linked`: identifiers and closed codes only. Acceptance also writes the existing `counseling.case.appointment_linked`. |

## Decisions

The owner approved building this in one package with the proposal's section 5 defaults.

| # | Decision |
|---|---|
| D1 | Only the case owner proposes; a covering Counselor may propose only while the coverage is accepted and in its interval. The office assistant cannot. |
| D2 | A proposal stays open until the earliest proposed time, and at most 7 days. |
| D3 | The Counselor can withdraw until the Student accepts. |
| D4 | The Student notification says only "Your Counselor proposed a session time. Please choose one." |
| D5 | "Complete this follow-up?" appears after acceptance or a recorded session. It is a prompt only. |

Interpretations made while building, where the proposal left room:

1. **"Also issue a Call Slip" records intent only.** The proposal says the Call Slip is issued after acceptance, and also that nothing is issued automatically. So acceptance turns on a prominent **Issue Call Slip** for that Appointment, and the Counselor issues it.
2. **Purpose is a closed list** (Follow-up session, Check-in, Continuing session). Free text could carry case narrative to the Student.
3. **One open proposal per case**, so the Student is never asked the same question twice.
4. **Proposing checks that each time is bookable now** and refuses one that isn't, naming it. It still reserves nothing; acceptance checks again under locks.
5. **A covering Counselor's proposal books the covering Counselor**, and the Appointment is still linked to the case.
6. **The linked Call Slip is marked "interview ended"** when the session for its Appointment is added to the case, as section 3.5 asks. This is the only lifecycle effect without its own click; it follows the Counselor's own recording or linking.
7. **Messages honours `return_to`** with a back link above the workspace, so Message student returns to the task.
8. **Proposal notifications are in-app only**, like case continuity reviews, because a push or email would reveal counseling activity.

## Backend

| File | Purpose |
|---|---|
| `be/compass/counseling/session_proposal_models.py` | `CounselingSessionProposal`, `CounselingSessionProposalOption`, `CounselingCaseCallSlip` |
| `be/compass/counseling/session_proposal_services.py` | Authority, context, slots, propose, withdraw, Student reads, accept, decline |
| `be/compass/counseling/session_proposal_api.py` | Nine operations and the staff and Student projections |
| `be/compass/counseling/case_call_slips.py` | Case Call Slip validation, link, and "interview ended" on session link |
| `be/compass/counseling/next_session_shortcuts.py` | Follow-up and case shortcuts, completion prompt |
| `be/compass/appointments/services.py` | Read-only `list_offerable_slots` and `check_offerable_interval`, sharing the booking rules |
| `be/compass/call_slips/services.py`, `api.py` | Optional case and Appointment on issuance; `counseling_case` and `appointment` on the operational response |
| `be/compass/counseling/case_api.py`, `case_services.py` | Case detail gains `session_proposals`, `can_propose_session`, `call_slips`, `message_thread_id`, `can_issue_call_slip`; `_link` ends linked Call Slips |
| `be/compass/guidance_followups/api.py`, `services.py` | `FollowUpDetail.shortcuts` |
| `be/compass/student_actions/` | `SESSION_PROPOSAL_RESPONSE` |
| `be/compass/notifications/policy.py`, `push_policy.py` | Two events, two target types (`SESSION_PROPOSAL`, `COUNSELING_CASE`) |
| `be/tests/test_ns1_session_proposals.py`, `test_ns1_session_proposal_concurrency.py` | 13 tests, registered in `BUNDLES` |

New operations, all tagged `counseling`:

| Operation | Method and path |
|---|---|
| `counselingGetSessionProposalContext` | `GET /counseling/session-proposals/context?case_id=` |
| `counselingListSessionProposalSlots` | `GET /counseling/session-proposals/slots?case_id=&delivery_mode=&date=` |
| `counselingProposeSession` | `POST /counseling/session-proposals` |
| `counselingGetSessionProposal` | `GET /counseling/session-proposals/{id}` |
| `counselingWithdrawSessionProposal` | `POST /counseling/session-proposals/{id}/withdraw` |
| `counselingListMySessionProposals` | `GET /counseling/session-proposals/me` |
| `counselingGetMySessionProposal` | `GET /counseling/session-proposals/me/{id}` |
| `counselingAcceptSessionProposal` | `POST /counseling/session-proposals/me/{id}/accept` |
| `counselingDeclineSessionProposal` | `POST /counseling/session-proposals/me/{id}/decline` |

Contract: 500 → 509 operations; nothing removed and no method or path changed. All schema changes are new schemas or new optional fields.

## Migration and deployment

- **One additive migration**, `counseling/0010_session_proposals`: three `CreateModel`s with their indexes and constraints inside. It does not alter, backfill or read an existing table.
- Registered in `be/compass/common/canonical_migrations.json` and pinned by SHA-256 in `be/deploy/staging/additive-migrations.json`. **If the file changes, re-pin its hash.**
- No new secret, keyring, setting, capability or synchronizer step. Students use `appointments.manage_self`; Counselors use their existing counseling, Appointment and Call Slip capabilities.
- The frontend relies on the new endpoints and fields, so deploy the backend first or together.

## Frontend

| Area | Files |
|---|---|
| Propose page `/portal/counseling/cases/<id>/propose-session` | `features/counseling/session-proposals/propose-session-page.tsx` |
| Session proposals panel and Withdraw | `case-session-proposals-panel.tsx`, wired into `case-overview-page.tsx` |
| Shortcuts | `next-action-shortcuts.tsx`, used by `case-next-actions-panel.tsx` and `guidance-followups/followups-detail.tsx` (with the completion prompt) |
| Student respond page `/portal/appointments/proposals/<id>` | `student-session-proposal-page.tsx` |
| Call Slip issuance prefill and return | `call-slips/call-slip-create-page.tsx`, `call-slip-form-fields.tsx` (`liveOnly`), `call-slip-detail-page.tsx` |
| Student actions, notifications, Messages back link | `student-actions-presentation.ts`, `notification-targets.ts`, `guidance-messages-workspace.tsx` |
| Copy and error mapping | `session-proposal-presentation.ts` (code-based; backend wording is never shown) |

States covered: loading, denied (Student or other Counselor), not found, stale (`session_proposal_changed`/`closed` reload), conflict (a named time taken, an open proposal), uncertain network results (no blind retry), and phone width.

## Verification

All runs were local on 14 November 2026. Backend tests used PostgreSQL database `test_compass_next_session` and Redis DB 15. The browser runs used a production test build (`NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1`, `next start` on 127.0.0.1:3199) with Chrome and Playwright WebKit.

| Check | Result |
|---|---|
| New backend tests (`test_ns1_session_proposals.py`, `test_ns1_session_proposal_concurrency.py`) | 13 passed |
| Affected backend files: canonical baseline, OpenAPI contract, staging deployment, notification cross-channel and push, Student actions, Call Slips (3 files), Follow-ups, counseling cases and concurrency, CW-2 (2), CW-3 coverage and transfers, CW-4 closure and integration, CW-6, Appointment slots and booking | 555 passed, 3 failed: all three were OpenAPI contract pins (the expected operation list, the Student-action kind count, and a contract re-exported mid-run). After updating the pins, the contract file and the NS-1 tests passed together (60 passed). Two later small changes (the context read and "closed case reads as expired") were covered by rerunning the NS-1 and contract tests, not this whole set. |
| `ruff check`, `ruff format --check`, `makemigrations --check`, `export_openapi --check` | clean / current |
| `backend_ci.py verify` | 237 test files bundled, each runs once |
| `pnpm validate` (generate, lint, typecheck, build) | passed; lint warnings only in earlier CW-4 test files |
| `pnpm test` | 1,316 passed, 0 failed (includes the new `next-session-proposals.test.mjs`) |
| New mocked suite `next-session-proposals.browser.mjs` | 11/11 in Chromium and WebKit |
| Affected mocked suites, each in Chromium and WebKit | guidance-followups 28/28, counseling-cases 62/62, counseling-closure 21/21, counseling-continuity 17/17, appointment-picker 26/26, call-slip-permissions 25/25, guidance-messages 42/42, guidance-messages-layout 18/18, student-actions 22/22 |
| Real Django + Next journey on a fresh `compass_next_session` database | 5/5 in Chromium (desktop) and 5/5 in WebKit (Student at 390 px) |
| Database oracle after the journey | One Appointment per Student, booked by the Student and linked to the case; proposal `ACCEPTED`; one live case Call Slip linked to that Appointment and created after acceptance; the next action still `PENDING`; no Messages thread created; notifications and audit carry no task text or case reference |

**Real journey.** The Counselor opened the case, used **Propose session** on the next action, offered an In person time with the Call Slip box ticked, and saw it waiting. The Student found it in Student actions, saw no case reference or task text, and accepted. The Counselor saw the accepted Appointment, issued the case Call Slip from the prefilled form and came back to the case, where Issue Call Slip was gone. The next action showed "Complete this follow-up?" and no Message student (no conversation existed). Another Counselor got 404 on the context read; the Student's own list had no case identifier and the staff read returned 403. The scripts are kept outside the repository.

**Repairs during verification.** `counseling-cases.browser.mjs` pins the case page's section headings; "Session proposals" was added to that list on purpose. Two new browser checks waited for `<option>` visibility, which Playwright never reports, and one looked for the row error inside the fieldset; the tests were corrected. A pending proposal on a since-closed case read as "Waiting for your answer" with no actions; it now reads as no longer open.

**Not covered.** The full backend suite and the full browser matrix are left to CI on the pull request. No upgrade rehearsal was run (the migration only creates tables). Nobody has used the screens with real office data.

## Known limitations and gaps

- Closing a case does not withdraw its pending proposal; it simply reads as no longer open. If the case is reopened before the proposal's expiry, the proposal can be accepted again.
- Cancelling or rescheduling the accepted Appointment does not void its case Call Slip; staff void it as usual.
- A covering Counselor follows the outcome through the notification and the task's completion prompt; they have no proposal list of their own because they cannot read the case.
- Message student opens the most recent Counseling conversation with that Student, which may belong to an older Appointment.
- A proposal does not stop the Student from booking another time on their own.
- Proposals have no Head or office view and no report dimension.

## Handoff

- CW-7 integrated verification should include: propose → accept → Call Slip → record session → Call Slip ended → complete the task, across the owner, a covering Counselor and the Student.
- If the office wants closure to require resolving pending proposals, add them to the CW-4 closure blockers.
