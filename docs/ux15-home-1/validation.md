# Validation record

Executed locally on October 22, 2026, in the isolated `feat/ux15-student-home` worktree.
Node `v26.7.0`, pnpm `11.19.0`, Next.js `16.3.4`, locked Playwright `1.62.1`.
All browser API responses/accounts were synthetic. The harness blocks nonlocal network access
and service workers; no live Student records, provider call or deployed environment was used.

## Final results

| Check | Result |
| --- | --- |
| Focused Node/component tests | **104/104**, including 11 new Home tests |
| Home browser suite | **39/39 Chromium; 39/39 WebKit** |
| Existing Student Actions browser suite | **22/22 Chromium; 22/22 WebKit** |
| Existing Portal Shell accessibility suite | **6/6 Chromium; 6/6 WebKit** |
| Distinct final browser cases | **67 per engine, 134 total** |
| API generation | Passed; no contract/generated-source changes committed |
| Lint | Passed, zero errors/warnings after the focused cleanup |
| Typecheck | Passed |
| Optimized synthetic browser build | Passed; 95 static pages |
| Ordinary optimized build, without test mode | Passed; 95 static pages |
| `git diff --check` | Passed |

## Exact commands

Commands run from `fe/` unless otherwise indicated:

```sh
node --version
pnpm --version
pnpm install --frozen-lockfile
pnpm api:generate

node --import ./tests/support/register-tsx.mjs --test tests/ux15-student-home.test.mjs
# Initial focused check: 11/11.

node --import ./tests/support/register-tsx.mjs --test tests/ux15-student-home.test.mjs tests/student-actions.test.mjs tests/portal-shell.test.mjs tests/portal-command-palette.test.mjs tests/portal-navigation-attention.test.mjs tests/collection-ordering.test.mjs tests/good-moral-preparation.test.mjs tests/exit-interview-workflow.test.mjs tests/account-cache-ownership.test.mjs tests/phase-12-copy.test.mjs
# Final Node selection: 104/104.

pnpm lint && pnpm typecheck
# Final run: zero lint warnings; typecheck passed.

NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 NEXT_TELEMETRY_DISABLED=1 pnpm build
pnpm start --hostname 127.0.0.1 --port 3123
# Optimized local synthetic browser artifact; the existing realtime test seam is compile-time only.

COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=chromium COMPASS_UI_ARTIFACTS=../docs/ux15-home-1/screenshots/after node tests/ux15-student-home.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=chromium COMPASS_UI_ARTIFACTS=/tmp/compass-home-final/chromium node tests/student-actions.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=chromium COMPASS_UI_ARTIFACTS=/tmp/compass-home-final/chromium node tests/portal-shell-accessibility.browser.mjs

COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-home-final/webkit node tests/ux15-student-home.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-home-final/webkit node tests/student-actions.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-home-final/webkit node tests/portal-shell-accessibility.browser.mjs

# Stopped the local synthetic server before rebuilding.
NEXT_TELEMETRY_DISABLED=1 pnpm build
# Ordinary build: no NEXT_PUBLIC_COMPASS_UI_TEST_MODE override, so test seams compile out.
pnpm start --hostname 127.0.0.1 --port 3123
# After the fixture-only contract correction, reran the two Home commands above against this
# ordinary build: 39/39 per engine. No production source changed after either optimized build.

pnpm typecheck
# Passed again after restoring generated next-env.d.ts to its tracked baseline.

git diff --check
git status --short
git diff --stat
```

Next regenerates `next-env.d.ts` imports between development and production type directories.
This generated path-only change was restored to the baseline after validation; it is not part of
the feature. No dependency, lockfile, compiler, lint rule or CI definition was changed.

## Scenario and geometry evidence

Home's 39 cases cover eight paired visual scenarios, all 12 width/text combinations, a new
Current Student Inventory action, exact first-five order and View all navigation, Graduated and
Former reading/action gates, missing capabilities/null summary, independent projection loading
and failure, Retry, stale rows and stale empty results, denial, session expiry, account switching,
Announcement audience-query ownership/order/pins/links, four professional role contexts and
keyboard/focus behavior. Initial rendering and navigation are asserted not to perform mutations.

The Node selection also checks unexpected professional summary sections are excluded from Student
composition, Current/Graduated/Former helper boundaries, exact metric labels/destinations, null
versus zero, original work ordering and account cache ownership. The existing Student Actions suite
verifies shared hints, focus, polling, reconnect, same-tab Message/consent invalidation, pagination
and unchanged full workspace behavior. The Portal Shell suite verifies overlays, dock/drawer,
long identity text and unsaved-form command-palette navigation.

Both engines measured Home at **320, 360, 390, 768, 1024 and 1440px**, each with normal and **200%
root text**. All 12 document widths equal their viewport widths, and each Home panel fits its own
content width. Targets stay inside the viewport, action/discovery targets retain their rem-scaled
44px minimum, and actionable Home links do not overlap. Long unbroken synthetic names/titles are
included. Expanded/collapsed dock contexts are exercised at 1440px.

The original Announcements case was reproduced before source changes: document **328px**,
viewport/header **320px**, root text **32px**. The final case has document/viewport/header **320px**.
Date/title stacking also prevents the former narrow title column. No global clipping or shared
Panel change was used. Existing shell-suite Inventory content overflow at 1024px/200% remains its
documented unrelated exception; it is not a Home regression.

Chromium exercises actual sequential Tab through Home links and Enter navigation. WebKit checks
the same authored DOM order, native focusability, focus ring and keyboard activation directly
because its macOS automation default skips links with Tab. Full Keyboard Access Safari traversal
remains a manual follow-up. No excessive refreshing action-count live region was introduced.

Machine-readable final records:

- [Chromium Home results](screenshots/after/ux15-student-home/results.json), [geometry](screenshots/after/ux15-student-home/geometry.json)
- [WebKit Home results](browser-results/webkit-home-results.json), [geometry](browser-results/webkit-home-geometry.json)
- [Chromium Student Actions](browser-results/chromium-student-actions.json), [WebKit Student Actions](browser-results/webkit-student-actions.json)
- [Chromium Portal Shell](browser-results/chromium-portal-shell-accessibility.json), [WebKit Portal Shell](browser-results/webkit-portal-shell-accessibility.json)

## Baseline/development and focused corrections

```sh
NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 NEXT_TELEMETRY_DISABLED=1 pnpm dev --port 3123
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_HOME_PHASE=before COMPASS_UI_ARTIFACTS=../docs/ux15-home-1/screenshots/before node tests/ux15-student-home.browser.mjs
# 8/8 baseline visual scenarios.
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_ARTIFACTS=../docs/ux15-home-1/screenshots/after node tests/ux15-student-home.browser.mjs
# Initial 8/8 visual review, then focused composition refinement and 8/8 again.
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_ARTIFACTS=/tmp/compass-home-development node tests/ux15-student-home.browser.mjs
# Development Chromium: 39/39.
COMPASS_UI_BASE_URL=http://localhost:3123 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-home-development-webkit node tests/ux15-student-home.browser.mjs
# Development WebKit: 39/39.

# Final matched baseline recapture in a temporary managed worktree at the exact integration SHA:
# /Users/reynantlntno/.codex/worktrees/ux15-home-baseline/COMPASS/fe
pnpm install --frozen-lockfile
pnpm api:generate
NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 NEXT_TELEMETRY_DISABLED=1 pnpm dev --hostname 127.0.0.1 --port 3124
COMPASS_UI_BASE_URL=http://localhost:3124 COMPASS_HOME_PHASE=before COMPASS_UI_ARTIFACTS=/Users/reynantlntno/.codex/worktrees/ux15-student-home/COMPASS/docs/ux15-home-1/screenshots/before node tests/ux15-student-home.browser.mjs
# 8/8 matched baseline cases using the final contract-corrected fixtures; application sources untouched.
```

The first baseline attempt used an incorrect synthetic Announcement endpoint fixture. It was
interrupted, corrected to the actual generated `/api/v1/announcements` route, then rerun successfully
before production-source changes. It was a harness setup error, not a product failure. An unused
test import produced one initial lint warning; it was removed and the final lint/typecheck run
passed. Visual review corrected excess empty-state whitespace before final captures. A final
domain-helper check corrected the audit's description of Good Moral counts (REQUESTED plus
READY_FOR_ISSUANCE) and the synthetic lifecycle fixtures (non-Current Routine draft count null,
matching source capabilities). Matched baseline/final captures and affected checks were rerun;
no application metric computation changed. No final
Node, browser, lint, typecheck or build failure remains; no unrelated full suite was repeated.

## Local versus hosted validation and remaining manual work

The inspected Actions definitions automatically target only `staging` and
`canon/compass-clean-baseline`; they exclude a PR targeting `integration/ux15-modernization`.
Local success must not be reported as hosted CI approval. The new browser suite is picked up by
the existing filename-based runner when those workflows apply. No CI definition was changed and
no workflow was dispatched. `deploy-staging.yml` is manual-only and requires the exact current
staging SHA. No staging/main update, merge or deployment was performed. External hosting-account
webhook settings were not inspected; no deployment command or hosting API was invoked.

Root-font enlargement is not browser zoom. Actual browser zoom, screen-reader speech, physical
device/Safari Full Keyboard Access and institutional UAT remain manual verification. Automated
checks establish neither WCAG certification nor release approval. Backend models, authorization,
encryption, persistence and APIs are unchanged; these synthetic frontend tests do not establish
live-backend enforcement. See [followups.md](followups.md).
