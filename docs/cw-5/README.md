# CW-5: Referral timing

**Date:** 13 November 2026 · Philippine Time

**Branch:** `codex/counseling-cw5-referral-timing`, based on `1995e6bbcd18d8fe851c9eb263751d4f76eb91bd` from `codex/counseling-cw1-case-foundation`. Stacked on [#360](https://github.com/ils12058/COMPASS/pull/360) only, independently of CW-2 and CW-3. #360 was still open at the delivery check.

**Specification:** [Counseling workflow plan](../counseling-workflow-plan.md), REF-01 to REF-04, CLOSE-07, UX-05, UX-07, the backend and migration decisions, and package CW-5.

**Builds on:** [CW-1 record](../cw-1/README.md) and the [Faculty Referral history](../fac-5/README.md).

**Status:** Implemented and verified locally with mocked and real backends: 760 affected backend tests, 1,260 frontend unit tests, the production build, 16 selected browser suites in each engine, both real-backend journeys, and the additive upgrade rehearsal. Not merged or deployed. Hosted CI, office UAT, physical-device checks and human screen-reader testing have not run.

## What Faculty and staff can do now

- Faculty answer **When can Guidance reach or meet the student?** before reviewing a Referral: **Known times**, with one to five windows and an optional scheduling note, or **Unknown / needs confirmation**.
- Each window distinguishes **The student is usually free** from **The student may leave my class**. A statement can contain both kinds, on specific dates or recurring Monday-to-Saturday weekdays with a validity date.
- Faculty read their own statement on their own Referral detail. The statement stays read-only; their page contains no staff verification or staff scheduling note.
- Staff recording a paper Referral answer the same question. Provenance says **Reported by the referrer, recorded by <staff name> on <date>**, so the encoder is not represented as the referrer.
- Staff with `referrals.view`, within existing Referral scope, read the reported statement beside **Verified availability**, including earlier verifications and expired windows.
- Staff with `referrals.manage` explicitly add a verification sourced from **Student confirmed**, **Referrer confirmed**, or **Office record**. They may instead record **No suitable time confirmed**.
- Staff see timing guidance beside the date/time fields when issuing a Call Slip from the Referral. They choose the Call Slip date and time themselves.
- Referral lists show only **Timing: Known**, **Timing: Unknown**, or **Timing: Not provided**.

The official Referral Slip PDF continues to contain the official slip only. Timing does not book an Appointment, reserve a slot, prefill a Call Slip or send a new Student notification.

## Rules the implementation enforces

| Rule | Enforcement |
|---|---|
| Legacy absence differs from Unknown. | Both creation APIs accept an omitted or null `scheduling_statement`; existing rows have no statement. The two create forms require an explicit answer. |
| Known means one to five windows. | Backend validation, table count constraints and the shared editor. Unknown has zero windows and no note; No suitable time confirmed has zero windows and may have a verification note. |
| Dates use institutional civil time. | Philippine today is authoritative. A specific date cannot precede today; recurring validity includes today through today + 180 days, inclusive. Recurring weekdays are Monday to Saturday. |
| Each interval has end after start. | Local times cannot carry timezone offsets. Normalized duplicate windows are rejected; overlapping windows remain valid. Valid nonzero seconds/fractions are retained in the readout. |
| A note is scheduling-only plain text. | At most 500 Unicode characters, rejecting NUL and malformed Unicode. Help text keeps Referral reasons in their existing field. |
| The referrer's statement never becomes a staff verification. | Separate immutable statement and append-only verification tables; no update endpoint. Model/queryset guards reject updates, deletion, conflicting bulk updates and a new instance replacing an existing UUID. |
| Confidential timing stays separate. | Windows and note share a bound v1 timing envelope under the existing Referral keyring. Envelope type, Referral/row identifiers and attribution codes are bound; copied ciphertext fails closed. |
| Scope and session are checked when writing. | Fresh actor/capability and session checks, the existing catalog gate, deterministic user locks and a Referral row lock fence responsibility changes, voiding and competing verifications. |
| A stale verification is refused. | Both the latest verification UUID and the Referral timestamp must match. The read token retains microseconds, avoiding Ninja's millisecond datetime rounding. No mutation is automatically replayed. |
| Voided and closed are distinct. | No verification on a voided Referral. Verification after administrative closure remains allowed, with a visible **Referral closed** label. |
| Expired windows stay visible. | Backend read-time flags use Philippine Time; the UI refreshes at expiry boundaries and shows **This time has passed** or **No longer valid after <date>**. |
| Audiences remain bounded. | Own Faculty detail exposes only its statement. Other Faculty, Students, out-of-scope staff and guessed IDs retain existing denials; only manage holders write. Existing own-Faculty denial of voided submissions remains `404 referral_not_found`. |
| Timing content stays out of unrelated projections. | No windows/notes in list rows, notifications, push, email, My work, reports, Office workload, audit metadata, application request logs or the PDF. Audit records contain identifiers and codes only. |

## Decisions

D1 to D7 from the brief were applied.

1. **D1 — COMPASS supplement.** The `referral_slip` family, UCN-OP-GCO-01F3 revision, schema version 1, template and institutional-form synchronizer are unchanged.
2. **D2 — Reported timing.** Both window kinds and both patterns are supported. The **180-day recurring validity limit and 500-character scheduling-note bound are provisional defaults**, not approved institutional policy. API timing remains optional.
3. **D3 — Immutable statement.** One `ReferralSchedulingStatement` is inserted in the Referral's creation transaction. It has its own bound envelope; the existing reason/status/void envelope is untouched. Absent timing is never backfilled.
4. **D4 — Staff verification.** Each `ReferralSchedulingVerification` is a new row with its own source, author, time and envelope. Newest is first; earlier records are retained. Status changes, acknowledgment, closure and voiding leave statement ciphertext byte-identical.
5. **D5 — Guidance only.** Staff Referral detail and linked Call Slip creation show the supplement. The existing course/year prefill is preserved; timing supplies no date/time prefill or booking behavior.
6. **D6 — Audiences.** Own-Faculty detail has a separate allowlisted schema. Lists carry only the timing marker. Staff verification content is never included in the Faculty projection.
7. **D7 — Existing policy infrastructure.** No new capability, setting, secret, keyring, Celery schedule or identity-policy synchronizer change.

Implementation adjustments preserve those decisions: nested validation locations now keep up to eight structural components so a window's actual field receives the error, without returning submitted values. The base branch already guarded the Faculty form's core fields; its dirty state now includes timing. GCO creation and verification use the same guard, and linked navigation respects partially entered verification windows.

## Backend and contract

| Source | Purpose |
|---|---|
| `be/compass/referrals/timing_models.py` | Statement and verification models, provenance, append-only guards and new-table constraints |
| `timing_content.py`, `timing_rules.py` | Separate bound v1 envelopes, civil-time rules, historical reads and expiry flags |
| `timing_services.py` | Atomic statement insert, scoped staff reads, verification ordering, session/scope/stale checks and content-free audit |
| Existing `services.py`, `faculty_services.py`, `api.py`, `faculty_api.py` | Optional creation supplement, legacy-compatible Faculty idempotency, list marker and own-detail projection |
| `be/tests/test_referral_timing.py`, `test_referral_timing_concurrency.py` | Rules, ciphertext preservation, binding/privacy/audiences, legacy endpoints and deterministic PostgreSQL races; both registered in CI `BUNDLES` |

All paths below have the `/api/v1` prefix.

| Operation | Method and path |
|---|---|
| `referralsGetTiming` | `GET /referrals/{referral_id}/timing` |
| `referralsRecordTimingVerification` | `POST /referrals/{referral_id}/timing/verifications` |

Verification supplies `expected_latest_verification_id` and `expected_referral_updated_at`. Stale or voided writes return `409 referral_timing_changed`; field errors are `422 referral_timing_invalid`; a lost session is `401 session_unavailable`.

Contract comparison by operations and schemas found **465 → 467 operations**, 15 added schemas, no removed operations/schemas/properties, and no changed existing methods or paths. Five existing schemas gain compatible additions; the creation statement remains optional. The canonical contract was exported from Django, then Orval generated the client. Generated client code is not committed.

## Migration and deployment

- One additive migration: `referrals/0003_referral_timing`, depending on `0002_database_guards` and the existing user model.
- Exactly **two CreateModel operations**. Indexes and constraints are inside those operations. No existing Referral column or release migration changes; no data migration, backfill or shared-database reset.
- Registered in `be/compass/common/canonical_migrations.json` and SHA-256 pinned in `be/deploy/staging/additive-migrations.json`:

```text
a05585c8a0aae8707e653b0a3218aa1e5058934d7aa6159457e99f02d2337505
```

Re-pin after any migration edit. CW-1 supplies the registered-addition routine preflight path; CW-5 is stacked on #360 only.

## Frontend

| Area | Change |
|---|---|
| `fe/src/features/referral-timing/` | Shared window editor, draft validation, provenance/readout, expiry helpers, staff timing and verification form |
| Faculty submission/detail/list | Explicit timing answer, review of the exact intended statement, own read-only content and marker-only list |
| GCO Referral creation/detail/list | Required timing answer, guarded draft, reported and verified content, expired/closed labels and marker-only list |
| Issue Call Slip from Referral | Read-only timing context beside existing fields, without time selection or prefill |
| Form safety and feedback | Named window rows, field errors and first-error focus, guarded Back/linked navigation, preserved failed/stale drafts, loading/empty/denied states, Retry and `ActionStatus` after confirmed verification |

Automated browsers covered 320-pixel phones, larger widths, 200% text, keyboard flow and focus. That is not human assistive-technology or physical-device sign-off.

## Verification

All commands ran locally in `/Users/reynantlntno/Projects/COMPASS-CW5`. The external wrapper `/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/run.py` records commands and their full sanitized output in `evidence/commands.jsonl`, with PostgreSQL `compass_cw5` / `compass_cw5_*` and Redis 5–9. Next used 3129; real Django used 8095. Only owned servers were stopped.

The following are the executed inner commands; the wrapper supplied isolation and recording.

| Command | Final outcome |
|---|---|
| `cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run python '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/run_affected.py'` | **760 passed**, 29 affected files, 601.86 seconds; not the full backend suite |
| `cd be && uv run ruff format --check . && uv run ruff check .` | 907 files formatted; all checks passed |
| `cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py check --database default` | Clean |
| `cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run` | No pending model changes |
| `cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi --check` | Canonical export current |
| `python3 -m unittest discover -s .github/scripts` | **81 tests, OK** |
| `python3 '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/compare_contract.py'` | 465 → 467 operations; nothing removed; optional creation statement retained |
| `cd fe && pnpm validate` | API generation, lint, typecheck and production build passed |
| `cd fe && pnpm test` | **1,260 passed**, 0 failed |
| `cd fe && node --import ./tests/support/register-tsx.mjs --test tests/referral-timing.test.mjs` | **13 passed**, including the sub-minute readout regression |
| `cd fe && node --import ./tests/support/register-tsx.mjs --test tests/call-slip-permissions.test.mjs` | **28 passed** after supplying the actual navigation-guard provider |

The affected backend roster is retained in external `affected-tests.txt`: timing and concurrency, Referrals/encryption/administration, Faculty submission/notices/assurance/concurrency/journey, Referral Messages, Call Slips/lifecycle/provenance, documents/forms/PDF, audit/activity/privacy, canonical baseline, OpenAPI, staging deployment, database-error mapping, lock scope and request context.

**Mocked browsers.** `run_browsers.py chromium affected-browsers-r1` and `run_browsers.py webkit affected-browsers-r1` ran the 16-suite rosters from `fe/`. `run_browser_repairs.py` then ran the five focused repairs sequentially. After the timing precision fix, both timing suites were rerun in both engines. Each actual browser command was `node tests/<suite>.browser.mjs` with `COMPASS_UI_BASE_URL=http://127.0.0.1:3129`, `COMPASS_UI_BROWSER_CHANNEL=chrome`, the engine in `COMPASS_UI_BROWSER`, and a unique evidence directory.

| Suite | Checks passing in each engine |
|---|---:|
| Faculty foundation | 11 |
| Faculty Referrals | 43 |
| Referral administration | 108 |
| CW-5 timing | 32 |
| Call Slip permissions | 25 |
| Draft and session safety | 24 |
| Frontend consistency | 52 |
| UX hardening | 60 |
| UX-P1 | 16 |
| User copy | 42 |
| F2 navigation | 48 |
| Portal collections | 7 |
| Task guides | 76 |
| UX-P2A | 6 |
| Form input standardization | 4 |
| Form UI-1B | 6 |
| **Total per engine** | **560** |

These are the latest successful runs per suite, combining the initial rosters and focused reruns. The initial complete rosters had red assertions; this is not a claim that one final whole-roster invocation passed. `evidence/browser-summary-final.json` identifies every selected final result.

**Real backend, both engines.** Fresh database `compass_cw5_browser_1794545420602`, synthetic users and protected ephemeral session/keyring state. No business endpoint was mocked. Each engine passed **7/7 steps**: Faculty submits mixed windows; the office records Unknown; statement checksums are captured before verification; staff read both and add Student confirmation; Call Slip context remains unbooked/unprefilled; Faculty reread without verification; and other audiences/guessed IDs are denied. WebKit ran at phone width.

Executed from `be/`:

```sh
POSTGRES_DB=compass_cw5_browser_1794545420602 DJANGO_SETTINGS_MODULE=tests.settings uv run python '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/real_backend.py' prepare '/private/tmp/compass-cw5-private-1794545420602/state.json' real-backend-r3
POSTGRES_DB=compass_cw5_browser_1794545420602 DJANGO_SETTINGS_MODULE=tests.settings uv run python '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/real_backend.py' serve '/private/tmp/compass-cw5-private-1794545420602/state.json' real-backend-r3
```

Executed from `fe/`, sequentially:

```sh
POSTGRES_DB=compass_cw5_browser_1794545420602 node '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/real_backend.browser.mjs' chromium '/private/tmp/compass-cw5-private-1794545420602/state.json' real-backend-r3
POSTGRES_DB=compass_cw5_browser_1794545420602 node '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/real_backend.browser.mjs' webkit '/private/tmp/compass-cw5-private-1794545420602/state.json' real-backend-r3
```

Then the `oracle` action of `real_backend.py` ran from `be/` with the same database/state/evidence arguments. It confirmed four Referrals, two statements and one verification per engine, unchanged original ciphertexts, known/unknown distinction, source/author accuracy and no plaintext timing note in audit metadata. Evidence: `evidence/real-backend-r3/`, including `database-oracle.json`.

**Upgrade rehearsal.** The executed command was:

```sh
cd be && POSTGRES_DB=compass_cw5_rehearsal_1794541908185 DJANGO_SETTINGS_MODULE=tests.settings uv run python '/Users/reynantlntno/Projects/COMPASS/Claude outputs/cw-5/migration_rehearsal.py'
```

It stopped Referrals at `0002_database_guards`, loaded seven legacy Referrals with 21 actions and seven linked historical Call Slips, then applied only `0003_referral_timing`. All complete column values/counts of 115 existing COMPASS tables retained their checksums; both supplement tables were empty; pins/check/model drift checks passed; permitted legacy reads and PDF text were preserved.

The guard-valid legacy states were Faculty Submitted/Acknowledged/Closed/Voided and GCO Recorded without receipt/Received/Voided. The existing GCO schema does not permit Faculty acknowledgment/closure. Faculty's existing own-read 404 on a voided submission was preserved.

The actual read-only routine checker accepted the addition with a scoped local `APP_ENV=live-staging` label and `STAGING_SEED_ENABLED=False`, because `tests.settings` otherwise opts into persistent seeds. This exercises the checker locally; it is not a staging environment or deployment. Evidence: `evidence/migration-rehearsal/compass_cw5_rehearsal_1794541908185/summary.json`.

## Red runs and stale assertions repaired

The external REPORT and command ledger retain every red run and its full sanitized output.

- Backend own-projection assertions in Faculty, administration, assurance and the Faculty journey gained the marker and own-statement allowlist. Assertions excluding staff/counseling content remain. OpenAPI assertions distinguish optional creation fields and the own-detail schema from lists.
- Faculty/browser fixtures now answer the required timing question. Administration, draft/session safety, user-copy and UX-hardening fixtures supply marker-only list data and safe timing responses.
- The standalone Call Slip permission fixture now includes `UnsavedChangesProvider`, as the real portal does. Every existing permission/history assertion remains.
- Existing frontend-consistency and UX-P1 assertions assumed an absent page-header action container, but the base branch already contains Guide or an empty container. Staff Graduate Tracer still permits zero actionable header commands; Student Graduate Tracer and Appointment headers assert Guide as their sole header command. The three Appointment operational actions still occur solely in the contextual rail. Those product areas have no CW-5 source changes.
- New tests exposed and fixed scope/void locking, session/CSRF fixtures, nested field-location truncation, phone/200% text overflow, guarded navigation and valid sub-minute windows displaying as equal minute values.
- Three unsuccessful rehearsal attempts used separate fresh databases; fixes were the catalog seed CLI signature, the local read-only checker settings, and the preserved Faculty voided-read denial.
- The first real journey lost a connection under concurrent browser load; the second used the wrong Student denial heading. Fresh r3 passed both engines and the database oracle after sequential execution and audience-specific assertions.
- An initial WebKit User copy page-load timeout passed on sequential rerun. Read-path mistakes, schema date-name shadowing, lint/import errors and a contract-comparison cwd mistake are separately retained in the ledger.

No script is delivered as unexecuted evidence. All external helpers used here were run; failed attempts are not counted as successful journeys.

## Known limitations and owner gaps

- **Staff-side booking remains absent.** Timing is guidance for office contact/Call Slip issuance; Students still use existing Appointment booking. No slot suggestions or availability/eligibility override is added.
- **The official PDF carries no timing.** Sharing a printed official slip does not share its COMPASS supplement.
- **180 days and 500 characters remain provisional defaults** pending institutional review.
- Verification history is retained without pagination; a long history may need a later bounded-history interface.
- The existing Referral encryption rotation command does **not** rotate supplement tables. Retain historical Referral keys; do not retire them on the assumption that rotating original Referral envelopes covered timing. A supplement rotation procedure remains an owner gap.
- Append-only behavior is enforced through services and model/queryset guards. Privileged direct SQL is outside the supported write interface.
- The full backend suite and entire browser matrix were not run locally. Hosted CI does not run for this stacked target; rerun the required checks after integration/rebase into `staging`.
- No merge, deployment, shared-database reset, Guidance Office UAT, physical-device test or human screen-reader sign-off occurred.

## Integration handoff

CW-5 depends only on CW-1's additive-migration infrastructure. Keep every entry when resolving `canonical_migrations.json` and `additive-migrations.json`; preserve every test/CI registration and each package's status row. Re-pin changed migration files.

After rebasing the combined candidate, **re-export `contracts/openapi.json` from Django and regenerate the client; never merge the generated contract by hand**. Recheck migration pins, contract compatibility, the affected suites and upgrade evidence for that combined candidate.
