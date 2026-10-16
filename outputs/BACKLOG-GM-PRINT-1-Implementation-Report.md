# BACKLOG-GM-PRINT-1 — Good Moral issuance-to-print

Date: October 16, 2026 (Asia/Manila)

## Baseline and independence

- After opening Security Activity PR #240 and verifying its clean worktree, fetched `origin/staging` again: `bea790e6c04a3ea6b7d69ce651e88d5ba3b724e2`.
- Branch: `feat/backlog-good-moral-print`.
- Worktree: `/Users/reynantlntno/Projects/COMPASS-BACKLOG-GM-PRINT`.
- This branch starts directly from staging, not from PR #240.
- Dedicated PostgreSQL cluster on 55472 with the `compass_agent_d_gm` test database; local frontend on 3148. Synthetic browser fixtures intercept all API traffic. No live institutional data or services were used.

## Issuance and PDF interaction

The existing Issue certificate action, consequential confirmation, `goodMoralIssueRequest`, reviewed preparation version, and refresh/uncertain-result recovery are unchanged. Only the confirmed operational `ISSUED` branch with `actions.can_download`, and without a detail-query error, mounts the new PDF workflow. A successful mutation response alone does not mount it: the existing detail refresh must return the official issued state.

The new component uses the generated `useGoodMoralDownloadCertificate` query, which calls the existing authenticated `goodMoralDownloadCertificate` endpoint. It prepares the finalized PDF, displays an inline browser PDF preview, and offers one primary Print certificate action and a secondary Download certificate action. Reopening an already-issued request offers the same actions without issuing again. Existing authorized GSS readers can also print their already-downloadable issued certificates; no role or capability grants were added.

PDF retrieval has no automatic retry. A failed read shows a PDF-specific error that keeps issuance acknowledged, disables Print, and offers Retry PDF. Retry and download recovery only perform PDF GETs. The PDF Blob is scoped to this mounted view (`gcTime: 0`), and authority errors do not expose cached PDF data. Downloads reuse the authorized finalized response and existing binary filename/download helper.

Student-facing downloads retain their original component and self-service endpoint. The physical-signature/dry-seal instruction is extracted without changing its wording and shared by both views.

## Browser behavior and resource lifetime

- No asynchronous popup is attempted after issuing or fetching. Preparing the PDF never opens a new tab or print dialog.
- Print certificate directly opens a new native PDF tab during the user's click. The user chooses the PDF viewer's Print action or the device/browser print command. The UI does not claim that opening the preview proves a dialog or physical printing completed.
- If `window.open` is blocked or throws, the UI explains the blocked preview and keeps Download available. Browsers/devices without usable inline/native PDF viewing can download the same PDF and print it from a PDF application.
- Cancelling or ignoring the native print dialog has no application callback or backend mutation. There is no printed status. The certificate remains issued and can be printed/downloaded later.
- Inline preview URLs remain alive until that preview is replaced/unmounted; cleanup removes the frame source before revoking the URL.
- External previews own separate URLs. Leaving the request view does not revoke an open external tab's URL. One timer per tab releases it once that tab closes; document/browser teardown also owns its resources. Blocked attempts revoke immediately.
- The PDF bytes are unchanged: no new renderer, template, watermark, signature, public URL, embedded credentials, or backend endpoint.

## Changed files

- `fe/src/features/good-moral/good-moral-counselor-detail.tsx`: mount the issued PDF experience in the existing issued/download-authorized branch.
- `fe/src/features/good-moral/good-moral-issued-pdf.tsx`: authorized PDF query, inline preview, print/download actions, PDF-specific recovery.
- `fe/src/features/good-moral/good-moral-print-preview.ts`: synchronous native PDF preview and independent URL cleanup.
- `fe/src/features/good-moral/good-moral-pdf.tsx`: share the unchanged physical fulfillment notice; preserve Student download behavior.
- `fe/tests/good-moral-print.test.mjs`: presentation gates, variants, Student regression, popup behavior and URL lifetime.
- `fe/tests/good-moral-print.browser.mjs`: production-browser issuance, PDF and printing regressions.
- `fe/tests/support/good-moral-print-fixtures.mjs`: synthetic records and a small valid test PDF, not an official certificate template.
- `outputs/BACKLOG-GM-PRINT-1-Implementation-Report.md`: this report.

## Validation

Passed checks:

- `pnpm api:generate`: passed using the unchanged staging OpenAPI contract.
- `node --import ./tests/support/register-tsx.mjs --test tests/good-moral-print.test.mjs tests/good-moral-preparation.test.mjs tests/good-moral-request-standardization.test.mjs tests/form-input-standardization.test.mjs`: **36 passed**.
- Production build served by `pnpm exec next start --hostname 127.0.0.1 --port 3148`.
- `COMPASS_UI_BASE_URL=http://127.0.0.1:3148 node tests/good-moral-print.browser.mjs`: **20/20 Chromium passed**.
- Same browser command with `COMPASS_UI_BROWSER=webkit`: **20/20 WebKit passed**.
- `pnpm lint`: exit 0, **0 errors**, four inherited unused-variable warnings in `tests/portal-navigation-attention.browser.mjs`. Focused lint of all changed source/test files also passed without warnings.
- `pnpm typecheck`: exit 0.
- `pnpm build`: exit 0, including Turbopack, TypeScript, and prerendering.
- `git diff --check`: passed.
- Visually inspected the 320px issued view; primary/secondary actions and physical-fulfillment guidance remain legible. Tests check horizontal overflow for phone and desktop F4/F6 workflows. Native PDF embedding/print UI depends on the browser; automated rendering of the full native PDF viewer is not asserted.

Browser coverage includes:

- Both F4/F6 variants at 320px and 1440px, confirmation retained while pending, duplicate submission blocked, exact reviewed preparation version, no PDF before the held official-state refresh, frozen issuer/form metadata, exact PDF download bytes, and reuse for reprinting.
- Issuance succeeded but PDF preparation failed; Retry PDF performs another PDF GET with one issue mutation total.
- PDF access refused with 403; no preview or enabled Print is exposed; download recovery does not issue.
- Uncertain 500 issuance resolving to ISSUED or still-ready, failed refresh after successful/uncertain issuance, and deliberate refresh recovery before PDF preparation.
- Stale preparation and no-longer-current Student rejections; a later deliberate review carries the updated version.
- Unissued states have no print workflow, existing GSS issued-PDF access has no issuance authority, and Student download keeps its self endpoint with no automatic PDF fetch.
- Direct user activation for popup opening, blocked/throwing popup fallback, native PDF tab creation in each engine, PDF retry/download fallback, inline URL cleanup on navigation, external URL retention until its tab closes, and no false printed-success message.

Backend regression and inherited failures:

- From `be/`, `POSTGRES_DB=compass_agent_d_gm POSTGRES_PORT=55472 /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python -m pytest tests/test_good_moral.py tests/test_good_moral_preparation.py -q`: **99 passed, 2 failed**.
- `test_safe_corrections_preserve_sources_and_ready_requires_reconfirmation` tries a new year-level correction of `Third`; `test_prepare_validates_completeness_and_rejects_stale_review` tries a noncanonical semester correction. Existing FORM-INPUT-1A validation correctly rejects these legacy test inputs.
- Both failures reproduce on an untouched archive of baseline staging, in a separate `compass_agent_d_gm_baseline` test database. No backend or test-fixture correction is included in this frontend slice.
- The passing regression set includes actual Chromium PDF generation and F4/F6 rendering/eligibility/provenance coverage.

Development diagnostics: an initial Next dev run replayed PDF reads under development lifecycle checks, so final exact-request assertions use the production server. A browser test initially checked POST count before its intercepted request arrived; an explicit request-start barrier fixed that test race. Final production suites above pass.

Unexecuted: the entire repository-wide test matrices, hosted CI completion, live-account/provider checks, real OS print-dialog interaction, and physical printing/fulfillment. Logs and screenshots are under `/tmp/compass-agent-d-gm/` (ephemeral synthetic local evidence).

Readiness: ready for owner review with inherited backend failures and native-print limitations disclosed; remain unmerged pending owner review.

## Integration, limitations and deferrals

- No backend source, contract, model, migration, official template, authorization grant, or other form module is changed.
- Existing backend tests cover F4/F6 eligibility, same-account lifecycle, duplicate issuance idempotency, issuer and frozen-value attribution, saved FormRevision/render provenance, issued-only/authorized PDF access, release-audit failure, and real PDF rendering.
- FORM-INPUT-1A current-student canonical selections and preservation of historical values remain unchanged; its focused frontend tests are included in validation.
- Browser tests can verify preparation, user activation, preview opening, exact downloaded bytes, fallback, resource cleanup, and absence of extra issue mutations. Headless tests do not prove an OS print dialog, cancellation of a real OS dialog, printer output, a physical signature, or a dry seal. Device-specific print UI remains browser-owned.
- Domain-Rich My Activity and GCO-assisted Good Moral initiation remain deferred.
- Open PRs #238 (Inventory), #239 (Exit Interview), and #240 (Security Activity) had no changed-file overlap at final inspection. PG-1A remains a separate audit worktree without an open PR; no privacy-governance code is changed.
- No merge or deployment is performed. Both enhancements require normal owner review and integration before reaching users.
