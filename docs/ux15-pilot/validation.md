# Targeted validation — October 21, 2026

Checks were rerun in the isolated `feat/ux15-form-foundation` worktree based on
`integration/ux15-modernization`; the application source matches the previously validated pilot. No full frontend/backend test suite ran.
Browser checks used the production Next build on localhost:3117, with synthetic API fixtures
and outbound provider/API access blocked by the shared harness.

| Check | Result |
| --- | --- |
| `pnpm install --offline --frozen-lockfile` | Passed; existing pinned dependencies, no lockfile change |
| `pnpm api:generate` | Passed against unchanged `contracts/openapi.json`; generated outputs remain uncommitted |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm build` | Passed |
| Focused unit tests below | 69/69 passed |
| `ux15-inventory.browser.mjs` — Chromium | 10/10 passed |
| `ux15-inventory.browser.mjs` — WebKit | 10/10 passed |
| `form-corr-1-inventory.browser.mjs` — Chromium | 13/13 passed |
| `form-corr-1-inventory.browser.mjs` — WebKit | 13/13 passed |
| `form-ui-1b.browser.mjs`, filtered to Inventory — Chromium | 1/1 passed |
| `draft-and-session-safety.browser.mjs`, filtered to `inventory-draft-survives` — Chromium | 1/1 passed |
| `git diff --check` | Passed |

## Reproduce

From `fe/`, with the pinned dependencies installed:

```sh
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
node --import ./tests/support/register-tsx.mjs --test \
  tests/form-corr-1-inventory.test.mjs \
  tests/form-input-standardization.test.mjs \
  tests/form-ui-1b.test.mjs \
  tests/routine-inventory-decoupling.test.mjs \
  tests/page-header-contract.test.mjs
pnpm start --port 3117
```

In another terminal, from `fe/`:

```sh
COMPASS_UI_BASE_URL=http://localhost:3117 node tests/ux15-inventory.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=webkit node tests/ux15-inventory.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3117 node tests/form-corr-1-inventory.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=webkit node tests/form-corr-1-inventory.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_CHECK=Inventory node tests/form-ui-1b.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_CHECK=inventory-draft-survives node tests/draft-and-session-safety.browser.mjs
```

The existing browser-suite discovery includes the new suite. However, the current GitHub
Actions PR branch filters exclude `integration/ux15-modernization`, so this PR relies on the
focused local validation reported here. No workflow was dispatched and no CI/deployment
configuration was changed. See [the workflow audit](integration-safety.md).
`COMPASS_UI_ARTIFACTS` can select an evidence directory. `COMPASS_UX15_SCREENSHOTS=before`
selects the two baseline screenshot scenarios and must be run on the original base editor
for a genuine baseline. Committed before captures came from that base under Next dev;
committed after captures came from the final production build. Both use the same synthetic
record, viewport and fonts.

## Regression evidence

- Free jumps, Back and Continue retain local edits without any write. Review is reachable
  without completing preceding sections; returning to an answer uses the original input.
- Save progress and Save & continue retain the existing manual persistence distinction.
  A failed save preserves values, dirty feedback and current section. Pending saves disable
  inputs and conflicting actions; a successful save includes the edited value and advances
  only when the user requested Save & continue.
- A named error summary supports keyboard selection, opens the original section and focuses
  the invalid input. Existing inline error associations and correction fallbacks remain tested.
- Submission requires a saved, valid draft and a separate confirmation. Cancel does not
  submit. Pending confirmation disables duplicate submission; confirmed success leaves the
  editor for the existing read-only presentation.
- Dirty sidebar navigation and browser Back ask before discard. Declining keeps answers.
  Native beforeunload/tab-close protection is exercised; confirmed saved work leaves without
  another warning.
- Whole-page overflow checks cover all nine sections at 1440px and 320px, plus personal/review
  at 390px. Field columns reflow with 200% root text; this assertion is scoped to the Inventory
  form because the unchanged global top bar overflows at 320px/200% text.
- Existing correction regressions cover staff target selection, target limits, pending/failure,
  view-only access, desktop/phone target navigation, keyboard focus, hidden-field fallbacks,
  advisory targets that never block resubmission, legacy reason-only corrections, and historical
  draft display. Unit checks retain payload normalization, requiredness, policy and snapshot
  boundaries. A transient refresh failure still preserves the draft.

## Review limits

Visual inspection covers the committed desktop/phone before-and-after captures and synthetic
browser flows. Automated WebKit is not a manual Safari or screen-reader UAT claim. No live
Student, confidential answer, credential or institutional record was used. Team review remains
required before rollout; this work does not merge or deploy the pilot.
