# ADR-103: Contextual Guidance Messages

## Status

Accepted. Builds on [ADR-102](ADR-102-guidance-messages-backend-foundation.md) (Guidance Messages
domain) and the Phase 4 Messages workspace (`/portal/messages`). Does not change ADR-102.

## Context

People working in a Counseling Appointment, its Counseling workspace or its E-Counseling session
should be able to exchange a short Guidance Message without leaving that work. ADR-102 already
anchors exactly one `COUNSELING` thread to one canonical Counseling Appointment and lets the first
Message create it. Those pages know the Appointment, not the thread.

## Decision

**One conversation, many entry points.** The Appointment detail page, the Appointment-anchored
Counseling workspace and the E-Counseling session (Student and Counselor) open the same
`GuidanceThread` that `/portal/messages/{thread_id}` shows. There is no second Message model, copy,
chat channel or WebSocket. The full workspace stays the canonical place for every conversation.

**A narrow resolver.** `GET /api/v1/guidance-messages/appointments/{appointment_id}/context`
(`guidanceMessagesGetAppointmentContext`) returns `{thread, can_start}`:

1. If a thread already exists for the Appointment, it is authorized only by the existing thread
   policy for its persisted participants (exact Student, exact persisted Counselor) and returned
   with `can_start: false`. The Appointment's current status or provider is not consulted, so
   cancellation, completion or no-show keeps access, and **reassignment never transfers it**: a
   new provider is concealed from a thread created with the previous one and cannot create a
   second thread for the same Appointment.
2. Otherwise the actor must be able to start it now under the same rules as
   `open_counseling_thread` (canonical Counseling service, SCHEDULED or COMPLETED, active exact
   Student or provider Counselor, provider with Messages view, actor with manage authority). Then
   `{thread: null, can_start: true}`; nothing is created.
3. Anything else, including GSS supervision, Head designation, IT Admin, DPO, an unrelated actor
   and a guessed Appointment, is concealed with the ordinary 404.

The response is structural (the existing thread schema, never a body, preview, email or
participant directory) and `no-store, private`. The browser never scans the thread directory to
find an Appointment's thread. The first contextual Message still goes through
`guidanceMessagesOpenCounselingThread`, which revalidates everything at send time.

**Anchors.** Only Appointment-anchored Counseling contexts qualify. A Routine Interview Counseling
context, a Referral, a Call Slip, an Encounter or a walk-in has no Counseling thread anchor and
shows no contextual Messages; widening that is a separate backend decision. Counseling Context
expiry is not Message expiry: the time-bounded context may disappear, but the thread, its access
and an open panel's draft remain, and the conversation stays in `/portal/messages`.

**Frontend shape.** The contextual panel reuses the Phase 4 pieces: history paging and joining,
the composer with one `client_message_id` per intended Message, private read state (marked only
while the panel is open, visible and at its newest Message), resolve and reopen, error mapping and
account-ownership protection. The draft and any unconfirmed send are held above the panel, so
closing or relaying out the panel keeps them; every contextual send uses the Appointment's open
endpoint, so an unconfirmed first Message can still be retried after its thread appears. Wide
pages dock the panel beside the work as a non-modal region; narrow pages open a full-width modal
drawer (Escape, focus return). The page's content keeps its place in the tree, so opening Messages
never remounts an E-Counseling call stage; the call runtime (ADR-094) is untouched.

**Freshness.** An open panel reconciles the context, the thread and its newest page on
`messages.thread_changed` for its thread (or any hint before a thread exists), on a new realtime
generation, about every 8 seconds when not live and every 60 seconds when live, and not while
hidden or offline. Bursts collapse into one trailing reconciliation. Realtime stays content-free;
HTTP and PostgreSQL stay authoritative.

## Boundaries and consequences

E-Counseling uses Guidance Messages, not Daily chat; Messages are not transcripts, Encounter notes,
session files, recording evidence or retention media artifacts, and nothing copies between them.
No migration, capability, encryption, realtime event, Notification, template, retention, Office
handler reassignment, attachment, presence, read receipt, edit or delete is added. Office
conversations get no contextual entry points in this change.
