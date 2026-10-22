# Validation

Validation was run from the isolated `feat/ux15-gss-home` worktree on the `217e1677` integration baseline. Browser suites use intercepted synthetic data; no institutional records were accessed.

## Build and static checks

- `pnpm lint` — passed.
- `pnpm typecheck` — passed.
- `pnpm build` — passed; Next.js compiled, typechecked, and generated all 95 static pages.
- `pnpm api:generate` — passed; no API contract changes were needed.
- `git diff --check` — passed.

## Focused Node tests

The relevant unit and presentation suites passed with Node test concurrency limited to one worker: 37/37 tests across GSS Home, Work Queue, Counselor Home, Student Home, Guidance Operations, and Portal Shell.

Commands, run from `fe/`:

```sh
pnpm exec node --import ./tests/support/register-tsx.mjs --test --test-concurrency=1 tests/ux15-gss-home.test.mjs tests/work-queue.test.mjs tests/ux15-counselor-home.test.mjs tests/ux15-student-home.test.mjs tests/guidance-operations.test.mjs tests/portal-shell.test.mjs
```

The command passed 37/37. Coverage includes capability filtering, backend work order, Manila-date filters, `null` versus zero metrics, and Counselor/GSS separation.

## Browser tests

| Suite | Chromium | WebKit |
| --- | ---: | ---: |
| Guidance Services Staff Home | 16/16 | 16/16 |
| Counselor Home and role regression | 13/13 | 13/13 |
| Student Home and role regression | 39/39 | 39/39 |
| Shared Work Queue | 19/19 | 19/19 |
| Portal Shell accessibility | 6/6 | 6/6 |

Each browser suite was run in both engines from `fe/`:

```sh
pnpm exec node tests/ux15-gss-home.browser.mjs
COMPASS_UI_BROWSER=webkit pnpm exec node tests/ux15-gss-home.browser.mjs
pnpm exec node tests/ux15-counselor-home.browser.mjs
COMPASS_UI_BROWSER=webkit pnpm exec node tests/ux15-counselor-home.browser.mjs
pnpm exec node tests/ux15-student-home.browser.mjs
COMPASS_UI_BROWSER=webkit pnpm exec node tests/ux15-student-home.browser.mjs
pnpm exec node tests/work-queue.browser.mjs
COMPASS_UI_BROWSER=webkit pnpm exec node tests/work-queue.browser.mjs
pnpm exec node tests/portal-shell-accessibility.browser.mjs
COMPASS_UI_BROWSER=webkit pnpm exec node tests/portal-shell-accessibility.browser.mjs
```

The GSS suite checks API request gating and filters, stale and failed reads, account switching, sensitive-purpose exclusion, keyboard focus, touch target size, the collapsed Portal dock, and layouts at 320, 360, 390, 768, 1024, and 1440 CSS pixels. A 320px viewport with a simulated 200% root text size also remained within the viewport; this is a text-size simulation, not browser zoom. Per-engine results and screenshots are linked from [screenshots](screenshots.md).

## Runner note

An earlier multi-file Node run using the default parallel worker setting failed during `@/lib` module resolution before assertions ran. All six relevant suites passed together when rerun with `--test-concurrency=1` (37/37). This runner condition did not affect lint, typecheck, build, or the browser suites.

Hosted GitHub CI was not run or observed during this local validation. Manual screen-reader/browser-zoom review and GCO operational UAT with real College and supervision assignments remain follow-ups; the 200% root-font check is a simulation. Automated checks do not replace those reviews.
