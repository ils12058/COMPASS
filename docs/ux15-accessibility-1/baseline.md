# Baseline reproduction

The baseline was reproduced with the original Portal Shell source from the requested integration checkpoint, using the same synthetic Student Inventory route, long display name, and unread-count fixture as the after run. The Portal Shell, command palette, navigation, Accessibility Control, notification, and Account Menu source files matched the fetched base byte for byte.

At a 320×844 CSS-pixel viewport and 200% root font size:

| Measurement | Before |
|---|---:|
| Viewport width | 320px |
| Document and body `scrollWidth` | 417px |
| Header `scrollWidth` / `clientWidth` | 417px / 320px |
| Account trigger right edge | 417px |
| Overview link target width | 16px |
| Action layout | Navigation, search, accessibility, notifications, and account controls competed in one row; their rectangles overlapped |

The Account Menu extended 97px beyond the viewport. The page could be horizontally scrolled to reach content, but the account action and other header targets were not reliably reachable within the visible viewport. This is the shared shell failure. The Inventory fields themselves reflowed at this width.

The exact-width baseline screenshot and browser-measured element data are retained at:

- [Before: Student Inventory at 320px / 200% root text](screenshots/before/before-inventory-320-200-root-text.png)
- [Baseline layout metrics](screenshots/before/layout-metrics.json)

The synthetic account name is `Alexandria Maria Catherine Johnson-Williams Santos de la Cruz, Jr.` and the notification fixture is `123 unread`. No personal or institutional records were used.
