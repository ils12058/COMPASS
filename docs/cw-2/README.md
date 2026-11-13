# CW-2: Next actions and scheduling coherence

**Date:** 13 November 2026 · Philippine Time
**Branch:** `codex/counseling-cw2-next-actions`, stacked on `codex/counseling-cw1-case-foundation` ([#360](https://github.com/ils12058/COMPASS/pull/360), not merged when this branch was cut)
**Specification:** [COMPASS counseling workflow plan](../counseling-workflow-plan.md) — FUP-01 to FUP-03, UX-01, UX-02, UX-07, UX-08, the backend and migration decisions, and package CW-2
**Builds on:** [CW-1 record](../cw-1/README.md)
**Status:** Implemented and verified locally on 13 November 2026, with mocked and real local backends: affected backend suites, frontend unit tests, build, the affected browser suites in Chromium and WebKit, a real-backend journey in both engines, and an upgrade rehearsal. Hosted CI has not run, nothing is deployed, and nobody at the Guidance and Counseling Office has tried it. See [Verification](#verification).

## What a counselor can do now

- On a case, see the **Next appointment** and the **Next action** among the case facts, each from the backend. When there is none, the page says "No upcoming appointment is linked to this case." or "No pending next action in this case."
- **Add next action** from the case. The task belongs to the case and needs no session or Routine Interview. It is confidential to the case's primary Counselor.
- Give every new task a short **action title** (at most 120 characters). The Follow-ups list, the task page and the case use it as the task's name. Older tasks without a title show their category.
- From a completed or pending task, **Create next action**: the form opens with the same Student, case and source, and records the earlier task as its predecessor.
- When creating a task from a session or Routine Interview that is already in one of their Active cases, see that case pre-selected in the form, and remove it if it does not belong.
- Read a **Next actions** panel on the case: pending tasks first, then recently completed and cancelled ones, each linking to the task.
- **Link appointment** to a case from an **Appointments** panel, and **unlink** a wrong one with a reason. The removed link stays visible in that panel.
- When a linked Appointment's session has been recorded but is not in a case, see it offered on the case for one explicit **Add to this case**.
- Find **Follow-ups** under **More** instead of in the daily menu. It is still in destination search, and **My work** links to it.
- Move from My work or Follow-ups to a case or task and back, landing on the same filters and page they left.

Nothing here books an Appointment, closes or transfers a case, or delegates a task. Those are a separate booking package, CW-4 and CW-3.

## Rules the implementation enforces

| Rule | Where it is enforced |
|---|---|
| Only COUNSELING Follow-ups may carry a case. | `policy.classify(..., case_id=)` refuses any other category with `follow_up_invalid`. |
| A case is attached only by its owner, to an Active case, for the same Student. | `policy.require_case(..., manage=True, active=True, lock=True)` at creation and when listing eligible assignees. |
| A case-only task (no source) is confidential to the case's primary Counselor. | `classify` returns `COUNSELOR_CONFIDENTIAL`; `authorized`, `require_assignee` and the SQL `scope` all check `case.primary_counselor`. The whole page is authorized in SQL before the offset. |
| A case link never widens access to a sourced task. | A task with an Encounter or Routine Interview source is authorized by its source only. `visible_case` shows the case only to its owner. Tested with a case and a source owned by different Counselors. |
| Case-only tasks are not recovered or delegated. | `recovery.recoverable_queryset` excludes rows with a case. Delegation belongs to CW-3. |
| The action title is protected text. | Encrypted with the existing Follow-up keyring as its own `title` section; it has its own envelope. It is returned only on authorized Follow-up reads and the case overview. It never appears in My work, notifications, push, email, the Follow-up report, Head or office workload views, audit metadata or logs. |
| A predecessor must be readable and match. | The creator must be authorized for the predecessor, and the Student and case must match. Several successors are allowed. Completing a task never closes a case or creates an Appointment. |
| An Appointment is in at most one case at a time. | Partial unique constraint `cw_case_appointment_one_current`, plus row locks. Tested with two cases linking one Appointment concurrently. |
| Only the case's own scheduled Counseling Appointments can be linked. | Eligibility: Counseling Service, the case's Student, provider equal to the primary Counselor, status `SCHEDULED`. |
| Linking never changes the Appointment. | Link rows only; the Appointment record, provider and status are untouched. Unlink requires a closed reason and keeps the row. |
| Next appointment is the earliest linked `SCHEDULED` Appointment that starts after now. | `case_appointment_services`. Cancelled, rescheduled away, no-show and completed Appointments never count. Tested across every status. |
| Next action is the earliest-due pending task the reader may see. | `case_next_actions`. Its title, due date and responsible person come from that authorized row. |
| Stale changes fail clearly. | Appointment link and unlink take `expected_version` and bump the case version; a mismatch is `409 counseling_case_changed`. The title uses the task's existing version check. |
| Nothing is guessed from the same Student. | Every value on the overview comes from an explicit link: case sessions, case Appointments, case tasks. |

## Decisions

D1 to D7 come from the CW-2 brief and were applied as written, except where noted.

1. **D1 Action title.** Optional in the API so older clients and rows keep working; required by the create form. Missing titles fall back to the category label (`followupActionLabel`).
2. **D2 Case relationship.** Nullable `GuidanceFollowUp.case`. Case-only COUNSELING tasks are new and confidential to the case owner. The create form pre-selects a case only when the source is explicitly linked to exactly one of the creator's Active cases (`workspace._source_case`); with zero or several it selects nothing.
3. **D3 Predecessor.** Nullable `GuidanceFollowUp.predecessor`. The "Create next action" link carries only `predecessor_id` (and `return_to`); the form reads the Student, case and source from an authorized read of the predecessor instead of copying them into the URL.
4. **D4 Appointments in a case.** `CounselingCaseAppointment`, mirroring `CounselingCaseSession`. Opening a case from a scheduled Appointment links it in the same transaction. Existing cases are not backfilled. Link provenance stays on the link rows; no `CounselingCaseEventKind` was added. Two audit actions were added: `counseling.case.appointment_linked` and `.appointment_unlinked` (identifiers and codes only).
5. **D5 No "Schedule session".** Staff-side booking does not exist. The case offers **Link appointment** instead. Staff booking stays an open gap.
6. **D6 Case overview.** Page-level commands are Record session and Add next action (at most three, per `fe/AGENTS.md`). Add recorded session moved into the Sessions panel header, and Link appointment is in the Appointments panel header.
7. **D7 Navigation.** Follow-ups moved from the Counselor's daily list to the top of More; other roles are unchanged. Return navigation uses a shared `withWorkflowReturn` helper (`fe/src/features/portal/workflow-navigation.ts`) that accepts only internal portal paths.

## Backend

| File | Purpose |
|---|---|
| `be/compass/counseling/case_models.py` | `CounselingCaseAppointment`, `CounselingCaseAppointmentRemovalReason` |
| `be/compass/counseling/case_appointment_services.py` | Appointment candidates, link, unlink, next appointment, sessions from linked Appointments |
| `be/compass/counseling/case_next_actions.py` | Next action and the Next actions panel projection |
| `be/compass/counseling/case_services.py`, `case_api.py` | Overview fields, opening from an Appointment links it, three new operations |
| `be/compass/guidance_followups/models.py` | `case`, `predecessor`, `title_ciphertext`, index `fup_case_pending_idx` |
| `be/compass/guidance_followups/policy.py`, `services.py`, `api.py`, `workspace.py`, `content.py`, `recovery.py` | Case-only authorization, title section, predecessor rules, source-case offer, recovery exclusion |
| `be/compass/guidance_followups/management/commands/rotate_guidance_followup_encryption.py` | Rotates the new `title` section with the other sections |
| `be/tests/test_cw2_next_actions.py`, `test_cw2_case_appointments.py` | 22 tests, registered in `BUNDLES` in `.github/scripts/backend_ci.py` |

New operations:

| Operation | Method and path |
|---|---|
| `counselingListCaseAppointmentCandidates` | `GET /counseling/cases/{case_id}/appointment-candidates` |
| `counselingLinkCaseAppointment` | `POST /counseling/cases/{case_id}/appointments` |
| `counselingUnlinkCaseAppointment` | `POST /counseling/cases/{case_id}/appointments/{appointment_id}/unlink` |

Changed schemas: `FollowUpCreate` and `FollowUpUpdate` accept an optional `title`; `FollowUpCreate` accepts optional `case_id` and `predecessor_id`; `FollowUpSummary` gains `title` and `case`; `FollowUpDetail` gains `predecessor_id` and `can_create_next_action`; the Follow-up source context gains `case`; `CounselingCaseDetailResponse` gains `next_appointment`, `next_action`, `next_actions`, `appointments`, `unlinked_appointment_sessions`, `can_add_next_action` and `can_link_appointments`. The list accepts a `case_id` filter that never widens authority. Comparing the old and new contract by operation and schema: 465 → 468 operations, nothing removed, no method or path changed (`test_cw2_contract_preserves_optional_legacy_fields_and_exposes_authorized_case_facts` keeps this).

## Migration and deployment

- **Two additive migrations:** `guidance_followups/0002_next_actions` (three nullable `AddField`s without defaults and one `AddIndex`, depending on `counseling/0003`) and `counseling/0004_case_appointments` (one `CreateModel` with its index and constraints inside). Neither alters, backfills or reads an existing table.
- **Routine deployment path:** both pass `database_preflight.validate_operations`. Both are registered in `be/compass/common/canonical_migrations.json` and pinned by SHA-256 in `be/deploy/staging/additive-migrations.json`. **If either file changes, re-pin its hash.**
- **No new secret, keyring, setting, capability or synchronizer step.** The title uses the existing `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS`.
- No deployment, reset, or change to any shared database was made.

## Frontend

| Area | Change |
|---|---|
| Case overview (`case-overview-page.tsx`) | Next appointment and Next action facts; Next actions panel (`case-next-actions-panel.tsx`); Appointments panel with link and unlink dialogs (`case-appointments-panel.tsx`, `case-appointment-dialogs.tsx`); offers for sessions from linked Appointments |
| Follow-ups list | Title (or category) is the row's primary label; on narrow screens the action and deadline come before secondary columns; case filter and case link |
| Follow-up create and detail | Action title field; case shown and removable; predecessor; "Create next action"; "Back to case" and return to the originating list |
| My work | Link to the complete Follow-ups workspace; task rows keep their generic label |
| Navigation | Counselor Follow-ups under More; `f2-navigation-expected.json` updated on purpose |
| Appointment, Encounter and Routine Interview detail | Return links preserved through `withWorkflowReturn` |

## Verification

All runs are local. Nothing here is hosted CI. Backend commands ran from `be/` with `POSTGRES_DB=compass_cw2` and Redis databases 10 to 14. Browser suites ran against `next dev` serving this worktree on port 3109, with installed Chrome (`COMPASS_UI_BROWSER_CHANNEL=chrome`) and Playwright WebKit. Commands and full output are kept outside the repository in `Claude outputs/cw-2/evidence/`.

| Check | Outcome |
|---|---|
| `uv run pytest tests/test_cw2_next_actions.py tests/test_cw2_case_appointments.py tests/test_canonical_baseline.py tests/test_openapi_contract.py` | 95 passed |
| Follow-ups, work queue, guidance operations, overview, counseling (8 files), routine interviews, Faculty referral journey, lock scope and audit (17 files) | 295 passed |
| `uv run pytest tests/test_staging_deployment.py` | 68 passed |
| `python3 -m unittest discover -s .github/scripts` | OK |
| `uv run ruff check .`, `uv run ruff format --check .`, `makemigrations --check --dry-run` | clean |
| Contract comparison by operation and schema | 465 → 468 operations, none removed |
| `pnpm validate` (api:generate, lint, typecheck, build) | passed |
| `pnpm test` | 1,255 passed, 0 failed |
| `pnpm lint` | clean |
| `tests/counseling-cases.browser.mjs` (extended for CW-2) | 62 of 62 checks in Chromium and WebKit |
| `tests/guidance-followups.browser.mjs` | 28 of 28 in Chromium and WebKit |
| `tests/counseling-encounter-consistency.browser.mjs`, including an active E-Counseling call while a case and a Follow-up are opened | 14 of 14 in Chromium and WebKit |
| `tests/f2-navigation.browser.mjs` | 48 of 48 in Chromium and WebKit |
| `tests/work-queue.browser.mjs` | 19 of 19 in Chromium and WebKit |
| `tests/portal-navigation-attention.browser.mjs` | 3 of 3 in Chromium and WebKit |
| `tests/case-coverage.browser.mjs` | 41 of 41 in Chromium and WebKit |
| `tests/user-copy.browser.mjs` | 42 checks passed, none failed, in Chromium and WebKit |
| `tests/counseling-context-confidentiality.browser.mjs` | 20 checks passed, none failed, in Chromium and WebKit |
| Real-backend journey (below), Chromium and WebKit | 8 of 8 steps in each engine; database check passed |
| Upgrade rehearsal (below) | passed |

**Real-backend journey.** A new scratch database `compass_cw2_browser_20261113_a`, synthetic actors and ephemeral keyrings; Django on port 8092 behind the Next dev server; no business endpoint mocked. In each engine (WebKit at phone width) the Counselor opened a case from a scheduled Appointment and saw it as the next appointment; added a case-only next action with a title, edited the title, completed it and created a successor, then cancelled that; linked and unlinked an Appointment, lost a race to a competing link and saw the latest case; recorded the linked Appointment's session and added it from the case's offer; created a task from a session in the case and saw the case pre-selected; and moved between the filtered Follow-ups list, My work, the case and the task, returning to the same filters. The Head, another Counselor, the office assistant, Faculty, the Student and IT Admin were each denied the task and the case, and the title never appeared in My work, the report or audit metadata. A database check then confirmed the encrypted title, the predecessor, the two retained removed Appointment links and the two explicit session links. Scripts: `Claude outputs/cw-2/real_backend.py` and `real_backend.browser.mjs`.

**Upgrade rehearsal.** On a new scratch database, every app was migrated to its leaf except Counseling (stopped at `0003`) and Guidance Follow-ups (stopped at `0001`). Legacy rows were loaded: 18 Follow-ups of every kind with 48 events and 30 receipts, a CW-1 case with sessions, and Appointments. The pending plan was only `counseling.0004_case_appointments` and `guidance_followups.0002_next_actions`, and the routine preflight accepted it. After `migrate`, the original columns of all 115 existing tables were byte-identical (same SHA-256 before and after), the new task fields were all null, the Appointment link table was empty, both migration pins matched, and `manage.py check` and `makemigrations --check --dry-run` were clean. Script: `Claude outputs/cw-2/migration_rehearsal.py`.

**Stale tests repaired.** None hid a defect.

- `guidance-followups.test.mjs`: "Create next follow-up" used to copy the Student or source into the link. Under D3 the link carries only the predecessor, and the form reads the rest from an authorized read. The test now checks that nothing else, including the title, enters the URL.
- `guidance-followups.browser.mjs`: fixtures gained `title`, `case`, `predecessor_id` and `can_create_next_action`, and rows are now named by title.
- `work-queue.test.mjs`: My work now renders a link to Follow-ups, which needs the router and the unsaved-changes provider.
- `f2-navigation.test.mjs` and `support/f2-navigation-expected.json`: the Counselor's Follow-ups moved to More (D7). A new test checks that only that entry moved and that Head and GOA are unchanged.
- `counseling-encounter-consistency.browser.mjs`: the case fixture gained next actions; the live-call check now also opens a Follow-up from the case and confirms the call is not left, rejoined or recreated.
- `counseling-cases.test.mjs`, `counseling-cases.browser.mjs`, `support/counseling-cases-fixtures.mjs`: extended for CW-2.

**Not covered.** The full backend suite and the full browser matrix are left to CI on the pull request. Nobody has used the screens with real office data.

## Known limitations and gaps

- **Staff-side booking does not exist.** A Counselor cannot schedule a session from a case; the Student still books. Building it (slot rules, reservations, Student notification) is a separate package.
- A case-only task can be assigned only to the case's primary Counselor. Until CW-3, it cannot be delegated or recovered, and it follows the case owner, not a transfer.
- Existing cases opened from an Appointment before CW-2 do not have that Appointment linked; the Counselor can link it by hand.
- The Follow-up report counts case-only tasks with the other COUNSELING tasks by category; it has no case dimension.
- The Appointments panel lists every link, current and removed, without paging.

## Handoff to CW-3

- **Case-task ownership on transfer.** Case-only tasks are authorized through `case.primary_counselor`. When a case changes hands, decide whether pending case tasks move with it, and change `require_case`, `scope` and `require_assignee` together.
- **Appointment review on transfer.** Linked Appointments keep their original provider. A transfer needs a rule for scheduled Appointments whose provider is no longer the case owner (they stop counting as eligible links, but existing links remain).
- **Delegation.** Recovery excludes case-only tasks on purpose. Delegation and coverage for them belong to CW-3.
- `CounselingCaseEventKind` is unchanged. A new kind without an Encounter needs the `counseling_case_event_session_named` constraint changed, which is not a routine-path operation.
