# BACKLOG-ACT-2 implementation report

## A. Baseline and evidence audit (before implementation)

- Fetched `origin/staging`: `8327862510ec8e45a5a008d21133b9b68997776d` (2026-10-16, Asia/Manila).
- Branch: `feat/backlog-domain-rich-my-activity`.
- Worktree: `/Users/reynantlntno/Projects/COMPASS-BACKLOG-MY-ACTIVITY`.
- ADR-011/013/073: AuditEvent is append-only authoritative evidence; synchronous closed-world
  presenters, server-side target validation and bounded chronological pages. No activity writes.
- Read the seven domains' actual services, models and API capability gates. Account/security
  presenters currently share an exclusion-based registry; replace that implicit coupling.

## B. Event decision matrix

All admitted domain events require SUCCESS + USER with the real actor retained. IDs are checked
against typed live source rows; metadata never establishes ownership. Every `student` relationship
below is a canonical FK, never a name snapshot. Student and staff branches have different static
copy. Staff branches always require self actor and current read authority; responsibility alone
never selects another person's event. Head means the Counselor designation, not a new role.

| Action constant | Target | Producer in domain services | Actual actor / affected relationship | Decision and read authorization | Title; description policy |
|---|---|---|---|---|---|
| APPOINTMENT_CREATED | appointments.appointment | create_student_appointment | Student; Appointment.student | Self Student only, appointments.view_self + owner | Appointment booked; You booked an appointment. |
| APPOINTMENT_CANCELLED | appointments.appointment | cancel_appointment | Student or managing staff; student FK | Both: owner/view_self; self staff with current managed scope | Appointment cancelled; You cancelled your appointment / Your appointment was cancelled / You cancelled an appointment. |
| APPOINTMENT_RESCHEDULED | appointments.appointment | reschedule_appointment | Student or managing staff; student FK | Both, same read boundaries | Appointment rescheduled; You rescheduled your appointment / Your appointment was rescheduled / You rescheduled an appointment. |
| APPOINTMENT_REASSIGNED | appointments.appointment | reassign_appointment | Managing staff; student FK | Both, same read boundaries | Appointment reassigned; Your appointment was reassigned / You reassigned an appointment. |
| APPOINTMENT_COMPLETED | appointments.appointment | complete_appointment | Managing staff; student FK | Both, same read boundaries | Appointment completed; Your appointment was marked as completed / You marked an appointment as completed. |
| APPOINTMENT_NO_SHOW | appointments.appointment | mark_appointment_no_show | Managing staff; student FK | Both, same read boundaries | Appointment marked as no-show; Your appointment was marked as a no-show / You marked an appointment as a no-show. |
| INVENTORY_CREATED | inventory.studentinventory | ensure_current_inventory | Student; StudentInventory.student | Self Student + owner + inventory.view_self | Individual Inventory started; You started your Individual Inventory. |
| INVENTORY_SUBMITTED | inventory.studentinventory | submit_current_inventory | Student; student FK | Self Student + owner + inventory.view_self | Individual Inventory submitted; You submitted your Individual Inventory. |
| INVENTORY_RESUBMITTED | inventory.studentinventory | submit_current_inventory (resubmission) | Student; student FK | Self Student + owner + inventory.view_self | Individual Inventory resubmitted; You resubmitted your Individual Inventory. |
| INVENTORY_REOPENED | inventory.studentinventory | reopen_inventory_for_correction | Counselor; student FK | Both: owner/view_self; self Counselor/inventory.view with existing scoped history access | Individual Inventory returned for correction; Your Individual Inventory was returned for correction / You returned an Individual Inventory for correction. |
| GOOD_MORAL_REQUEST_CREATED | goodmoral.request | create_my_current_student, create_my_graduate | Student; GoodMoralRequest.student | Self Student + owner + good_moral.view_self | Good Moral certificate requested; You requested a Good Moral certificate. |
| GOOD_MORAL_REQUEST_UPDATED | goodmoral.request | update_request | Counselor or GSS; student FK | Both: owner/view_self; self operational role/good_moral.view (domain is institution-wide) | Good Moral request updated; Your Good Moral request was updated / You updated a Good Moral request. |
| GOOD_MORAL_PREPARED | goodmoral.request | prepare_request | Counselor or GSS; student FK | Both, same read boundaries | Good Moral certificate prepared; Your Good Moral certificate was prepared / You prepared a Good Moral certificate. |
| GOOD_MORAL_RETURNED_TO_PREPARATION | goodmoral.request | update_request (ready request changed) | Counselor or GSS; student FK | Both, same read boundaries | Good Moral request returned for preparation; Your Good Moral request was returned for preparation / You returned a Good Moral request for preparation. |
| GOOD_MORAL_REQUEST_CANCELLED | goodmoral.request | cancel_request | Student or Counselor; student FK | Both: owner/view_self; self Counselor/good_moral.view | Good Moral request cancelled; You cancelled your Good Moral request / Your Good Moral request was cancelled / You cancelled a Good Moral request. |
| GOOD_MORAL_ISSUED | goodmoral.request | issue_request | Counselor; student FK | Both: owner/view_self; self Counselor/good_moral.view | Good Moral certificate issued; Your Good Moral certificate was issued / You issued a Good Moral certificate. |
| EXIT_INTERVIEW_CREATED | exitinterviews.exitinterview | ensure_my_current | Student; ExitInterview.student | Self Student + owner + exit_interviews.view_self | Exit Interview started; You started your Exit Interview. |
| EXIT_INTERVIEW_SUBMITTED | exitinterviews.exitinterview | submit_my_current, submit_mine | Student; student FK | Self Student + owner + exit_interviews.view_self | Exit Interview submitted; You submitted your Exit Interview. |
| EXIT_INTERVIEW_RESUBMITTED | exitinterviews.exitinterview | submit_my_current, submit_mine | Student; student FK | Self Student + owner + exit_interviews.view_self | Exit Interview resubmitted; You resubmitted your Exit Interview. |
| EXIT_INTERVIEW_REOPENED | exitinterviews.exitinterview | reopen_for_correction | Head-authorized actor; student FK | Both: owner/view_self; self Counselor/exit_interviews.view (existing list/history authority) | Exit Interview returned for correction; Your Exit Interview was returned for correction / You returned an Exit Interview for correction. |
| EXIT_INTERVIEW_OPPORTUNITY_OPENED | exitinterviews.exitinterviewopportunity | opportunity services open_opportunity | Authorized opportunity manager; separate student FK | Exclude: separate admission resource; defer timing/visibility design | None |
| EXIT_INTERVIEW_OPPORTUNITY_REVOKED | exitinterviews.exitinterviewopportunity | opportunity services revoke_opportunity | Authorized opportunity manager; separate student FK | Exclude: admission lifecycle, not a submitted interview | None |
| EXIT_INTERVIEW_OPPORTUNITY_COMPLETED | exitinterviews.exitinterviewopportunity | _complete_opportunity | Student submit context; separate student FK | Exclude: derived completion duplicates submission; not interview evaluation completion | None |
| ROUTINE_INTERVIEW_CREATED | routine.interview | ensure_for_appointment, create_direct | Student or assigned Counselor; RoutineInterview.student/counselor | Self Student only + owner + routine_interviews.view_self; staff creation deferred | Routine Interview intake started; You started your Routine Interview intake. |
| ROUTINE_INTERVIEW_INTAKE_SUBMITTED | routine.interview | submit_my_intake | Student; student FK | Self Student only + owner + routine_interviews.view_self | Routine Interview intake submitted; You submitted your Routine Interview intake. |
| ROUTINE_INTERVIEW_ENCOUNTER_LINKED | routine.interview | _link_encounter | Counselor; student/counselor FKs | Exclude due to professional confidentiality; linking is not completion | None |
| ROUTINE_INTERVIEW_EVALUATION_FINALIZED | routine.interview | finalize_assigned_evaluation | Assigned Counselor; student/counselor FKs | Exclude due to professional evaluation existence/timing | None |
| REFERRAL_CREATED | referrals.referral | create_referral | Counselor or GSS; Referral.student | Professional/operational self only: referrals.view + operational role + existing college scope; never Student | Referral recorded; You recorded a referral. |
| REFERRAL_STATUS_UPDATED | referrals.referral | update_status_note | Counselor or GSS; student FK | Same professional/operational self only; no notes shown | Referral status updated; You updated a referral status note. |
| REFERRAL_ACTION_RECORDED | referrals.referralaction | _create_action_locked (record_action/ensure_call_slip_action) | Counselor or GSS; ReferralAction.referral.student | Same self only; child must join scoped canonical parent | Referral action recorded; You recorded an operational referral action. |
| REFERRAL_VOIDED | referrals.referral | void_referral | Counselor or GSS; student FK | Same professional/operational self only | Referral voided; You voided a referral. |
| CALL_SLIP_CREATED | callslips.callslip | _create_new_call_slip_locked | Counselor or GSS; CallSlip.student | Both: owner/call_slips.view_self; self operational role/call_slips.view + existing college scope | Call Slip recorded; A Call Slip was recorded for you / You recorded a Call Slip. Recording copy covers live and historical entries. |
| CALL_SLIP_VOIDED | callslips.callslip | void_call_slip | Counselor or GSS; student FK | Both, same read boundaries | Call Slip voided; Your Call Slip was voided / You voided a Call Slip. |
| CALL_SLIP_INTERVIEW_ENDED | callslips.callslip | record_interview_ended | Counselor or GSS; student FK | Exclude due to interview existence/timing confidentiality | None |

Appointment staff access reuses `scope_managed_appointments`, preserving relationship-only
Counseling access, Head provider-only management, and GSS delegated college scope. Inventory
reuses `_scoped_students`, which is also used by scoped history; reopened drafts remain eligible
history without exposing answers. Referrals/Call Slips reuse their `_scope_queryset` read rules.
Those operational APIs do not grant Student referral access. Call Slips explicitly have Student
list/detail APIs. Good Moral staff read access is institution-wide under its operational role and
view capability; this feature does not broaden that policy. Exit Interview summary listing is
capability-gated; the new staff branch is additionally limited to Counselors. IT Admin and DPO
remain account-only even with accidental professional capability overrides.

## C. Implementation changes

- `be/compass/activity/domains.py`: 28 explicit action policies across the seven audited domains;
  separate Student self, affected Student and staff self relationships and descriptions.
- `be/compass/activity/projections.py`: OR the eligible domain selection into My Activity only;
  use the existing single AuditEvent query, page bounds, `occurred_at DESC, id DESC`, and lookahead.
  Source authorization is inside SQL before OFFSET/LIMIT. OR predicates do not duplicate events.
- `be/compass/activity/presenters.py`: Security Activity now names every permitted action explicitly.
  Its exact existing action set and copy are preserved; AUTH_SESSION_CREATED remains absent.
- `be/docs/decisions/ADR-013-user-activity-projections.md`: record the explicit domain refinement.
- `fe/src/features/account/activity/activity-page.tsx`: empty copy is "No activity is available yet."
  The existing layout, tabs, time formatting, accessibility, query/error handling and paging remain.
- Tests: `be/tests/test_domain_activity.py`, expanded `fe/tests/activity-retrieval.test.mjs`, and
  `fe/tests/domain-activity.browser.mjs`. Generated client regenerated locally, without tracked changes.

No schema/OpenAPI change, migration, audit mutation, new producer/table, domain service edit,
record URL, notification, role/capability grant, retention or CI change. Student target subqueries
return canonical primary keys from current owned records; staff subqueries return currently
readable typed sources. ReferralAction joins Referral before eligibility. Only IDs enter these
subqueries: no answers, notes or encrypted source content are selected/decrypted. AuditEvent SELECT
loads only event ID/action/actor ID/time and materializes at most 51 rows. Source histories and
caseloads are never copied into Python. The existing domain helpers resolve organizational scope;
query count does not grow with the event count or page size (tested at 1/20/50 items). Existing
OFFSET pagination limits still apply; this does not introduce cursor/snapshot semantics.

## D. Security verification

The 54 new backend cases cover all 28 policies, all six account perspectives (Head is a
Counselor designation), cross-user isolation, self-versus-affected wording, source/child validation,
wrong domains/types/IDs, orphan/deleted sources, spoofed metadata, SUCCESS-only USER provenance,
revoked read authority, active college/campus scope, responsibility/provider/supervision changes,
professional exclusions, and IT/DPO denial even under explicit professional capability overrides.

A real `reopen_inventory_for_correction` service call verifies correction-target confidentiality
and retained actual Counselor provenance in a synthetic Inventory sequence; the initial creation,
submission, resubmission and unrelated issuance use synthetic audit fixtures. The unrelated
applicant sees its own issuance effect only, never another Student's Inventory. This fixture
explicitly does not claim a live end-to-end domain workflow or institutional approval.

A 64-visible/63-hidden tied-time history spans four pages without gaps, duplicates or misleading
has_next; Student reads use at most five queries regardless of page. A self/affected overlap is
returned once. API tests check exactly the five public fields, absence of source/actor/request IDs
and secrets, ignored impersonation selectors, unchanged evidence, and append-only rejection.
Security regression cases preserve login/logout and session-creation exclusion. Existing supervised,
Privacy export and Platform tests are exercised separately from the new domain policies.

## E. Validation

Environment: existing Python 3.13 backend virtualenv; PostgreSQL test databases dedicated to this
assignment (`test_compass_act2_validation` and baseline-only `test_compass_act2_baseline`); installed
frontend dependencies from the frozen lockfile/offline store. Local Next server at port 3109 with
synthetic API fixtures only. No institutional data or remote service was modified.

Commands run from the corresponding worktree `be/` or `fe/`:

```sh
# Existing backend Python is /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python
POSTGRES_DB=compass_act2_validation python -m pytest --reuse-db -q \
  tests/test_domain_activity.py tests/test_activity.py tests/test_activity_retrieval.py \
  tests/test_privacy_activity.py tests/test_platform_activity.py tests/test_audit.py
# 187 passed, 2 inherited audit-test failures; see backend-tests.txt.

POSTGRES_DB=compass_act2_validation python -m pytest --reuse-db -q \
  tests/test_appointment_management_scope.py tests/test_inventory_correction_targets.py \
  tests/test_exit_interview_correction_targets.py
# 66 passed; see BACKLOG-ACT-2-domain-regressions.txt.

ruff check compass/activity tests/test_domain_activity.py
ruff format --check compass/activity/domains.py tests/test_domain_activity.py
pnpm api:generate
pnpm typecheck
pnpm exec eslint src/features/account/activity/activity-page.tsx \
  tests/activity-retrieval.test.mjs tests/domain-activity.browser.mjs
node --import ./tests/support/register-tsx.mjs --test tests/activity-retrieval.test.mjs
# 17 passed.
COMPASS_UI_BASE_URL=http://localhost:3109 node tests/domain-activity.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3109 COMPASS_UI_BROWSER=webkit node tests/domain-activity.browser.mjs
# 10/10 per engine: all account perspectives, account-only/mixed/empty/long history,
# pagination, keyboard, loading, failed backend and Retry, institutional time and mobile layout.
COMPASS_UI_BASE_URL=http://localhost:3109 node tests/security-activity.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3109 COMPASS_UI_BROWSER=webkit node tests/security-activity.browser.mjs
# 2/2 per engine: login/logout, tabs, paging and session-creation regression.
git diff --check
```

Screenshots visually reviewed at 320px and desktop width; ordered activity remains readable without
horizontal overflow. The structured browser evidence records all 24 final checks. Initial new-test
fixture failures (form-family/destination constants and a dev-remount retry race) were corrected;
all affected feature tests passed afterward. These were test-fixture issues, not product regressions.

Inherited failures (not changed):

- `test_audit.py::test_success_audit_event_rolls_back_with_surrounding_transaction`
- `test_audit.py::test_policy_sync_rolls_back_if_audit_recording_fails`

Both expect an initially empty AuditEvent table despite the autouse institutional-form bootstrap
record. They reproduce on untouched `origin/staging` at the baseline SHA using a separate detached
temporary checkout and test database. See `BACKLOG-ACT-2-inherited-baseline.txt`. The rest of the audit
suite, including append-only protections, passes. No new feature test failure remains.

Not run: repository-wide backend/frontend suites, full frontend production build, CI stabilization,
live user accounts, load benchmarks against institutional histories, merge or deployment. This is a
focused projection change with no contract or build-configuration change; typecheck, focused lint,
component tests, browser checks and relevant domain regressions validate the affected behavior.
The source existence requirement intentionally hides history after source deletion or lost access;
My Activity is a curated current-authority feed, not a complete audit export.

Overall backend validation: **253 passed, 2 confirmed inherited failures** across the two focused
runs; all 54 new domain cases passed. Frontend: **17 component cases and 24 browser checks passed**;
typecheck, generation, focused ESLint/Ruff, formatting check and diff whitespace checks passed.

## F. Deferred scope

Routine professional creation, encounter linking/evaluation; Exit opportunity lifecycle; Call Slip
interview completion; Counseling/assessment/media events; other optional domains. No new audit
producer, lifecycle change, retention change, migration, notification or record link is planned.
