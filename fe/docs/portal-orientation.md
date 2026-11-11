# Portal orientation

`Getting around COMPASS` is an optional frontend guide. It starts manually from **Guide** on every
role's Home, or **Help & guides** in the user menu and Account navigation. Help contains only this
guide. Completing it changes Start guide to Replay guide in this browser.

The five steps introduce Home, portal navigation, feature search, the portal bar's account
controls, and Help & guides. Home copy mentions attention/work and shortcuts only when their
source-owned regions are present. Navigation explains the visible desktop collapse/expand control
or the mobile drawer button. Missing targets are omitted; the guide can exit even when none remain.

The panel uses the shared Radix Dialog in nonmodal mode. It highlights real source-owned targets,
brings them into view, fits the visual viewport, and scrolls its contents in short or enlarged-text
layouts. Next, Back, Skip guide, Exit guide, Finish guide, and Escape are available. Step descriptions
describe the focused Next/Finish action. Explicit dismissal restores the visible opener; starting
from Help restores focus to Guide on Home after navigation. Existing dialogs, drawers, and menus
take priority. The guide never opens or changes them, so their navigation state needs no rollback.

The existing unsaved-navigation guard protects both the Help link and launch navigation to Home.
Session, maintenance, privacy/security prompts, role/capability-derived navigation, API queries,
and consequential workflows retain their current owners.

Completion/dismissal uses `compass.portal-orientation` with `{version: 1, status}` only. It contains
no account, record, or content identifiers. Malformed/older/future values become a new guide;
unavailable storage leaves the guide usable. The browser-wide status does not synchronize across
accounts or devices. No server preference, API operation, analytics call, or generated API edit
was introduced.

## Reproduce validation

From `fe/`, run `pnpm api:generate`, `pnpm lint`, `pnpm typecheck`, `pnpm build`, and `pnpm test`.
With a local production server (`pnpm start --port 3217`), run:

```sh
COMPASS_UI_BASE_URL=http://127.0.0.1:3217 node tests/portal-orientation.browser.mjs
COMPASS_UI_BASE_URL=http://127.0.0.1:3217 COMPASS_UI_BROWSER=webkit node tests/portal-orientation.browser.mjs
```

The browser harness answers all APIs with synthetic fixtures and blocks external requests and
service workers. Coverage includes role/lifecycle/designation profiles, capability filtering,
missing targets, 320px/200% text and short windows, reduced motion, storage failure/versioning,
keyboard focus, dismissal/replay, unchanged navigation state, no added guide API requests,
existing dialogs/maintenance, and unsaved-change protection. The suite is automatically discovered
by the repository's Chromium/WebKit CI runner.

For a safe manual Safari preview, keep the local Next server running and start
`node tests/support/portal-orientation-preview.mjs`. Open the printed loopback URL in a separate
Safari window. The proxy answers every API with synthetic data, refuses writes, excludes credentials
from upstream requests, prevents external browser connections, and does not install a worker.

Actual macOS Safari was checked in a separate synthetic window for launch, keyboard traversal,
Next/Back, completion, Help replay, Escape, and focus restoration. The test window was closed and
the original pages/draft were preserved. Safari's Option-Tab traverses all controls when ordinary
Tab follows the browser's narrower default. Automated WebKit is a separate verification; physical
mobile Safari, VoiceOver, and real institutional UAT were not exercised.

The final panel mounts after its placement is ready, so autofocus never targets a hidden control.
Actual Safari also passed launch, Option-Tab traversal, Next/Back, Escape, and focus restoration
with COMPASS Reduce motion enabled after that adjustment. The synthetic preference was restored,
and only the preview window was closed.

## Validation results — 11 November 2026

- Required generation, lint, typecheck, and production build passed.
- Unit suite: 1,174/1,174; focused orientation/navigation/header contracts: 56/56.
- Portal orientation: 28/28 in Chromium and 28/28 in WebKit, including both system and COMPASS
  reduced-motion preferences and focus restoration when every guide target is unavailable.
- Existing shell accessibility: 6/6 in each engine, including the layout matrix and unsaved forms.
- Existing F2 navigation: 48/48 in each engine, including role/capability reachability and account
  changes.

The task handoff includes `desktop-orientation.png`, `mobile-orientation.png`,
`help-guides-start.png`, `help-guides-replay.png`, and engine-specific machine-readable results.

Backend files, the OpenAPI contract, generated source ownership, permissions, and workflows are
unchanged.
