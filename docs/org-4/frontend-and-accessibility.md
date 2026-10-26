# Frontend, recovery and accessibility

Existing Catalog Node and browser suites passed against the current production build; no UI/runtime
fix was required. Full Node selection: **1,021** distinct passing cases. Catalog: **53 Chromium +
53 WebKit**. Good Moral print: **24 + 24**. Receipt: **37 + 37**. Thus 114 logical mocked scenarios
per engine, 228 engine executions, reported separately from 18 real authenticated Chromium cases.

Catalog scenarios cover Catalog-only/relationship-only/combined/read-only entry, Student denial,
all operation families, pending/configured/noncontiguous policy, blockers/warnings, duplicates,
stale versions/impact, history pagination, MFA setup/verification and no replay, failed reads,
saved-but-refresh-failed, lost committed/unconfirmed rename/creation, first-page uncertainty,
actor/session transitions, removed parents and deliberate dirty discard. Existing Responsibilities,
Student Affiliations and supervision surfaces remain guarded by relationship authority.

The editor holds a local draft bound to account/session UUID and refreshes authoritative state
before review/submission. A new session clears old values; failed authority reads stop submission.
No consequential mutation retry is enabled. Saved response and refresh outcome are separate.
Uncertain outcome recovery reads current row and exact target history, matching actor/action/basis,
safe proposed fields and version transition; a second current-detail read handles a later concurrent
commit. Missing first-page evidence stays unconfirmed. This is **client recovery, not backend
idempotency**; no backend idempotency feature was added.

Real integration additionally proves primary account/session/CSRF/TOTP flows, version conflicts,
MFA re-review after a competing target change, and one committed PUT with lost response reconciled
without another mutation. It does not turn the other mocked failure variants into real execution.

## Automated accessibility and visual review

Both Catalog engines exercised keyboard-only rename/confirmation, labeled policy checkboxes,
dialog focus containment/return/Escape, disabled blocked actions, contextual alerts/status, history
paging, narrow 320px phone emulation, tablet/desktop and long institutional labels. Root font-size
200% checks text reflow, heading wrapping, reachable confirmation and absence of page overflow.
Print/receipt suites retain render/preview/URL-lifecycle and safety behavior using mocked PDF/API
fixtures; native OS print dialogs and actual paper are outside headless evidence.

ORG-4 visually inspected the final Chromium narrow-policy screenshot and WebKit 200%-text
confirmation screenshot. Fields, warnings and actions remain readable/reachable; no clipping or
page overflow was found in those artifacts. This is agent inspection of automated screenshots,
not a human accessibility study or proof of every viewport/assistive-technology combination.

| Manual requirement | Status |
|---|---|
| Human-observed screen-reader announcements | NOT EXECUTED |
| Native browser-menu 200% zoom | NOT EXECUTED |
| Human keyboard-only task observation | NOT EXECUTED (automated keyboard checks passed) |
| Physical phone/tablet interaction | NOT EXECUTED (emulated viewports passed) |
| Human native-browser focus/long-history usability | NOT EXECUTED (automated focus/paging passed) |
| Native OS certificate print/paper inspection | NOT EXECUTED |
| Institutional GCO/Registrar usability/UAT | NOT EXECUTED |

These gaps keep overall engineering/accessibility assurance PARTIAL. CSS text scaling is not native
zoom, and automation is not institutional UAT. Screenshots/results remain under the local evidence
root in `chromium/organization-catalog/`, `webkit/organization-catalog/`, `print-*` and `receipt-*`.
