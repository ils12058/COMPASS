# Final Validation Record

## Environment and commands

All frontend commands ran in the isolated `audit/ux15-final-consolidation` worktree using the
lockfile-pinned pnpm 11.19.0 and synthetic browser fixtures. Dependencies were installed from the
local store with `pnpm install --offline --frozen-lockfile`; no lockfile changed.

From `fe/`:

```sh
pnpm install --offline --frozen-lockfile
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
pnpm exec node --import ./tests/support/register-tsx.mjs --test --test-concurrency=1 tests/*.test.mjs
```

Results:

| Check | Result |
| --- | --- |
| API generation | Passed; unchanged OpenAPI, no generated files committed |
| ESLint | Passed |
| TypeScript | Passed |
| Ordinary optimized production build | Passed; 95 static pages generated |
| Full single-worker Node/component test inventory | 862 passed, 0 failed |
| `git diff --cached --check` | Passed after all 14 final PR files were staged |

The full Node suite used `--test-concurrency=1`, as documented for this repository after a prior
multi-file module-resolution issue. Its test of the browser runner deliberately simulates a failed
suite and an interrupted suite; those are assertions inside passing Node tests, not failed real
browser runs.

## Synthetic browser results

Each suite used local Next pages, synthetic accounts and intercepted API responses. The harness
blocks nonlocal requests and service workers. Thirteen suites were run in Chromium and WebKit:

| Suite | Chromium | WebKit |
| --- | ---: | ---: |
| `ux15-inventory.browser.mjs` | 13/13 | 13/13 |
| `ux15-exit-interview.browser.mjs` | 15/15 | 15/15 |
| `ux15-graduate-tracer.browser.mjs` | 26/26 | 26/26 |
| `ux15-routine-intake.browser.mjs` | 22/22 | 22/22 |
| `ux15-counselor-evaluation.browser.mjs` | 18/18 | 18/18 |
| `ux15-feedback-csm.browser.mjs` | 27/27 | 27/27 |
| `ux15-consolidation.browser.mjs` | 61/61 | 61/61 |
| `ux15-student-home.browser.mjs` | 39/39 | 39/39 |
| `ux15-counselor-home.browser.mjs` | 13/13 | 13/13 |
| `ux15-gss-home.browser.mjs` | 16/16 | 16/16 |
| `portal-shell-accessibility.browser.mjs` | 6/6 | 6/6 |
| `work-queue.browser.mjs` | 19/19 | 19/19 |
| `guidance-operations.browser.mjs` | 20/20 | 20/20 |
| **Total** | **295/295** | **295/295** |

The normal build intentionally compiles out the local realtime test seam. The first ordinary-build
run therefore failed only the two realtime seam scenarios in Work Queue/Guidance Operations
(18/19 and 19/20). They passed after a separate optimized local build with
`NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1`, the repository's documented runner mode. Both complete
shared suites passed in both engines against that build.

The first WebKit GSS run reported canceled Next route-prefetch requests as page errors during the
synthetic full reload (15/16). The browser test was corrected to call the harness's existing
`settleFetches()` before reload. The focused account-switch case passed in both engines, and the
entire GSS suite then passed 16/16 in both engines. This is the sole final-PR source change and
does not change production behavior.

The 295-per-engine totals are the final suite results after these environment/test-harness
corrections. Additional focused reruns were performed; the initial setup failures are retained
here for an auditable record.

## Browser commands

From `fe/`, the browser runs used this local-only build/server setup:

```sh
NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 NEXT_TELEMETRY_DISABLED=1 pnpm build
pnpm start --hostname 127.0.0.1 --port 3107
COMPASS_UI_BASE_URL=http://127.0.0.1:3107 COMPASS_UI_BROWSER=chromium pnpm exec node tests/<suite>.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3107 COMPASS_UI_BROWSER=webkit pnpm exec node tests/<suite>.browser.mjs
```

`<suite>` was each of the 13 filenames in the table. The two shared realtime suites and full GSS
suite were rerun against test mode in both engines. The final GSS account-switch test waits for
prefetches before `page.reload()`. After browser validation, the ordinary build is restored with
`NEXT_PUBLIC_COMPASS_UI_TEST_MODE` unset; it must remain the final local build artifact.

## Compatibility, hosted CI, and gaps

- No backend files changed, so backend test suites, migration checks, and database migrations were
  not run. Existing backend authorization/idempotency test files were inspected; their settings
  require local PostgreSQL and Redis services.
- No staging or production request was made; browser API responses were synthetic.
- No GitHub-hosted PR check is claimed. Current frontend/backend PR filters exclude the integration
  branch; no CI/deployment workflow was edited or dispatched.
- Actual browser zoom, screen-reader speech, physical-device interaction, manual accessibility
  review, staging UAT, institutional acceptance, and production validation remain open.

The test results establish a local integration baseline, not backend runtime acceptance, WCAG
conformance, staging deployment success, or production readiness. See
[staging compatibility](staging-compatibility.md), [accessibility audit](accessibility-final-audit.md),
and [UAT matrix](uat-matrix.md).
