# COMPASS-STAB-FINAL — Regression Stabilization Report

## Scope and baseline

- Repository: `ils12058/COMPASS`
- Target branch: `staging`
- Base revision: `cb3ab69717345238995fc15a9f7e7898a3a9e8cf`
- Work branch: `codex/compass-stab-final`
- Scope: regressions exposed by the CAL-1, FUP-UX-1, ACAD-1, GM-UX-2, and UX-FINAL slices.

No application redesign, authorization change, new workflow, or live staging operation was made. The only seeded data correction changes the existing graduating Bachelor's persona from an unsupported fifth year to the supported fourth year; its account identity and credential selection remain unchanged.

## CI audit and classification

The newest exact-base backend run was #159 (`39102260958`, `cb3ab697`). Earlier runs #154 (`39092946546`), #156 (`39095607999`), #157 (`39098450326`), and #158 (`39100612710`) and their JUnit artifacts were compared to identify recurring failures.

| Finding | Classification | Evidence and disposition |
|---|---|---|
| Existing inactive Program reference was expected to block every draft edit | Outdated test expectation | The inventory service permits editing a draft while retaining its current inactive Program, but blocks selecting an inactive Program and blocks submission while the Program/College/Campus chain is inactive. The regression now checks each distinction. This failure appeared in exact-base run #159; its other logged failures mirrored the Exit Interview fixture, seed setup, confidential-content, and OpenAPI categories in #158. |
| Exit Interview F4 prerequisite tests had no submitted Bachelor's Inventory | Invalid fixtures | Their setup failed at the earlier F4 classification gate, before testing Exit Interview behavior. Both fixtures now use the canonical submitted BSIS Year 4 inventory helper. |
| `RICH_GRADUATING` used Bachelor's Year 5 | Invalid seeded data | ACAD-1 allows Bachelor's Years 1–4. The existing persona and Good Moral narrative now use Year 4, with a regression asserting the seeded history and current record. |
| New Good Moral endpoints absent from the expected OpenAPI operation registry | Contract-test drift | Registered `goodMoralListDegreeOptions` and `goodMoralGetMyF4AcademicContext`; added a self-service role check for the F4 academic-context endpoint. No API behavior changed. |
| Availability test formatting failed Ruff | Formatting | Reformatted the assertion to the repository's Ruff output. |
| Two F4 frontend component tests rendered the loading skeleton | Missing test fixture | The component fixture now supplies the contract-shaped `ELIGIBLE`, Bachelor's, Year 4 academic-context response. The F4 gate and product copy are unchanged. |
| Guidance Messages browser test searched for the former accessible label | Stale test selector | The current rendered label is “Search Students”; the test now uses that exact accessible name and still verifies Enter submits the search. |
| Call Slip action-label check counted screen-reader-only “Call Slip” text | Test assertion measured the wrong text | The test now checks the visible label text node (“Download”) separately from the accessible name. The rendered control already had the intended concise visible label. |
| Menu/dialog focus checks ran before WebKit completed focus restoration | Browser-test timing | The checks now wait for the trigger to regain focus before asserting it. Focus behavior itself was not changed. |
| Availability browser suite crashed while loading Next.js navigation under Node 22.18 | CI runtime mismatch | The frontend unit-test job already uses Node 26.7 for this TSX/CommonJS interop. The browser regression job now uses the same runtime; the build job remains on Node 22.18. The same suite passes locally under Node 26.7. |
| One Good Moral assisted-notification assertion failed in #154/#156/#157 | Superseded historical expectation | The assertion expected the former “Sign in to COMPASS” phrase. It did not recur in the newer #158/#159 failures and the current assisted-request test file passes locally (46 tests). No copy change was made for this historical failure. |

Run #157 also showed the unsupported seed year cascading into seeder setup errors. Run #158 added the Exit Interview fixture and OpenAPI failures. The exact-base run #159 retained the inactive-Program test mismatch. The prior UX-FINAL browser logs additionally exposed the two F4 test-fixture failures, browser-runtime import error, stale Messages label, visible-label assertion, and focus-check timing addressed above.

## Changes

- Corrected the seeded graduating Bachelor's year and matching narrative; added an explicit Year 4 seed regression while preserving the frozen account and credential snapshot apart from that intentional year-level correction.
- Updated the inactive Program regression to preserve the current draft reference, allow draft edits, reject re-selection of an inactive Program, and block submission while the academic hierarchy is inactive.
- Reused a canonical submitted Bachelor's Inventory in Exit Interview test setup.
- Updated the OpenAPI operation allowlist and added role coverage for F4 academic context.
- Updated affected frontend synthetic fixtures and browser assertions; aligned the browser regression Node runtime with the runtime used by frontend unit tests.
- No application page, copy, authorization, eligibility, or domain-service implementation was changed.

## Validation

| Check | Result |
|---|---|
| Backend focused regression bundle: availability, inventory academic context, Exit Interviews, Good Moral, OpenAPI, seed, inventory, and Student Profiling | **492 passed** in 14m42s |
| `tests/test_good_moral_assisted.py` | **46 passed** in 20.22s |
| `uv lock --check` | Passed |
| `ruff format --check .` and `ruff check .` | Passed; 777 Python files formatted |
| Python `compileall` | Passed |
| `makemigrations --check --dry-run` | No changes detected |
| Local migrations and Django system check | No migrations pending; no system-check issues |
| Generated OpenAPI contract check | Contract is current |
| `pnpm api:generate` | Passed |
| `pnpm lint` and `pnpm typecheck` | Passed |
| `pnpm test` | **818 passed, 0 failed** |
| Synthetic production build | Passed |
| Browser regression suites, Chromium | Availability **5/5**; Follow-Ups **18/18**; Messages **41/41**; UI hierarchy **18/18** |
| Browser regression suites, WebKit | Availability **5/5**; Follow-Ups **18/18**; Messages **41/41**; UI hierarchy **18/18** |
| ESLint on the modified frontend test files | Passed |

Backend tests and Django checks used only the local test database. Browser checks used synthetic fixtures and a loopback-only server. No live staging database, UAT account, credential, or participant data was changed.

## Remaining status

The fixes are locally validated. Pull-request and exact-head GitHub Actions results are reported separately from these local results; this report does not claim a green remote CI run, merge, or deployment. No genuine application blocker was reproduced in the affected workflows.
