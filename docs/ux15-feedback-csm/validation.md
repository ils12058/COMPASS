# Focused validation

All browser tests use synthetic Student identities, opportunities, form responses and intercepted
API calls. They connect only to the local Next.js server; no live Student data or institutional API
was used.

## Results

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed. Generated output added no tracked API client or contract changes. |
| Focused Node tests: `ux15-feedback-csm.test.mjs`, `customer-feedback-identity.test.mjs`, `feedback-access.test.mjs` | 8/8 passed. |
| `pnpm test:ui:feedback-csm` — Chromium | 18/18 browser checks passed. |
| `pnpm test:ui:feedback-csm` — WebKit | 18/18 browser checks passed. |
| Existing `pnpm test:ui:feedback` — Chromium | 14/14 checks passed. |
| Existing `pnpm test:ui:feedback` — WebKit | 14/14 checks passed. |
| `pnpm lint` | Passed without warnings. |
| `pnpm typecheck` | Passed. |
| `pnpm build` | Passed; Next.js compiled and generated all 95 static pages. |
| Final `git diff --check` | Passed. |

`pnpm api:generate`, `pnpm lint`, `pnpm typecheck` and `pnpm build` ran from `fe/`. Browser
commands used `COMPASS_UI_BASE_URL=http://localhost:3128` and the local Next server. The focused
browser command is `pnpm test:ui:feedback-csm`; the existing identity regression is
`pnpm test:ui:feedback`. The last visual-evidence-only change added a desktop rating capture and
was rerun as `COMPASS_UI_CHECK='customer desktop context'` against the production build (1/1 pass).

## Behavioral coverage

- Customer Feedback: completed-service preselection and context, all 12 five-option rating groups,
  all nine in-page destinations, navigation without answer mutation/submission, the “Other” and
  Counselor conditional fields, browser-native required focus, optional identity remaining blank,
  required Course/Year and bounds, canceled confirmation, exact request payload, confirmed success,
  and same-body/same-key retry when the result is uncertain.
- CSM: all four continuous groups, all nine six-option SQD groups in original order, numeric `0`
  submission, CC1 answer 4’s N/A mapping, clearing derived CC2/CC3 when returning to CC1 answers 1–3,
  required and optional email validation, canceled confirmation, payload, success and exact retry.
- Shared safety: already-submitted and ineligible states, malformed and unrelated opportunity IDs,
  no submission on canceled confirmation, Customer Feedback guarded-link and browser-Back warning,
  and preservation of the response when navigation is canceled.
- Layout/input: 1440px desktop, 768px tablet, 390px phone and 320px narrow phone; native arrow-key
  selection; at least 44px radio targets; one/two/three-column reflow; and modified-form reflow at
  200% root text size.

## Scope limits

The Customer Feedback identity regression continues to cover blank optional fields with both empty
and populated cached profile fixtures, and existing authorization tests remain green. The general
portal shell may fetch its own profile for the account header; neither form reads those values into
its response fields or payload.

At 320px and 200% text, this pilot checks that each modified form reflows within its own width. The
portal top bar has a known separate overflow at that setting and was not changed or reported as
passing. Automated WebKit is not a real-device Safari check. Manual screen-reader testing, real
phone testing and GCO/user acceptance remain pending. No backend test suite was run because no
backend, contract, schema or institutional rule changed.

The PR target is the dedicated UX15 integration branch, which is excluded by the current targeted
GitHub Actions branch filters. These local checks are the validation for this slice; no workflow was
manually dispatched and no deploy workflow ran.
