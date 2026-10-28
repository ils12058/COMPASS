# Accessibility audit

Local synthetic browser audit of all seven experiences at integration baseline
`757eb933786b8067724394c365d3a760279a1627`, with selective presentation corrections.
This is not a WCAG conformance assessment or manual screen-reader test.

## Automated checks

`fe/tests/ux15-consolidation.browser.mjs` uses the existing local Playwright harness and real
Next pages. It adds DOM/geometry checks, not an axe/pa11y scan or a new testing dependency:

- Each of the seven experiences at **1440, 768, 390 and 320px**, at both default and **200% root
  text**: 56 cross-form cases per engine. Root text enlargement is not browser zoom emulation.
- Unique IDs; existing accessible labels for native inputs; resolved `aria-labelledby` and
  `aria-describedby` references in the exercised states. This does not test every ARIA rule or
  claim complete accessible-name computation.
- Whole-page horizontal overflow at default text size. At enlarged text, independent form-sheet
  scroll/client dimensions and viewport-edge checks exclude content inside intentional local
  matrix scrollers. The global header's failing measurements are retained, not hidden.
- Enter activation of the continuous section links focuses the original named destination and
  leaves it visible. Navigation sends no unsafe API operation.
- Two extra Inventory cases inspect every selectable section and actual choice-label heights at
  1440/320px, including an added sibling and the conditional boarding-house Boolean group.
- One extra finalized Evaluation case verifies 320px/200% sheet reflow and read-only content.
- Two focused cases exercise draft/finalized Evaluation through the existing Counseling workspace
  entry point at 320px/200%. The same renderer is covered in both contexts without changing the
  surrounding workspace. Total: 61 distinct audit cases per engine.

Existing pilot suites supply domain-specific native-keyboard, error-focus, matrix-scroll,
confirmation, pending/success/failure, read-only, dirty-guard and submission-recovery checks.
The exact executed counts and reruns are in [validation.md](validation.md). Passing fixtures do
not prove server authorization, encryption, concurrency or end-to-end persistence.

## Findings corrected

| Finding | Reproduction | Change and verification |
| --- | --- | --- |
| Smaller choice targets in Inventory | Local checkbox helper minimum 32px, Boolean/transport 36px and sibling marker 40px, compared with other pilot choice targets at 44px. Family sample measured 32/40px depending on wrapping. | Existing labels now use 44px minimums. Native controls, focus, values, labels and option order stay unchanged; browser coverage visits all sections and the conditional helper. |
| Smaller Exit Interview checkbox targets | At 390px, all 11 initially visible checkbox labels measured 36px. Rating labels were already 44px. | Existing `ChoiceCheckbox` labels use 44px minimums. Conditional answers and native radio/checkbox behavior are exercised by the existing Exit suite. |
| Evaluation text exceeded its own sheet | At 320px/200% text, editable Evaluation client/scroll width was 254/267px; finalized content was 254/287px. Previous viewport-only checks missed the spill into surrounding padding. | Inherited emergency wrapping on the existing editor panel and read-only answer content. Corrected editable/finalized measurements are 254/254px in the focused Chromium reproduction. Final results also cover WebKit. No clipping, hidden text or reduced font/target size. |

44px is the pilots' touch-comfort convention. These smaller baseline targets are not, by that
measurement alone, declared WCAG failures. The Evaluation correction changes wrapping only;
official strings and user-authored narrative values are untouched.

## Keyboard, focus and status assessment

Headings and named form groups retain their actual institutional hierarchy. Panel sections are
not replaced with generic cards or simulated controls. Native labels, fieldsets, legends and
rating choices remain in place. Inventory keeps its free section selection and effect-based
field focus; its native mobile selector retains focus. Continuous forms keep mounted sections,
explicit destination focus and existing scroll margins. E/G's Back to sections behavior stays
in their existing pilot regressions. No forced order, percentage, active-scroll tracker or new
keyboard handler is introduced.

Error summaries remain supplied by domain validators and focus their original field or rating.
Feedback/CSM retain browser-native required/numeric/email validation and their original controls.
Intake's conditional Other field retains its inline description and error association. Evaluation
does not acquire a new required answer or error-summary engine.

`FormSaveStatus` keeps one mounted polite status. Its owners compare against canonical saved data;
failed saves do not clear dirty state. One-time forms do not receive a Saved indicator.
ConsequentialActionDialog and the existing Radix-based dialog/return-focus infrastructure retain
their accessible names, cancel/confirm focus and pending protection. No dialog/safety primitive
source changes. Automated focus checks are not an assertion about spoken announcements.

## Global portal header — remains deferred

Reproduction: open any of the seven synthetic forms at **320px**, set the root font to **200%**.
The page and header scroll width remain **417px** for a **320px** viewport, while the corrected
form sheets fit their own available width. The account-menu control reaches x=417px. The header
also squeezes/overlaps available space among the left navigation/overview/search controls.

Source inspection identifies `fe/src/features/portal/components/portal-shell.tsx`: a single
unwrapped flex header combines the mobile navigation/mark, a flexing command-palette area and a
nonshrinking account-controls group. Minimum targets/gaps grow with rem text sizing. Related
components are `portal-command-palette.tsx`, `accessibility-control.tsx`, `notification-bell.tsx`
and `account/components/account-menu.tsx`. This is shared shell layout, not questionnaire width.

Actual impact: the account action extends outside the initial viewport and other header controls
compete for space; a reader needs horizontal movement and may encounter overlapping targets.
Do not call whole-page enlarged-text reflow passing. Recommend a separate **P1 portal
accessibility-hardening PR**, preserving controls, target sizes, focus order and discoverability.
No shell source is changed here. A representative screenshot retains the visible header overflow.

## Remaining verification

Manual screen-reader testing, physical-device Safari/Chrome, browser zoom, alternative input,
high-contrast/forced-colors review, systematic contrast measurement and GCO UAT were not performed.
The baseline DOM checks do not exhaustively explore every possible conditional combination;
the existing domain suites cover their named synthetic scenarios. Use [followups.md](followups.md)
for recommended tasks, priorities and dependencies. Proposal #15 remains experimental.
