# ADR-094: Persistent E-Counseling runtime and global call continuity

- Status: Proposed
- Date: 2026-10-08
- Refines: [ADR-093](ADR-093-native-ecounseling-call-and-compact-session-workspace.md) (call
  ownership and lifetime only)
- Preserves unchanged: [ADR-092](ADR-092-ecounseling-media-governance-v2.md) consent, capture,
  custody, downloads and retention/disposition; ADR-093's Call Object client, controls, layouts and
  governance boundary; [ADR-024](ADR-024-ecounseling-daily.md) room and token security

## Context

ADR-093 made the call COMPASS-rendered, but the E-Counseling page still owned it: its workspace
created the `DailyCallSession` and destroyed it on unmount. Opening the Routine Interview to write
the Counselor Evaluation, the Student opening their Intake, or any other portal page ended the
conversation. Duplicating Student Intake or Counselor Evaluation inside E-Counseling would split
those records' canonical surfaces, so the call has to follow the person instead.

## Decision

### The call belongs to the authenticated portal session

`ActiveECounselingRuntimeProvider` (`fe/src/features/ecounseling/runtime/`) owns the portal's only
`DailyCallSession`. `PortalBoundary` mounts it inside the portal layout — which Next.js keeps across
`/portal/...` navigations — above its session-loading, session-verification and maintenance
presentations, and keys it by the confirmed user so another account never inherits a call. The
unsaved-changes provider moved up with it, unchanged. Ordinary portal navigation therefore never
leaves, rejoins or requests a new meeting token. Public and sign-in pages are outside it.

The runtime has its own closed state — inactive, activating, joining, active, reconnecting,
leaving, ended, failed — separate from COMPASS's capture state. It becomes active only when a person
presses Join on an authorized session page; viewing a session never starts it, and nothing restores
or auto-joins a call after a reload, in another tab or on navigation.

It ends the call only on: Leave; the call ending itself (fatal Daily error or Daily ending the
meeting); sign-out; the server confirming the session is gone (a confirmed 401 on the session
read); the portal unmounting; and the document unloading. Route changes, opening dialogs, layout
presets and the full stage unmounting are not terminal. `DailyCallSession.dispose()` is now called
only for those terminal cases; ADR-093's attempt guards, listener cleanup, single call object,
serialized teardown, excluded recording/transcription methods and unsubscribed
`transcription-message` are unchanged.

### One call, two views, one audio owner

`CallStage` on the session page and `GlobalCallDock` elsewhere are views of the same runtime state
and actions; there is no second session. The runtime renders the one `<audio>` element that plays the
other participant for the whole portal session, so moving between the stage and the dock never
doubles or restarts the sound, and this person's audio is never played. Autoplay recovery ("Audio is
ready / Play audio") is runtime state shown by whichever view is on screen. Each view's video element
attaches its own track with ADR-093's stale-cleanup protection; a view unmounting clears only itself.

The session page registers that it is showing the full stage for the active Appointment; the dock
appears whenever no such stage is on screen. This hides it on the active session page and shows it
everywhere else — another Appointment's session page, maintenance, session verification — without
pathname parsing in components. A single route helper builds and recognizes session paths.

### The dock

The dock is an in-app call surface, not browser or native Picture-in-Picture. It sits bottom right of
the workspace on wider screens and spans the bottom on phones, below modal dialogs (`z-40` under the
`z-50` dialog layer) and above collection tools, whose bottom offset it respects; while shown it
publishes its height so the portal content and the action status stay clear of it. Placement is
fixed: no drag positioning or stored coordinates.

It shows the other participant's name, connection state, remote video (no self view, to avoid a
picture inside a picture), COMPASS capture indicators, and Mic, Camera, Devices (the existing device
dialog), Return to session and Leave. It folds to one row — name, status, Mic, Return, Show call,
Leave — with audio continuing and capture indicators still listed, which keeps long Intake and
Evaluation forms usable on phones. It shows no Appointment reference, files, consent history or
provider details. If the call ends on its own while the stage isn't on screen, a dismissible notice
replaces the dock.

### COMPASS state off the session page

While the call is live the runtime observes the role's generated E-Counseling workspace query (the
Student's own or the Counselor's assigned) every 7 seconds and when Daily reports a recording or
transcription event. It uses the same query keys as the session page, which stops polling for that
Appointment while the runtime does, so there is one truth and one poll. A failed refresh keeps the
last confirmed state, marked as such; local controls keep working.

Capture indicators, a Student's pending-permission cue ("Media permission requested" with Review,
which opens the session page and its existing consent flow — no Allow/Decline in the dock), and a
Counselor's notice that the Student withdrew all come from that state. Starting recording or
transcription stays on the expanded session page with its confirmation. The assigned Counselor's
protective Stop is available from the dock through the existing COMPASS endpoints (one shared stop
hook with the page), shows Stopping… until COMPASS confirms, and reports failures truthfully. Students
never get a stop. Leaving from the dock gives the Counselor ADR-093's warning while capture runs.

### Authentication, sign-out and maintenance

The runtime keeps the last confirmed user while the portal re-checks the session. A session the
server confirms is gone ends the call before the portal clears its data and redirects; a check that
merely couldn't complete keeps a working call (the portal still shows its verification failure and
withholds content, and no governed start is reachable). Sign-out with a live call asks "Sign out and
end this call?", warns the Counselor that leaving doesn't confirm running capture stopped, leaves and
destroys the call, then signs out. Confirming an email change, which ends the sign-in, ends the call
before reloading. Maintenance replaces portal pages but not the runtime: a connected call continues
with its dock; joining and starting capture are unreachable, and a stop reports the backend's answer.

### Leaving the document

Portal-to-portal navigation never warns about the call. While a call is live the runtime asks the
browser to confirm unloading (reload, closing the tab, same-tab external navigation) through the
standard `beforeunload` prompt, separate from unsaved-changes guarding. A guarded portal link that
leads outside the portal asks "Leaving the portal will end your E-Counseling call." first.

### Cross-tab advice

Over `BroadcastChannel` each tab holds a random in-memory ID. A tab starting a call claims a lease
(short claim window, earliest claim wins), renews it every 2 seconds, and releases it when the call
ends or the page hides; leases expire after 6 seconds, so a crashed tab stops blocking on its own. A
new tab asks for current owners; while one exists, Join shows "Another COMPASS tab has an active
E-Counseling session." Messages carry only the tab ID, message type and claim time — no Appointment,
participant, room URL, token or media — and nothing uses browser storage. Without BroadcastChannel
each tab still allows one call. No backend lease is introduced: the coordination is advisory and the
backend still authorizes every join.

### Credentials and privacy

Join credentials remain attempt-scoped and memory-only (ADR-093): no browser storage, URL, query or
mutation cache, logs, audit or cross-tab message. The active Appointment ID lives only in the
runtime's memory. No transcript text is subscribed to, stored or shown.

## Consequences

An active conversation follows the Counselor through Routine Interviews, Counseling work and other
portal pages, and the Student through their Intake, while those records keep their own pages.
ADR-092 governance and retention are unchanged, and no backend, OpenAPI or dependency change was
needed.

Known limits: a same-tab navigation to a file download (for example a Resource PDF opened with
`window.location`) can show the browser's unload prompt during a call even though the page stays;
advisory cross-tab protection cannot stop deliberate concurrent joins from another browser or
device; and a real Daily join still needs staging verification. Browser/native Picture-in-Picture,
dock dragging, call restoration after reload and a backend call lease remain out of scope.
