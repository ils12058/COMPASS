> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-2B + FUP-3A validation record

**Branch:** `integration/ux15-modernization`
**HEAD:** `9ad73c9c219aa8e4dc8ae56d7c71a9b89c35fc4a`
**Validation date:** 2026-11-05
**Scope:** FUP-2B and FUP-3A only
**Authority:** all behavior and copy in this slice, and all five code-owned provisional providers,
are **Provisional — pending GCO/FAC**. This record is engineering regression evidence, not UAT,
institutional approval or deployment evidence.

## 1. Base confirmation

```bash
git rev-parse HEAD
git status --short
```

Result: `9ad73c9c219aa8e4dc8ae56d7c71a9b89c35fc4a`; the working tree contained only the expected
FUP-2B/FUP-3A edits and the pre-existing untracked `outputs/paper-screenshots/` before this
package was written.

## 2. Commands and results

| Purpose | Exact command | Result |
|---|---|---|
| Targeted backend | `cd be && .venv/bin/python -m pytest tests/test_faculty_referrals.py tests/test_referral_administration.py tests/test_guidance_followups.py tests/test_fup3a_faculty_referral_journey.py -q` | **135 passed in 89.15s (0:01:29)** |
| Contract check | `DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi --check` | `OpenAPI contract is current: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |
| Contract diff | `git diff --exit-code -- contracts/openapi.json` | exit `0`; no diff |
| Generated/contract diff | `git diff -- contracts/openapi.json fe/src/lib/api/generated` | no output; exit `0` |
| Frontend unit | `cd fe && node --import ./tests/support/register-tsx.mjs --test tests/guidance-followups.test.mjs` | **4 passed, 0 failed** |
| Follow-Up browser (Chromium) | `cd fe && node tests/guidance-followups.browser.mjs` | **28/28 browser checks passed** |
| Faculty Referrals browser (Chromium) | `cd fe && node tests/faculty-referrals.browser.mjs` | **35/35 browser checks passed** |
| Referral Administration browser (Chromium) | `cd fe && node tests/referral-administration.browser.mjs` | **108/108 browser checks passed** |
| Faculty Foundation browser (Chromium) | `cd fe && node tests/faculty-foundation.browser.mjs` | **11/11 browser checks passed** |
| Typecheck | `cd fe && pnpm typecheck` | `$ tsc --noEmit`; exit `0` |
| Lint, first run | `cd fe && pnpm lint` | exit `1`; one `react/no-unescaped-entities` error, see §4.2 |
| Lint, final run | `cd fe && pnpm lint` | `$ eslint .`; exit `0` |
| Whitespace hygiene | `git diff --check` | exit `0` |
| Working tree | `git status --short` | see §7 |

### 2.1 Backend counts

The combined run collected 135 tests from the four files:

| File | Tests |
|---|---|
| `be/tests/test_faculty_referrals.py` | 59 |
| `be/tests/test_referral_administration.py` | 27 |
| `be/tests/test_guidance_followups.py` | 43 |
| `be/tests/test_fup3a_faculty_referral_journey.py` | 6 |

All 135 passed. The six FUP-3A tests are:

- `test_canonical_faculty_referral_journey_is_available_by_default`
- `test_provisional_evidence_is_fixed_idempotent_and_truthful`
- `test_live_scope_removal_denies_affected_provisional_operation`
- `test_empty_provisional_scopes_fail_closed_without_creating_evidence`
- `test_approved_and_provisional_evidence_cannot_cross_activate`
- `test_empty_scope_keeps_events_uncreated_even_after_prior_resolution`

The two renamed tests keep their original fail-closed assertions:

- `test_missing_lookup_or_submission_provider_denies_confirmation_and_submission`
- `test_missing_acknowledgment_or_closure_provider_denies_transition`

### 2.2 Frontend unit

`tests/guidance-followups.test.mjs` ran 4 tests, including the new
`Create next follow-up links only the readable source or the standalone Student identity`. Result:
4 passed, 0 failed.

### 2.3 Browser checks

The combined browser total is **182 checks** (28 + 35 + 108 + 11), all passing. The six FUP-2B
checks are:

- `A completed follow-up offers one explicit next-task link to its readable source`
- `An unavailable related record starts the next task as a standalone follow-up`
- `No next-task action is offered for a view-only account`
- `No next-task action is offered for a Pending follow-up`
- `No next-task action is offered for a cancelled follow-up`
- the extended `Follow-Up Help is supplementary and keyboard accessible` check

Artifacts:

```text
/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-guidance-followups
/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-faculty-referrals
/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-referral-administration
/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-faculty-foundation
```

## 3. Contract and generated client

- `export_openapi --check` reported the contract current.
- `contracts/openapi.json` has no diff.
- `fe/src/lib/api/generated/**` has no diff and was neither regenerated nor hand-edited.
- No API operation, schema, model or seed changed in this slice.

## 4. First-run failures and fixes

### 4.1 Journey test authoring errors

First run: **1 failed, 5 passed**. The failure was
`FollowUpContentUnavailable: Protected Follow-Up content is unavailable.` because the new test
fixture did not configure `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS`.

Fix: the fixture now receives `settings` and sets a per-run Fernet key.

Second run: **1 failed, 5 passed**. The failure was
`assert Notification.objects.count() == start_notifications == 0`; the actual count was 2. The two
rows are the existing in-app Follow-Up assignment notices produced when the test creates two
assigned Follow-Ups. They are not Referral notices and are not introduced by FUP-3A.

Fix: the assertion now verifies the truthful scoped property — no notification from submission,
acknowledgment, closure, completion or voiding; no Referral-targeted or Referral-sourced
notification; all notifications are the existing Follow-Up assignment notices to the assignee;
no notification to Faculty; no `EmailDelivery`. Final result: 6 passed.

### 4.2 Lint

First `pnpm lint` run failed with one `react/no-unescaped-entities` error at
`fe/src/features/guidance-followups/followups-help.tsx:10:385` for the apostrophe in
`earlier task's`. The JSX now uses `task&apos;s`, which renders the same plain apostrophe. The
Follow-Up browser suite was re-run after this change and still passed 28/28. Final lint passed.

### 4.3 Notification nuance (disclosed deviation)

The brief's literal expectation was no `Notification` from any step. The existing Follow-Up domain
emits an in-app `FOLLOWUP_ASSIGNED` notification when a staff member is assigned. Creating the
Referral-linked tasks through the existing create path therefore produces two notifications in the
journey test. FUP-3A does not suppress this unrelated existing behavior. The test asserts the
truthful property described in §4.1; the Referral journey itself produces no referral notice and
no external delivery. This is a disclosed deviation, not a hidden pass.

### 4.4 Local smoke-check side effect

Before the pytest runs, a local smoke import resolved the provisional lookup and tracking policies
against the local `compass_test` database. That created two fixed provisional Audit events:

```text
f3a00001-0000-4000-8000-000000000001  (STUDENT_CONFIRMATION)
f3a00005-0000-4000-8000-000000000005  (FACULTY_TRACKING)
```

Audit rows are append-only, so they were not deleted. The targeted pytest run uses a separate
`test_compass_test` database and is unaffected. No production, staging or shared database was
touched.

## 5. Temporary server disclosure

The browser harness requires a local Next server at `localhost:3107`. A temporary development
server was started only for the browser commands:

```text
pnpm exec next dev --port 3107
```

Readiness was confirmed with an HTTP 200 from `http://localhost:3107/portal/follow-ups`. The server
was stopped after the four suites. It was restarted once solely to re-run the Follow-Up suite after
the lint fix, confirmed HTTP 200 again, and stopped again.

No manual UI session, live backend, seed, dev database or institutional environment was used. This
is synthetic browser-harness evidence, not dev-server feature verification or UAT.

## 6. Repository state

`git status --short` after all changes:

```text
 M be/compass/referrals/administrative_policy.py
 M be/compass/referrals/faculty_policy.py
 M be/tests/test_faculty_referrals.py
 M be/tests/test_referral_administration.py
 M docs/fac-5/readiness.md
 M fe/src/features/guidance-followups/followups-detail.tsx
 M fe/src/features/guidance-followups/followups-help.tsx
 M fe/src/features/guidance-followups/followups-shared.tsx
 M fe/tests/guidance-followups.browser.mjs
 M fe/tests/guidance-followups.test.mjs
?? be/compass/referrals/provisional_activation.py
?? be/tests/test_fup3a_faculty_referral_journey.py
?? docs/fup-2b-3a/
?? outputs/paper-screenshots/
```

- `contracts/openapi.json` and `fe/src/lib/api/generated/**` are unchanged.
- `outputs/paper-screenshots/` pre-existed and was left untouched.
- Changes remain uncommitted. No commit, merge, push, rebase, stash or reset was run.

## 7. Evidence limits

- Only the four listed backend test files were executed. No full-suite or shard result is claimed.
- The browser suites use synthetic accounts and HTTP fixtures. They do not exercise a live backend,
  database, notification provider, storage provider or institutional record.
- The browser matrix was Chromium only; WebKit was not run.
- No performance, accessibility-audit, load, security-scan or penetration result is claimed.
- No manual dev-server feature verification, staging, production, seed or migration result is
  claimed.
- No GCO, FAC, UAT, privacy or records acceptance is claimed. The provisional providers are
  code-owned defaults, not institutional approval.
- The only notification evidence is the scoped assertion in the journey test; no delivery provider
  was exercised.

## 8. Not run

- Full backend pytest suite and shards.
- Full frontend unit suite (`pnpm test`); only `tests/guidance-followups.test.mjs` was run.
- Full browser regression matrix and every other browser suite outside the four listed.
- WebKit matrix (`COMPASS_UI_BROWSER=webkit`).
- `pnpm build`.
- Migrations, migration checks, seed and database queries beyond the targeted pytest run.
- Manual dev-server feature verification, staging and production.
- FUP-1D, FUP-2C, FUP-3B, FUP-3C and FUP-4.
- Full regression is deferred to FUP-4.

## 9. Final status

The prescribed targeted backend, contract, frontend unit, browser, typecheck and lint checks pass
after the fixes disclosed above. The work remains uncommitted on
`integration/ux15-modernization`, and no commit, merge, push, rebase, stash or reset was performed.
