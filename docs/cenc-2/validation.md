# CENC-2 — Validation evidence

**Dates:** implemented and validated 2026-11-05 → 2026-11-06 (the session spans midnight)
**Working tree:** uncommitted on `integration/ux15-modernization` at `22675506`
**Environment:** Django 6.1, Django Ninja, PostgreSQL 17, `uv`; Next.js App Router, React, strict
TypeScript, pnpm, Orval, TanStack Query; `DJANGO_SETTINGS_MODULE=tests.settings`
**Commands run from:** `/Users/reynantlntno/Projects/COMPASS/be` and `/Users/reynantlntno/Projects/COMPASS/fe`

Only the slice's targeted checks were run. CENC-2 is not the final CENC slice, so the full backend
and full frontend regression suites were deliberately **not** run (see §6).

## 1. Start-state gate

```bash
git log -1 --format='%H %s'
git status --short
```

`22675506 Add CENC-1 atomic counseling appointment finish`, matching the expected HEAD. The only
pre-existing uncommitted entry was the untracked `outputs/paper-screenshots/`, which this slice did
not touch, clean, stash, reset or revert. No unrelated work existed in `be/`, `fe/` or
`contracts/openapi.json` before editing.

## 2. Targeted test commands and final results

### Backend

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest \
  tests/test_counseling_context.py tests/test_counseling_finish.py \
  tests/test_openapi_contract.py -q
```

**Final result:** `97 passed in 146.62s (0:02:26)`. An identical run earlier in the slice reported
`97 passed in 153.92s (0:02:33)`; the count is stable, only wall time differs.

| File | Result |
|---|---|
| `tests/test_counseling_context.py` | Passed — includes new `test_detail_projects_whether_the_appointment_encounter_is_recorded` (§4.4 cases 1–8) |
| `tests/test_counseling_finish.py` | Passed — includes new `test_detail_projects_the_encounter_recorded_by_a_finish`; CENC-1 finish behavior and lock order unchanged |
| `tests/test_openapi_contract.py` | Passed — includes new `test_appointment_detail_encounter_record_projection_openapi_contract` |

Focused first-pass runs used while writing the projection tests:

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest tests/test_counseling_context.py -q -k "encounter_is_recorded"
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest tests/test_counseling_context.py tests/test_counseling_finish.py -q -k "recorded or projection"
```

**Results:** `1 passed, 30 deselected in 13.31s` and `2 passed, 52 deselected in 13.89s`.

### Frontend

Client regeneration (feeds every query key and model type used by the new modules):

```bash
pnpm api:generate
```

New behavior suite:

```bash
node --import ./tests/support/register-tsx.mjs --test tests/counseling-finish.test.mjs
```

**First run result:** `tests 9 / pass 9 / fail 0` — `duration_ms 1888.778`. It passed the first time;
no production behavior was changed to satisfy a test.

Targeted counseling regression set (Finish suite plus the three existing files whose rendered
surfaces CENC-2 modified):

```bash
node --import ./tests/support/register-tsx.mjs --test \
  tests/counseling-finish.test.mjs \
  tests/counseling-context-confidentiality.test.mjs \
  tests/counseling-online-delivery.test.mjs \
  tests/counseling-encounter-consistency.test.mjs
```

**Final result:** `tests 45 / pass 45 / fail 0`. Run twice — once before and once after the dialog
restructure in §3.1 — with the same 45/45/0 both times.

## 3. First-run failures and resolutions

This was not a clean first run. Three issues appeared on first execution, all in static or tooling
checks and one of them a build side effect; none was a behavioral test failure.

### 3.1 `pnpm lint` — 1 error, 1 warning

```
src/features/counseling/finish-counseling-dialog.tsx
   7:10  warning  'Label' is defined but never used          @typescript-eslint/no-unused-vars
  70:5   error    Calling setState synchronously within an effect can trigger cascading renders
                 react-hooks/set-state-in-effect
✖ 2 problems (1 error, 1 warning)
[ELIFECYCLE] Command failed with exit code 1.
```

The error came from a `useEffect(() => { if (open) return; setUncertain(false); setChecking(false);
setStillUnconfirmed(false); setAttempted(false); }, [open])` used to reset dialog flags on close.

**Resolution:** deleted the effect and the `useEffect`/`Label` imports, and moved the same flag resets
into a `changeOpen(next)` handler wired to `<Dialog onOpenChange>`, `Cancel` and the uncertain-state
`Close`. Clearing `uncertain` now happens inside `checkAgain()` when the recheck confirms the record.
Reset semantics are unchanged; the state update now happens in an event handler instead of an effect.
Second `pnpm lint` run: clean.

### 3.2 `uv run ruff format --check` on the two modified backend test files

```
unformatted: File would be reformatted  --> tests/test_counseling_context.py:1076:16
unformatted: File would be reformatted  --> tests/test_counseling_context.py:1097:12
unformatted: File would be reformatted  --> tests/test_counseling_finish.py:821:12
```

Hand-wrapped multi-line `assert ( appointment_encounter_recorded(...) is None )` forms.

**Resolution:** `uv run ruff format tests/test_counseling_context.py tests/test_counseling_finish.py`
→ `2 files reformatted`; `ruff check` then `All checks passed!` and the tests re-ran green in §2. No
assertion, case or message changed — only line wrapping.

### 3.3 `pnpm build` side effect on `fe/next-env.d.ts`

`pnpm build` rewrote the generated reference lines from `./.next/dev/types/…` to `./.next/types/…`.
That churn is a build artifact, not CENC-2 work.

**Resolution:** restored the file with `git checkout -- fe/next-env.d.ts` so the review diff stays
slice-only. `next-env.d.ts` is not in the CENC-2 file list.

### 3.4 Working-tree reconciliations caught by inspection (not test failures)

- A short-lived `actionState` helper plus `AppointmentActionStateResponse` import was added to
  `appointment-detail-page.tsx`, then removed; `displayedUnavailable` filtering replaced it. Keeping
  it would have been dead code and an unused-import lint error.
- `unconfirmedFinishMessage` was initially concatenated with extra guidance in the dialog, which
  would have made the DOM disagree with the §6 copy inventory. The extra sentence was removed.
- `docs/cenc-2/implementation.md` first cited `finish-counseling-availability.ts:11`; the exported
  `finishCounselingState` is at `:10`. Verified against the file and corrected.

## 4. Contract and migration checks

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
  --output ../contracts/openapi.json
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
  --check --output ../contracts/openapi.json
```

**Result:** `OpenAPI contract is current: ../contracts/openapi.json`, exit 0. The artifact was
regenerated by the command above and never hand-edited.

**Contract diff summary:** `13 insertions(+), 1 deletion(-)`, single hunk — the new
`counseling_encounter_recorded` property on `AppointmentDetailResponse`, typed as a
`boolean`/`null` `anyOf`, plus its entry in the required list (the property is always present; `null`
means "not exposed to this viewer"). No new path, operation, request schema, response schema, error
code or enum was added. The `counselingFinishAppointment` operation from CENC-1 is unchanged.

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run
```

**Result:** `No changes detected`, exit 0. As expected: CENC-2 adds a read-only projection, no model,
field, constraint or migration.

## 5. Static checks

```bash
uv run ruff check compass/counseling/services.py compass/appointments/api.py \
  tests/test_counseling_context.py tests/test_counseling_finish.py tests/test_openapi_contract.py
uv run ruff format --check compass/counseling/services.py compass/appointments/api.py \
  tests/test_counseling_context.py tests/test_counseling_finish.py tests/test_openapi_contract.py
```

**Result:** `All checks passed!` and `5 files already formatted`.

```bash
uv run ruff check .
```

**Result:** exit 1 with 4 errors, all pre-existing in files CENC-2 did not touch, and all left as-is
rather than "fixed" inside this slice:

| Location | Rule |
|---|---|
| `compass/referrals/provisional_activation.py:334` | `E501` line too long (111 > 100) |
| `tests/test_fup3a_faculty_referral_journey.py:7` | `I001` import block un-sorted |
| `tests/test_guidance_followups.py:464` | `E501` line too long |
| `tests/test_guidance_followups.py:565` | `E501` line too long |

```bash
pnpm lint          # exit 1 first run (§3.1), clean second run
pnpm typecheck     # $ tsc --noEmit — clean, no errors
pnpm build         # exit 0
```

`pnpm typecheck` passing with zero `TS` errors matters here: the projection is
`boolean | null` in the generated model, the refresh module indexes generated query keys, and neither
uses `any` or `@ts-ignore`.

## 6. Deliberately not run

| Item | Why |
|---|---|
| Full backend regression suite | The CENC-2 prompt states CENC-2 is not the final CENC slice and forbids full-suite runs; reserved for the last CENC slice |
| Full frontend regression suite | Same instruction; only the four files whose rendered surfaces changed were run |
| Browser/E2E and visual regression tests | Not part of this slice's validation scope; no screenshot or `outputs/paper-screenshots/` work was performed |
| UAT, GCO review, institutional/security/privacy/clinical sign-off | Not run and not claimed. D-CENC-01/05/06/07/08/10/18 ship as provisional engineering decisions |
| Accessibility audit beyond the emitted `role="alert"`/`role="status"`, `aria-invalid`, focus restore and disabled-state markup | No automated a11y tool was run |
| Load/performance profiling of the projection | The per-viewer extra work is one indexed `.exists()` query behind the existing relationship gate |
| `makemigrations` without `--check --dry-run` | Forbidden; no migration is intended |
| Commit, push, amend, rebase, branch creation | Forbidden unless explicitly asked — none performed |

## 7. Guardrail compliance evidence

| Guardrail | Evidence |
|---|---|
| No feature flag / toggle / provisional-gating env var | No setting or capability added; `grep` of the diff for flag identifiers is empty; route and projection always registered |
| No migration, persisted documentation status, Needs-documentation worklist | §4 `No changes detected`; no model field added |
| CENC-1 finish behavior, lock order, audits, Feedback, notifications unchanged | `be/compass/counseling/finish_service.py` and `be/compass/counseling/api.py` absent from `git diff --numstat`; the 22 finish tests and 10 concurrency tests still pass inside §2 |
| No auto-replay of an uncertain Finish | Dialog offers only "Check again"; the uncertain branch never re-issues `mutateAsync`; asserted by the render tests |
| Actual times never prefilled from the schedule | Dialog initializes `startedAt`/`endedAt` to `""`; the four-fact `<dl>` shows the schedule as reference only |
| `counseling_encounter_recorded` not exposed beyond the provider | Projection returns `None` for non-canonical/inactive/non-COUNSELOR/non-provider/no-view; §4.4 cases 2–4 covered by the context test |
| Finish hidden without `counseling.manage_assigned` **and** `appointments.manage` | `canFinishCounseling` conjunction; `finishCounselingState` returns `NOT_AVAILABLE` without it |
| E-Counseling workspaces, direct recording, Routine workspaces untouched | No such file appears in the diff |
| No hand-editing `fe/src/lib/api/generated/**` or `contracts/openapi.json` | Generated by `pnpm api:generate` / `export_openapi`; generated client is gitignored |
| No `any`, no `@ts-ignore` | `pnpm typecheck` clean; not present in the new modules |
| `docs/cenc-0/` and `docs/cenc-1/` unmodified | Only `docs/cenc-2/` appears as new in `git status` |
| Worktree left for review | §8; nothing cleaned, stashed, reset or reverted except the self-inflicted `next-env.d.ts` artifact |

## 8. Working tree evidence

```bash
git diff --numstat
```

```
8	0	be/compass/appointments/api.py
33	0	be/compass/counseling/services.py
110	2	be/tests/test_counseling_context.py
28	0	be/tests/test_counseling_finish.py
11	0	be/tests/test_openapi_contract.py
13	1	contracts/openapi.json
90	8	fe/src/features/appointments/appointment-detail-page.tsx
4	0	fe/src/features/counseling/counseling-shared.tsx
95	1	fe/src/features/counseling/counseling-workspace.tsx
1	0	fe/tests/counseling-online-delivery.test.mjs
```

New untracked files: `fe/src/features/counseling/finish-counseling-availability.ts` (52 lines),
`finish-counseling-refresh.ts` (72), `finish-counseling-dialog.tsx` (234),
`fe/tests/counseling-finish.test.mjs` (188), `docs/cenc-2/` (3 files). The pre-existing untracked
`outputs/paper-screenshots/` remains untouched.

Modified + new totals: **393 insertions, 12 deletions** across the ten tracked files, plus **546
lines** of new source and test files.

## 9. Conclusion

Targeted evidence is green: 97 backend tests, 45 frontend tests (9 of them new Finish cases passing on
first run), a current OpenAPI artifact differing only by the single nullable projection property, an
empty migration check, clean ruff and eslint on every changed file, clean `tsc --noEmit`, and a
successful production build. The three first-run failures — the `react-hooks/set-state-in-effect`
error, the two ruff-format reflows, and the build's `next-env.d.ts` churn — were all tooling-level and
are recorded above rather than smoothed over. Nothing was committed or pushed, and no approval is
claimed for the provisional decisions.
