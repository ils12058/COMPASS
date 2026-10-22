# Validation record

All browser accounts and API responses were synthetic. Browser tests used the local app at `http://localhost:3117`; no live COMPASS records or providers were contacted.

The focused Portal Shell suite passed 6/6 checks in Chromium and 6/6 in WebKit:

- `shell-layout-matrix-320-to-1440-normal-and-200-percent-text`
- `student-home-shell-context-at-320px-200-percent-text`
- `header-actions-drawer-overlays-account-and-notifications`
- `counselor-mobile-drawer-long-navigation-scrolls`
- `counselor-workspace-desktop-dock-expanded-and-collapsed`
- `command-palette-keeps-unsaved-form-navigation-guard`

The active-call sign-out safeguard passed 1/1 in each engine. Existing Portal Shell, Command Palette, navigation, and navigation-attention Node tests passed 38/38.

The commands and results were:

```sh
# Existing focused Node/component regressions
node --import ./tests/support/register-tsx.mjs --test tests/portal-shell.test.mjs tests/portal-command-palette.test.mjs tests/portal-navigation-attention.test.mjs
# 38/38 passed

# New synthetic shell suite; artifact output includes the after screenshots and measurements
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=chromium COMPASS_UI_ARTIFACTS=/Users/reynantlntno/.codex/worktrees/ux15-portal-accessibility/COMPASS/docs/ux15-accessibility-1/screenshots/after node tests/portal-shell-accessibility.browser.mjs
# 6/6 passed
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/ux15-portal-shell-webkit-final-rerun2 node tests/portal-shell-accessibility.browser.mjs
# 6/6 passed

# Active-call sign-out safeguard
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=chromium COMPASS_UI_CHECK='sign-out-ends-call-after-confirmation' COMPASS_UI_ARTIFACTS=/tmp/ux15-portal-signout-chromium node tests/ecounseling-runtime.browser.mjs
# 1/1 passed
COMPASS_UI_BASE_URL=http://localhost:3117 COMPASS_UI_BROWSER=webkit COMPASS_UI_CHECK='sign-out-ends-call-after-confirmation' COMPASS_UI_ARTIFACTS=/tmp/ux15-portal-signout-webkit node tests/ecounseling-runtime.browser.mjs
# 1/1 passed

pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
git diff --check
```

`pnpm api:generate`, `pnpm lint`, `pnpm typecheck`, `pnpm build`, and `git diff --check` completed successfully. No API contract change was made; API generation was run as a consistency check. The optimized Next.js build generated all 95 static pages successfully.

The measurements intentionally distinguish the shared shell from page content. At 1024px / 200% root text, the expanded desktop dock leaves a 512px header region and the header’s own `scrollWidth` is 512px. The Student Inventory page has a separate 1,223px document width in that case; the main form content causes that spill and is outside this shell slice. At 320px / 200%, the Student Home page has a separate 328px document width while its header remains 320px wide; the Announcements heading is the content source. Both findings are recorded in [followups.md](followups.md).

The repository workflow filters were inspected. `frontend-targeted.yml` and the backend targeted/full workflows run automatically only for `staging` and `canon/compass-clean-baseline`; a PR targeting `integration/ux15-modernization` is outside those automatic filters. The deployment workflow is manually dispatched from `staging`. No deployment workflow was dispatched, and no staging or main branch was modified.
