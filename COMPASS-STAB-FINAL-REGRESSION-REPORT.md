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
- Corrected the weekly-schedule tab's accessible name, waited for initial consent reads and a ready socket before lifecycle simulation, and settled router prefetches before notification preference navigations.
- Made the Good Moral print regression verify the PDF MIME type and signature, then simulate the native viewer load event that headless Playwright does not emit.
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
| PR checks on code/test commit `b5f42ad90acacd66db9812f91d12bf44e31340f6` | Targeted frontend lint/typecheck/build, unit tests, and all **8 Chromium/WebKit browser shards** passed ([run](https://github.com/ils12058/COMPASS/actions/runs/39105799716)) |
| Targeted backend CI on the same code/test commit | All **4 test shards** passed ([run](https://github.com/ils12058/COMPASS/actions/runs/39105799709)) |
| Full backend CI on the same code/test commit | Static and contract checks plus all **6 test shards** passed ([run](https://github.com/ils12058/COMPASS/actions/runs/39105806817)) |
| Good Moral issued-PDF browser regression | **22/22 passed** on Chromium and WebKit; verified the PDF payload and simulated the headless viewer load event |
| E-Counseling consent foreground recovery | **11/11 passed** on Chromium and WebKit |
| Realtime notification preferences | **12/12 passed** on Chromium and WebKit |
| Draft/session safety browser regression | **24/24 passed** on Chromium and **24/24 passed** on WebKit |
| Browser regression suites, Chromium | Availability **5/5**; Follow-Ups **18/18**; Messages **41/41**; UI hierarchy **18/18** |
| Browser regression suites, WebKit | Availability **5/5**; Follow-Ups **18/18**; Messages **41/41**; UI hierarchy **18/18** |
| ESLint on the modified frontend test files and browser harness | Passed |

Backend tests and Django checks used only the local test database. Browser checks used synthetic fixtures and a loopback-only server. No live staging database, UAT account, credential, or participant data was changed.

## Remaining status

All PR checks and the full backend workflow passed on code/test commit `b5f42ad90acacd66db9812f91d12bf44e31340f6`. PR #286 was subsequently merged into `staging` at `c568f2ff222ce069926330db3466b232c0172f12`; no deployment was performed. No application implementation change or genuine application blocker was reproduced in the earlier follow-up browser cases. Native PDF viewer rendering, print dialogs, and physical printing remain outside headless browser proof.

## Follow-up: admin-initiated email-change verification

### Root cause and severity

**High impact workflow gap.** The backend already staged administrator-initiated address changes in the existing `EmailChangeRequest` workflow and required the account holder to prove possession of the proposed mailbox before changing `User.email`. The owner could complete that workflow only while the browser still held the response from their own initiation. The email-change page kept that response in component state, and there was no authenticated status read. After refresh or reauthentication, an admin-initiated request was invisible to its owner. The IT Admin's pending notice was also local-only, so it did not survive navigation or confirm completion. The security-code email did not explain where to enter the code.

### Affected files

- `be/compass/authentication/email_change.py`
- `be/compass/authentication/api.py`
- `be/compass/account_management/api.py`
- `be/compass/authentication/security_email.py`
- `be/compass/authentication/tasks.py`
- `be/compass/authentication/templates/authentication/email/security_code.html`
- `be/compass/authentication/templates/authentication/email/security_code.txt`
- `be/tests/test_email_change.py`
- `be/tests/test_openapi_contract.py`
- `contracts/openapi.json`
- `fe/src/features/account/security/security-overview.tsx`
- `fe/src/features/account/security/email/email-change-page.tsx`
- `fe/src/features/accounts/detail/overview/account-overview.tsx`
- `fe/tests/email-change.browser.mjs`

The Orval-generated TypeScript client was regenerated locally from the committed OpenAPI contract; generated client files are ignored by repository policy.

### Fixes

- Added an authenticated owner status endpoint that scopes all reads to the signed-in account. It returns only the latest request state, proposed address, expiry, and identifiers needed for confirmation. The OTP, hash, and other authentication material are never returned, and responses are marked `Cache-Control: no-store`.
- Added an `accounts.manage`-protected status read so IT Admin can see pending, completed, expired, replaced, or unavailable verification state after refresh. The account record continues to show the existing address until owner verification succeeds.
- Added a persistent Security notice with a keyboard-accessible **Verify email** link. The owner can enter the proposed-mailbox code directly; they do not need to start another email-change request first. Expired, replaced, and exhausted challenges lead back through the existing safe request flow and its existing proof/rate limits.
- Kept the existing OTP confirmation authoritative, including account-owner binding, TOTP step-up, audit events, and session invalidation. No administrative confirmation path was added.
- Updated the security-code email with a generic instruction to sign in and use **Account Security → Verify email**; it contains no account address or bearer link.
- Replaced the admin page's transient success-style message with durable pending/completed state. It refreshes the managed account after confirmation.

### Focused verification

| Check | Result |
|---|---|
| `uv run pytest tests/test_email_change.py tests/test_openapi_contract.py::test_core_schemas_and_realistic_error_responses_are_typed -q` | **11 passed** |
| `DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi --check` | Passed; contract current |
| Targeted `ruff check` and `ruff format --check` on affected backend files | Passed |
| `pnpm api:generate` | Passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `COMPASS_UI_BASE_URL=http://localhost:3115 node tests/email-change.browser.mjs` | **5/5 passed** on Chromium, including phone viewport |
| `COMPASS_UI_BASE_URL=http://localhost:3115 COMPASS_UI_BROWSER=webkit node tests/email-change.browser.mjs` | **5/5 passed** on WebKit |

Backend and browser scenarios cover admin staging without changing the current address, owner-only discovery, reauthentication/refresh rediscovery, code confirmation and wrong-code feedback, wrong-owner rejection, expiration, superseding, attempt exhaustion, MFA step-up, security-event provenance, admin-visible completion, and generic email instructions. The browser checks use synthetic API responses and a loopback Next.js server. No broad CI suite was run for this follow-up; no merge or deployment was performed.

### Follow-up status

Implementation is on branch `codex/stab-final-email-change-verification`, based on `staging` revision `c568f2ff222ce069926330db3466b232c0172f12`. It remains unmerged and undeployed pending review.
