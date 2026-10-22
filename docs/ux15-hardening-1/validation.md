# Validation record

Validation ran locally against the feature worktree and synthetic API fixtures. The local browser UI used `http://127.0.0.1:3123`; this is separate from hosted CI or an institutional backend.

## Frontend checks

From `fe/`:

- `pnpm api:generate` — passed; generated clients were not changed or added to the PR.
- `pnpm test` — **850 passed, 0 failed**.
- `pnpm lint` — passed.
- `pnpm typecheck` — passed.
- `pnpm build` — passed; production build compiled and generated 95 static pages.

From the repository root:

- `git diff --check` — passed before documentation was finalized; it is repeated before commit.

## Focused Chromium and WebKit suites

| Package | Chromium | WebKit |
|---|---:|---:|
| Routine Intake (`ux15-routine-intake.browser.mjs`) | 22/22 | 22/22 |
| Inventory (`ux15-inventory.browser.mjs`) | 13/13 | 13/13 |
| Feedback/CSM (`ux15-feedback-csm.browser.mjs`) | 27/27 | 27/27 |
| Portal Shell reflow matrix (focused existing scenario) | 1/1 | 1/1 |
| Form consolidation Inventory choice targets (320px and 1440px) | 2/2 | 2/2 |

Exact focused suite invocations from `fe/`:

```sh
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UX15_ROUTINE_PHASE=after node tests/ux15-routine-intake.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_BROWSER=webkit COMPASS_UX15_ROUTINE_PHASE=after node tests/ux15-routine-intake.browser.mjs

COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UX15_SCREENSHOTS=after node tests/ux15-inventory.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_BROWSER=webkit COMPASS_UX15_SCREENSHOTS=after node tests/ux15-inventory.browser.mjs

COMPASS_UI_BASE_URL=http://127.0.0.1:3123 node tests/ux15-feedback-csm.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_BROWSER=webkit node tests/ux15-feedback-csm.browser.mjs

COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_CHECK='shell-layout-matrix-320-to-1440-normal-and-200-percent-text' node tests/portal-shell-accessibility.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_CHECK='shell-layout-matrix-320-to-1440-normal-and-200-percent-text' node tests/portal-shell-accessibility.browser.mjs

COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_CHECK='inventory all choice targets' node tests/ux15-consolidation.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_CHECK='inventory all choice targets' node tests/ux15-consolidation.browser.mjs
```

An earlier full Feedback WebKit attempt had one transient failure in the existing browser-back confirmation scenario. Its isolated rerun passed 1/1, and the subsequent complete WebKit suite passed 27/27. The final complete result is the one reported above.

## Package evidence

- Routine scenarios include committed POST/lost response, stale cached DRAFT, fresh canonical submitted or draft, already-submitted conflict, GET 403/404/503, preserved answers, explicit confirmation, and duplicate-operation guards. The fixtures verify client behavior only; they do not prove a deployed database race.
- Inventory measurements cover 320, 360, 390, 768, 1024, and 1440px, at 100% and 200% root text; expanded/collapsed desktop dock; editable and submitted/read-only at the reproduced 1024px/200% case. The before/after geometry and screenshots are in [screenshots](screenshots.md).
- Feedback/CSM scenarios cover lost response, 408/500/503, in-progress reservations, exact body/key replay, key conflict, invalid key, canonical status failure/authorization, submitted flags, duplicate clicks, optional identity, CSM zero, and instrument separation.

No backend files changed, so no backend test suite or migration check was run. Backend transaction, authorization, and idempotency behavior was inspected in source. No hosted CI run is claimed; no CI filters or deployment workflows were changed. Manual assistive-technology, browser-zoom, physical-device, and institutional UAT remain open in [follow-ups](followups.md).
