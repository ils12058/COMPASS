# Validation — COMPASS-UX15-PILOT-4

## Baseline and scope

- Source baseline: `integration/ux15-modernization` at `f74ee48da7191e1a2a3f0e7ba5bc4e0127655870`.
- API generation, lint, typecheck, and production build ran from `fe/`.
- Browser checks use Playwright with synthetic API fixtures and a local Next server. They make no live API writes.
- No backend, API contract, schema, official question, answer mapping, requiredness, permission, lifecycle, or submission behavior changed.

## Checks

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed. |
| `pnpm lint` | Passed with zero warnings. |
| `pnpm typecheck` | Passed. |
| `COMPASS_API_BASE_URL=http://127.0.0.1:8000 pnpm build` | Passed; all 95 static pages generated. |
| `node --import ./tests/support/register-tsx.mjs --test tests/routine-inventory-decoupling.test.mjs tests/routine-encounter-linking.test.mjs` | 12/12 passed. |
| `node tests/ux15-routine-intake.browser.mjs` against the production build, Chromium | 18/18 passed. |
| Same focused browser suite with `COMPASS_UI_BROWSER=webkit` | 18/18 passed. |
| Baseline `before` visual phase, Chromium | 6/6 passed. |
| `git diff --check` | Passed. |

The browser suite covers seven-group continuity and navigation, keyboard focus, optional responses, exact explicit draft persistence, save success/failure/pending states, dirty-navigation protection, meaningful-response validation, Other specification and clearing behavior, linked error focus, submit gating and confirmation, successful read-only transition, historical cancelled/no-show states, Student eligibility/capability boundaries, and Counselor draft confidentiality.

## Responsive and visual checks

- Tested 1440px desktop, 768px tablet, 390px phone, and 320px narrow phone.
- At 320px with the root text size enlarged to 200%, the form panel measures 254px scroll width by 254px client width. The page still measures 417px by 320px because the existing portal top bar overflows at this size; that measurement was the same on the baseline.
- The baseline form panel measured 334px scroll width by 254px client width at 320px/200% text. The pilot removes that form-level horizontal overflow.
- Generated Chromium screenshots were visually inspected at desktop and phone sizes, including concern selection, conditional Other, validation, saved progress, and read-only submission. WebKit completed the same behavior suite.

## Remaining checks and limits

- Manual screen-reader and real-device testing remain pending.
- The existing portal top-bar overflow at 320px/200% text remains outside this pilot.
- Student Intake still has no automatic canonical reconciliation for an uncertain submit response. The UI advises the Student to refresh and check status before retrying; it does not replay the submission automatically.
- The full frontend/backend suites were not run; validation stayed focused on the affected flow and related Routine Interview regressions.
