# ADR-093: Native E-Counseling call experience and compact session workspace

- Status: Proposed
- Date: 2026-10-08
- Refines: [ADR-091](ADR-091-ui-information-hierarchy-progressive-disclosure-product-voice.md) for
  the live E-Counseling session; implements the call-UI slice that
  [ADR-092](ADR-092-ecounseling-media-governance-v2.md) names as next
- Preserves unchanged: [ADR-024](ADR-024-ecounseling-daily.md) room/token security,
  [ADR-026](ADR-026-ecounseling-media-consent.md) and ADR-092 consent, capture, custody, access and
  retention/disposition contracts, ADR-089 saved Appointment provenance, ADR-090 ordering

## Context

E-Counseling embedded Daily Prebuilt (`Daily.createFrame`). The call surface, its controls and its
states belonged to the provider frame, while COMPASS placed recording, transcription, consent and
file controls in a separate, form-like "Media controls" panel beside it. The live session read as a
provider video window surrounded by administrative cards: the conversation competed with consent
metadata, Record (audio/video) sat near Record (encounter), and the Student's permission decisions
were long, permanently expanded paragraphs.

The pinned `@daily-co/daily-js` 0.92.2 type definitions were verified for every method and event this
decision uses. Daily positions the Call Object as the path for fully custom UIs. No dependency was
upgraded or added; `@daily-co/daily-react` is not used, because a two-person call needs only a small
COMPASS wrapper around the pinned `daily-js`.

## Decision

### Daily is the media engine; COMPASS owns every visible part of the call

The session uses `Daily.createCallObject()`. There is no Daily Prebuilt iframe. COMPASS renders the
remote participant, the self view, call state, network and device problems, and all controls.

### One call-client boundary

`DailyCallSession` (`fe/src/features/ecounseling/call/daily-call-session.ts`) is the only code that
touches the Call Object. It owns creation, join, leave, destroy, event subscription, participant and
track projection, local media, devices, network state and error normalization, and exposes one
immutable snapshot. `useDailyCall` binds it to React with `useSyncExternalStore`. Visual components
receive COMPASS state and actions, never the Call Object.

`DailyCallClient` is a `Pick` of the pinned `DailyCall` type limited to join/leave/destroy,
participants, local audio/video, device enumeration/selection and event subscription. Daily's
recording and transcription methods are not part of that type, so the call code cannot call them.

The call lifecycle is closed: `idle`, `requesting` (fresh credential from COMPASS), `joining`, `joined`,
`reconnecting`, `leaving`, `left`, `failed`. The stage derives Join, Connecting…, Waiting for the other
person, Connected, Reconnecting…, You left the call / Rejoin, and Try again from it alone.

### Lifecycle safety

- Construction has no side effects and nothing joins until the person presses Join, so React Strict
  Mode's repeated renders and effects cannot create a second call object or a second join.
- Each join is an attempt with its own number. Every asynchronous continuation and every bound
  Daily event checks that its attempt is current, so a late credential, a slow join or an event from
  a call being destroyed cannot replace newer state. Leaving and unmounting supersede the attempt.
- Teardown unsubscribes every listener, leaves when still connected, and always calls `destroy()`.
  A module-level teardown promise is awaited before another call object is created, so two live call
  objects never coexist (Daily also refuses this). The session object stays reusable after unmount
  cleanup, as Strict Mode's simulated remount expects.

### Credentials

The existing backend join endpoint is unchanged. The frontend requests a credential only when the
person joins, with the generated imperative client and `cache: "no-store"`, so the room URL and
meeting token never enter TanStack query or mutation caches, browser storage, the URL, logs, audit or
the snapshot. The credential lives in one join attempt and is dropped when that attempt is
superseded, fails or completes; an already-expired credential is never used. Rejoining always asks
the backend again, which keeps the Appointment's join window (`TOO_EARLY`/`OPEN`/`CLOSED`/
`PROVIDER_DISABLED`) authoritative. A temporary network interruption is `reconnecting`, not a new
token.

### Participants and media

Sessions are two-person. The other participant is the dominant stage; this person is a small,
mirrored self view. Projection uses `participants()` (local under `local`, remote by `session_id`)
and the current `tracks.audio`/`tracks.video` state with `persistentTrack`, not the deprecated
`audioTrack`/`videoTrack`. Tiles are keyed by `user_id` — the COMPASS user UUID the backend puts in
the meeting token — because `session_id` changes on every join; the browser makes no authorization
decision from either.

`ParticipantVideo` and `RemoteAudio` attach one track per element through a fresh single-track
stream and detach it on replacement, stop or unmount; a stale cleanup never clears a newer stream.
Video elements are always muted and only the remote participant's audio is rendered, so this person
never hears themself and the other person stays audible with their camera off. When the browser
rejects `play()` for autoplay, an "Audio is ready / Play audio" control appears instead of silence.

### Local controls versus governed actions

Local call controls act directly through Daily: microphone (`setLocalAudio`) and camera
(`setLocalVideo`) as `aria-pressed` toggles, device selection (`enumerateDevices`,
`setInputDevicesAsync`, `setOutputDeviceAsync`), join, leave and full screen of the COMPASS stage
element. Device names fall back to "Camera 1"/"Microphone 1"/"Speaker 1" before permission and raw
device IDs are never shown; hot-plug refreshes the lists and the selection always reflects what Daily
reports. Speaker choice appears only where `HTMLMediaElement.setSinkId` exists, otherwise "Uses your
system default". Daily `camera-error` categories, fatal errors and network quality become product
copy; provider messages and error class names are never shown.

Recording, transcription, transcript-storage choice, media consent, artifact download and
retention/disposition remain institutional actions through the COMPASS backend exactly as ADR-092
defines them. The Counselor's Record and Transcript controls sit in the call tray but call the
existing start/stop endpoints; starting is reviewed in a `ConsequentialActionDialog`, stopping is a
direct labelled action that shows Stopping… until the COMPASS session confirms. Transcription start
offers "Live transcription only" (the default) or "save transcript" only when transcript-storage
consent is effectively approved. Starts fail closed when consent or the latest session state cannot
be confirmed; stopping a running capture stays available, including outside the call.

Daily's `recording-*` and `transcription-*` browser events only ask COMPASS to re-read the session;
they never change what COMPASS shows as captured. `transcription-message` is never subscribed: no
live caption or transcript text is rendered, stored, logged, cached or sent anywhere. Live captions
need their own consent and product decision.

Leaving the call does not complete the Appointment, record an Encounter, stop capture or affect
retention. A Counselor leaving while recording or transcription is active or starting is warned
that leaving does not confirm the capture stopped. A Student gains no media authority. Screen share,
chat, reactions, hand raising and participant lists are not part of the UI, matching the room and
token policy.

### Compact control vocabulary

`CallControl` is a feature control: a roughly square tile with an icon above a short visible label,
at least 44px each way, a visible focus ring and the visible label inside its accessible name. Tones
distinguish ordinary, turned-off, running-capture and leave. It is deliberately not ADR-091's
`IconAction`, which stays limited to conventional low-risk actions. Tiles wrap rather than scroll;
on narrow stages the Counselor's Devices moves to the stage's top bar so Mic, Camera, Record,
Transcript and Leave stay in one row.

### Progressive disclosure

A shared `Disclosure` (native `<details>`) holds inline detail and `DisclosureSection` (heading plus
an `aria-expanded` button, content kept mounted) holds collapsible sections with a one-line status
that stays visible when collapsed. Settled metadata and longer explanation collapse: consent
explanations and request/decision times, the Appointment reference and Routine Interview under
Session details, Student information, the Counseling Encounter and Session files. Active capture
indicators, camera/microphone state, connection problems, pending Student decisions, denial and
withdrawal, Leave and consequences at confirmation time are never collapsed.

Student permission rows show the scope, status, one sentence and Allow/Decline; the full meaning is
under Details and in the confirmation. V1 sessions keep three distinct historical permissions and V2
sessions two; the version itself is never shown. Session files describe outcomes from the ADR-092
artifact state — Ready, Preparing file…, No transcript saved, Deleted under an approved retention
rule — and each download still requests a fresh short-lived link on click.

### Layout presets instead of drag resize

Wide Counselor workspaces offer Compact, Balanced (default) and Focus as a single-choice group of
labelled toggle buttons. They switch at the workspace's own width (container query, 56rem), so an
expanded dock stacks the columns instead of squeezing the video; the control is shown only where it
changes the layout. Presets are predictable, keyboard operable, responsive, testable and keep the
video's aspect ratio; a free drag splitter, pixel persistence or a resizable-panel dependency is not
introduced. Focus gives the call the full width and moves secondary work below as collapsed
sections. The stage stays mounted at one place in the tree. Phones use one adaptive layout: compact
header, edge-to-edge call, one row of controls, critical status, decisions, then secondary sections.

### Session state

The canonical workspace still refreshes every 7 seconds while the call is active or capture is live
or transitional or a file is being prepared, and on provider hints. A failed refresh keeps the last
confirmed session on screen instead of replacing the page, so it never unmounts a live call; local
controls keep working while governed starts pause until the state is confirmed again.

### Testing

Tests use a deterministic fake Call Object (`fe/tests/support/fake-daily.mjs`) for node unit tests
and browser tests; no test reaches Daily. Browser tests install it through a development-only
`window.__COMPASS_FAKE_DAILY__` seam that production builds compile away.

## Consequences

The live session reads as a COMPASS call: the conversation is the most prominent object, controls
are part of the call, and media governance stays where ADR-092 put it. ADR-092 and its V1/V2
semantics, custody, access and retention behavior are unchanged; this slice only consumes them. No
backend, OpenAPI or dependency change was needed.

Browser support for element full screen and output-device selection now matters to the COMPASS UI
rather than to Daily Prebuilt; both degrade by omission. Daily's call-machine bundle and media
connections now load in the COMPASS page itself, so any future Content-Security-Policy must allow
Daily's documented hosts. A real-provider join still needs verification on staging, because local and
CI environments have no Daily credentials.

Live captions, a transcript viewer, Student downloads, screen sharing, chat, reactions, group calls,
AI summaries or notes, background effects, a drag-resizable layout, browser recording or
transcription authority, and any consent or retention change remain out of scope.

## Call ownership refinement (ADR-094)

[ADR-094](ADR-094-persistent-ecounseling-runtime-and-global-call-continuity.md) moves ownership of the
one `DailyCallSession` from the session page to the authenticated portal runtime, so a call continues
across portal pages in a call dock. `useDailyCall` is replaced by that runtime; the stage becomes one
of its views and the remote audio plays from it. This decision's client boundary, controls, layouts
and governance are otherwise unchanged.
