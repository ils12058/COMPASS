# Validation record

All browser journeys use intercepted API fixtures with synthetic records. The Counselor browser suite ran against the optimized production build at `http://localhost:3107`; the Student regression suite ran against the same build. No institutional records or live service were used.

## Results

| Check | Result |
| --- | --- |
| `pnpm install --frozen-lockfile` in feature frontend | Passed |
| `pnpm api:generate` | Passed; ignored generated client files only |
| Counselor and Student focused Node tests | 19/19 passed |
| Counselor browser suite — Chromium | 14/14 passed |
| Counselor browser suite — WebKit | 14/14 passed |
| Student/professional Home regression — Chromium | 39/39 passed |
| Student/professional Home regression — WebKit | 39/39 passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm build` | Passed |
| `git diff --cached --check` | Passed on the final staged patch |

The focused Node command was:

```sh
node --import ./tests/support/register-tsx.mjs --test tests/ux15-counselor-home.test.mjs tests/ux15-student-home.test.mjs
```

The browser cases cover the bounded chronological self agenda; synthetic long names; canonical first-five work order and pagination; confirmed empty states; partial failures; stale and 403 behavior; schedule cancellation/rescheduling after refresh; Head designation and capability gates; Counselor absence of self-Appointment access; Counselor-to-Student account switching; agenda-to-work focus order and visible focus; responsive geometry; and GSS/IT composition. Chromium exercises native Tab sequence; WebKit verifies link focusability and visible focus using the project's established macOS/WebKit test approach. The Student regression suite also covers Student action states, account switch/session expiry, announcements, role-specific composition, and keyboard/focus navigation.

Responsive layout assertions ran at 320, 360, 390, 768, 1024, and 1440 CSS-pixel viewport widths with 100% and 200% root font size. They checked page/panel overflow, visible/focusable link bounds, collisions, and a rem-scaled minimum touch target for agenda/work links. Measurements are in the per-engine `geometry.json` files linked from [screenshots](screenshots.md).

## Baseline screenshot setup

To capture the before state from the verified baseline in a disposable detached checkout, the first `pnpm build` could not resolve ignored generated API clients. `pnpm api:generate` then passed, and the baseline build completed. This setup does not affect the feature worktree or its validation results.

## Limits and pending checks

- No hosted CI result is claimed here; the PR is targeted to the integration branch and has not been merged.
- No staging/production deployment or live UAT occurred.
- Screen-reader testing, actual browser zoom, real-device touch testing, formal accessibility review, and Counselor/Head/GCO UAT remain outstanding.
- Passing automated checks do not establish WCAG conformance or institutional approval.
