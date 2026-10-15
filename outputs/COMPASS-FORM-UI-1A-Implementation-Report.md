# FORM-UI-1A — Call Slip permission-aware lifecycle actions

## Baseline and confirmed defect

- Repository: `ils12058/COMPASS`; target: `staging`.
- Fetched `origin/staging`: `b7f365b5828ab5db8fc541d90321558a5183f7f2` (same as the audit baseline).
- Initial checkout: clean `staging` at `40492b1aacca7b608c1cf8bc0a4aef618d9d78f1`; no staged, unstaged, or untracked changes. Created `fix/form-ui-1a-call-slip-permissions` directly from fetched `origin/staging`.
- PR #232 (FORM-ID-1) merged to staging as `180759f0b79b8a3d2b418ad0fd38101196f18942`; PR #233 (FORM-INPUT-1C) merged as `b7f365b5828ab5db8fc541d90321558a5183f7f2`. Confirmed through GitHub and staging history.
- Reviewed the original FORM-FIDELITY-0 discrepancy register, FF-03, in the audit package dated October 15, 2026. It identifies view-only operational users seeing ACTIVE-record management actions despite backend management checks.
- FF-03 remained present at current staging. The new actual-component tests reproduced three failures before the rendering guard (active view-only Counselor, active view-only GSS, and view-only Counselor with Referral viewing); 22 other cases passed. All 25 pass with the fix.
- The list and creation pages already gate management affordances with the established helper. No necessary coupled affordance fix was found.

## Changes and authorization boundaries

Application code changes only `fe/src/features/call-slips/call-slip-detail-page.tsx`: derive `getCallSlipAccess(user)` in the operational detail and require `access.canManageOperational && !slip.isError` at the existing lifecycle panel boundary. The panel retains its own ACTIVE-state requirement.

Previously, a healthy ACTIVE record offered both lifecycle operations to operational viewers. Now only authorized managers receive those controls. No disabled substitute, new permission explanation, helper, capability, role exception, or grant is added.

The outer detail router still independently requires `canViewSelf` or `canViewOperational`; management does not imply viewing. Permit, reporting, issuance, state, official identity, and existing Referral presentation remain outside the new guard. The PDF action and its operational/self download calls remain outside it. Student detail and withdrawal presentation are unchanged.

The lifecycle functions, dialogs, date/reason validation, mutation recovery, query invalidation, and Guidance Work invalidation are unchanged. Interview-end time retains its existing semantics; no Appointment, Referral, or Counseling Encounter completion rule changes.

Server authorization remains authoritative: `call_slips_record_interview_ended` and `call_slips_void` in `be/compass/call_slips/api.py` each call `_require_operational(request, "call_slips.manage")` before processing. No endpoint or service implementation changed. New API tests revoke management explicitly for each operational role, verify detail GET succeeds, then verify both mutation endpoints return 403 `permission_denied` and every saved Call Slip field is unchanged.

## Changed files

1. `fe/src/features/call-slips/call-slip-detail-page.tsx` — existing capability guard at action boundary.
2. `fe/tests/call-slip-permissions.test.mjs` — 25 actual-component rendering regressions using the existing Node/TSX harness and real access helper.
3. `fe/tests/call-slip-permissions.browser.mjs` — 25 synthetic API scenarios per browser against the actual Next UI.
4. `fe/package.json` — focused two-engine browser command, included in existing UI suites.
5. `be/tests/test_call_slips.py` — two parameterized backend permission-defense cases using explicit management revocation.
6. `outputs/COMPASS-FORM-UI-1A-Implementation-Report.md` — this report.
7. `outputs/COMPASS-FORM-UI-1A-Validation-Evidence.json` — compact validation and baseline reproduction evidence.

## Test matrix

| Scenario | Evidence and outcome |
|---|---|
| Student owner | Component and Chromium/WebKit checks preserve details and the self PDF endpoint for ACTIVE, COMPLETED, and VOIDED; no operational actions. The rendering test also supplies operational capabilities to prove the role boundary remains. |
| View-only Counselor | Explicit `call_slips.view` only; details, official identity, PDF, and allowed Referral presentation remain; no action inputs, triggers, or management dialogs in all three lifecycle states. |
| View-only GSS | Same explicit capability restriction, including a phone-width browser check; no reliance on default management grants. |
| Authorized Counselor | Both view/manage; interview-end and void confirmations, cancel focus return, required reason, confirmed mutation refresh, and uncertain-response reconciliation pass. |
| Authorized GSS | Same manager behavior and both mutation recovery paths pass. |
| Completed/voided | Managers and viewers receive no prohibited lifecycle controls; Student withdrawn wording persists. |
| No applicable viewing capability | Direct URL requests make no detail API call; seeded component data is not exposed. Manage-only does not imply view. |
| Student owner scope | Browser 404 fixture conceals another owner's record and PDF; existing backend owner-scope regression verifies the actual server restriction. |
| Direct unauthorized API mutations | Explicit REVOKE override for Counselor and GSS; both interview-end and void return 403 without changing the record. |
| Other capability/role combinations | Unrelated capability alone grants nothing; IT Admin and Institutional Officer remain excluded even if Call Slip capability strings are supplied. |
| Query refresh failure | Existing confirmed facts and PDF remain visible; operational action panel is absent. |
| Accessibility/responsiveness | Keyboard PDF activation, real download events, accessible confirmation labels, opener focus return, required void reason, and no horizontal page overflow pass; desktop and GSS phone screenshots inspected. |

## Verification

Commands run from the stated directory:

| Directory | Command | Exact final outcome |
|---|---|---|
| `fe` | `pnpm api:generate` | Passed; Orval generated successfully. |
| `fe` | `pnpm test` | **712 passed, 0 failed**, including all 25 new actual-component tests. |
| `fe` | `pnpm typecheck` | Passed (`tsc --noEmit`). |
| `fe` | `pnpm lint` | Passed (`eslint .`). |
| `fe` | `pnpm build` | Passed, production compilation, TypeScript, and route generation. |
| `fe` | `COMPASS_UI_ARTIFACTS=../outputs/form-ui-1a pnpm test:ui:call-slips` | **25/25 Chromium and 25/25 WebKit**. |
| `be` | `uv run pytest tests/test_call_slips.py tests/test_referral_call_slip_lifecycle.py --reuse-db -q --junitxml=../outputs/form-ui-1a/backend-final.xml` | **52 passed in 62.23s**. |
| `be` | `uv run ruff check tests/test_call_slips.py` | Passed. |
| `be` | `uv run ruff format --check tests/test_call_slips.py` | Passed; file already formatted. |
| repository | `git diff --check` | Passed. |

The initial backend attempt passed 50 existing tests and failed the two new fixtures because they used an invalid override value; those fixtures were corrected to `UserCapabilityOverride.Effect.REVOKE`. The focused defense rerun passed 2/2 and the final combined rerun passed 52/52. The initial attempt also warned that two connections from the existing concurrency test prevented test-database teardown; the final `--reuse-db` run completed without that warning.

### Inherited Guidance Operations browser failures

Ran `node tests/guidance-operations.browser.mjs` and `COMPASS_UI_BROWSER=webkit node tests/guidance-operations.browser.mjs`: **17/20 pass in each engine**, exit 1. Exact failing checks:

1. `navigation and direct route authority for COUNSELOR` — navigation text is `My work31`, while the test expects `My work`.
2. `navigation and direct route authority for GUIDANCE_SERVICES_STAFF` — navigation text is `My work22`, while the test expects `My work`.
3. `same-tab reading preserves reply backlog; confirmed send reconciles it without a socket` — assertion `Canonical HTTP summary was invalidated by confirmed send`.

Reproduced the three failing check names against a pristine `git archive` of baseline staging in a temporary directory (shared installed dependencies; archived OpenAPI clients regenerated; Next webpack development server on port 3108). Both engines returned **0/3** for the filtered checks. The navigation mismatches were identical. The WebKit backlog failure reproduced the same invalidation assertion; the Chromium baseline timed out earlier waiting for `Messages awaiting reply` to show `1`. This is a difference in the failure point, not proof that the later Chromium assertion reproduces identically.

Reproduction filter: `COMPASS_UI_CHECK='navigation and direct route authority for (COUNSELOR|GUIDANCE_SERVICES_STAFF)|same-tab reading'`; set `COMPASS_UI_BASE_URL=http://localhost:3108`, then run the same browser command for each engine. No unrelated fix was included. Compact result messages, commands, baseline identity, and hashes are retained in `outputs/COMPASS-FORM-UI-1A-Validation-Evidence.json`. Raw logs, screenshots, and browser JSON are retained locally outside the checkout in the task's artifact directory.

Browser APIs and PDF bytes use synthetic fixtures only. The browser suite asserts the download endpoint and filename; it does not validate PDF layout or binary fidelity, which this slice does not change. The complete frontend browser suite and full repository backend suite were not run; the relevant suites are listed above. Do not interpret focused results as fully green repository CI.

## Compatibility

No backend API change; no database migration; no encryption change; no FormRevision modification; no document-template change; no historical record rewrite; no lifecycle transition change; no new permission grants. No generated client is edited or committed. No merge, deployment, staging reset, or live institutional record mutation was performed.

## Deferred findings

- FF-01 remains the intentional Inventory text-fit/ellipsis implementation. Whether official output must contain every answer verbatim remains an unresolved institutional output-completeness decision; no QMS approval is claimed.
- FF-02 remains the independently tracked PDF row-capacity limitation for Inventory siblings/organizations (FORM-UI-1B / DOC-TPL-1A). No row cap, data removal, or pagination change is introduced.
- Additional Call Slip paper fields remain subject to GCO approval and any necessary data-contract/privacy design.
- All these concerns remain outside FORM-UI-1A.
