# SIMPLIFY-3C — booking orientation

Baseline: `4bfc1b4185c46cff2a40598f071bad1f2e40168e` on `integration/ux15-modernization`, fetched 29 October 2026. This is a bounded Student booking change, not completion of the wider SIMPLIFY-3C or application audit.

The previous full-width “Ways to get support” panel put three explanatory rows ahead of the service-selection sheet. The same pathways now sit in an unframed introduction with concise links; the service sheet remains the active workspace. Contextual Help retains the explanation of appointment choices and recovery. The existing schedule/eligibility qualification and unavailable messages remain visible. The illustration is larger and softly masked into the right edge of the background, while its unchanged source remains decorative. It is suppressed in narrow containers so it does not squeeze the text. The same treatment is applied to the already-approved Good Moral and Graduate Tracer introductions, under their existing safe-state conditions. My appointments remains in local navigation; My Registrations remains available when previously permitted.

The change does not query availability from navigation or claim that a published opportunity exists. It leaves pathway access conditions and all booking, freshness, idempotency, error and recovery logic in their existing owners.

## Synthetic before/after

Local Next development server with the same synthetic Student and service fixture at each size. The fixture has group browsing access but not scheduled-slot catalog access, so the unavailable message is visible; it is not evidence that fixed slots are generally unavailable.

| Viewport | Before | After |
| --- | --- | --- |
| 320px | [Before](screenshots/before-320.png) | [After](screenshots/after-320.png) |
| 390px | [Before](screenshots/before-390.png) | [After](screenshots/after-390.png) |
| 1440px | [Before](screenshots/before-1440.png) | [After](screenshots/after-1440.png) |

The [Good Moral introduction before](../simplify-2c/screenshots/after-good-moral-1440.png) and [after](screenshots/after-good-moral-1440.png), and the [Graduate Tracer introduction after](screenshots/after-tracer-1440.png), show the treatment on additional eligible surfaces. Inventory's current start panel, the compact Home and empty-state surfaces, and the public title band need separate composition review: enlarging their artwork in place would consume task space or affect a different component. No extension to private records or error states is implied.

## Validation and limits

Focused browser checks passed 5/5 in each of Chromium and WebKit at 320, 390, 768, 1024 and 1440px, covering service selection, decorative-image removal after selection, 200% root text with reduced motion and forced colors emulated, and horizontal overflow. Before the final illustration-mask refinement, the existing service-pathway suite passed 40/40 in each engine, including enabled and unavailable navigation, keyboard activation, selected Service context, fixed-slot conflict and uncertain outcomes, and group registration recovery. The final illustration suite passed 21/21 in each engine across booking, Inventory, Good Moral and Tracer introductions, including blocked and error states. Focused ESLint, typecheck, a webpack production build and 10/10 booking outcome/recovery unit tests passed; synthetic fixtures do not establish actual authenticated integration, physical-device, real screen-reader or institutional UAT coverage. Dark theme, live call interference and the full set of Student journey states are not established by this slice.
