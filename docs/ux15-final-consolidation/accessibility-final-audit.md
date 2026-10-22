# Accessibility and Responsive Audit

## Automated coverage

Automated Playwright checks ran against local Next production builds with synthetic API responses.
The form consolidation matrix checked each of the seven form experiences at **320, 390, 768, and
1440 CSS px**, at default and simulated **200% root text size**: 56 matrix cases per engine. Five
additional cases cover all Inventory choice targets, finalized Evaluation, and Evaluation opened
inside the existing Counseling workspace. The suite passed **61/61 Chromium** and **61/61 WebKit**.

Home suites covered the following responsive widths:

- Student: 320, 360, 390, 768, 1024, and 1440 CSS px, including enlarged root text, shell/dock, and
  announcements cases.
- Counselor and Head: the same six widths, normal and enlarged text, with authorized and restricted
  views and expanded/collapsed dock coverage.
- GSS: the same six widths plus a 320px/200% root-text case, including a long synthetic name and a
  collapsed dock.
- Portal Shell: header actions, mobile navigation drawer, command palette, accessibility popover,
  account menu, notifications, focus return, and expanded/collapsed desktop dock.

The browser suites' geometry checks found no unintended overflow in the exercised final UX15 form,
Home, or shell cases. Inventory's previously reproduced 1024px/200% text issue, Student
Announcements at 320px/200%, shell overflow at 320px/200%, Evaluation wrapping, and form-choice
targets are covered by the relevant regression tests. This statement applies to those measured
surfaces and states, not every page or all conditional records in COMPASS.

## Keyboard, focus, and dialogs

- Automated checks cover skip-to-content, authored navigation order, visible focus, native form
  control behavior, section/error-summary destination focus, mobile drawer and dialog dismissal,
  focus return, command-palette shortcuts/search/selection, and the existing dirty-form navigation
  guard.
- Chromium checks sequential Tab order in the exercised shell/Home paths.
- The local WebKit automation follows macOS form-control-only Tab defaults. WebKit checks
  authored DOM order, native focusability, visible focus, and activation; it does not prove full
  Safari Tab traversal with Full Keyboard Access enabled.
- Popovers and dialogs use existing primitives. No hand-built focus trap or new modal layer was
  introduced.

## What was not tested

- Simulated 200% root text is **not** actual browser zoom. Actual Chromium and Safari zoom were not
  performed.
- No screen reader was used. Speech order, live-region announcements, rotor/landmark behavior, and
  modal announcements need manual assistive-technology review.
- Playwright WebKit is not physical Safari. No physical phone/tablet touch test was performed.
- Contrast was not exhaustively measured, forced-colors/high-contrast mode was not audited, and
  automated checks do not prove complete accessible names for every conditional combination.

## Manual acceptance still required

Use the approved institutional browsers and devices to verify actual zoom at 200%, keyboard-only
operation, dialogs/popovers, focus visibility and return, Student form summaries/errors, Home
navigation, and responsive touch behavior. Perform manual screen-reader checks with the
institution's supported assistive technology. Record browser/OS/version, role, test data class,
actual result, evidence, and any defect in the blank [UAT matrix](uat-matrix.md).

These checks are not represented as complete. This is not a WCAG conformance report or
accessibility certification.
