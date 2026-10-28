# Follow-ups

Priorities are recommended sequencing, not authorization to change domain rules or deploy.

## Correctness/security

- **P1 — Routine Intake uncertain submission (separate PR).** `routine-student-intake.tsx`
  does not canonically reconcile generic network/5xx uncertainty. The dialog can retain its error
  and the instruction to refresh; it does not establish whether the server committed. Review the
  authorized `routineInterviewsGetMine` response, submitted/draft states, 409 codes, parent query
  behavior and stale-read/concurrency guarantees with the backend/API owner. Require a successful
  status read before another deliberate confirmation, retain answers on read failure and never
  auto-resubmit. Test committed-but-response-lost, still-draft, denied/unavailable and failed-read
  cases. The existing submit service locks/checks state; do not invent a new submission identity
  or equate advisory copy with reconciliation. This known limitation is intentionally unchanged.
- **P2 — Feedback generic HTTP uncertainty (separate PR).** The exact body/key retry applies to
  retained network/idempotency uncertainty. Generic 408/5xx currently clears intent and advises
  checking status. Review the backend idempotency result/error contract and opportunity refresh
  together before broadening recovery. Preserve optional identity, body/fingerprint/key integrity
  and the distinction between a new edited intent and a retry. No security boundary expansion is
  proposed; the audit did not establish a new immediate security blocker.

## Accessibility

- **P1 — Portal header enlarged-text reflow (separate PR).** Reproduced in all seven contexts:
  viewport 320px, root font 200%, page/header scroll width 417px. `PortalShell` uses one unwrapped
  header row; rem-sized minimum controls, the overview mark, command-palette trigger and
  nonshrinking account group compete for the width. `AccountMenu` reaches beyond the viewport.
  A dedicated slice should preserve access to navigation, feature search, Accessibility,
  Notifications and account actions while allowing useful wrapping/reorganization. Include
  keyboard order, focus visibility, account-menu/drawer behavior, long names, 320–1440px,
  200% text and browser zoom. Do not fix by clipping the page or shrinking required targets.
  Dependencies: shell/accessibility owner review; no questionnaire or backend change needed.
- **P2 — Assistive-technology review.** Check required-group announcements, matrix headers and
  native radio traversal, summary-to-original-field descriptions, canonical status announcements,
  dialog focus trap/return, read-only records and conditional content with VoiceOver/Safari and
  another supported desktop screen reader/browser. DOM association checks do not verify speech.

## UX consistency

- **P3 — Observe return-to-sections usefulness during GCO UAT.** E/G have footer return links;
  R/F have top navigation and C/P have no rail. Add controls only if actual task testing warrants
  them. Preserve optionality and continuous layouts; a separate PR only if changes are justified.
- **P3 — Check target comfort on actual phones.** This slice adopts the established 44px choice
  label convention for the smaller I/E choices. Physical-device testing should assess spacing and
  label wrapping; it must preserve native controls and every answer option.

## Architecture/maintainability

- Retain domain-owned payloads, validators, focus fallbacks, saves and submission/finalization
  state. No universal engine or second safety provider is recommended.
- Carry the matrix into the future Student Home/role-adaptive architecture review after this
  consolidation is reviewed and merged. That phase requires its own specification and PRs;
  this slice implements no Home, portal navigation, Counselor/GSS workspace or Service Catalog work.
- Existing integration-targeted hosted-CI branch exclusion remains visible in validation.
  Any future CI coverage change needs a separately justified review, not a workflow dispatch
  or branch retargeting in this slice.

## Manual testing and GCO UAT

- **P2 — GCO and Student task review before acceptance.** Cover unfinished/partial drafts,
  save failure and deliberate retry, corrections, conditional Other, graduated eligibility,
  optional Intake answers, professional null/1–10 ratings and Encounter finalization,
  optional blank respondent identity and CSM zero/N/A branching.
- **P2 — Real-device Safari/Chrome and browser zoom.** Test 320/390px phones, tablet rotation,
  200% text/zoom, touch targets, matrix scroll reachability, keyboard focus and confirmation.
- **P2 — Domain integration testing for uncertainty.** Local intercepted APIs validate frontend
  behavior, not database locking, encryption enforcement, authorization or network races against
  a running backend. Use synthetic institutional test accounts through a separately approved test
  process. No live Student/Counselor content is required.

No follow-up here constitutes institutional policy approval, WCAG certification or deployment
authorization. Proposal #15 remains experimental pending team and GCO acceptance.
