# Frontend confidentiality and accessibility

Routes and generated contracts PASS the focused checks. Existing coverage UI is preserved; this slice adds browser evidence only. Source inspected: coverage page/request/detail, `protected-record.tsx`, `use-coverage-privacy.ts`, `coverage-safety.ts`, portal session ownership/revalidation, shared consequential dialogs, Query transport and `public/sw.js`.

## Protected state

Body query keys include confirmed account, Grant, Grant version, source/Handoff identity and authorization generation. The detail remount key additionally includes session, role and sorted capabilities. Protected queries have zero retention after observation (`gcTime:0`), no retry, zero stale time, focus/reconnect rechecks and a 15-second active-query interval. The server independently authorizes every body request; a browser key/generation is only a cancellation barrier.

Clear/cancel/remove and unmount after known expiry, denied or failed body refresh, policy loss, account/session/role/capability revalidation, offline, hidden tab and matching content-free tab hint. Ordinary observer cancellation is distinct from revocation; React effect replay invalidates obsolete completions without fabricating a new authorization. Late HTTP responses cannot repopulate an invalid generation. A deliberate Check access again fetches Grant/configuration and requires a fresh protected read; it never replays a mutation.

| Boundary | Evidence | Result |
| --- | --- | --- |
| Logout / account switch | Existing two synthetic session-change browser cases; account-cache ownership unit tests | PASS |
| Role / capability loss | New CONT-4 cases with changed same-account session projection and denied body refresh | PASS |
| Grant revocation / expiry | Status denial, expiry clock, tab hint, backend-denial browser cases; new two-real-tab hint case | PASS |
| Student affiliation change | New browser case simulates authoritative 404 after an already open Evaluation and Handoff; real backend affiliation tests are separate | PASS for clearing behavior |
| Failed reauthorization / policy invalidation | Backend-denial and policy-loss browser cases | PASS |
| Offline / reconnect / hidden tab | Existing clearing cases, deliberate recheck and no silent resurrection | PASS |
| Late response / cancellation / generation replay | Existing deferred-response browser case and `case-coverage.test.mjs` barrier tests | PASS |
| Cross-tab | New same-origin two-page BroadcastChannel case asserts exact `{grant_id}` message and clears an open record | PASS |
| Stale confirmation / draft conflict | Existing background-version closure and deliberate saved-version review cases | PASS |
| Persistent browser storage | Sentinel absent from local/session storage in browsers; source inspection finds no body persistence/IndexedDB/query persister/SW API cache | PASS for stated checks; forensic browser-cache inspection NOT VALIDATED |

Both Evaluation and Handoff are open in the new authority-loss scenarios; both disappear on failure. Browser HTTP APIs are mocked and outbound providers are blocked. These tests establish client behavior, not genuine backend authorization; the latter uses real PostgreSQL and authenticated encryption tests.

Remote changes are discovered at the next backend request, active polling or session/focus/reconnect check. Timers can be delayed by browsers and connectivity. An invalidation hint can clear immediately if received, but cannot grant access. There is no claim of instant remote recall. Earlier authorized responses, screenshots, memory and manual copies remain outside technical recall.

## Workflow and presentation

Planned and unexpected-absence selection, exact recipient/source/date review, independent approval/decline/cancel/revoke, scheduled/active/expired states, optional Handoff lifecycle, stale versions and unavailable policy are exercised. No missing policy is represented as operational success. Approver views do not request body endpoints. Receivers use only the exact selected-source operations; no secondary ordinary detail fetch enriches the projection. Omitted fields, null ratings and empty text remain distinct.

Chromium and WebKit each execute the same 41 existing coverage scenarios plus six CONT-4 scenarios, and 20 Student Summary/Context confidentiality scenarios: **67 distinct scenarios / 134 engine outcomes**. The Summary group rechecks all four Context anchors with/without summary capabilities, no retired background request, author publication, Student published-only detail, canonical Notification destinations and the removed frontend route without redirect/body. The new keyboard scenario checks repeated forward/reverse Tab containment, Escape and return focus in approval confirmation. Existing scenarios exercise accessible labels/names, required/date fields, error/status messages, recipient/expiry confirmation, unsaved text, desktop, mobile portrait, long wrapping and 200% CSS zoom. CSS zoom is not an operating-system browser zoom or screen-reader certification.

Representative Chromium mobile Evaluation and WebKit mobile confirmation screenshots were visually inspected; text wraps within the viewport and the confirmation retains recipient, Student, selected sources, expiry and actions. Page titles/route metadata and tab hints contain no professional body or Student narrative; authenticated bodies are not embedded into public page-preview metadata.

**NOT VALIDATED:** physical phone/tablet, OS-level previews/back-forward snapshots, screen readers, magnification/high-contrast assistive technology, production proxy/cache behavior, institutional usability and production policy/provider interactions. These require the separately authorized [UAT package](uat-package.md); automated synthetic results do not imply those evaluations occurred.
