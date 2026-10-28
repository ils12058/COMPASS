# SIMPLIFY-2A follow-up: product experience

University of Camarines Norte (UCN) · reviewed 28 October 2026 · baseline
`integration/ux15-modernization` at `843e96ebde4f22d9668b80e0bde3a17a3a5de54c`.

## Completed and proposed

The Home pilot is **complete and merged** in [PR #338](https://github.com/ils12058/COMPASS/pull/338).
Its [before/after pairs](README.md) show the initial pilot. This follow-up implements the corrected
[app-like composition](composition-refinement.md), shared interaction patterns and bounded fixes for
Messages, Good Moral, Graduate Tracer, Service Catalog and the booking roadmap. The observations
below record the original baseline; remaining candidates are distinguished from completed changes.

## Representative assessment

This is a bounded source review, not an exhaustive product audit. The linked renders use synthetic
fixtures; the remaining observations are source-based and need visual verification before redesign.

| Area | Current evidence and direction |
| --- | --- |
| Appointments | [Booking](../../fe/src/features/appointments/appointment-booking-page.tsx) already uses one progressive sheet with numbered sections and a final review; a separate roadmap repeats that sequence. [Managed list, 375px](product-screenshots/appointments-375.png) uses a bounded results surface and floating search/filter control. Keep slot freshness, prerequisites and booking recovery. The booking interaction candidates remain in the existing SIMPLIFY-3 plan. |
| Service Catalog | [List](../../fe/src/features/services/services-list-page.tsx) uses divided rows and contextual filtering. In the [390px render](product-screenshots/services-390.png), pathway and flexible-booking status occupy separate labels; consider a single clearer summary that still distinguishes supported pathways from an enabled booking option. |
| Guidance Messages | [Workspace](../../fe/src/features/guidance-messages/guidance-messages-workspace.tsx) intentionally switches between directory and conversation rather than stacking panels. In one [390px conversation](product-screenshots/messages-390.png), the composer extends slightly below the initial viewport; see priority 1. Preserve confidential content, focus return, scroll position and unsent-message identity. |
| Individual Inventory | [Editor](../../fe/src/features/inventory/editor/inventory-editor.tsx) uses one sectioned editor with section navigation, draft controls and review. The [390px capture](product-screenshots/inventory-390.png) is long because it shows actual form fields; improve orientation and action proximity only where evidence supports it, without changing controlled questions or validation. |
| Counseling and E-Counseling | [Counseling](../../fe/src/features/counseling/counseling-workspace.tsx) uses contextual tabs with separate content surfaces. [E-Counseling](../../fe/src/features/ecounseling/ecounseling-workspace.tsx) gives the call stage and media state priority; [Phone prejoin](product-screenshots/ecounseling-prejoin-390.png) and [desktop test-call](product-screenshots/ecounseling-test-call-1440.png) captures are synthetic. Preserve active-call continuity, capture/consent states and confidentiality; no decorative art in confidential work. |
| Guidance Follow-Ups | [List](../../fe/src/features/guidance-followups/followups-list.tsx) combines status, workload, filtered results and search; distinct empty and error states are intentional. Consider reducing repeated list explanation after observing real use, but retain scope, responsibility, timing and lifecycle consequences. |
| Good Moral | The [request page](../../fe/src/features/good-moral/good-moral-request-page.tsx) presents F4/F6 distinctions and eligibility. In the [F6 capture](product-screenshots/good-moral-1440.png), the selection page and embedded form repeat a page heading and Back link. Preserve F4/F6 eligibility, unverified degree guidance and uncertain-request recovery. |
| Exit Interview | [Form](../../fe/src/features/exit-interviews/exit-interview-form.tsx) has a single sheet, in-page section links and saved-draft/submit controls; the [390px capture](product-screenshots/exit-390.png) shows a deliberate mobile reading order. Preserve controlled questions, ratings, unsaved work and review. |
| Graduate Tracer | The [student workspace](../../fe/src/features/graduate-tracer/graduate-tracer-student-workspace.tsx) and [form](../../fe/src/features/graduate-tracer/graduate-tracer-form.tsx) repeat the survey title in the [390px capture](product-screenshots/tracer-390.png). A later heading/section pass can keep the draft privacy, save-before-submit and finality guidance intact. |
| Reports | [Index](../../fe/src/features/reports/reports-index.tsx) offers two scope-derived report destinations as bounded links, without invented metrics. Keep the distinction between global and college scope; no blanket card removal is justified by source alone. |
| Organization | [Structure](../../fe/src/features/organization/structure/organization-structure-page.tsx) now preserves Campus → College → Program with divided children and contextual actions from SIMPLIFY-1B; do not turn each Program into a card. Retain separate Catalog and relationship authority, policy and history. |
| Account Management | [Accounts list](../../fe/src/features/accounts/list/accounts-list.tsx) uses explicit Search/Enter, applied filters, a results panel and pagination; the [393px capture](product-screenshots/accounts-393.png) uses a deliberately long synthetic identifier. Keep identity legibility, role/status context, access review and session consequences. |

## Interface decisions to reuse

- Keep one page title and one clear primary work region; use a bounded surface for a genuinely
  stateful task and headings/dividers for secondary links or related facts. Keep meaningful sections
  and row identity; do not remove framing mechanically.
- Keep relevant actions beside the task, with visible labels, existing Lucide vocabulary and
  keyboard focus. Retain existing `PageAction`, `FloatingListTools`, dialog and form primitives;
  shared patterns were subsequently adjusted for the approved icon-and-label composition.
- Put search, filters and empty/loading/error states where the collection already expects them;
  distinguish filtered-empty, denied, stale and unavailable. Check floating controls against
  pagination and fixed composers at phone widths and enlarged text.
- Remove duplicate orientation and generic helper copy only when the remaining label gives enough
  context. Keep consent, authorization, saved-history, uncertain-outcome and controlled-form
  information at the decision; never hide material warnings in a tooltip.
- On mobile, order work before secondary context and maintain reachable actions, readable long
  names, touch targets and focus. A viewport screenshot is not a native zoom or screen-reader test.

## Original candidates and disposition

Candidates 1–4 and the duplicate booking roadmap in candidate 5 are implemented in this follow-up.
The original observations and baseline captures are retained here for traceability. The remaining
[prioritized follow-on shortlist](composition-refinement.md#follow-on-candidates) is separate.

1. **Messages phone viewport:** reproduce and correct the composer/viewport relationship on
   `/portal/messages`. In Chromium's synthetic 390×844 phone scenario after opening an Office
   conversation, the input rectangle ended at 849px with `scrollY=0`; the document was 888px
   high. The existing “composer is on screen” assertion failed twice, while scrolling remains
   possible. Check safe areas, keyboard, call-dock clearance, viewport resizing, tab focus and both
   engines; do not alter message content, send/retry identity, privacy or realtime behavior.
2. **Good Moral request hierarchy:** avoid the embedded form's second page heading and Back link
   when it appears under certificate selection. Keep a usable heading and standalone return path for
   other entry contexts. Verify F4/F6, access, drafts, uncertainty and keyboard behavior.
3. **Graduate Tracer orientation:** review the repeated survey page/section title and nearby
   navigation on narrow screens. Preserve all instrument wording, draft privacy, section links,
   save/submit distinction, validation and unsaved-navigation safeguards.
4. **Service Catalog row summary:** prototype one concise booking summary on desktop and phone,
   retaining flexible/fixed/group support, actual enablement and duration. Coordinate with the
   existing SIMPLIFY-3 W3 candidate rather than implementing it twice.
5. **Appointments and account collection controls:** compare floating search/filter placement
   against pagination and long identities at 320–390px. Preserve each collection's existing search
   timing, applied filters, sort, authorization and empty-state semantics. Booking's duplicate
   roadmap/acknowledgment is already tracked under SIMPLIFY-3, separately from this visual pass.

These are scoped candidates, not a single implementation PR or a new policy. Recheck current
rendering and owning tests at the start of each slice.

## Illustration handoff

The asset owner retains `fe/public/illustrations/`, `fe/public/brand/` and public illustration
components. This baseline contains the four existing illustration PNGs; no new 3D filenames or
completed conversions are assumed. Candidate surfaces for a later, separately reviewed integration:
a restrained Student Home welcome or an appropriate service-discovery/empty state, only where
copy and layout remain usable without art. Avoid task lists, sensitive records, live Counseling
and security/error states. The asset owner should provide the actual approved file path, intended
surface, dimensions, transparency and alt/decorative intent; the integrating change can then verify
fit and mobile behavior. Follow existing illustration guidance until its owner updates it.

## Evidence and limits

Current source was reviewed at the baseline above. Chromium synthetic captures include the
appointments list, Service Catalog, Messages, Inventory, Exit Interview, Graduate Tracer, Good
Moral, Accounts and E-Counseling prejoin; desktop and phone cases were sampled where the fixtures
supported them. Other entries are source-only. The original Service Catalog responsive fixture failed twice because its sample lacked the
`booking_pathways` value consumed by the UI; the fixture was corrected. The original Messages
phone containment assertion failed twice as described above; the follow-up changes the measured
viewport relationship and rechecks it with synthetic fixtures. These findings are not UCN acceptance
or proof of a live-system failure.

The production-build E-Counseling active-call fixture could not use the development/test-only fake
Daily seam; the same case passed in a separate loopback test build with the existing fake seam enabled. No real provider,
production account, database or institutional record was accessed. The Home pilot's earlier
Chromium/WebKit, keyboard and enlarged-text results are documented in PR #338; native screen
reader, native zoom, physical-device, authenticated Home integration and UCN user testing remain
unperformed.
