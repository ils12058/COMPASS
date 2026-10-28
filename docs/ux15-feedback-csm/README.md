# COMPASS-UX15-PILOT-6 — Customer Feedback and CSM

This experimental slice modernizes the Student-facing Customer Feedback and Client Satisfaction
Measurement forms while keeping them continuous, one-time submissions tied to completed-service
opportunities. It is a review proposal, not institutional approval or rollout authorization.

**Source baseline:** `integration/ux15-modernization` at
`a4c8bed349e0a7e774f8a6bde3bb805fb0168543`
**Implementation branch:** `feat/ux15-feedback-csm`
**Pull request target:** `integration/ux15-modernization`

## Focused audit

The current Student flow begins at the Feedback opportunity list. Each available instrument is
opened with its selected opportunity ID; the form then fetches that Student-owned opportunity and
keeps the completed service label in view. Customer Feedback and CSM have separate submission
eligibility and already-submitted states.

Both forms are continuous one-page questionnaires inside one `Panel`, grouped with
`FeedbackSection`/`PanelSection`. Their shared `FeedbackRadioGroup` already uses native fieldsets,
legends, radios and browser required validation. The forms use `reportValidity()`, an explicit
review-and-submit confirmation, `Notice`, `Button`, shared inputs and the form-safety guard. The
domain components own their request bodies and submission mutations.

The interaction differences are intentional. Customer Feedback has nine sections, a service
selection tied to the opportunity, conditional “Other” and Counselor questions, and optional
respondent identity. Its length makes direct section links useful. CSM has four continuous groups;
the existing vertical layout is simple enough without additional navigation. CSM also has a
Citizen’s Charter branch and a valid numeric `0` answer for SQD Not Applicable. Neither instrument
has a server draft or Save Progress operation.

The main presentation gaps were the narrow-screen list of nine groups, choice labels with only a
40px minimum target and three columns beginning at small widths, missing explanatory copy for the
asterisk, and duplicated uncertain-submission messaging. Browser-native validation already moves
focus to missing or malformed controls, so a second form error engine or `FormErrorSummary` would
duplicate that behavior. The custom Customer Feedback service-selection error now returns focus to
its checkbox group when that exceptional branch is reached.

### Reuse and changed components

| Component | Change |
| --- | --- |
| `fe/src/features/feedback/feedback-shared.tsx` — `FeedbackSection` | Exposes the existing stable heading-ID convention so section links can target the original group headings. |
| Same file — `FeedbackRadioGroup` | Uses 44px minimum labels with visible selected, hover and focus states; keeps the original native radios and order; changes three-column groups to one column by default, two at `sm`, and three at `lg`; associates an optional hint with its fieldset. |
| `fe/src/features/feedback/customer-feedback-form.tsx` | Adds plain in-page links to the existing nine groups, focuses the destination heading, clarifies required/optional notation, increases checkbox and action targets, and focuses custom service validation. Consolidates uncertain-result copy into one warning with the existing same-intent retry action. |
| `fe/src/features/feedback/csm-form.tsx` | Clarifies required and optional information, increases action targets, and uses the same single uncertain-result warning while preserving the existing submission/retry path. |
| `fe/tests/ux15-feedback-csm.test.mjs` | Covers both continuous group structures, section-link targets, required/optional copy, and exact CSM SQD radio value order including `0`. |
| `fe/tests/ux15-feedback-csm.browser.mjs` | Synthetic Chromium/WebKit regressions for navigation, validation/focus, branching, payloads, cancellation, success, uncertain retries, opportunities, dirty navigation, keyboard behavior and reflow. |
| `fe/package.json` | Adds the focused `test:ui:feedback-csm` command. |

`FormSectionLinks` is reused for Customer Feedback; no new navigation abstraction was needed. Both
forms retain their existing presentation, query and mutation ownership. No universal form engine,
completion score, visit tracking, wizard step state, persistent draft or autosave was added.

## Invariants preserved

- All nine Customer Feedback sections, twelve rating items, question wording, option order and
  values, requiredness, bounds, and conditional fields are unchanged.
- CSM retains its four groups and all official questions, choices and values. CC1 answer 4 still
  maps CC2/CC3 to their existing N/A codes; leaving that branch clears those derived answers as
  before. SQD `0` remains a valid selected answer.
- Customer Feedback respondent name, address and mobile remain optional and blank at composition;
  no profile, academic-record or Inventory value is used to prefill them. The existing account and
  separate submission-activity explanation remains, and the response is not called anonymous.
- Opportunity ownership, eligibility, service provenance, server request contracts, response
  encryption, policy and historical records are untouched.
- The prepared body, fingerprint, idempotency key reuse, pending protection, confirmation, uncertain
  recovery and confirmed-success behavior remain domain-owned and unchanged. Canceling the dialog
  sends no request; an uncertain retry resends the exact same body with the same key.
- `useUnsavedChangesGuard` and `GuardedPortalLink` remain in use; browser Back and guarded-link
  cancellation retain the unfinished response.
- No backend file, API schema, migration, institutional instrument or authorization change is part
  of this PR.

## Workflow and branch safety

The integration branch was fetched and verified to include PRs #297–#301, with #301’s merge commit
at the source baseline above. The implementation worktree and feature branch start from that exact
integration head.

The frontend and backend targeted workflows only accept PRs targeting `staging` or
`canon/compass-clean-baseline`. The frontend workflow also filters for frontend/OpenAPI paths. The
backend-full workflow runs on pushes to those same protected baselines and only on PRs touching its
CI scripts/workflow. This PR targets `integration/ux15-modernization`, so those existing PR events do
not match. The staging deploy workflow is `workflow_dispatch` only and requires a full current
`staging` SHA. No workflow was manually dispatched, and no deployment was triggered.

## Visual evidence

The paired and state-specific synthetic screenshots are indexed in
[screenshots.md](screenshots.md). Automated browser evidence is not a manual screen-reader audit,
real-device Safari check, GCO UAT, or approval to roll out Proposal #15.

## Later adoption candidates

1. **Good Moral Request** — review the Student request and assisted-request paths separately; keep
   their ownership, correction and idempotency rules.
2. **Appointment booking** — consider the larger touch targets and concise choice presentation
   while preserving service, provider, availability and slot-selection behavior.
3. **Service, Announcement and Resource editors** — assess the shared field spacing and error-focus
   patterns for staff configuration pages without creating a metadata-driven form engine.

Each candidate needs its own focused audit and review. Existing Inventory, Exit Interview, Graduate
Tracer, Routine Intake and Counselor Evaluation pilots retain their separate draft or professional
record workflows.

This work is ready for review on `integration/ux15-modernization`. It has not been merged or
deployed; Proposal #15 remains experimental pending team acceptance.
