# CW-4: Case closure and reopening

**Date:** 13 November 2026 · Philippine Time  
**Branch:** `codex/counseling-cw4-closure`, stacked on `codex/counseling-cw3c-coverage` ([#365](https://github.com/ils12058/COMPASS/pull/365), open when this branch was cut)  
**Specification:** [Counseling workflow plan](../counseling-workflow-plan.md), CLOSE-01 to CLOSE-07, HAND-05, FUP-03, APT-01, UX-01/04/05, and the owner's CW-4 implementation brief and decisions D1 to D8.  
**Builds on:** [CW-1](../cw-1/README.md), [CW-2](../cw-2/README.md), and [CW-3](../cw-3/README.md).  
**Status:** Implemented and verified locally: backend, canonical contract, frontend validation and unit tests, the mocked browser matrix in Chromium and WebKit, real Django + Next journeys in both engines with a database oracle, and the upgrade rehearsal. This stacked feature branch has no hosted CI run; nothing is merged or deployed.

## What staff can do

The current eligible primary Counselor can deliberately close one counseling episode, after reviewing all its outstanding work. The Head uses the same owner rule on her own cases. Head designation gives no closure or case-read authority over another Counselor's cases.

The review identifies pending transfers, pending/accepted coverage, delegated work still out, future scheduled linked Appointments, and pending case tasks. Each item links to its own workflow. Closure never completes, cancels, revokes, reassigns or unlinks any of those records. A pending task may remain only after an explicit administrative-action choice, with an eligible named assignee and a due date. Otherwise it must be completed or cancelled through Follow-ups first.

A Closed case retains its sessions, links, tasks, continuity, immutable handoffs and chronology. Its owner sees the closure date, responsible Counselor, reason, outcome and protected optional note. The workspace offers Reopen case instead of case-management commands. Existing tasks remain manageable through their normal workflow; even an unmarked task on an inconsistent Closed case can still be completed or cancelled.

The eligible current owner can reopen the same episode with a bounded reason. The screen says: **“If this is a different concern, open a new case instead.”** A different concern uses a new case for the same Student. Reopening preserves the earlier closure cycle.

If the closed case's owner is unavailable, eligible office staff can prepare a **REOPEN transfer** with `OWNER_UNAVAILABLE`. Independent Head authorization and explicit receiver acceptance apply. Acceptance changes responsibility and reopens the case together; retained administrative tasks keep their explicit owners. Office and Head review projections contain routing metadata, never closure notes, outcomes or task narrative. An office-prepared request to the sole Head as receiver remains blocked when no independent authorizer exists.

Students and Faculty receive no new case information. Faculty administrative Referral progress remains independent of the case lifecycle. My cases offers Active, Closed and All, with Active as its default; closed list rows show the date and reason without a success badge.

## Rules enforced

| Rule | Enforcement |
|---|---|
| Only the current active COUNSELOR with `counseling.manage_assigned` closes/reopens. | Owner checks under case, User and authority locks; the Head has no bypass. Other audiences and guessed IDs are denied. |
| A blocked close changes nothing. | `409 counseling_case_close_blocked`, with `error.details.blocking_item_kinds`; all blockers are evaluated inside the transaction. |
| Every pending-work kind is reviewed. | Live review-window checks, derived coverage states, delegated-task return reconciliation, future scheduled current Appointment links, and every pending case task. |
| Administrative retention is deliberate. | `administrative_action=true`, explicit assignee, due date, case version and task version. Initial designation/reassignment uses existing assignee rules; it does not change the COUNSELING category or confidentiality. |
| Retained tasks do not gain case/source access. | A marked case-only task remains readable/manageable by its eligible explicit assignee after a REOPEN transfer, independently of case ownership. Source-linked tasks retain their existing source ACL. `visible_case` still requires the case owner. |
| New case work requires Active. | Session/Appointment link and unlink, case session recording, task creation, ordinary transfer and coverage remain refused while Closed. |
| One immutable closure per cycle. | New `CounselingCaseClosure`, a single unreopened-cycle constraint and model/service guards. Only reopening attribution is subsequently filled. Earlier closures and reopenings cannot be overwritten/deleted. |
| Reasons and outcomes are separate. | Five closure reason codes and four outcome codes. Only planned support concluded plus goals met permits “Support concluded — goals met”; no combination is “Resolved” or “Successful.” |
| Contact attempts require a note. | `CONTACT_NOT_REESTABLISHED` requires at least 20 trimmed characters, at most 4,000 plain-text characters; no invented attempt count. |
| The note stays confidential. | Existing Handoff keyring, distinct schema-versioned row-bound envelope, fenced current-owner reads and private no-store/no-cache responses. No note in audit, notifications, lists, reports, My work or Office workload. |
| Stale/concurrent actions fail atomically. | Expected case/task versions; case then source records then Users/authority, followed by NOWAIT task locks. Existing task writers cannot deadlock closure by holding a User before their task. |
| REOPEN acceptance is one transition. | Existing transfer authorization/acceptance, primary Counselor change, responsibility period, ACTIVE status, closure reopening fields and one case-version bump in the same transaction. |
| Closure has no independent side effects. | Content-free `counseling.case.closed`/`.reopened` audit; no owner-close/reopen notifications. Student accounts, Referrals, Call Slips, published summaries and Messages remain independent. |

## Decisions D1 to D8

1. **D1 Ownership.** Applied as written. An unavailable active case owner first uses CW-3 responsibility transfer; no extra closure capability or Head bypass.
2. **D2 Closure record.** New closure table, optional encrypted note, reopening fields and retained cycles. The note uses `COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS`; the established rotation command verifies its binding before rewrapping ciphertext only. No new keyring.
3. **D3 Outstanding work.** Every blocker is shown and checked again transactionally. Since existing case Follow-ups must be COUNSELING and confidential, administrative retention is an explicit attestation rather than a category/confidentiality change. The nullable timestamp records the deliberate mark; the optional closure relationship records its first closure-cycle provenance. Reopening does not undo that administrative disposition or reassign its owner.
4. **D4 Closed case.** Existing records/history and authorized reads remain. All case membership/new-work mutations require Active. Existing marked and unmarked tasks remain completable/cancellable through existing authority; marking a task never opens its case or source to the assignee.
5. **D5 Same-episode reopening.** Owner-only, one of `SAME_CONCERN_RETURNED`, `FURTHER_SUPPORT_NEEDED`, `CLOSED_IN_ERROR`, preserved closure fields and a version bump. New concerns use Open case.
6. **D6 Unavailable closed owner.** Implemented with nullable transfer `purpose=REOPEN`. Office preparation requires `OWNER_UNAVAILABLE`; the unchanged independent-Head matrix applies. No task/Appointment dispositions, handoff or new deferred communication task. Acceptance uses `FURTHER_SUPPORT_NEEDED`, as allowed by the brief, and preserves retained task owners. Stale acceptance fails; invalidated pending REOPEN offers can be explicitly cancelled or declined without changing the case.
7. **D7 Audiences.** No Faculty/Student projection additions. Closing and reopening are projected into Privacy governance by the existing content-free continuity pattern; owner transitions produce no notification. REOPEN transfers reuse established in-app transfer notifications, work kinds and audience rules.
8. **D8 Workspace.** Closure/reopening is contextual to the case, with outstanding-work review, reason/outcome/note and consequential confirmation. The Closed overview suppresses case-management commands. History combines opening, closure/reopening cycles and continuity chronologically. Dates use Philippine Time; the portal call runtime remains mounted across navigation.

## Backend and API

| Owning area | Change |
|---|---|
| `case_closure_models.py`, `case_closure_content.py` | Retained cycles, bounded reason/outcome codes and confidential row-bound closure-note envelope. |
| `case_closure_services.py`, `case_closure_schemas.py`, `case_api.py` | Outstanding review, owner close/reopen, task designation, list/detail fields and protected owner note reads. |
| Guidance Follow-ups models/policy/services/API | Nullable retention fields; normal eligibility and workflow; retained case-only task authority after ownership changes. |
| Existing transfer rules/services/projections/schemas/work | Nullable REOPEN purpose, Closed office lookup, independent review/acceptance, atomic reopening and preserved task owners. |
| Existing Handoff rotation command | Verify/rewrap closure-note envelopes without changing closure attribution, chronology or business versions. |
| Audit actions and Privacy governance activity | Identifiers and bounded codes only for closed/reopened events. |

New canonical operations, below `/api/v1/counseling/cases`:

| Operation | Method and path |
|---|---|
| `counselingGetCaseClosureContext` | `GET /{case_id}/closure-context` |
| `counselingCloseCase` | `POST /{case_id}/close` |
| `counselingReopenCase` | `POST /{case_id}/reopen` |
| `counselingDesignateCaseTaskAfterClosure` | `POST /{case_id}/tasks/{task_id}/after-closure` |

Task designation retains Follow-ups' existing recent-MFA boundary. Owner case close/reopen adds no MFA requirement. The closure context supplies blocker kinds and item identities, authorized task titles and owning-workflow context. The list gains only `closed_at` and `closure_reason`; owner detail gains the closure cycles and `can_close`/`can_reopen`. Follow-up summaries expose nullable designation time/cycle identity to their authorized readers. Existing operation IDs and routes remain.

REOPEN uses the existing transfer operations and notifications. No new WorkKind, notification event, capability, setting, secret or Celery beat entry is introduced. Canonical backend export precedes ordinary Orval generation; generated client files are not edited or committed by hand. **Verified comparison:** 493 to 497 operations, four added, no removed operations, changed method/path or removed schemas/properties; 891 to 905 schemas. `test_openapi_contract.py` passed 49 tests.

## Migration and deployment

- `counseling/0009_case_closure`: nullable transfer `purpose` AddField without a default, plus closure CreateModel with its constraints/index inside the operation.
- `guidance_followups/0005_case_closure`: nullable `post_closure_designated_at` and `post_closure_closure` AddFields without defaults, depending on the new Counseling leaf.
- No changes to existing case status choices, case-event kinds, CW-3 state/reason choices, constraints, release baselines or source data. No backfill/data migration.
- Both are registered in `canonical_migrations.json` and SHA-256 pinned in the additive-migration manifest. Any migration edit requires re-pinning.
- The corrected upgrade rehearsal began at `counseling/0008` and `guidance_followups/0004`, prove only the two CW-4 migrations apply through routine preflight, compare every original legacy column and verify empty new tables/null new fields. **Executed evidence:** fresh `compass_cw4_rehearsal_20261113_02` passed routine preflight, verified identical checksums for all original columns in 128 legacy COMPASS tables, and checked every required populated session/link/task/transfer/handoff/coverage/grant resource. Only the two CW-4 migrations applied; the closure table stayed empty and every new nullable field stayed null. The first rehearsal's table selection produced empty checksum maps; that incomplete byte-preservation evidence is retained and superseded by this corrected fresh run.
- No shared database, reset, merge or deployment is authorized by this implementation.

## Frontend

The case overview and My cases filter consume the canonical generated contract. Closure review links to transfers, coverage, Appointments and Follow-ups; administrative retention requires an explicit checkbox, named owner and due date. Inputs survive failed/stale requests for deliberate review; consequential actions are never replayed automatically. Closed lists show the closure reason plainly. The Closed case removes Record session, Add next action, link/unlink, Transfer and Arrange coverage; its eligible owner can reopen. Office continuity can select Closed cases for an independently reviewed reopening transfer.

The main owners are `cases/case-closure-page.tsx`, `cases/closure-presentation.ts`, `cases/case-overview-page.tsx`, `cases/counselor-cases.tsx`, `cases/case-history-panel.tsx`, and the existing continuity prepare/review pages. After every repair below, `pnpm validate && pnpm test` passed with 1,292 unit tests. The mocked CW-4 suite passes 21/21 in Chromium and WebKit, and every affected existing suite passes in both engines.

## Verification

All command text, exit codes and complete redacted output are in the external `Claude outputs/cw-4/evidence/commands.jsonl`. They are local evidence. Every shell command runs through `evidence/run.py --cwd <directory> '<command>'`.

Backend commands below run from `be/` with this isolation prefix:

```sh
POSTGRES_DB=compass_cw4 REDIS_URL=redis://127.0.0.1:6379/10 REDIS_CACHE_URL=redis://127.0.0.1:6379/11 REDIS_RATE_LIMIT_URL=redis://127.0.0.1:6379/12 REDIS_IDEMPOTENCY_URL=redis://127.0.0.1:6379/13 REDIS_REALTIME_URL=redis://127.0.0.1:6379/14 PYTHONPATH='/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-4/evidence:.' DJANGO_SETTINGS_MODULE=cw4_test_settings
```

The external `cw4_test_settings` creates a unique `compass_cw4_pytest_*` database for each process. No full backend suite was run locally.

| Executed command | Outcome |
|---|---|
| `uv run python manage.py check` | Passed with isolated CW-4 settings. |
| `uv run pytest tests/test_canonical_baseline.py tests/test_staging_deployment.py -q --tb=short` | 84 passed; migration graph, model drift, manifests and additive deployment checks. |
| `uv run pytest tests/test_openapi_contract.py -q --tb=short` | 49 passed on the final canonical contract. Earlier combined OpenAPI/Privacy activity run passed 60 tests. |
| `uv run pytest tests/test_cw4_case_closure.py tests/test_cw4_closure_concurrency.py tests/test_cw4_closure_audiences.py -q --tb=short` | Final current-source run: 40 passed in 136.37s. |
| `uv run pytest tests/test_cw4_reopening_transfers.py tests/test_cw3_transfers.py tests/test_cw3_transfer_concurrency.py -q` | Final current-source run: 59 passed in 150.60s. |
| `uv run pytest tests/test_cw4_integration.py -q --tb=short` | 6 passed. |
| `uv run pytest tests/test_cw2_next_actions.py tests/test_cw3_case_coverage.py -q --tb=short --junitxml='/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-4/evidence/backend-owning-rerun.xml'` | Coverage's 22 passed; CW-2 had a new test-only exception-attribute fault, corrected below. |
| `uv run pytest tests/test_cw2_next_actions.py -q --tb=short --junitxml='/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-4/evidence/backend-cw2-final.xml'` | 22 passed in 53.98s after adding an explicit HTTP 409/code assertion. |
| `uv run pytest tests/test_cw3_case_coverage.py tests/test_cw2_next_actions.py tests/test_cw4_integration.py tests/test_cw4_reopening_transfers.py -q --tb=short` | 73 passed in 641s on the final backend source, covering both files that were red in the broad run. |
| `uv run ruff check . && uv run ruff format --check .` | Passed; 938 files formatted. |
| `python3 -m unittest discover -s .github/scripts` (repository root) | 81 passed after registering inherited CW-3 coverage and all five CW-4 files in BUNDLES. |
| `pnpm validate && pnpm test` (`fe/`) | Passed after all repairs; 1,292 tests, zero failed/skipped. |
| Mocked browser matrix on a CI-equivalent production test build (`NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 pnpm build`, `pnpm start` on 3149) | Chromium 12/12 suites and WebKit 12/12 suites: counseling-closure (21), counseling-cases (62), counseling-continuity (17), counseling-handoffs (10), counseling-coverage (9), case-coverage (41), work-queue (19), guidance-followups (28), faculty-referrals (35), user-copy (42), counseling-context-confidentiality (20), counseling-encounter-consistency (14). After the three repairs below, closure, continuity, coverage, handoffs, case-coverage, Follow-ups, cases and work-queue were rerun on a fresh test build: 8/8 suites in Chromium and 8/8 in WebKit. |
| Real Django 8096 + Next 3149 journeys (`real_backend.browser.mjs`) and database oracle (`real_backend.py oracle`) on fresh `compass_cw4_browser_20261113_e` | 7/7 journeys in Chromium and 7/7 in WebKit; the oracle passed for both engines, with original sessions, Appointment links, summaries and independent sources byte-identical and audit/notifications content-free. The journeys include closing blocked by active CW-3c coverage, then ending coverage and returning the delegated task, so CW-3c now has a real-backend journey. |
| `POSTGRES_DB=compass_cw4_rehearsal_20261113_02 <Redis10–14> DJANGO_SETTINGS_MODULE=tests.settings uv run python '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-4/migration_rehearsal.py'` | Corrected fresh upgrade rehearsal passed, as described above. |

The bounded backend regression selected 65 files across all CW-2/CW-3/CW-4, cases, continuity/handoff, Follow-ups, work queue, notifications, Appointments, Referral/Faculty Referral, privacy governance, audit, baseline/contract and staging deployment. The exact file list is `evidence/affected-backend-files.json`; the external `backend_regression.py 0` and `backend_regression.py 1` commands split that list across isolated databases.

The two broad runs were **727 passed/1 failed** and **956 passed/1 failed**, rather than a green full run. The first red result was transient PostgreSQL NOWAIT contention on `accounts_capability` in inherited CW-3 coverage; its owning 22 tests passed on the isolated rerun. The second was the inherited CW-2 expectation of `FollowUpInvalid` for new work on a Closed case. CW-4 requires a conflict (409); the test now expects `FollowUpConflict` and separately asserts the API's status/code, with no business assertion removed. Its first repair tried a nonexistent exception `.status` attribute; the HTTP assertion replaced that test fault and the final 22 passed.

Other recorded red runs were initial model drift before registered/pinned migrations; wrong new-test cancellation codes/missing Follow-up cancellation reasons; unsorted imports/an overlong test comment; a new D6 test reading a top-level code instead of `error.code`; and the inherited CW-3 coverage file missing from BUNDLES. Each owning repair and rerun is retained in the command ledger. A lock review also found a User/task inversion; source lock order was corrected and a deterministic existing-task-completion race added.

A final frontend repair synchronizes the privacy generation with the live barrier after React StrictMode effect replay. The old returned state generation could reject a successful case mutation after its response, so all stale-response assertions stay enforced and affected browser/full frontend checks must follow the repair. Browser evidence distinguishes stale fixtures/selectors from source defects and unhealthy-server timeouts. Runs against the webpack dev server under heavy machine load timed out inconsistently; the same suites passed on the production test build, which is what CI uses. No assertion is removed or weakened to make a run pass.

The real-backend journeys found three frontend defects that the mocked suites had missed. Each is fixed, and the mocks now behave like the backend so they fail without the fix:

1. **Close/Reopen completion disappeared.** After a confirmed close, the page refetched the Active-only closure review, received `409 counseling_case_closed` and replaced the "Case closed" confirmation with an error. The page now stops the review query once the action is confirmed. The mocked closure review now answers 409 for a Closed case, and the close checks trigger a refetch while the confirmation is open.
2. **After-closure owner options failed.** The eligible-assignee query sent `source_id=null` for case-only tasks, which the backend rejects with 422, so the plan could not be saved. Absent values are now omitted; the mock rejects any literal `null` query value.
3. **Stale reopening acceptance left its dialog open.** When the owner reopened the case first, acceptance correctly received `409 case_continuity_case_not_closed`, but the frontend did not treat that code as stale. It now closes the dialog, refreshes and shows "This case is no longer Closed, so this reopening transfer can't be accepted." A unit test and the mocked stale journey use the backend's exact code.

Each failed real-backend run used a fresh database (`_a` to `_d`); the passing run used `_e`. One failure was a script selector only: the single-Head refusal message has a second sentence.

## Known limitations and gaps

- Staff-side booking remains unavailable; closure routes to existing Appointment actions or deliberate case unlink. CW-4 does not build booking.
- Retention is an explicit administrative-action declaration. The system does not infer whether confidential task wording is administrative, and it does not rewrite the task's category or text.
- Initial case-only task assignment remains confined to the primary Counselor by existing rules. Retained explicit case-only task authority survives a REOPEN transfer; it does not make an inactive/ineligible assignee eligible or create a confidential recovery bypass.
- A manually inconsistent Closed case without a real closure row cannot be reopened by fabricating history; it fails with a clear conflict requiring review.
- Closure/history and linked Appointment collections retain their existing unpaged per-case shape. There is no new report dimension or global closure narrative disclosure.
- Full backend/full browser matrices, hosted CI on feature-branch stacked PRs, institutional UAT, physical-device/screen-reader checks, deployment and real-key custody/recovery are outside the local evidence unless separately recorded.

## Handoff to CW-6 and CW-7

CW-6 must keep counselor About and Message context separate from case closure and ownership. Never add a newly assigned Counselor to old Student Message audiences or stop/recreate the active portal call on case navigation.

CW-7 should verify the exact combined stack on its intended integration candidate, rerun the bounded audience/continuity/closure journeys, and obtain institutional UAT and release evidence separately. Preserve the existing Handoff keyring's custody/rotation procedures for closure notes. Administrative Referral closure, Student publication, case closure and individual task completion remain separate lifecycle decisions.
