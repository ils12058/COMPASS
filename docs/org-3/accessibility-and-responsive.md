# Accessibility and responsive evidence

Existing COMPASS PageHeader/PageAction, Panel, Notice, form controls, ContextHelp, shared Dialog,
ConsequentialActionDialog, canonical pagination and unsaved-navigation infrastructure are reused.
No custom focus trap, second modal framework, tree keyboard system or table-to-card redesign exists.

Fields have visible labels, native required/length constraints, policy fieldsets/legends and labeled
Year Level checkboxes. Duplicate code has aria-invalid and a described field error. Recoverable
errors stay in a contextual alert; successful and important recovery outcomes use status notices.
There is one review action and a target-named consequential confirmation; pending prevents duplicate
submission/dismissal. The full Program form is an inline sheet, avoiding nested modal entry.

Editor focus moves to its title. Review uses the shared alert dialog's initial focus/containment,
Escape/cancel and explicit return to Review change. History uses the shared dialog and returns to
its actual opener. The original editor opener receives focus on close; the shared focusHeading
helper supplies a safe fallback if that button no longer exists. MFA appears only after review
closes, so two modals are not nested. Its existing keyboard/security implementation is retained.

Synthetic Chromium and WebKit scenarios exercise keyboard rename/confirmation, Tab containment,
Escape, focus return, dirty cancellation, long names/codes, policy checkboxes, full impact counts,
history paging and announcements/semantic locators. At 320px, actions wrap and no horizontal page
spill occurs. 1024px tablet and desktop scenes keep the bounded hierarchy. CSS root font-size 200%
checks readable heading wrapping, text reflow, impact and reachable confirmation controls. A local
container query stacks the Structure header when its actual workspace width is narrow, including
beside the expanded dock at enlarged text size. Browser screenshots were inspected for form/hierarchy
legibility, dialog size, wrapping and meaningful pending/status presentation.

These are automated DOM/keyboard/layout checks using actual application components and mocked API
fixtures. They are not a formal accessibility audit or assistive-technology user study. No manual
VoiceOver/NVDA session, native browser-menu zoom, physical phone or institutional usability/UAT was
performed. CSS 200% text scaling is not claimed as native zoom. ORG-4 must complete these checks,
including contrast, error announcements and long translated/real approved institutional labels.
