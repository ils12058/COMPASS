# Accessibility and interaction validation

The focused synthetic Playwright suite ran in Chromium and WebKit against a local Next.js server. It exercised the Student Inventory shell at 320, 360, 390, 768, 1024, and 1440px with both 100% and 200% root text. At 320px / 200% root text, document and header widths are both 320px; all six header actions remain within the viewport, retain 88×88px targets, and do not overlap. At 100% root text, their targets are at least 44×44px. The dynamic header stays above the workspace in each checked layout.

Chromium verified the actual keyboard Tab sequence from the Skip link through mobile navigation, Overview, feature search, Accessibility settings, notifications, and Account Menu. It also checked visible focus indicators on each action. The local WebKit runner follows macOS-style form-control-only Tab navigation by default, so WebKit validation checks the authored DOM order, keyboard focusability, and visible focus style for each action. Full Tab traversal in Safari still needs a manual check with full keyboard navigation enabled.

Both engines checked Escape dismissal and focus return for Account Menu, Accessibility settings, Command Palette, and the mobile navigation drawer. They also checked `Ctrl+K` and `Meta+K`, palette search and keyboard selection, Overview navigation, notifications’ unread label and current-page state, the long role-appropriate Counselor drawer’s internal scrolling, and the desktop Counselor dock’s expanded and collapsed states.

The Account Menu was opened with the synthetic long name at 320px / 200% root text. Its popup stayed within the viewport, allowed internal vertical scrolling, and exposed Account and Sign out. The Accessibility popover stayed within the viewport, opened below its own trigger, and scrolled internally when enlarged settings exceeded available height. The Command Palette and mobile drawer fit within the viewport. Header height changes did not cover the workspace.

A synthetic edited Service form confirmed that choosing a palette destination still invokes the existing unsaved-changes confirmation and preserves the edit when navigation is canceled. The E-Counseling synthetic active-call scenario confirmed the existing sign-out confirmation flow remains active in both engines.

The root font-size setting models enlarged text. It is not browser zoom, and `deviceScaleFactor` was not used as a substitute. Playwright in this setup did not provide a reliable browser-zoom control. Manual browser-zoom verification remains: at 200% browser zoom, check 320px and 1024px effective layouts, header actions and popup bounds, document scrolling, keyboard focus, and the long-name Account Menu in current Chromium and Safari.

These automated checks are focused layout and interaction evidence. They do not establish WCAG conformance. Screen-reader and physical-device checks remain outstanding; see [followups.md](followups.md).
