# Validation evidence

Date: 2026-10-24, Asia/Manila. Verified base and final pre-PR integration fetch: **`09c7fd82fb1d77cdc1f47d9435d122a2a853ca56`**. Worktree `gm-or-3-receipt-experience`, branch `feature/gm-or-3-receipt-experience`. Original checkout, other worktrees, staging and main were untouched.

## Environment and contract boundary

Isolated frontend dependencies installed with `CI=true pnpm --dir fe install --frozen-lockfile`; no new dependencies or lockfile changes. Orval 8.29.0 generated the existing canonical contract before edits and again for final checks. Generated clients remain ignored/uncommitted. Next.js 16.3.4 production build served on loopback port 61739 for final browser evidence. Local runtime logs are under `/tmp/gm-or-3/`.

No backend source, OpenAPI contract, capability definition/grant, migration, fee-policy provider, print/PDF source component or institutional form changed. Backend API/contract suites and Ruff were not rerun for this frontend-only slice, as requested. Earlier GM-OR-2 PostgreSQL/authentication results are historical dependency evidence, not counted as newly executed tests. No integrated browser-to-real-authenticated-API/PostgreSQL smoke was performed; browser authorization/state transitions are local mocked contract simulations.

## Static and Node checks

```sh
pnpm --dir fe api:generate
pnpm --dir fe lint
pnpm --dir fe typecheck
pnpm --dir fe build
node --import ./fe/tests/support/register-tsx.mjs --test \
  fe/tests/good-moral-receipt.test.mjs \
  fe/tests/good-moral-preparation.test.mjs \
  fe/tests/good-moral-print.test.mjs \
  fe/tests/good-moral-assisted.test.mjs \
  fe/tests/good-moral-request-standardization.test.mjs \
  fe/tests/account-cache-ownership.test.mjs
```

**55 distinct Node tests passed**: 22 new receipt presentation/review tests, 27 existing Good Moral tests and six global account-cache ownership tests. Repeated focused executions are not added to that total. Orval, TypeScript, ESLint (no warnings), optimized production build and Git whitespace/scope checks passed. Build-generated `next-env.d.ts` changes were restored to HEAD, followed by another typecheck.

New unit coverage includes all eight inspection labels, DORMANT/FENCED availability, backend refusal despite capability possession, unconfirmed/editor state, actual inspector provenance, metadata-only history, expected-fee projection, mismatch guidance, exact payload, immutable review facts, stale resource/revision, historical invalidation, Student guidance and ACTIVE editor semantics.

## Browser checks and unique counts

Commands use `COMPASS_UI_BASE_URL=http://127.0.0.1:61739` and `COMPASS_UI_BROWSER=chromium` or `webkit`:

| Suite | Chromium | WebKit |
| --- | ---: | ---: |
| `good-moral-receipt.browser.mjs` | 37 distinct passing cases across coherent/focused runs | 37 distinct passing cases across coherent/focused runs |
| Existing `good-moral-print.browser.mjs` | 24/24 | 24/24 |
| Existing `good-moral-receipt-correction.browser.mjs` | 5/5 | 5/5 |
| Existing `good-moral-request.browser.mjs` | 2/2 | 2/2 |
| Existing `good-moral-assisted.browser.mjs` | 13/13 | 13/13 |
| **Distinct total** | **81** | **81** |

**162 distinct browser checks**, with no rerun counted twice. The first coherent production receipt run was 34/37 in Chromium and 37/37 in WebKit. Focused reruns of the successful GSS flow plus all three responsive/focus cases passed 4/4 per engine after refining explicit cross-browser focus return. This does not claim one latest full 37-case Chromium run. Existing print/correction/request/assisted suites each completed coherent passing runs per engine.

New receipt scenarios cover missing/incomplete/mismatch/unavailable/ambiguous/disputed states; inactive inspection availability; backend `can_verify=false`; intentional unchecked GSS attestation; pinned four-field payload; real backend inspector reference presentation; correction/reinspection/re-preparation; another inspector's original attribution; stale receipt and late invalidated success response; policy/fence/cancellation/authority/session/account changes; network loss before/after commit; identical operation UUID retry after deliberate review; failed refresh; retained correction draft; pending dismissal/double-submit prevention; keyboard focus; metadata disclosure; receipt-free Student F4/F6 creation and next steps; Counselor preparation/issuance without printing on inspection.

Responsive cases use 320px, 768px and 1440px viewports with 200% root text scaling at tablet, a 200-character synthetic name, 96-character OR and large synthetic amount display. Horizontal-overflow checks and screenshots were inspected. The large amount/approved amount in layout fixtures is explicitly fictional backend data, not an institutional fee decision. Root text scaling is not native browser zoom.

Existing print tests retain F4/F6 at 320px/1440px, exact issue tokens, uncertain issuance, PDF failures/retry, GSS reprint, owned Student downloads, finalized PDF bytes, Blob lifecycle and native-print instrumentation. Actual native OS dialogs/paper/signatures/dry sealing were not exercised. PDF/print production components are unchanged.

## Failures and fixes

- Initial compilation found a missing JSX property brace in the new header action; corrected before functional testing.
- Cached-detail SSR initially hid established preparation controls during an ordinary background fetch. Existing assertions were retained: last confirmed actions remain usable under their existing version gates, while new personal inspection specifically waits for a confirmed fresh detail. Failed refresh still blocks writes and preserves the editor.
- A new unit-test regex contained an unescaped closing slash; fixed without changing product behavior. All 22 new unit cases passed.
- The initial development browser run was 27/30. Duplicate fee-blocker prose was consolidated into the receipt section; preparation points to it. The FENCED locator was corrected to recognize paused copy. Pending controls becoming disabled could leave focus on Radix's guard; the feature now focuses its recording status while Radix continues to own containment.
- Additional Student coverage initially used exact labels that omitted their required marker. Locators now match the established Degree/Graduation date labels; payload assertions remain receipt-free.
- Production focus checks now wait for the dialog to close/focus to settle. Safari does not always focus a clicked button, so closing explicitly returns to the Verify control when present and the receipt heading after completion. Both engines passed the same resulting behavior.
- The new routine ActionStatus adds another status region. Existing print assertions had assumed the last status was the PDF outcome; they now target the same actual print-request notice by content. Print-call count/user-gesture, PDF/download and no-reissue assertions remain intact. No print implementation changed.

## Hosted CI, limits and release

The unchanged backend/frontend workflow PR filters include staging/canonical branches and exclude this integration base. Exact-head hosted check/workflow state and mergeability are verified in the PR handoff. No workflow filters were changed or manually dispatched.

All browser accounts, grants, policies, receipts and transitions were mocked locally. Passing these tests does not prove real authenticated backend authority, an actual physical inspection, institutional policy approval, manual screen-reader/device accessibility, native zoom, print output, production performance or UAT. GM-OR-4 owns integrated and manual release evidence.

No merge, deployment, SSH, live-data inspection/import/migration, real inspector grant, institutional fee publication or operational activation occurred. Runtime/provider/grant defaults remain unchanged. Test-owned local frontend servers are stopped at handoff. Remaining release decisions are listed in [gm-or-4-handoff.md](gm-or-4-handoff.md).
