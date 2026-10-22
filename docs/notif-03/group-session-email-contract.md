# Group Session email contract

All four events use the existing Group Session route and producers. Only an active
Student with `appointments.view_self` and the exact owned registration relationship
qualifies. Endpoint parity was verified: `get_session` permits retained detail
access through any owned registration, including after registration/session
cancellation. An unregistered Student's access to a public discovery record alone
does not justify receiving a participant's email. No new staff/Student recipients
or booking/publication/attendance/capacity/facilitator rules are introduced.

## Sources and lifecycle

- Registered: exact `group_session_registration` UUID, matching target parent and
  Student, REGISTERED state, PUBLISHED upcoming session. No frozen initial
  schedule exists. Details explicitly label the verified **current** date/time;
  they do not claim these were the initial registration values after a later edit.
- Registration cancelled: same exact source, CANCELLED with timestamp. A later or
  ambiguously tied registration supersedes the old cancellation email. No active
  registration status or upcoming schedule is shown. Retained session access
  permits the authenticated history link.
- Session cancelled: exact `group_session` UUID equals target, actual CANCELLED
  state with timestamp. Recipient must own a cancelled registration stamped at
  the same instant as the session and registered by then. This is the producer's
  durable participant-batch proof. Merely finding a cancelled session/Notification
  or an unrelated older cancelled registration is insufficient for a link/details.
- Rescheduled: source UUID equals target and `group_session_schedule_vN` exactly
  matches current schedule revision; PUBLISHED upcoming session and current owned
  REGISTERED row required. Updated date/time/mode are accurate current-revision
  values. No previous interval is manufactured. Older revisions suppress.
  Matching legacy `group_session_vN` compares the old general version and retains
  a minimal authorized link, without a certified rich schedule. A later general
  version makes it stale under the existing shared guard.

Registration/session cancellation is not a replacement booking or attendance
promise. Terminal/past or withdrawn sources cannot confirm upcoming registration
or rescheduling. Supported services prevent schedule edits after terminal state.
No new snapshots/history tables are justified: qualified current labels and
conservative suppression address the unavailable event-time intervals.

## Title, venue and rendering policy

Titles and descriptions have no email-suitability classification. The single
`venue_or_meeting_url` field mixes destinations and credentials. Version 1 therefore
omits all these values, even if public-looking, short, escaped or currently visible
in the portal. Long/HTML-like/sensitive titles and missing/online venues do not
change the projected plan. Roster, facilitator names, organizer notes, registration
reasons and cancellation reasons are never projected.

Approved rows use a fixed “Group Session” label/status and, only for registered/
current schedule-revision messages, institutional-local date/time/mode. Cross-date
intervals show both dates and Philippine Time through the shared display helper.
HTML uses escaped semantic rows; text has identical facts and URL. Event-specific
code-owned headings/intros distinguish confirmation, registration cancellation,
session cancellation and rescheduling. Generic event-code previews keep old copy.

Missing sources/invalid legacy references give safe generic projection, while the
existing shared currentness may already cancel Group emails at claim. Unauthorized
relationships get no fields/link; obsolete/superseded sources suppress. Typed
source/revision/registration/interval/status guards participate in final equality,
including in minimal link plans. New email restrictions do not alter shared Push
or in-app currentness/history; `notifications/current.py` remains unchanged.
