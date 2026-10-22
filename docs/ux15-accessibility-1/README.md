# COMPASS-UX15-ACCESSIBILITY-1 — Portal Shell Reflow and Accessibility

This slice fixes the shared authenticated Portal Shell at narrow widths and enlarged text while preserving its current navigation and account workflows. It is an experimental UX15 proposal, not a Student Home or workspace redesign.

The feature branch is `feat/ux15-portal-accessibility`, based on the fetched `integration/ux15-modernization` commit `af171d2a41fb1dab4d83b04fc9c285cec6365ce8` (2026-10-22). That base contains the six UX15 pilots and consolidation PR #303.

The confirmed cause was a single unwrapped header flex row. At 320px with the root font set to 200%, its intrinsic control widths competed for one row: multiple targets overlapped, the Overview target collapsed to 16px, and the long-name Account Menu extended beyond the viewport. The same header pattern also made its responsive behavior depend on the desktop dock’s remaining content width.

The header now wraps its existing controls in DOM order. The mobile navigation and Overview link stay together; the search trigger retains flexible space; the utility controls can move to a separate row while keeping their existing touch-target sizes. The header’s height grows with its contents, and the workspace begins below it. No new navigation system, breakpoint, or JavaScript viewport listener was added.

Three directly affected controls were tightened around that layout. The Account Menu trigger and popup stay within the viewport, with long identity text wrapping or truncating and the menu scrolling within the available height. The header Accessibility popover is anchored to its own trigger, so it follows the header as it wraps and can scroll when enlarged text makes its contents taller than the viewport. The Command Palette records the clicked trigger and restores focus after the native dialog closes, including in WebKit.

Portal navigation, Overview, feature search and `Ctrl+K`/`Meta+K`, text-size and spacing preferences, underline and reduced-motion switches, notifications and unread count, account actions, unsaved-form confirmation, and active-call sign-out protection remain available. The change does not alter domain behavior, authorization, API contracts, or session handling.

Production changes are limited to:

- `fe/src/features/portal/components/portal-shell.tsx`
- `fe/src/features/portal/components/portal-command-palette.tsx`
- `fe/src/features/accessibility/accessibility-control.tsx`
- `fe/src/features/account/components/account-menu.tsx`

Synthetic before/after measurements and browser checks are in [baseline.md](baseline.md), [accessibility-validation.md](accessibility-validation.md), and [validation.md](validation.md). The visual evidence index is in [screenshots.md](screenshots.md). Remaining findings and manual checks are in [followups.md](followups.md).
