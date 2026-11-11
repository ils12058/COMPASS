# Guidance Messages frontend review

Implemented in the isolated `codex/guidance-messages-ui` worktree from `origin/staging`
`ed73c8ff32b81f2cbb248d5238c4bbf9f17298b1` on November 11, 2026.

## Changes

- The directory, conversation header and recipient choices use the shared `PersonAvatar` initials
  primitive for people. Shared office recipients use a restrained office icon and the explicit
  Guidance Office label. Staff retain the Student/Faculty identity and existing office-kind context.
- Full names wrap without ellipses or horizontal overflow. Recipient radios have a visible focus
  ring; long names retain room when header actions wrap onto another line.
- Conversations show their genuine, explicitly labeled start time to help distinguish threads
  with the same person. Existing kind, referral reference, routing, handler and status facts remain.
  The recipient query's supplied Counseling Appointment dates remain visible.
- The workspace and contextual surfaces reserve the measured height of controls and at least six
  rem of history. In a constrained viewport, the document or existing drawer can scroll to the
  composer. Send wraps beside/below the input as space permits. History scrolls independently and
  can chain to the containing scroller at its edge.
- The exact requested reminder appears once in the shared composer as readable secondary text,
  with no acknowledgment checkbox or popup.

The composer controller, send intent, API query functions, request payloads, polling, reconciliation,
read receipts and authorization predicates are unchanged. Layout observers update CSS dimensions
only. Existing new-message recipient changes retain editable text; deliberate navigation/discard
resets a conversation draft. Pending and uncertain attempts retain their original target, ID and text.

## Data and browser limits

The canonical thread response includes an appointment ID, but no appointment start time or service
name. No extra query is made to fill that gap. A conversation's **Started** time is not presented as
an appointment date. Optional unavailable facts are omitted. Existing contextual links, concealed
records, revoked access and controlled institutional wording remain governed by their current flows.

Native macOS Safari rendered the separate local synthetic production preview and exposed its full
identity, history, composer, Send and reminder. Short-window resizing could not be completed because
the active Safari window changed during UI control; native interaction stopped. Existing user tabs
and drafts were not edited and no messages were sent. The synthetic preview window may remain open.
Actual Safari short-window/zoom and physical mobile-keyboard behavior are **not verified**.

Chromium/WebKit short windows, 320px widths, enlarged text (up to 200%), CSS zoom and reduced-viewport
tests are automated simulations. They do not establish physical-device or assistive-technology UAT.

## Validation

Required frontend checks passed: `pnpm api:generate`, `pnpm lint`, `pnpm typecheck`, `pnpm build`.
API generation was run normally; generated API code was not hand edited. All 1,170 frontend unit
tests passed. A later focused run of messaging, case-coordination and avatar tests passed 57/57.

| Synthetic browser suite | Chromium | WebKit |
| --- | ---: | ---: |
| Existing Messages workspace | 42/42 | 42/42 |
| Existing contextual Messages | 29/29 | 29/29 |
| Existing staff assignment/templates | 28/28 | 28/28 |
| Identity, layout and recovery coverage | 18/18 | 18/18 |

The browser checks cover individual/shared-office identity; long names; Faculty inquiry/referral,
Counselor direct/case coordination and staff Student choices; supplied dates; keyboard selection;
loading, empty, error, stale and concealed states; draft behavior; uncertain Retry and duplicate
protection; history pagination; reconciliation; read state; templates; and absence of added context
or profile reads. Contextual tests also verify that the E-Counseling call remains mounted.

Workspace tests ran against the local development server. Contextual and staff suites ran against a
separate local production browser-test build with the repository's explicit test seams enabled.
The ordinary production build also passed with those seams disabled. The final 18-check layout
suite also passed against that ordinary production build. All API reads/writes in the
automated suites were intercepted with synthetic fixtures; provider calls used the established fake.

Final browser JSON results and completed images are under `screenshots/`. Selected images:

- [Desktop conversation](screenshots/webkit/guidance-messages-layout/desktop-completed.png)
- [Narrow conversation](screenshots/webkit/guidance-messages-layout/narrow-completed.png)
- [Narrow recipient selection](screenshots/webkit/guidance-messages-layout/narrow-recipients.png)

## Reproduce locally

From `fe/`, install the locked dependencies and run the four required checks. Start the separate
frontend with `pnpm start --hostname 127.0.0.1 --port 3127`. Run the new suite with
`COMPASS_UI_BASE_URL=http://127.0.0.1:3127 node tests/guidance-messages-layout.browser.mjs`, then repeat
with `COMPASS_UI_BROWSER=webkit`.

For the established contextual/staff fake-provider suites, first make a separate local browser-test
build using `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 pnpm build` and restart that local server. This is a
test artifact and must not be deployed. The safe native-browser preview is started separately with
`node tests/support/guidance-messages-preview.mjs`; its loopback proxy answers every API path locally
and refuses mutations. Its default upstream/preview ports are 3127/3128.

No backend file, OpenAPI contract, API request shape, permission or workflow changed. The main
checkout's unrelated outputs were preserved. After local validation, the user separately authorized
a commit, a push to `staging`, and `vercel --prod --yes`, without waiting for GitHub CI. Deployment
completion is reported separately from this local validation evidence.
