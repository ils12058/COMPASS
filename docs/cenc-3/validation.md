# CENC-3 — Validation evidence

Protocol for this slice: **targeted + static only** (the full-suite gate is CENC-5). One deliberate
deviation is recorded in §3.5: three pre-existing browser regression files were executed, read-only, to
capture the stop-condition conflict verbatim rather than assert it analytically. Nothing was done that
touches a real account, room, credential or institutional record — every browser request is answered by
the synthetic fixture router, and E-Counseling calls use the fake Call Object.

## 1. Start-state gate

| Check | Result |
|---|---|
| `git log --oneline -1` | `70fdb31d Add CENC-2 Finish counseling UX for Detail and Workspace` — matches the required base |
| Branch | `integration/ux15-modernization` |
| `git status --short` before editing | only `?? outputs/paper-screenshots/` — the one expected pre-existing entry |
| CENC-0/1/2 docs, finish service, appointments services, call runtime | unmodified at the end (`git status --short` in §8) |

## 2. Targeted test commands and final results

### Backend (from `be/`)

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest tests/test_ecounseling.py \
  tests/test_counseling_finish.py tests/test_counseling.py tests/test_openapi_contract.py -q
```

Final result: **`105 passed, 1 warning in 134.18s (0:02:14)`** (exit 0). The warning is a pre-existing
Ninja `DeprecationWarning: Returning tuple (status_code, response) is deprecated` raised from
`ninja/operation.py:220` inside `test_counseling.py`; no code in this slice produces it.

Component runs that make the coverage explicit:

| Command | Result |
|---|---|
| `uv run pytest tests/test_ecounseling.py -q` | `16 passed in 25.80s` |
| `uv run pytest tests/test_ecounseling.py -q -k "recorded_is_this or agree_on_the_documentation"` | `2 passed, 13 deselected in 13.78s` (the two new parity/semantics tests, clean on first run) |
| `uv run pytest tests/test_ecounseling.py -q -k "never_mistaken_for_a_finished_session"` | `1 passed, 15 deselected in 11.66s` (after the §3.2 fix) |
| `uv run pytest tests/test_openapi_contract.py -q -k "ecounseling_join_and_context_readiness"` | `1 passed, 42 deselected in 3.29s` (after the §3.1 fix) |

CENC-1's finish tests were not edited; `tests/test_counseling_finish.py` passes inside the 105.

### Frontend (from `fe/`)

| Command | Final result |
|---|---|
| `node --import ./tests/support/register-tsx.mjs --test tests/ecounseling-finish.test.mjs` | `ℹ tests 14 / ℹ pass 14 / ℹ fail 0` in 1833 ms |
| `node --import ./tests/support/register-tsx.mjs --test tests/ecounseling-finish.test.mjs tests/ecounseling-safety-access.test.mjs tests/ecounseling-call.test.mjs tests/counseling-finish.test.mjs tests/counseling-online-delivery.test.mjs tests/counseling-encounter-consistency.test.mjs` | `ℹ tests 86 / ℹ pass 86 / ℹ fail 0` in 3120 ms |

`pnpm test` (the whole `tests/*.test.mjs` glob) was **not** run — full frontend suite belongs to CENC-5.

## 3. First-run failures and resolutions (verbatim)

### 3.1 `tests/test_openapi_contract.py` — Ninja adds a `title`

First run:

```
>       assert encounter_summary["properties"]["recorded"] == {"type": "boolean"}
E       AssertionError: assert {'title': 'Re...e': 'boolean'} == {'type': 'boolean'}
E
E         Omitting 1 identical items, use -vv to show
E         Left contains 1 more item:
E         {'title': 'Recorded'}
E         Use -v to get more diff

tests/test_openapi_contract.py:3043: AssertionError
FAILED tests/test_openapi_contract.py::test_ecounseling_join_and_context_readiness_openapi_contract
1 failed, 1 passed, 41 deselected in 4.73s
```

Cause: Django Ninja emits a `title` for every schema property, so an exact-dict comparison of the
property schema can never pass. Resolution: assert the meaningful parts instead —
`encounter_summary["properties"]["recorded"]["type"] == "boolean"` and
`"anyOf" not in encounter_summary["properties"]["recorded"]`. No production behavior changed; this was a
test-expression problem, not a contract problem. Re-run: `1 passed, 42 deselected in 3.29s`.
While applying that fix I also introduced and immediately repaired a stray `}` in the edited line; it was
caught by inspection before anything ran.

### 3.2 The new mismatch test — 422 instead of the expected 409

First run:

```
>       assert response.status_code == 409
E       assert 422 == 409
E        +  where 422 = <HttpResponse status_code=422, "application/json; charset=utf-8">.status_code

tests/test_ecounseling.py:847: AssertionError
```

Cause: the test built `actual_ended_at` as `appointment.starts_at + 50 minutes`, i.e. in the future, so
the finish request was rejected by the time contract (`ended_at must not be in the future`) before it
could reach the Encounter-match check. Resolution: derive both times from `timezone.now()`
(`- timedelta(minutes=45)` / `- timedelta(minutes=5)`). The production ordering the test is about — the
`_encounter_matches` check at `be/compass/counseling/finish_service.py:214-230` running before the
access-window check at `:241-252` — is unchanged. Re-run: `1 passed, 15 deselected in 11.66s`.
An intermediate selection `-k "mismatch or ..."` silently matched nothing, because the test's name
contains `non_matching`/`mistaken` rather than `mismatch`; the deselection count exposed it and the test
was re-run by its exact name.

### 3.3 Backend static checks on the new test code

First run:

```
E501 Line too long (102 > 100)
   --> tests/test_ecounseling.py:825:101
Found 1 error.
--- ruff format ---
1 file would be reformatted, 3 files already formatted
```

Resolution: the `_link_encounter(appointment, counselor=…, entry_mode=CounselingEntryMode.WALK_IN, …)`
call was wrapped across lines. Re-run: `All checks passed!` and `4 files already formatted`, then the
full `tests/test_ecounseling.py` file still green (`16 passed in 25.80s`).

### 3.4 The static workspace render

The plan anticipated the Daily call runtime blocking a static render; that is what happened first, in a
throwaway prototype (`fe/tests/ecounseling-static-scratch.mjs`, since deleted):

- `SyntaxError: missing ) after argument list` — an unbalanced `h(...)` chain in the prototype itself;
  reformatted the nesting.
- `Error: useActiveECounselingCall must be used inside the portal's E-Counseling runtime.` thrown from
  `fe/src/features/ecounseling/runtime/active-call-context.ts` through `useSessionCallView` →
  `CounselorSession`.
  Resolution: the test supplies an **idle `ActiveECounselingCallContext.Provider` value**. No file under
  `fe/src/features/ecounseling/runtime/` or `call/` was edited, per the do-not-touch list.
- First assertion pass of the real suite: `ℹ tests 14 / ℹ fail 1`. The sweep
  "nothing authoring is offered while the online access window is open" used
  `doesNotMatch(html, /Finish counseling|Record encounter/)`, which matched the `WINDOW_OPEN` *sentence*
  "…Finish counseling becomes available here once it ends." (`encounter-section-state.ts:99`) rather than
  a control. Resolution: the assertion targets button-shaped markup
  (`/>Finish counseling<`, `>Record encounter<`), which is what "no authoring action" means. Re-run:
  `ℹ tests 14 / ℹ pass 14 / ℹ fail 0`. The detailed node failure block was truncated in the captured
  output; the counts above are the recorded evidence.
- Two further test-design mistakes were caught by reading the component before running it, not by a red
  test: expecting `state === "RECORDED"` for `uncertainSave: "FINISH"` (the state machine answers
  `UNCERTAIN`), and expecting `FALLBACK_RECORD` for a Counselor lacking `appointments.manage` (the
  component never issues the Appointment read in that case, so nothing is confirmed).

**No production behavior was changed to make any test pass.** Every fix above was to a test expression,
a fixture timestamp in a test, or test formatting.

### 3.5 Pre-existing browser regressions that contradict this slice (reported, not rewritten)

The slice's stop condition says: *"Also stop if a pre-existing test asserts behavior this slice
contradicts — quote it and explain the conflict rather than silently rewriting it."* That condition is
met. These files were left byte-for-byte untouched and are **not** part of the passing evidence.

`node tests/ecounseling-call.browser.mjs` → **`38/40 browser checks passed`**, exit 1:

```
FAIL encounter-separate-from-recording: locator.waitFor: Timeout 12000ms exceeded.
FAIL encounter-save-dismissal: locator.click: Timeout 12000ms exceeded.
```

`node tests/counseling-encounter-consistency.browser.mjs` → **`2/14 browser checks passed`**, exit 1:

```
FAIL ecounseling-dialog-identity-matches-overview: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-dialog-without-institutional-id: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-validation-is-specific-and-announced: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-save-success-other-browser-zone: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-pending-then-unconfirmed: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-rejected-save-keeps-values: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-already-recorded: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-dialog-keeps-times-and-call: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-dialog-narrowPhone: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-dialog-phone: locator.click: Timeout 12000ms exceeded.
FAIL ecounseling-dialog-tablet: locator.click: Timeout 12000ms exceeded.
FAIL counseling-workspace-dialog-identity: locator.click: Timeout 12000ms exceeded.
```

`node tests/ui-information-hierarchy.browser.mjs` → **`17/18 browser checks passed`**, exit 1:

```
FAIL counseling-workspace: locator.waitFor: Timeout 12000ms exceeded.
```

**The conflict, explained.** All of the `ecounseling-*` failures open the Record dialog inside a session
and then drive it. The shared fixture entry point is
`fe/tests/counseling-encounter-consistency.browser.mjs:91` —
`encounterSection(page).getByRole("button", { name: "Record encounter", exact: true }).click()` — and
`fe/tests/ecounseling-call.browser.mjs:694` —
`page.getByRole("button", { name: "Record encounter", exact: true })`. This slice removes exactly that
control from the session (D-CENC-23: `Finish counseling` replaces `Record encounter`;
`encounter-separate-from-recording` additionally asserts
`/^Counseling Encounter.*Not yet recorded/` alongside it, and `ecounseling-already-recorded` at
`fe/tests/counseling-encounter-consistency.browser.mjs:264` expects
`"An encounter was already recorded for this Appointment. The latest details are now shown."`).
Two independent mechanisms produce the same result with these fixtures:

1. `fe/tests/support/ui-hierarchy-fixtures.mjs:37` sets `join_state: "OPEN"`, so the section resolves to
   `WINDOW_OPEN` and offers nothing authoring at all — which is precisely outcome 2 of the mission.
2. Even with a CLOSED window the state would be `FINISH`, because the harness does stub the Appointment
   read (`fe/tests/support/browser-harness.mjs:143` answers
   `GET /api/v1/appointments/{appointmentId}` with the fixture `appointment`,
   `status: "SCHEDULED"`, `actions.complete.allowed: true`, no `counseling_encounter_recorded` key →
   `finishCounselingState` = `OFFERED`).

So these cases assert the pre-CENC-3 behavior the slice exists to replace. Updating them is a real UI
verification task for **CENC-5**, where the browser gate is in scope; rewriting them here would either
silently delete the safeguard assertion or fabricate a browser pass this slice has not earned.

**Two failures are not CENC-3's.** 13 of the 15 failures above are E-Counseling session cases (2 in
`ecounseling-call`, 11 in `counseling-encounter-consistency`, including the three device variants the
loop at `fe/tests/counseling-encounter-consistency.browser.mjs:286` generates). The remaining two —
`counseling-workspace-dialog-identity` and `ui-information-hierarchy`'s `counseling-workspace` — both
navigate to `/portal/counseling/workspace/appointment/${appointmentId}` and
assert `Record encounter` (`fe/tests/ui-information-hierarchy.browser.mjs:47`). That is the CENC-2
surface: `fe/src/features/counseling/counseling-workspace.tsx` is not in this slice's diff at all
(§8), and CENC-2's own record notes browser tests were outside its validation scope
(`docs/cenc-2/validation.md:206`). These two are therefore **pre-existing failures from the already
committed CENC-2**, surfaced by running the browser files for the first time since; they are reported
here rather than fixed, because fixing CENC-2's test debt is not this slice's scope and would change
files the CENC-3 brief assigns elsewhere.

## 4. Contract and migration checks

| Command | Result |
|---|---|
| `DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi --check --output ../contracts/openapi.json` | `OpenAPI contract is current: ../contracts/openapi.json` |
| `git diff --stat contracts/openapi.json \| wc -l` | `0` — the contract diff is empty, as required |
| `DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run` | `No changes detected` |

`contracts/openapi.json` and `fe/src/lib/api/generated/**` were never hand-edited; no Orval run was even
necessary, because the wire shape did not change. `be/tests/test_openapi_contract.py` pins
`CounselingEncounterWorkspaceSummary` to `{"id", "recorded"}`, `recorded` as a non-nullable required
`boolean`, `additionalProperties: false`.

## 5. Static checks

| Command | Result |
|---|---|
| `uv run ruff check compass/counseling/services.py compass/ecounseling/services.py tests/test_ecounseling.py tests/test_openapi_contract.py` | `All checks passed!` |
| `uv run ruff format --check` on the same four files | `4 files already formatted` |
| `uv run ruff check .` (repo-wide) | `Found 4 errors.` — identical to the recorded pre-existing baseline: `compass/referrals/provisional_activation.py:334` (E501 111 > 100), `tests/test_fup3a_faculty_referral_journey.py:7`, `tests/test_guidance_followups.py:464` and `:565` (E501 102 > 100). All in files this slice does not touch; left alone |
| `pnpm lint` (`eslint .`) | clean, no output |
| `pnpm typecheck` (`tsc --noEmit`) | clean, exit 0 |
| `pnpm build` (`next build`) | exit 0 — see §7 for the `fe/next-env.d.ts` restore |

## 6. Deliberately not run

| Item | Why |
|---|---|
| Full backend suite (`uv run pytest -q`) | CENC-5 gate; this slice is not the final CENC slice |
| `pnpm test` (full `tests/*.test.mjs` glob) | Same reason |
| `fe/tests/run-browser-regressions.mjs` and every other `*.browser.mjs` | Not in scope. Three files were executed in §3.5 **only** to capture the pre-existing-test conflict; they are reported as failing-by-design, not as passing coverage |
| Daily media, capture, consent and download E2E against a real room | No account, room or credential used; the call runtime is untouched |
| WebKit browser passes (`COMPASS_UI_BROWSER=webkit`) | Not run |
| Accessibility tooling and screenshot work | Not run; `outputs/paper-screenshots/` untouched |
| GCO, institutional, security, privacy, clinical or UAT sign-off | **Not obtained.** Decisions here are engineering-provisional |
| CENC-4 reconciliation/worklist behavior | Out of scope by design |

## 7. Build artifact handling

`pnpm build` (exit 0) rewrites the `fe/next-env.d.ts` reference lines. The churn was exactly two lines —
`./.next/dev/types/routes.d.ts` and `./.next/dev/types/root-params.d.ts` reverting to
`./.next/types/…` — and the file was then restored alone with `git checkout -- fe/next-env.d.ts`. The
final `git status --short` in §8 shows no entry for it, which is the evidence that the restore happened.

## 8. Working tree evidence

`git status --short` at the end of the slice:

```
 M be/compass/counseling/services.py
 M be/compass/ecounseling/services.py
 M be/tests/test_ecounseling.py
 M be/tests/test_openapi_contract.py
 M fe/src/features/ecounseling/ecounseling-workspace.tsx
 M fe/src/features/ecounseling/session-help.tsx
?? fe/src/features/ecounseling/encounter-section-state.ts
?? fe/tests/ecounseling-finish.test.mjs
?? outputs/paper-screenshots/
?? docs/cenc-3/
```

`git diff --numstat` (tracked files):

| File | Added | Removed |
|---|---|---|
| `be/compass/counseling/services.py` | 21 | 10 |
| `be/compass/ecounseling/services.py` | 11 | 2 |
| `be/tests/test_ecounseling.py` | 207 | 2 |
| `be/tests/test_openapi_contract.py` | 8 | 0 |
| `fe/src/features/ecounseling/ecounseling-workspace.tsx` | 141 | 43 |
| `fe/src/features/ecounseling/session-help.tsx` | 2 | 2 |
| **Total** | **390** | **59** |

New files: `fe/src/features/ecounseling/encounter-section-state.ts` (127 lines) and
`fe/tests/ecounseling-finish.test.mjs` (361 lines) = 488 lines, plus this `docs/cenc-3/` package.

`outputs/paper-screenshots/` is the pre-existing untracked entry the brief predicted; nothing under it
was created, modified or removed by this slice.

## 9. Guardrail compliance evidence

| Guardrail | Evidence |
|---|---|
| Provisional and enabled | No flag, toggle, env gate or disabled route anywhere in the diff; the projection and the online Finish path ship on |
| Zero contract diff | §4: `export_openapi --check` current + `git diff --stat contracts/openapi.json` → 0 lines; no generated file or contract edited |
| No migrations, no model fields, no persisted state, no worklist | `makemigrations --check --dry-run` → `No changes detected`; no model file in the diff |
| CENC-1 finish semantics untouched | `be/compass/counseling/finish_service.py`, `be/compass/appointments/services.py` and `tests/test_counseling_finish.py` are absent from the diff; the endpoint is called, not edited |
| No attendance inference from media/capture/join/call state | `joinState` is read once, in `encounter-section-state.ts:95`, and only selects explanatory copy; no status write and no derived "took place" claim anywhere |
| Actual times typed, never prefilled | The CENC-2 `FinishCounselingDialog` is reused unchanged; no join/leave/capture timestamp is imported into it (the diff never reads those fields) |
| Never auto-replay an uncertain request | `checkFinishAgain` (`ecounseling-workspace.tsx:426-437`) refetches and verifies `COMPLETED && counseling_encounter_recorded === true`; `handleFinishStale` reloads and reports. No mutation is re-issued |
| Do-not-touch list honored | No change under `fe/src/features/ecounseling/call/` or `runtime/`, capture/consent flows, Routine workspaces, direct-recording lookup scope, `outputs/paper-screenshots/`, or `docs/cenc-0..2/` |
| No `any`, `@ts-ignore`, TODO/FIXME | `pnpm typecheck` and `pnpm lint` clean; none introduced by the diff |
| Reuse shared primitives | `DisclosureSection`, `Button`/`buttonVariants`, `ActualTimeFields` via the existing dialogs, `finishCounselingNotice/State`, `invalidateAfterCounselingFinish`, `counselingErrorMessage` |
| Not committed, not pushed | §8 shows a dirty working tree; no commit, amend, rebase or push was run |

## 10. Conclusion

Every targeted and static gate for this slice is green: 105 backend tests across the four named files,
86 targeted frontend tests, contract current with an **empty** diff, no migrations, and clean
lint/typecheck/build. The browser files executed for conflict evidence fail exactly where the slice
intends to change behavior, and those failures are quoted rather than rewritten.

This is an engineering-validated, **provisional** slice. It carries no GCO, institutional, security,
privacy, clinical or UAT approval, and it does not claim any. The work is left uncommitted in the working
tree for review.
