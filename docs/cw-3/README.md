# CW-3: Case transfer, handoff and temporary coverage

**Date:** 13 November 2026 · Philippine Time  
**Specification:** [Counseling workflow plan](../counseling-workflow-plan.md), with the owner's CW-3 decisions dated 13 November 2026.  
**Builds on:** [CW-1](../cw-1/README.md) ([#360](https://github.com/ils12058/COMPASS/pull/360)) and [CW-2](../cw-2/README.md) ([#361](https://github.com/ils12058/COMPASS/pull/361)). Both are open; CW-3a is based on `codex/counseling-cw2-next-actions` at `15f0f8f9`. Nothing is merged or deployed.

| Part | Branch | Status |
|---|---|---|
| CW-3a Transfer | `codex/counseling-cw3a-transfer` | Implemented and verified locally; stacked on CW-2. |
| CW-3b Handoff | `codex/counseling-cw3b-handoff` | Implemented and verified locally; stacked on CW-3a. |
| CW-3c Coverage | `codex/counseling-cw3c-coverage` | Not started. |

## CW-3a: What staff can do

- The primary Counselor prepares **Transfer case** from the case's **Continuity** panel, selecting a receiver and neutral reason, every pending task's disposition, every upcoming linked Appointment's plan, and Student communication status. Saving the plan does not transfer the case. The review page supplies the explicit submission step.
- An eligible Guidance Office Assistant or Head prepares an unavailable/conflicted owner's arrangement through the metadata-only **Case continuity** lookup. It shows case reference, Student, primary Counselor and status. Task titles are hidden; office preparation cannot write clinical content or create a sourced-task successor.
- An independent current Head authorizes an ordinary submitted request from **My work**, using the narrow review page. The Head's own outgoing case is directly authorized on submission.
- The receiver reviews an authorized offer and explicitly accepts or declines. A seven-day offer expires by time, with no scheduled job. Accepting immediately changes the primary Counselor and applies the reviewed tasks in one transaction. A declined, cancelled or expired offer leaves the owner unchanged and says another arrangement is needed.
- The current owner sees responsibility periods and continuity activity. The initial period is derived from the case's opening; only real transfers create responsibility rows. A later owner can open earlier transfer metadata from this history.
- A retained Appointment continues to count as the case's next appointment with its actual provider. New Appointment links retain CW-2's provider eligibility rule. The case opens supported Appointment actions; it never books or edits an Appointment itself.

## Rules enforced in CW-3a

| Rule | Enforcement |
|---|---|
| Ordinary A → C needs an independent Head and C's acceptance. | `eligible_authorizers` excludes requester and receiver, checks the live roster and capabilities; accepting rechecks the route and authorizer. |
| With one Head, C's personal request to the Head can proceed without a third party. | Only the current owner's personal request uses `OWNER_TO_HEAD`; explicit Head acceptance remains required. History, Audit and Privacy governance activity record `independent_authorization = false`. With another eligible Head, the ordinary independent route applies. |
| Office-prepared incoming requests to the sole Head are blocked. | `No independent approver is available`, before writing any arrangement/task. The Head cannot prepare her own receipt. |
| Every pending task has a disposition. | Case-only: `TRANSFER` or `RESOLVE_FIRST`. Sourced: `RETAIN`, `HAND_OVER_AS_NEW`, or `RESOLVE_FIRST`, under source authority. Office sees only category, deadline and assignee, and uses case-only transfer or resolve first. Impartiality concern refuses sourced-task retention. |
| A safe successor never copies confidential history. | The outgoing Counselor explicitly writes an encrypted new title/deadline. Acceptance creates a case-only predecessor-linked task, cancels the original with a fixed reason, and copies no description. |
| Appointment plans require real supported actions. | Every future scheduled current link is reviewed. Reassign/cancel/reschedule must be reflected in the Appointment before acceptance. Retaining the outgoing provider is refused for an impartiality concern. |
| Pending review never grants case management or old source access. | Review returns the plan, categories/deadlines and Appointment metadata; titles remain with the authorized preparer. The package ends at acceptance, decline, cancellation or expiry. The outgoing Counselor keeps authored Encounters but loses the case and later work. |
| Changed work fails atomically. | Optimistic arrangement versions plus current owner/status/receiver/task/Appointment checks; case-first locks, then sources and sorted Users. Busy inverted work locks return a conflict. Audit failure rolls back ownership and task changes. |
| Active legacy coverage blocks acceptance. | Student-keyed active approved legacy grants are conservatively treated as conflicting with that Student's case. They must be explicitly revoked or expire. They are not converted or ended by transfer. |
| Student communication is attributed. | Yes requires an informed timestamp. Deferred requires a closed reason, named case-only task and future deadline; it is assigned to the current primary until transfer. No automatic Student message. |
| Notifications and Audit carry no content. | Next-actor in-app notification uses the existing notification producer/currentness pattern and generic wording. Audit carries identifiers, versions and authorization codes only. |

## Decisions and limitations

The single-Head rule is the owner's decision of 13 November 2026; section 5.2, CONT-03 and the matching section 13 scenario were updated. The function evaluates whether another eligible Head exists; it does not encode a particular Head or assume one designation row.

Optional reason explanation is omitted: there is no existing arrangement-explanation codec, and the brief forbids a new keyring. The closed neutral reason is implemented. This is a recorded gap, not plaintext storage. CW-3a has no structured handoff prerequisite; that belongs to CW-3b. Existing legacy handoff/grant screens and message audiences keep their current behavior.

Task and Appointment plan collections allow at most 2,000 entries per request. History and the case's continuity panel are not paginated. The scope of office lookup follows existing office Student responsibility; Head lookup is institution-wide metadata. No new capability, identity-policy change, setting, secret, keyring or Beat entry is introduced.

## Backend and canonical API

Code: `case_continuity_rules.py`, `case_transfer_models.py`, `case_transfer_plans.py`, `case_transfer_services.py`, `case_transfer_projections.py`, `case_transfer_work.py`, `case_transfer_schemas.py` and `case_transfer_api.py` under `be/compass/counseling/`. Follow-up history gains a nullable transfer reference. My work gains authorization/acceptance items, and Privacy governance activity safely presents the authorization fact.

| Operation | Method and path below `/api/v1/counseling/continuity` |
|---|---|
| `counselingListContinuityOfficeCases` | `GET /office-cases` |
| `counselingGetCaseTransferContext` | `GET /cases/{case_id}/transfer-context` |
| `counselingPrepareCaseTransfer` | `POST /cases/{case_id}/transfers` |
| `counselingGetCaseTransfer` | `GET /transfers/{transfer_id}` |
| `counselingUpdateCaseTransfer` | `PUT /transfers/{transfer_id}` |
| `counselingSubmitCaseTransfer` | `POST /transfers/{transfer_id}/submit` |
| `counselingAuthorizeCaseTransfer` | `POST /transfers/{transfer_id}/authorize` |
| `counselingAcceptCaseTransfer` | `POST /transfers/{transfer_id}/accept` |
| `counselingDeclineCaseTransfer` | `POST /transfers/{transfer_id}/decline` |
| `counselingCancelCaseTransfer` | `POST /transfers/{transfer_id}/cancel` |

The case response gains `continuity`; the next Appointment includes its real provider and record accessibility. Follow-up events expose the transfer reference without widening case access. Backend-owned OpenAPI is exported, then Orval is generated; generated files remain uncommitted.

## Routine migration path

CW-3a adds three migrations: `counseling/0005_case_transfers` (three new plan/arrangement tables), `counseling/0006_transfer_history` (responsibility and append-only transfer events), and `guidance_followups/0003_case_transfers` (one nullable `case_transfer` event field, without a default). Every index/constraint on a new table is declared inside `CreateModel`. All are registered in `canonical_migrations.json` and SHA-256 pinned in `deploy/staging/additive-migrations.json`. Re-pin after an edit.

No existing grant choices, constraints, case event kinds or immutable release migration are altered. No data migration or backfill runs. Deployment uses the routine forward path and the normal synchronizers; live deployment and database resets are outside this task.

## Local verification

Commands and complete red/green output are outside the checkout at `Claude outputs/cw-3/evidence/commands.jsonl`; the external `REPORT.md` records the command ledger, defects and evidence paths. Backend runs use `POSTGRES_DB=compass_cw3`, Redis databases 10–14, and local PostgreSQL. Browser runs serve this worktree on `http://127.0.0.1:3113`, with installed Chrome and Playwright WebKit.

| Command/check | Outcome |
|---|---|
| `uv run pytest tests/test_cw3_transfers.py tests/test_cw3_transfer_concurrency.py tests/test_canonical_baseline.py tests/test_openapi_contract.py tests/test_staging_deployment.py tests/test_audit.py -q --tb=short` | 180 passed before the additional repeated-transfer history test. |
| Affected Counseling/case/continuity/handoff/Follow-up/work/Appointment/lock suites (23 files; exact command in evidence) | Initial 632 passed, two stale tests failed; both repaired and the two files rerun: 38 passed. All 634 distinct cases have passing final evidence. |
| `uv run pytest tests/test_cw3_transfers.py tests/test_cw3_transfer_concurrency.py -q --tb=short` | 36 passed, including repeated transfers and concurrency. |
| `uv run python manage.py makemigrations --check --dry-run` and `uv run python manage.py export_openapi --check` with `DJANGO_SETTINGS_MODULE=tests.settings` | Passed; no missing migration or contract drift. |
| Canonical contract comparison by operation, schema and property sets | 468 → 478 operations; 834 → 864 schemas. No operation, path, method, schema or property removed. |
| `python3 -m unittest discover -s .github/scripts` | 81 passed. |
| `pnpm validate` | Passed: API generation, lint, TypeScript and production build. |
| `pnpm test` | 1,260 passed in the final run after the edit-form correction. |
| `tests/counseling-continuity.browser.mjs`, both engines | 17/17 in each engine. |
| Real Django + Next journey, both engines | 7/7 per engine; database oracle passed. |
| Upgrade rehearsal | Passed on fresh `compass_cw3_rehearsal_a_20261113_02`: only the three new migrations applied; preflight accepted them; all legacy table/column checksums were identical; five new tables empty; nullable event field all null; pins and Django checks passed. |
| Affected browser regressions | Eight suites, 243 checks in each engine, passed across the recorded final runs. WebKit user-copy was rerun successfully after restoring the local server. |

The adjacent backend command was:

```sh
POSTGRES_DB=compass_cw3 REDIS_URL=redis://127.0.0.1:6379/10 REDIS_CACHE_URL=redis://127.0.0.1:6379/11 REDIS_RATE_LIMIT_URL=redis://127.0.0.1:6379/12 REDIS_IDEMPOTENCY_URL=redis://127.0.0.1:6379/13 REDIS_REALTIME_URL=redis://127.0.0.1:6379/14 uv run pytest tests/test_counseling.py tests/test_counseling_context.py tests/test_counseling_documentation_review.py tests/test_counseling_downstream_lifecycle.py tests/test_counseling_finish.py tests/test_counseling_frontend_readiness.py tests/test_counseling_cases.py tests/test_counseling_cases_concurrency.py tests/test_cw2_next_actions.py tests/test_cw2_case_appointments.py tests/test_continuity.py tests/test_continuity_access.py tests/test_continuity_contract.py tests/test_continuity_release_concurrency.py tests/test_handoff.py tests/test_handoff_concurrency.py tests/test_handoff_configuration.py tests/test_guidance_followups.py tests/test_work_queue.py tests/test_appointments.py tests/test_appointment_management_scope.py tests/test_appointment_action_projection.py tests/test_lock_scope.py -q --tb=short
```

The external browser runner records each exact invocation separately:

```sh
python3 '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-3/browser_matrix.py' cw3a --suites counseling-continuity counseling-cases case-coverage guidance-followups work-queue user-copy counseling-encounter-consistency counseling-context-confidentiality
```

The real-backend scripts are `Claude outputs/cw-3/real_backend.py` and `real_backend.browser.mjs`, run on fresh `compass_cw3_browser_a_20261113_03`, with ephemeral keys/sessions confined to a mode-0600 `/tmp` file. No business endpoint is mocked. Each engine exercises ordinary acceptance, task successor and communication, retained-provider appointment, decline, sole-Head receipt, office preparation and blocked incoming Head, stale acceptance after cancellation, and the Head's outgoing route. The database oracle confirms ownership, tasks, encrypted successor titles, unchanged source descriptions, responsibility/event attribution and content-free notifications/Audit.

Stale checks repaired: CW-2's next-appointment test assumed a current provider must still be the primary; D5 intentionally changes that projection. My work's explicit response-field inventory gained the nullable case reference, with its no-ciphertext assertion preserved. Case fixtures gained continuity. Active-call checks now navigate through preparation/review. New confirmation tests use the dialog's completed title after success; a broad alert selector was scoped to the feature error. Subordinate continuity headings use level 3. Phone tests count page commands in the page header and still check every command's bounds and 44px target, including panel commands. A shared back-link styling violation in office lookup and a duplicated expired label were fixed, with their failed runs preserved.

The edit form now derives its initial reason from the saved arrangement and waits for its reason-specific context before allowing a save; this removed a synchronous state update in an effect flagged by lint. A broader browser run was interrupted after navigation timeouts and a local HTTP check returned no response within ten seconds. After validation and restarting this worktree's development server with its default compiler, the page checks returned HTTP 200 and the active-call journey passed with the same call-lifetime assertions. All failed and interrupted runs remain in the command ledger.

On continuation, the inherited server had become orphaned and logged `write EPIPE`; browser navigations produced blank pages. That run was interrupted. Its screenshots and the output available at interruption are preserved; the older capture wrapper lost some earlier output during interruption. The wrapper now streams redacted output and keeps every captured line across interruption. Restarting this worktree's server with file-backed logs and webpack restored the two failing sign-in checks (2/2) and the complete WebKit user-copy suite (42/42), with the same assertions. No application assertion was weakened.

Not run: full backend suite, full browser matrix, hosted CI, institutional UAT, physical-device or screen-reader checks, staging deployment, and real-key custody/recovery. Stacked PRs target feature branches, so the current hosted workflow does not run checks on them.

## Handoff to CW-4

Closure must check pending transfers and active or accepted-pending coverage before changing case state. It must resolve continuing clinical tasks through explicit actions and preserve task/Appointment provenance. Handoff readership after closure must remain available to the authorized case owner. Coverage expiry must return unfinished delegated work or flag confidential recovery; it must not complete/cancel a task. Closing a case cannot delete transfer or responsibility history, cancel Appointments silently, or alter old message audiences.

## CW-3b: Structured handoff

The primary Counselor prepares four narrative sections: current concern and purpose, support and progress, considerations for continuing support, and what the receiver should review or do next. Their aggregate limit is 12,000 characters. Pending actions and Appointments form a read-only snapshot of the reviewed plan, including their named responsibility and dates; task titles and descriptions are excluded. Saving a transfer may create a Draft. The author opens it and submits it deliberately before submitting the transfer for authorization.

A submitted handoff is immutable. The author can add dated, attributed information. After acceptance, the current case owner can add an addendum and retain handoff readership, including after closure and later ownership changes. A former owner retains only their historical authorship rights. The prospective receiver can read the submitted package only during authorized review. An authorized non-author read records the first receipt; acceptance neither endorses the narrative nor completes any action.

The office cannot write narrative. An eligible Head records **Handoff unavailable** with a closed reason before the office submits its prepared plan. My work routes that exception review to the Head, then submission to the preparer. The receiver sees a missing-information warning and accepts explicitly. An incoming personal request to the sole Head cannot use this exception; its outgoing author can prepare the handoff. The Head's own outgoing case retains the existing direct route.

Editing a recipient, reason or work plan clears the selected handoff and exception pointers, retaining the old immutable rows. Saving/submitting handoff content or adding information to a pending offer clears its authorization and advances the optimistic version. An accepted-owner addendum also advances the version while retaining accepted ownership; an unconfirmed retry with the old version cannot add twice. Only genuinely pre-CW-3b submitted offers without the nullable prerequisite marker retain their earlier behavior. No historical handoff, exception or acceptance is fabricated.

Protected content uses the existing `COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS`. Distinct versioned envelope bindings identify the handoff, transfer, case, Student, author, receiver and plan digest; addenda have their own bound identity and attribution. The existing rotation command verifies and rewraps both new resource types while preserving business timestamps, versions, receipts and history. It is not a legacy codec converter. No keyring, setting or secret was added.

Case/source/User/authority and live AuthSession locks fence each protected operation. Permission and session time are rechecked after decryption and synchronous content-free Audit, before the durable transaction commits and returns the body. Every continuity response, including errors, uses private no-store/no-cache headers. The frontend clears transient protected content on hidden/offline/session revalidation and requires an explicit recheck; late responses cannot refill a cleared view. Draft conflicts preserve typed text for deliberate review of the latest saved version. Addenda page at 20, with page input bounded to 1–1,000. Already delivered information cannot be recalled.

## CW-3b API and migration

New owning files are `case_handoff_models.py`, `case_handoff_content.py`, `case_handoff_services.py`, `case_handoff_schemas.py` and `case_handoff_api.py`. Legacy grant-linked `CounselorHandoffSummary` and its routes remain independently usable.

| Operation | Method and path below `/api/v1/counseling/continuity` |
|---|---|
| `counselingSaveCaseHandoff` | `PUT /transfers/{transfer_id}/handoff` |
| `counselingSubmitCaseHandoff` | `POST /transfers/{transfer_id}/handoff/submit` |
| `counselingGetCaseHandoff` | `GET /handoffs/{handoff_id}` |
| `counselingAddCaseHandoffAddendum` | `POST /handoffs/{handoff_id}/addenda` |
| `counselingRecordCaseHandoffUnavailable` | `POST /transfers/{transfer_id}/handoff-unavailable` |

`counseling/0007_case_handoffs` contains four `CreateModel` operations and three nullable transfer fields without defaults (`case_handoff`, `handoff_exception`, `handoff_required_at`). New-table constraints and indexes are inside `CreateModel`. The registered and pinned SHA-256 is `7a0a60dee3cd35e2d96402c10df93e11c8b6ad22f8133551eeeeca7b71a0f22a`. No existing migration, case event constraint or legacy grant choice was changed.

The fresh upgrade rehearsal applied only that migration. Routine preflight accepted it, all legacy original-column checksums matched, the four new tables remained empty, and all three new transfer fields remained null. The fixture included prepared and authorized pre-CW-3b transfers as well as legacy cases, tasks, grants and handoffs. Evidence: `Claude outputs/cw-3/evidence/cw3b/migration-rehearsal/compass_cw3_rehearsal_b_20261113_01/rehearsal-evidence.json`.

The canonical comparison found 478 → 483 operations and 864 → 878 schemas, with no operation, route, schema or property removed. Backend export precedes ordinary Orval generation; generated files are not committed. One initial API signature incorrectly treated an unannotated response argument as a required query parameter; it was removed from the owning endpoints and the contract regenerated.

## CW-3b local verification

| Command/check | Final outcome |
|---|---|
| `uv run pytest tests/test_cw3_case_handoffs.py tests/test_continuity_contract.py tests/test_cw3_transfers.py tests/test_cw3_transfer_concurrency.py tests/test_openapi_contract.py tests/test_canonical_baseline.py tests/test_staging_deployment.py -q --tb=short` | 203 passed. |
| Adjacent 27-file Counseling/case/continuity/handoff/Follow-up/work/Appointment/audit/baseline/deployment run (exact command in external ledger) | 779 passed and one stale legacy-path assertion failed initially. Its legacy-only filter was corrected, retaining all five assertions; its final file passed in the 203-test run. All 780 distinct cases have final passing evidence. |
| `ruff format` / `ruff check`, `makemigrations --check --dry-run`, `export_openapi --check` | Passed. |
| `python3 -m unittest discover -s .github/scripts` | 81 passed. |
| `pnpm validate`, then `pnpm test` after the final focus fixes | Passed; 1,261 frontend tests passed. |
| Nine affected browser suites | 253 distinct checks per engine have passing final evidence. WebKit passed the complete matrix. Chromium's three navigation failures were rerun successfully; transfer and handoff were rerun in both engines after the focus fixes. |
| Real Django + Next, Chromium and WebKit | 7/7 journeys in each engine on fresh `compass_cw3_browser_b_20261113_05`; database oracle passed. |
| Upgrade rehearsal | Only `0007_case_handoffs` applied; preflight, checksums, empty new tables and null new fields passed. |

Backend commands use the same isolated PostgreSQL/Redis environment as CW-3a. The final browser rerun was:

```sh
python3 '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-3/browser_matrix.py' cw3b --suites counseling-continuity counseling-handoffs
```

Real scripts `real_backend_b.py` and `real_backend_b.browser.mjs` were executed, not merely written. Both engines exercised genuine API submission of the structured Draft, immutable handoff, receipt, unavailable exception, accepted-owner addendum, ordinary and sole-Head transfer routes, office boundaries, decline and stale acceptance. Ephemeral sessions/keyrings remained in a mode-0600 `/tmp` file. The database oracle verified ciphertext, receipt/addendum attribution, unchanged source descriptions and content-free Audit/Notifications. Evidence: `Claude outputs/cw-3/evidence/cw3b/real-backend/` and `real-backend-oracle.json`.

Initial failures exposed a missing default AuditContext, a typed UUID expectation, an overbroad legacy contract path filter, and an expired-session fixture that violated expiry-after-creation. All were corrected. Body tests also encountered transient authority-table contention during fixture setup; their test transaction now holds a setup fence with bounded waiting, leaving application NOWAIT fences and separate real concurrency tests unchanged. The final complete 203-test run passed.

The initial real browser attempts were interrupted by API regeneration, cold page compilation, and then automatic Next memory-threshold restarts. The latter were confirmed in `next-webpack.log`, and explain the repeated navigations and lost transient dialog/focus state. No application assertion was relaxed. The final build completed before a new server was started, required routes were prewarmed, and browser/real journeys ran serially. The final server log contains no memory-threshold restart. The two new focus assertions first failed: immutable submission removed the draft editor's opener, and the unavailable exception removed its button. They now focus stable page/panel headings and pass in both engines.

Existing transfer fixtures now satisfy the real handoff prerequisite instead of fabricating readiness. The preparation journey checks six sections and a separate handoff submission. The legacy contract test is explicitly scoped to grant-linked handoff paths; a separate case-handoff contract test asserts the new operations. The active-call journey opens the handoff and preserves all create/join/leave/destroy counts. Red attempts, screenshots, their fixes and every command remain in the external ledger/report.

Not run: full backend suite, full browser matrix, hosted CI, institutional UAT, physical-device/screen-reader checks, deployment or real-key custody/restore verification. Stacked PRs target feature branches, while hosted CI runs only against `staging`. No merge, shared database change, reset or external messaging was performed.

CW-4 must preserve authorized current-owner handoff reads after closure, resolve pending arrangements explicitly and retain immutable narrative/addenda, receipt, exception and responsibility attribution. Clinical closure, automatic source disclosure and Student messaging remain outside CW-3b.
