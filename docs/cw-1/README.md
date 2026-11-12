# CW-1: Counseling case foundation and overview

**Date:** 12 November 2026 · Philippine Time
**Branch:** `codex/counseling-cw1-case-foundation`, cut from `origin/staging` at `751f31ea`
**Specification:** [COMPASS counseling workflow plan](../counseling-workflow-plan.md) — CASE-01 to CASE-07, UX-01, UX-07, the backend and migration decisions, and package CW-1
**Status:** Implemented in source. Backend verified locally. Frontend typechecks and lints, but its tests, build and browser journeys have **not** been run; see [What still has to be run](#what-still-has-to-be-run). Not committed, pushed, reviewed, deployed or tried by anyone at the Guidance and Counseling Office.

## What a counselor can do now

- Open **Counseling** and see **My cases** instead of a list of sessions.
- **Open a case** from a Counseling intake (choose the Student), one of their own Appointments, one of their own recorded sessions, or one of their own Routine Interviews. Before confirming, they see the active cases they already hold for that Student.
- Open a case and read, on one page: the Student, the case reference, whether it is Active, who is responsible, how many sessions were completed, the latest session, the linked sessions and the case history.
- **Record a session** from inside the case. The session is linked to the case in the same step.
- **Add a recorded session** that is not in any case yet.
- **Remove** a session that was linked to the wrong case, with a reason. The session record itself is untouched and can then be added to the right case.
- Still reach every session they ever recorded under **Session records**, with a column and a filter showing whether each one is in a case.

Nothing here closes, reopens or transfers a case. Those belong to CW-3 and CW-4, and no endpoint or button for them exists.

## Rules the implementation enforces

| Rule | Where it is enforced |
|---|---|
| A case is one episode. A Student may have several, including several Active ones. | No uniqueness on Student. Sessions join a case only through an explicit link; nothing groups by Student. |
| One primary responsible Counselor per case. | `CounselingCase.primary_counselor`. Only the primary Counselor reads or changes the case (`case_services._accessible_cases`). No endpoint changes it. |
| Being Head, holding a College, authoring a session, or guessing an ID grants no case access. | Every read and write filters on `primary_counselor`. Others receive `404 counseling_case_not_found`; non-Counselors receive `403`. |
| A Counselor links only their **own** Encounters. | Linking and opening look up the source with `counselor_id = actor`. Another Counselor's record answers "not found", even for the same Student. Cross-Counselor linking waits for the CW-3 disclosure route. |
| A session belongs to at most one case at a time, and counts once. | Partial unique constraint `counseling_case_session_one_current_case`, plus row locks. The count is current links only; an Appointment or Routine Interview attached to the same Encounter adds nothing. Scheduled, cancelled and missed Appointments are never counted. |
| A wrong link is corrected explicitly and stays in history. | `unlink_session` requires a closed reason code, keeps the removed row, appends a case event and an audit event. |
| A case link never widens access to the linked record. | The case projection carries scheduling facts and the original author only. `record_accessible` says whether the reader may open the Encounter; the Appointment reference is withheld when they may not. Encounter and Student Session Summary endpoints keep their own checks. |
| Opening a second case is deliberate. | `known_active_case_ids` must equal the Counselor's current Active cases for that Student, or the request is refused with `counseling_case_review_required`. This also makes a double submission harmless. |
| Stale changes fail clearly. | Link and unlink take `expected_version`; a mismatch is `409 counseling_case_changed`. |
| History is not rewritten. | Encounters, authors, Appointment providers and published summaries are never updated by case code. `CounselingCaseEvent` is append-only and records who was responsible at each event. |

## Decisions made while implementing

These were routine implementation choices under the specification. Each one can be revisited.

1. **No free-text case label yet.** The plan treats case labels as sensitive. Storing one properly needs its own encryption keyring, which is a new mandatory secret on every environment before any deployment. CW-1 identifies a case by reference, opened date, origin and sessions, as in the plan's own overview sketch. A confidential label can be added with the structured handoff content in CW-3.
2. **No new capabilities.** Reads use `counseling.view_assigned`; opening, linking and correcting use `counseling.manage_assigned`. The narrowing comes from the primary-Counselor relationship. No `sync_identity_policy` change is needed.
3. **Reference format** `CASE-<year>-<6 digits>`, allocated like Appointment references, in institutional time.
4. **Opening from a scheduled Appointment does not auto-link its later session.** When that session is recorded, the case overview offers it for one-click, explicit linking.
5. **No status filter in My cases.** Nothing can be Closed until CW-4, so the filter would always be empty. The API already accepts `status`.
6. **Removal reasons are a closed list** (`BELONGS_TO_ANOTHER_CASE`, `NOT_PART_OF_THIS_CASE`, `LINKED_BY_MISTAKE`) so history and audit stay free of narrative.
7. **Next appointment and next action are omitted** from the overview. No authoritative case relationship for them exists until CW-2, and showing "none" would be a false statement.
8. **No staging seed data for cases.** Dataset v1 and its `verify` are unchanged.

## Backend

| File | Purpose |
|---|---|
| `be/compass/counseling/case_models.py` | `CounselingCase`, `CounselingCaseSession`, `CounselingCaseEvent`, `CounselingCaseReferenceCounter` |
| `be/compass/counseling/case_services.py` | Opening, linking, correcting, listing, overview, opening context, recording into a case |
| `be/compass/counseling/case_api.py` | Router mounted at `/api/v1/counseling/cases` |
| `be/compass/counseling/api.py`, `services.py` | `in_case` and `case` on Encounter responses; `case_link` filter; optional `case_id` when recording |
| `be/compass/audit/actions.py` | `counseling.case.opened`, `.session_linked`, `.session_unlinked` (identifiers and codes only) |
| `be/tests/test_counseling_cases.py`, `test_counseling_cases_concurrency.py` | 21 tests |

New operations:

| Operation | Method and path |
|---|---|
| `counselingListMyCases` | `GET /counseling/cases` |
| `counselingOpenCase` | `POST /counseling/cases` |
| `counselingGetCaseOpeningContext` | `GET /counseling/cases/opening-context` |
| `counselingGetCase` | `GET /counseling/cases/{case_id}` |
| `counselingListCaseSessionCandidates` | `GET /counseling/cases/{case_id}/session-candidates` |
| `counselingLinkCaseSession` | `POST /counseling/cases/{case_id}/sessions` |
| `counselingUnlinkCaseSession` | `POST /counseling/cases/{case_id}/sessions/{encounter_id}/unlink` |

Changed operations: `counselingListMyEncounters` (new `case_link` query parameter), and every `CounselingEncounterResponse` (new `in_case`, `case`). `CounselingCreateRequest` accepts `case_id`. No operation or schema was removed; this was checked by comparing the old and new contract by operation and schema, because the textual diff is large from reordering.

Lock order in case code is always case, then Encounter, then Users. `create_encounter` locks the case first when `case_id` is given.

## Migration and deployment

- **One additive migration:** `counseling/0003_counseling_cases`. It contains four `CreateModel` operations and nothing else; every index and constraint is declared inside the `CreateModel` for its new table. It does not alter, backfill or read an existing table, and it creates no cases for existing data.
- **Routine deployment path:** `database_preflight.validate_operations` accepts `CreateModel` without a reviewed exception, so this migration does not need a reset. A test now asserts that registered additive migrations use only operations that preflight accepts.
- **Registered in two places:** `be/compass/common/canonical_migrations.json` (`additive_migrations`) and the new `be/deploy/staging/additive-migrations.json`, which pins the file's SHA-256. A test keeps the two in step. **If the migration file changes, its hash in `additive-migrations.json` must be updated.**
- **Reset tooling change:** `reset_preflight.classify_database` previously required the applied history to equal the baseline exactly. A database carrying this migration would have been refused as "Unrecognized" at the next reset. It now accepts the complete baseline plus any registered additive migrations, and still refuses anything unregistered. This touches `.github/scripts/`, so the pull request triggers the full backend regression.
- **No new secret, setting, capability or synchronizer step.** Deployment order is unchanged: migrate, then the usual synchronizers.
- No deployment, reset, or change to any shared database was made.

## Frontend

| Route | Screen |
|---|---|
| `/portal/counseling` | **My cases** for Counselors. Students still see their Session Summaries; coverage-only staff still get the Case coverage link. |
| `/portal/counseling/cases/new` | **Open case**. Query: `student=<id>` for an intake, or `origin=<APPOINTMENT\|ENCOUNTER\|ROUTINE_INTERVIEW>&source=<id>`. |
| `/portal/counseling/cases/[caseId]` | **Case overview** |
| `/portal/counseling/encounters` | **Session records**: the previous Encounter list, the record form and the documentation review panel, moved here unchanged apart from the Case column and filter. |
| `/portal/counseling/cases` | Redirects to `/portal/counseling`. |

New code is under `fe/src/features/counseling/cases/`. Existing Encounter, coverage, Student Session Summary and workspace routes keep their URLs. "Open a case" links were added to the Encounter detail page and the Counseling workspace. Links that pointed at `/portal/counseling#encounters` now point at `/portal/counseling/encounters`.

The Follow-ups menu position is unchanged; that move belongs to CW-2. The portal workspace registry was not changed.

## Verification

### Run on this branch (local, 12 November 2026)

Backend commands ran from `be/` with `POSTGRES_DB=compass_cw1` and Redis databases 10 to 14, so they did not share state with other sessions.

| Check | Outcome |
|---|---|
| `uv run pytest tests/test_counseling_cases.py tests/test_counseling_cases_concurrency.py` | 21 passed; repeated three times with a fresh database |
| Counseling, continuity, handoff, routine interview, session summary, baseline, database-error, capability and staging-seed files (24 files) | 616 passed |
| `tests/test_openapi_contract.py` after registering the new operations and ordering | 48 passed |
| `tests/test_lock_scope.py`, `tests/test_audit.py` | passed (in an earlier 147-test run) |
| `python3 -m unittest discover -s .github/scripts` | 81 tests, OK |
| `uv run ruff format --check .` and `uv run ruff check .` | clean |
| `manage.py check`, `makemigrations --check --dry-run` | no issues, no changes |
| `manage.py export_openapi`, then `pnpm api:generate` | contract exported and client regenerated |
| `pnpm typecheck` | clean |
| `pnpm lint` | clean |

### What still has to be run

Deferred at the owner's instruction for another agent. None of these has been run on this branch.

1. **`pnpm test`** (frontend unit tests). A run was started and stopped before it reported. Expect failures in tests that assumed the Encounter list lives at `/portal/counseling`; these were found by search, not by running:
   - `fe/tests/counseling-documentation-review.test.mjs` — `PATHNAME` and the two expected hrefs should become `/portal/counseling/encounters`.
   - Any test that calls `encounterCreatePayload` still passes three arguments; the fourth (`caseId`) is optional.
2. **`pnpm build`** (and so `pnpm validate`). Restore `fe/next-env.d.ts` afterwards if Next rewrites it.
3. **Existing browser specs** that open the Encounter list or record form at `/portal/counseling` and should open `/portal/counseling/encounters`:
   - `fe/tests/counseling-encounter-consistency.browser.mjs` (`waitForURL` on `/portal/counseling`, and the `standalone-appointment-recording` check)
   - `fe/tests/user-copy.browser.mjs` (`counseling-validation`; the list now also calls `/api/v1/counseling/cases`)
   - `fe/tests/case-coverage.browser.mjs` (`counseling-navigation`; "Case coverage" is now a page action link on My cases, same accessible name)
   - `fe/tests/faculty-foundation.browser.mjs` and `fe/tests/counseling-context-confidentiality.browser.mjs` reference `/portal/counseling` for non-Counselor audiences and should be unaffected, but were not run.
   - Encounter fixtures in browser specs need `in_case: false, case: null` to match the contract.
4. **New frontend tests, not written:** unit tests for `cases/case-presentation.ts`, and browser journeys for opening a case (each origin), the review-required refusal, adding and removing a session, recording from a case, the stale-version notice, denied access, phone width and keyboard use.
5. **Migration rehearsal, not run:** a fresh install was exercised only through pytest's test database. An upgrade rehearsal (apply the baseline, load legacy Encounters, Follow-ups, published summaries and coverage grants, then apply `0003`, confirm nothing changed and no case was created) is still owed.
6. **Full backend suite and browser matrix:** GitHub CI on the pull request head is the full run.
7. **No screen was opened in a browser.** Layout, focus order, and behaviour during an active E-Counseling call are unverified.

### New test files to keep in CI

`test_counseling_cases.py` and `test_counseling_cases_concurrency.py` are registered in the `counseling` bundle in `.github/scripts/backend_ci.py`.

## Known limitations

- A Counselor cannot yet link a session recorded by another Counselor, and a case cannot change hands. Existing coverage grants and handoffs keep working through their current pages and are not connected to cases.
- Cases opened for the same Student by two different Counselors do not know about each other. That is deliberate under CASE-07.
- A case cannot be closed. `CLOSED` exists in the vocabulary and is refused for changes, but only a direct database edit can set it.
- The case history lists every event without paging. It grows by one or two rows per link or correction.
- If a Counselor's `counseling.manage_assigned` is revoked, they can still read their cases but not change them; if `counseling.view_assigned` is revoked they lose the case list, as with Encounters.

## Handoff to CW-2

CW-2 (next actions and scheduling coherence) can build on:

- `CounselingCase` as the anchor for an optional Follow-up relationship and a case-to-Appointment relationship. Adding nullable foreign keys or new tables stays on the routine deployment path; register each migration in both manifests.
- `CounselingCaseEvent` for new event kinds. The `counseling_case_event_session_named` constraint requires an Encounter for every kind except `OPENED`; a new kind without an Encounter needs that constraint changed, which is **not** a routine-path operation and needs a reviewed migration.
- The overview page's `PageHeader` actions and panels for "Schedule session", "Add next action", the next appointment and the next action.
- The Follow-ups menu move described in UX-08, which CW-1 left alone.
