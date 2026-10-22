# Accessibility and responsive evidence

The local Chromium and WebKit campaigns use real COMPASS pages with intercepted
synthetic HTTP. Center desktop: 1440x1000; phone: 390x844 (touch/mobile emulation).
Email previews: 390px and 680px widths. Existing realtime/browser scenarios also
exercise a 320px heads-up. See validation for exact per-suite counts and evidence.

Automated checks inspect no document horizontal overflow, semantic ordered-list/
article structure, labeled actions and unread status, focused keyboard Enter activation,
error alerts/retry, successful/failed read state and already-read navigation. Loading
uses the existing polite status and aria-busy region; separate coverage holds the
HTTP response until the busy state is inspected. Existing primitives supply visible
focus rings and motion-reduce transitions. API denial pages hide protected record facts.

Saved long-copy desktop/mobile Center screenshots were visually inspected. Long
sentences wrap within the content panel; named Open action, time, unread wording,
mark-all command and preferences link remain available. No Notification Center
production design change was warranted. The OS dark-color-scheme preference and
reduced motion are exercised on mobile; the current app has no alternate dark theme,
so this is preference compatibility, not certification of a separate dark palette.

Local email screenshots include desktop Scheduled, long-label mobile and mobile
Good Moral issuance. These validate browser layout only. No installed axe/automated
WCAG scanner is part of the repository test dependencies, so no axe/WCAG audit pass
is claimed. Role/label/keyboard checks are narrower supporting evidence.

Real screen-reader announcements, full keyboard/focus usability acceptance, phone
hardware, browser zoom and institutional accessibility sign-off remain Not executed.
Browser engines in headless emulation are not physical Safari/iPhone acceptance.
