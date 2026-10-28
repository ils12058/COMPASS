# Targeted validation

All records, accounts and mutations are synthetic and local. No full frontend/backend suite runs.
The integration-targeted PR is excluded by existing hosted CI branch filters; no manual workflow
is dispatched to work around that. The results below come from this isolated implementation.

| Check | Result |
| --- | --- |
| Pinned offline install, `pnpm api:generate` against unchanged contract | Passed |
| `pnpm lint` | Passed, no warnings |
| `pnpm typecheck` | Passed |
| Focused unit checks listed below | 58/58 passed |
| `pnpm build` | Passed; rebuilt after the keyboard fix |
| New UX suite — Chromium / WebKit | 15 scenarios passed per engine; WebKit needed the focused narrow-phone rerun described below |
| Existing correction/reopen suite — Chromium / WebKit | 13/13 per engine |
| Existing field-limit / form guidance suite — Chromium / WebKit | 6/6 per engine |
| Existing Exit draft refresh-retention check — Chromium / WebKit | 1/1 per engine |
| `git diff --check` | Passed |

The 70 unique browser scenarios have passing results: 35 per engine. Chromium's new UX suite
passed 15/15. WebKit initially passed 14/15; the remaining narrow-phone keyboard-scroll check
was fixed in the local matrix region handler and passed a focused 1/1 production rerun.
That focused check also passed in Chromium and now verifies native radio-group arrow selection.
The remaining WebKit suites ran after the fix. Unit checks were rerun after the final change;
full lint passed earlier and the changed matrix file passed focused lint again after the fix.

## Reproduce

From `fe/`:

```sh
pnpm install --offline --frozen-lockfile
pnpm api:generate
pnpm lint
pnpm typecheck
node --import ./tests/support/register-tsx.mjs --test \
  tests/exit-interview-workflow.test.mjs \
  tests/form-corr-1-exit-interview.test.mjs \
  tests/form-ui-1b.test.mjs \
  tests/page-header-contract.test.mjs
pnpm build
pnpm start --port 3119
```

From another terminal in `fe/`, run each browser suite once per engine:

```sh
COMPASS_UI_BASE_URL=http://localhost:3119 node tests/ux15-exit-interview.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3119 node tests/form-corr-1-exit-interview.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3119 node tests/form-ui-1b.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3119 COMPASS_UI_CHECK=exit-interview-draft-survives node tests/draft-and-session-safety.browser.mjs
```

Repeat these commands with `COMPASS_UI_BROWSER=webkit` added. The shared harness blocks external
requests and supplies synthetic API responses; it also fails checks on browser runtime errors.
`COMPASS_UI_ARTIFACTS` sets the evidence folder. The existing suite runner discovers the new
`.browser.mjs` file automatically, without a workflow configuration change.

## Behavioral coverage

- All five official groups stay mounted in the same order. In-page links and Back to sections
  move keyboard focus with a header offset; they do not write, hide answers or change dirty state.
- Wide desktop 1920px, normal desktop 1440px, tablet 768px, phone 390px and narrow phone 320px
  are exercised. Whole-page overflow is checked at default text size. At 200% root text, form and
  navigator reflow are checked independently of the existing global top-bar limitation. Matrices
  retain intentional local scrolling; their scroll regions support keyboard access and each
  choice has a 44px minimum label target at default text size.
- Missing ratings navigate to the original row/control; the focused radio is described by the
  inline error. Ratings of 0 remain answered, are saved as 0, and acquire no new meaning.
- The existing positive-whole-number check for delayed extra terms still focuses its field and
  prevents the save. The shared summary also links to it. Native conditional requiredness still
  prevents final confirmation when a required Other answer is absent; no validation rule is
  reimplemented in the shared layer.
- Failed save preserves input/dirty status. Pending save disables conflicting actions and inputs;
  confirmed save displays the server-confirmed result. Section links never silently save.
- Confirmation Cancel sends nothing. Pending submission disables repeat submission. A confirmed
  submission becomes read-only. Both a committed-but-unconfirmed submission and an unchanged
  draft after a transport failure are reconciled through Refresh Exit Interview. Failed refresh
  keeps writes blocked. Refresh itself sends no submit; retry requires deliberate confirmation
  only after the canonical response is confirmed still a draft.
- Dirty Back links, browser Back and native beforeunload/tab-close retain the existing warnings.
  Declining keeps the answers; a confirmed save permits leaving without another warning.
- Existing correction tests cover targeted text, conditional parent fallback, selected rating,
  section hints, historical events, legacy Program Chair fields, advisory targets and successful
  resubmission. The new suite also follows a hidden target, reveals its owning field, and mixes
  section links with correction focus without reinterpreting an answer as invalid.
- Existing field/guidance regressions preserve F9/legacy limits, whole overlong saved values,
  original option labels, submission, and Inventory's default shared-summary wording/focus.
  Transient Exit Interview refresh failure still keeps the draft and blocks writes appropriately.

## Investigation and review limits

During development, screenshot review found a squeezed mobile question column after target
sizes increased; minimum/capped question widths corrected it. An existing legacy-correction
check caught a collision between a new review heading ID and the correction-hint suffix; the
new heading ID was changed and the focused failure passed. Two new test assumptions were
corrected: a tablet matrix need not overflow when it fits, and a pending Save button is named
Saving while disabled. Focused reruns passed. Production WebKit then reproduced a failure of
native ArrowRight scrolling on a focused 320px matrix region. The form now handles unmodified
Left/Right only when the region itself has focus, leaves modified shortcuts alone, and leaves
radio-group arrow selection native. The focused production check passed in both engines after
rebuilding; unrelated suites were not repeatedly rerun.

Automated Chromium/WebKit and viewport emulation are not manual screen-reader, real-device Safari
or GCO UAT. Those have not been executed. The existing top bar at 320px/200% text remains a separate
accessibility issue. No live institutional data, backend tests, merge or deployment is involved.
