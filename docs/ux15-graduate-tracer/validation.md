# Focused validation

All browser reads/writes use the local harness with synthetic records and blocked external API/
provider requests. No live Student/Graduate record, backend test suite, full frontend suite,
workflow dispatch, deployment or merge is involved.

| Check | Executed result |
| --- | --- |
| `pnpm install --offline --frozen-lockfile` | Passed; pinned dependencies, unchanged lockfile |
| `pnpm api:generate` | Passed against unchanged contract; generated outputs uncommitted |
| `pnpm lint` | Passed; final full lint after visual spacing fix |
| `pnpm typecheck` | Passed; final check after visual spacing fix |
| `pnpm build` | Passed; final production build after visual spacing fix |
| Focused unit files below | 35/35 passed |
| Existing Graduate Tracer confidentiality unit check | 1/1 passed |
| New Graduate Tracer UX browser suite | 26 distinct scenarios have passing results per engine (52 total); initial runs plus affected reruns, detailed below |
| Existing pinned-column reachability regression | 2/2 per engine at 320/390px |
| Existing Graduate Tracer confidentiality browser checks | 2/2 per engine at 320/1440px |
| Baseline capture scenarios | 3/3, exact integration archive under Next dev |
| `git diff --check` | Passed |

There are **60 distinct implementation/neighbor browser scenarios with passing results**, 30 per
engine. Baseline capture checks and repeated checks are not added to that count. There are **36
unit checks**. These are local fixture results, not live-backend, institutional or production acceptance.

## Commands

From `fe/` in the isolated worktree:

```sh
pnpm install --offline --frozen-lockfile
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
node --import ./tests/support/register-tsx.mjs --test \
  tests/ux15-graduate-tracer.test.mjs tests/form-ui-1b.test.mjs tests/page-header-contract.test.mjs
node --import ./tests/support/register-tsx.mjs --test --test-name-pattern='Graduate Tracer' tests/user-copy.test.mjs
pnpm start --port 3127
```

Browser commands, run separately for each `COMPASS_UI_BROWSER=chromium` / `webkit`:

```sh
COMPASS_UI_BROWSER=chromium COMPASS_UI_BASE_URL=http://localhost:3127 \
  node tests/ux15-graduate-tracer.browser.mjs
COMPASS_UI_BROWSER=chromium COMPASS_UI_BASE_URL=http://localhost:3127 \
  COMPASS_UI_CHECK='tracer-answer-columns-reachable' node tests/ux-hardening.browser.mjs
COMPASS_UI_BROWSER=chromium COMPASS_UI_BASE_URL=http://localhost:3127 \
  COMPASS_UI_CHECK='graduate-tracer-confidentiality' node tests/user-copy.browser.mjs
```

`COMPASS_UI_ARTIFACTS` selects an isolated evidence folder. The runner discovers the new `.browser.mjs`
suite automatically. Do not run all browser suites for this pilot. For the baseline, archive exact
`132be02d`, install/generate its dependencies, run Next dev on port 3128, and invoke this same new
suite with `COMPASS_UX15_TRACER_PHASE=before COMPASS_UI_BASE_URL=http://localhost:3128`.
Only the three shared capture scenarios run in baseline mode.

## Passing behaviors

- Five links in original order; keyboard Enter focuses each original named section below the portal
  header; all controls stay mounted and navigation sends no mutation. Back to sections restores focus.
- Responsive form/navigation at 1440, 1920, 768, 390 and 320px, plus 200% root text. Named matrix
  regions handle local keyboard scroll; native radio arrows and checkbox Space remain native;
  touch labels are at least 44 × 44px. Existing regressions reach both complete answer columns.
- Explicit partial save succeeds without final answers. Invalid draft degree/training rows block
  replacement; summaries navigate to original fields with existing error descriptions. Draft/email
  and final issues deduplicate; optional feedback/contact answers do not acquire new requiredness.
- Save failure (500 and network) and conflict (409) retain unsaved input and block submission.
  Pending save disables inputs/actions and navigation never saves. A differing canonical response
  updates the editor only after confirmed persistence; reload returns that saved draft.
- College → Program filtering clears incompatible selected programs. Degree/training/exam add,
  edit and remove retain row identity and values, and internal keys never enter payloads.
- Self-employed skills, first-job/related-course conditions, Other answers, not-employed,
  never-employed and employed transitions use existing normalization. Inactive answers are absent
  from saved payloads and hidden employed fields do not become validation destinations.
- Matrix validation links focus the original first/current job radios and preserve their existing
  error descriptions; one active radio group per column and original values remain.
- Confirmation Cancel sends nothing; pending submit cannot repeat or dismiss. Confirmed submission
  becomes read-only. Uncertain committed success reconciles to read-only; an unchanged canonical
  draft requires deliberate resubmission. Failed canonical check blocks submission until a status
  check confirms Draft; checking itself sends no submission. No replacement save is added to submit.
- Dirty internal route navigation, browser Back and native beforeunload keep their existing guard;
  declining keeps input, confirmed save permits navigation.
- Existing GRADUATED/capability boundaries, restricted accounts, read-only draft/submitted responses,
  disposed responses and historical summary-to-ID compatibility retain their behavior.
- Existing Inventory default summary and Exit Interview field-limit regressions pass in the focused
  unit files; no shared component source is changed.

## Investigation and reruns

The initial Chromium UX run passed 20/25. Five layout cases found that enlarged matrix label wrappers
were missing; correcting the wrappers passed the affected 5/5 rerun. WebKit then passed 25/25.
The existing reachability regression initially failed 0/2 in each engine because a narrow automatic
answer column exceeded the free space beside the pinned label. The narrow fixed table layout
corrected that: 2/2 passed in each engine. After that change, affected UX navigation/reflow cases
passed 5/5 per engine, and a new matrix error-focus case passed 1/1 per engine, bringing the new
suite inventory to 26. Chromium's representative captures were refreshed.

Visual inspection then caught adjacent Review answers/Back to sections links. A wrapping action row
corrected their spacing. Final affected reflow/navigation and visual checks were rerun after the final
production build: Chromium 8/8 (five layouts and three capture scenarios), WebKit 5/5
(the affected layouts). Final lint, typecheck and build passed. Unrelated suites were not rerun.

Browser geometry checks and inspected screenshots support responsive/accessibility behavior, but
manual screen-reader, real-device Safari and Guidance Office UAT remain unexecuted. The pre-existing
320px/200% portal top bar remains outside this form-scoped change. No layout is hidden to mask it.
