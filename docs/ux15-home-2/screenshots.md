# Synthetic visual evidence

All samples use synthetic identities and intercepted responses. The before view is rendered from the exact verified integration baseline, while after views use this feature branch's production build.

## Before — Counselor using the shared Overview

[Open the 1440px synthetic Counselor baseline screenshot](screenshots/before/chromium/ux15-counselor-home/before-counselor-shared-overview.png).

The baseline had the shared professional attention list and summary/announcements composition. It did not put the Counselor's today-only Appointment agenda beside My work.

## After — Counselor Home

| Scenario | Chromium | WebKit |
| --- | --- | --- |
| Desktop: today's agenda beside canonical My work | [View](screenshots/after/chromium/ux15-counselor-home/after-counselor-desktop-agenda-work.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-counselor-desktop-agenda-work.png) |
| Desktop: no pending work | [View](screenshots/after/chromium/ux15-counselor-home/after-counselor-desktop-no-work.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-counselor-desktop-no-work.png) |
| Head with authorized oversight destinations | [View](screenshots/after/chromium/ux15-counselor-home/after-head-authorized-oversight.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-head-authorized-oversight.png) |
| Head without optional management capabilities | [View](screenshots/after/chromium/ux15-counselor-home/after-head-without-optional-capabilities.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-head-without-optional-capabilities.png) |
| Stale agenda with last-confirmed rows and retry | [View](screenshots/after/chromium/ux15-counselor-home/after-stale-agenda.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-stale-agenda.png) |
| Mobile, 390px | [View](screenshots/after/chromium/ux15-counselor-home/after-counselor-mobile-390.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-counselor-mobile-390.png) |
| 320px, 200% root text | [View](screenshots/after/chromium/ux15-counselor-home/after-counselor-320-200-text.png) | [View](screenshots/after/webkit/ux15-counselor-home/after-counselor-320-200-text.png) |

## Non-regression evidence

- [Student Home at desktop](screenshots/non-regression/chromium/student-home-after-desktop.png) — synthetic Student scenario from the updated Home suite.
- [GSS existing Overview](screenshots/non-regression/chromium/gss-existing-overview.png) — synthetic GSS scenario, retaining the shared professional Overview composition.
- [Chromium layout measurements](screenshots/after/chromium/ux15-counselor-home/geometry.json)
- [WebKit layout measurements](screenshots/after/webkit/ux15-counselor-home/geometry.json)
- [Chromium Counselor results](screenshots/after/chromium/ux15-counselor-home/results.json)
- [WebKit Counselor results](screenshots/after/webkit/ux15-counselor-home/results.json)

Viewport assertions cover 320, 360, 390, 768, 1024, and 1440 CSS pixels at normal and 200% root font size. The 200% case is text enlargement and is not a substitute for browser zoom or assistive-technology review.
