# COMPASS-UX-P3 Implementation Report

**Base and PR target:** `staging`

**Branch:** `codex/compass-ux-p3`

**Scope:** E-Counseling presentation refinement plus the explicitly authorized Good Moral print CSS and rendering-test exception

**Deployment:** None

## Summary

Made the E-Counseling workspace easier to scan while keeping device diagnostics, consent meaning, and media-safety status available. Added a fullscreen sizing correction so portrait participant video can shrink inside the call stage and remain fully visible. Scoped black generated text to Good Moral certificates, with other form colors unchanged. The issued-certificate Print action now tries the already authorized PDF preview's browser print function after its frame loads, then offers the same finalized PDF in a new tab or as a download when direct printing is unavailable.

No call lifecycle, Daily integration, backend authorization, media consent, recording/transcription, certificate issuance, template content, or API behavior was changed. The only backend production change is the authorized, Good Moral-scoped print stylesheet rule.

## Architecture and correctness audit

Reviewed UX-P1/UX-P2A/UX-P2B, EC-FIX-1, and ADR-091 through ADR-094 against the affected call, consent, media, and document flows.

| Existing boundary | Disposition |
| --- | --- |
| `DailyCallSession` and the portal runtime own call state and media-provider operations. Stage and device UI receive projected state/actions. | Kept unchanged. Preview remains local; orientation/fullscreen changes do not join, leave, or recreate the call. |
| Consent meaning and media capture state are separate. V1 has three decisions; V2 has combined media capture and a separate transcript-storage decision. | Kept distinct. Pending decisions retain their explanation and confirmation; terminal decisions remain terminal. Active capture, failed stop, and uncertain provider state stay visible. |
| Governed recording/transcription and authorized media access remain COMPASS actions under ADR-092 and EC-FIX-1. | Kept unchanged. No provider event, permission, endpoint, query key, or authorization behavior changed. |
| ADR-091 calls for progressive disclosure, visible names, consequence-aware controls, and privacy-safe product copy. | Applied to presentation only. Advanced device diagnostics moved behind Devices; user-facing controls retain visible labels and names. |
| Good Moral issuance and PDF access are state- and capability-gated. | Kept unchanged. Print/download render only after the existing issued-state and authorized-PDF checks succeed. |

## Implementation

### E-Counseling workspace

- Reduced the default pre-join panel to the local camera preview, square Mic/Camera/Devices controls, concise readiness, Join session, and Close preview. Device selection, refresh, microphone-level diagnostics, speaker test, and actionable errors remain in Devices.
- Added cancellation and unmount cleanup for the local speaker test tone, including a pending speaker-routing operation.
- Made pre-join device selection explicitly apply to the local preview. The connected-call Devices dialog retains its existing immediate-apply meaning and refresh support.
- Tightened Student consent rows while preserving pending explanations, Allow/Decline confirmation, distinct V1/V2 scopes, terminal states, withdrawal consequences, and details.
- Reordered Counselor media permission/status content so capture uncertainty, errors, and Stop actions precede settled permissions; uncertain stop outcomes remain explicit.

### FIX-1A — Fullscreen video fit

The fullscreen stage is a column flex container. Its video pane used an aspect-ratio-sized flex item, while a tall portrait track could impose a large intrinsic minimum height. That prevented the pane from shrinking to the available space and could push the controls outside the stage even though the remote video itself used `object-contain`.

Made the remote stage wrapper and fullscreen video pane shrinkable with `min-height: 0`/`min-width: 0` at the relevant flex boundaries. The remote video remains centered with `object-contain`; local self-view and pre-join preview retain their intentional mirrored `object-cover` behavior. Camera-off and waiting states are unchanged.

The browser regression switches one synthetic remote track through 9:16, 4:3, and 16:9 while fullscreen, checks the frame fit and control bounds, verifies camera-off and exit, and asserts the call object/join count stays at one.

### FIX-1B — Good Moral generated ink

Added `.good-moral-certificate .generated-value { color: #000000; }` after the shared blue rule in `print.css`. No template, data, label, issuance, or global generated-value rule changed. Rendered-PDF coverage checks current-student v1, UCN current-student v2, graduate v1, Referral Slip, and Call Slip. Long synthetic names, academic details, receipt, date, and issuer values remain extractable on the single certificate page.

### FIX-1C — Issued Good Moral print

The `Print certificate` click now calls `print()` through the loaded iframe containing the same authorized finalized PDF Blob used by the embedded preview. The browser return value cannot establish that a print dialog appeared, so the UI only says a request was sent and tells the user to use the PDF viewer's Print action or download if no dialog appears.

If the frame is not ready, exposes no print method, or throws, the click opens the same finalized Blob in the existing accessible PDF preview flow. A blocked/failed preview shows an alert and leaves Download available. `opener` is cleared for the preview tab; its Blob URL is revoked when the tab closes, and the embedded URL is revoked when its component unmounts. Printing remains separate from issuance, so retry, cancellation, and fallback do not issue again.

Automated browser tests replace the print method with a stub. They verify the direct user-gesture call, readiness gate, fallback, blocked preview, download, authorization, cancellation, and no duplicate issuance; they do not open a real operating-system dialog.

## Visual evidence

All fixtures and document data are synthetic. The Good Moral comparison uses the same UCN current-student v2 context and renderer: “before” omits the new scoped override and “after” includes it.

| Scenario | Before | After / control |
| --- | --- | --- |
| UCN current-student certificate generated values | [PNG](fe/docs/ux-p3-visuals/documents/current-student-ucn-v2-before.png) | [PNG](fe/docs/ux-p3-visuals/documents/current-student-ucn-v2.png) |
| Graduate certificate generated values | — | [PNG](fe/docs/ux-p3-visuals/documents/graduate-v1.png) |
| Other institutional generated values stay blue | Existing shared styling shown by control | [Referral Slip PNG](fe/docs/ux-p3-visuals/documents/referral-control-v1.png), [Call Slip PNG](fe/docs/ux-p3-visuals/documents/call-slip-control-v1.png) |
| Fullscreen 9:16 / 4:3 / 16:9 remote video | UAT issue description; no baseline capture was recorded | [Portrait](fe/docs/ux-p3-visuals/chromium/ecounseling-call/fullscreen-video-portrait.png), [4:3](fe/docs/ux-p3-visuals/chromium/ecounseling-call/fullscreen-video-classic.png), [landscape](fe/docs/ux-p3-visuals/chromium/ecounseling-call/fullscreen-video-landscape.png) |
| Pre-join and consent/media presentation | Existing behavior audited in source and tests | Synthetic captures are under `fe/docs/ux-p3-visuals/chromium/` and `fe/docs/ux-p3-visuals/webkit/`. |

## Validation

| Check | Result |
| --- | --- |
| `pnpm lint` | Full lint passed before the final iframe-readiness guard; focused lint passed after that change |
| `pnpm typecheck` | Passed after the final iframe-readiness guard |
| `pnpm test` | Passed: 816 passed, 0 failed |
| `pnpm build` | Passed before the final iframe-readiness guard; not rerun during the requested pause |
| `pnpm api:generate` | Passed; generated API client files have no diff |
| Good Moral print browser suite | Chromium 22/22 and WebKit 22/22 before the final iframe-readiness guard; rerun pending |
| E-Counseling Chromium browser checks | Call 37/37 and consent/realtime 11/11. Media/realtime was stopped at 8/16 after the user requested pausing heavy tests under high system load; the initial-ready/reconnect case separately passed 1/1. The remaining media checks are pending. |
| E-Counseling WebKit browser checks | Consent/realtime 11/11, media/realtime 16/16, fullscreen-fit 1/1. The full call suite remains pending. |
| Targeted backend document rendering/color checks | Passed: 10 passed, 36 deselected |
| Ruff on `be/tests/test_documents.py` | Passed |

The user requested that heavy tests remain paused until system load clears. No browser tests were started after that request. The pending browser checks above are intentionally left visible rather than reported as passing.

## Changed files

- `be/compass/documents/static/documents/css/print.css`
- `be/tests/test_documents.py`
- `fe/src/features/ecounseling/call/call-stage.tsx`
- `fe/src/features/ecounseling/call/device-dialog.tsx`
- `fe/src/features/ecounseling/call/prejoin-device-check.tsx`
- `fe/src/features/ecounseling/counselor-media.tsx`
- `fe/src/features/ecounseling/student-consent-panel.tsx`
- `fe/src/features/good-moral/good-moral-issued-pdf.tsx`
- `fe/tests/ecounseling-call.browser.mjs`
- `fe/tests/ecounseling-consent-realtime.browser.mjs`
- `fe/tests/ecounseling-media-realtime.browser.mjs`
- `fe/tests/ecounseling-media-v2.test.mjs`
- `fe/tests/good-moral-print.browser.mjs`
- `fe/tests/guidance-messages-contextual.browser.mjs`
- `fe/tests/support/browser-harness.mjs`
- `fe/tests/support/fake-daily.mjs`
- `fe/tests/ui-information-hierarchy.test.mjs`
- `fe/docs/ux-p3-visuals/` (synthetic Chromium/WebKit screenshots and PDF-render comparison images)
- `COMPASS-UX-P3-IMPLEMENTATION-REPORT.md`

## Preserved behavior and limitations

- No backend behavior, API, database, authorization, consent meaning, Daily provider integration, or certificate template content changed.
- Headless tests cannot prove Safari displayed a system dialog, nor can any page-level code prove paper was printed. Browser behavior also depends on PDF viewer and user settings.
- The browser matrix and PDF renders use synthetic fixtures; they do not replace staging role-based UAT or institutional review.
- No merge or deployment was performed.
- Browser validation is incomplete because the user asked to pause heavy tests while system load was high. Rerun the pending suites after the load clears, especially Good Moral print after the final readiness guard and the complete Chromium/WebKit E-Counseling matrices.

### Manual Safari/macOS UAT

1. Sign in as a Counselor with existing Good Moral preparation/issue authority and open an already `ISSUED` record with PDF access.
2. Click **Print certificate** once. Confirm whether Safari opens the system print dialog for the embedded PDF. If no dialog appears, use the embedded PDF viewer's Print action or **Download certificate** and print from Preview.
3. Cancel the dialog and confirm the record stays `ISSUED`, the same certificate remains available, and no new issue request was sent. Repeat print/download to confirm the finalized PDF remains usable.
4. With Safari pop-ups blocked, exercise the fallback; confirm the page explains that the preview could not open and Download remains available.
5. Compare current-student and graduate Good Moral generated values with Referral Slip/Call Slip output. Confirm Good Moral values are black and the other forms retain blue.
6. In E-Counseling, use portrait remote video, change orientation, turn the camera off, enter/exit fullscreen, and confirm the complete frame and call controls remain visible without a reconnect or second join.

## PR status

One PR against `staging` will contain the UX-P3 implementation, FIX-1 follow-up, this report, and synthetic evidence. It will remain unmerged, and no deployment is authorized.
