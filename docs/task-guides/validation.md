# Validation — 11 November 2026

All local checks passed against the production Next build.

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed; Orval regenerated from the unchanged canonical contract. No manually edited/generated tracked changes. |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm build` | Passed |
| `pnpm test` | 1,180/1,180 passed |
| Task guides — Chromium | 76/76 passed |
| Task guides — automated WebKit | 76/76 passed |
| Existing orientation — Chromium | 28/28 passed |
| Existing orientation — automated WebKit | 28/28 passed |
| Existing Inventory regression — Chromium/WebKit | 13/13 in each engine |
| Existing Messages layout regression — Chromium/WebKit | 18/18 in each engine |
| `git diff --check` | Passed before commit |

The 76 task checks cover all 11 page starts, keyboard launch, Next/Back, Escape/focus return, Skip/Finish/Replay, independent completion, malformed/older/blocked storage, capability-derived catalogs, safe catalog navigation, missing targets, available/empty/ineligible/completed/read-only states, user-opened details, later booking stages/prerequisites/no slots, new/open/closed conversations, retained message and Faculty drafts, unchanged form values, no guide-triggered requests/writes, route/session/access invalidation, competing menus, and narrow/short/200% text layouts. The existing orientation checks also cover expanded/collapsed desktop navigation, native dialogs and mobile drawers, system and COMPASS reduced motion, storage versions, maintenance and unsaved navigation protection. Existing Inventory/Messages regressions exercise draft, validation, uncertain result, duplicate prevention and access recovery behavior.

## Actual Safari smoke

Actual macOS Safari was checked through its native UI on the isolated synthetic preview at `127.0.0.1:3219`. Verified page launch, readable panel/target, Next, Back, safe later-stage fallbacks, Finish without booking, Escape and focus restoration, catalog discovery/completion, catalog Replay navigation and Skip/focus return. The preview rejects API writes, blocks external connections with CSP, and does not forward cookies to Next or register a service worker. Only the local synthetic preview tab was used; unrelated user tabs and drafts were not operated on.

This Safari smoke is separate from automated WebKit. Actual Safari narrow-window/200% browser-zoom testing, physical-device checks and assistive screen-reader testing were not performed. Automated narrow viewport and 200% text enlargement are not physical-device or browser-toolbar zoom tests. Human UAT and live authenticated production workflow checks remain unperformed. No claim of institutional approval or backend release readiness follows from synthetic fixtures.

## Hosted checks and deployment

The user authorized a direct `staging` push and `vercel --prod --yes`, and explicitly asked not to wait for hosted CI. Local validation above was completed first. Hosted CI is not awaited or represented as passed. Backend deployment and live data mutations are outside this work.

## Evidence

Logs are in `evidence/`; per-engine JSON records are in `evidence/chromium/` and `evidence/webkit/`. Representative screenshots for all 11 guides and both catalog layouts are in `screenshots/`, embedded in [the implementation handoff](README.md).
