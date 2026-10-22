# Synthetic screenshots

All screenshots use synthetic accounts, names, Appointments, Work Queue items, and aggregate values. No institutional records are accessed. The former shared GSS Home is captured in the HOME-2 evidence as the before reference:

- [Before — GSS shared Overview (Chromium)](../ux15-home-2/screenshots/non-regression/chromium/gss-existing-overview.png)

The HOME-3 browser suite captures after screenshots in both engines:

| Scenario | Chromium | WebKit |
| --- | --- | --- |
| Desktop work and office workload | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-desktop-work-operations.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-desktop-work-operations.png) |
| Managed Appointment preview | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-desktop-managed-appointments.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-desktop-managed-appointments.png) |
| Desktop with Portal dock collapsed | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-desktop-work-operations-dock-collapsed.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-desktop-work-operations-dock-collapsed.png) |
| No work, schedule remains | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-desktop-no-work.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-desktop-no-work.png) |
| Restricted Appointment capability | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-restricted-capabilities.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-restricted-capabilities.png) |
| Stale, partially refreshed data | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-partial-stale-data.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-partial-stale-data.png) |
| 390px mobile | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-mobile-390.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-mobile-390.png) |
| 320px at simulated 200% root text | [PNG](screenshots/after/chromium/ux15-gss-home/after-gss-320-200-text.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-gss-320-200-text.png) |
| Counselor Home non-regression | [PNG](screenshots/after/chromium/ux15-gss-home/after-counselor-non-regression.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-counselor-non-regression.png) |
| Student Home non-regression | [PNG](screenshots/after/chromium/ux15-gss-home/after-student-non-regression.png) | [PNG](screenshots/after/webkit/ux15-gss-home/after-student-non-regression.png) |

Per-engine `results.json` records the 16 passing browser checks. `geometry.json` records document width and root font size at 320, 360, 390, 768, 1024, and 1440 CSS pixels, plus 320px with a simulated 200% root font size. This text enlargement is a CSS simulation, not browser zoom. Automated checks do not replace screen-reader review.
