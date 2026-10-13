# Daily webhook security (Slice 1C.3 / EC-04, EC-06, EC-09)

Contract/design review began 2026-10-13, before implementation. HMAC authenticity and freshness
authenticate the delivery, not ownership of an appointment, room, instance or artifact.

## Event identity matrix

All supported events require a bounded event ID, object payload and finite numeric dispatch
`event_ts`. Identifiers are nonempty bounded strings; present optional identifiers must also
validate and must not contradict persisted identity. No identifier is truncated or guessed.

| Event | Identity used for mutation | Other documented evidence | Policy |
| --- | --- | --- | --- |
| `recording.started` | Reserved `instance_id` and `recording_id`. No room identity is guaranteed in this event; any supplied room/session must agree. | `start_ts` is media start, when supplied. | Resolve a unique, historically authorized reservation by exact instance. Only this verified Start may establish an absent artifact binding. Never replace instance/artifact. |
| `recording.ready-to-download` | Already bound `recording_id`, expected `room_name`; any known session must match when supplied/required locally. No guaranteed instance. | `status=finished`, integer start/duration; event type describes completed artifact. | No room-only adoption. Unbound completion remains pending for bounded replay, which still requires the later verified Start binding. |
| `recording.error` | Exact reserved `instance_id`, expected `room_name`; any supplied artifact/session must agree. | Error `timestamp`: integer epoch; the official example also uses decimal integer text. | Preserve Stop/terminal state and trusted bindings; never bind a new artifact from error prose. |
| `transcript.started` | Reserved `info.instanceId`, `id`, `room_name`, `mtg_session_id`; supplied `room_id` must agree. | `status=t_in_progress`; no guaranteed media-start time. | Check exact reservation before associating transcript/session. No dispatch-time start fallback. |
| `transcript.ready-to-download` | Already bound `id`, expected room, exact known session; optional `info.instanceId` must agree. | `status=t_finished`; numeric duration; output location is ignored. | Completion does not enable storage, prove VTT availability or establish institutional custody. |
| `transcript.error` | Reserved `info.instanceId`, `id`, expected room/session; optional room ID must agree. | `status=t_error`; optional documented `info.startTs/endTs` are validated. | Error cannot swap artifact identity, reauthorize storage or prove cessation. |
| `meeting.started/ended` | `room`, `meeting_id`; no capture mutation. | Numeric `start_ts` / `end_ts` describe meeting events. | Persist validated telemetry only; meeting end is not capture cessation. |

Status is optional for compatibility with existing deliveries; when present it must match the
documented event. The completion event type itself describes completion. Optional media times
and duration may be absent, but malformed supplied values quarantine the event; they never fall
back to dispatch/receipt time. Recording timestamps/duration use integers; transcript ready/error
duration accepts finite numbers. Booleans, strings (except the documented recording-error timestamp
example), negative/nonfinite/overflow values are rejected. A seven-day duration ceiling is a
COMPASS defensive bound, not a claimed Daily contract limit. Recording computed end is approximate
start plus duration, never proof of an exact physical cutoff. Transcript completion does not
fabricate an end time. A valid completion's dispatch timestamp is the existing readiness/retention
observation anchor, explicitly distinct from physical cessation; receipt time is stored separately.

Sources: [recording started](https://docs.daily.co/reference/rest-api/webhooks/events/recording-started),
[recording ready](https://docs.daily.co/reference/rest-api/webhooks/events/recording-ready-to-download),
[recording error](https://docs.daily.co/reference/rest-api/webhooks/events/recording-error),
[transcript started](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-started),
[transcript ready](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-ready-to-download),
[transcript error](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-error),
[meeting started](https://docs.daily.co/reference/rest-api/webhooks/events/meeting-started),
[meeting ended](https://docs.daily.co/reference/rest-api/webhooks/events/meeting-ended).
The transcript-ready example repeats `room_id`; it is not a guarantee that a room name can be
interpreted as a provider room ID. Contradictory/duplicate JSON keys are rejected.

## Receipt, replay and anomaly boundary

An additive receipt extension preserves all historical rows as HISTORICAL_UNVERIFIED. New rows
distinguish application, unresolved association, malformed/conflicting identity, terminal ignore,
disposition/cleanup blocks and anomalies. The unique event ID serializes delivery/replay; capture
mutations also lock room → consent → capture → artifact → reconciliation. No external I/O occurs
under these locks. Original identity evidence survives duplicate-ID conflicts.

Only allowlisted normalized media identity, status, finite duration and sourced timestamps are
retained. No raw JSON, error prose, layout, participant details, object location, links or token
is retained. Replay is restricted to validated unresolved completion events: six committed attempts,
one-hour age, sixty-second delay and twenty candidates per pass. It rechecks the exact currently
bound artifact, room/session/instance, consent and custody/disposition; it never adopts or resets
capture reconciliation. A verified Start can drain matching pending completions after commit.
An independent, explicitly enabled Beat task recovers interrupted delivery callbacks; a crash
rolls back a DB-only replay transaction. Uncorrelatable cases stay durably available for review.

Unknown room/instance, missing reservation, conflicting room/session/artifact, expired-room Start,
ineffective consent and events after cleanup are distinct closed anomalies. A Start event proves a
past observed Start, not that the provider is still active now. Error, ready, delayed or expired-room
events do not establish ongoing activity. Operators see this distinction and whether review remains
current or was superseded by correctly correlated completion. A conflicting reuse of an already
applied event ID quarantines that capture's binding and prevents reconciliation/new custody from
certifying it; it does not replace the original identity. Foreign events alone cannot overwrite a
known good capture.

Only a newly validated Start for the exact authorized reservation can set the capture's binding
verification timestamp. Existing captures/receipts receive no trust backfill. A terminal event for
an unverified historical binding remains pending for bounded replay/investigation, never foreign
adoption. Metadata reconciliation performs no HTTP check for an unverified binding; new custody and
provider cleanup are also fenced. Already verified institutional storage/access is preserved.
A second documented Start for the same reserved instance but another artifact quarantines that
binding, independently of event-ID conflict; an unrelated instance does not poison a good binding.
The operator readout counts unverified historical bindings. No reset/verification override is exposed.

## Mitigation safety

The [recording Stop](https://docs.daily.co/reference/rest-api/rooms/recordings/stop) is room-scoped;
the [transcription Stop](https://docs.daily.co/reference/rest-api/rooms/transcription/stop) accepts
`instanceId`. No unknown/foreign event may trigger either operation or provider deletion. Existing
authorized consent-withdrawal Stop/storage-disable behavior remains. The existing targeted transcription webhook policy
Stop is permitted only for an exact historically authorized reservation with ineffective consent,
without an existing Stop intent or conflicting/protected binding. The room-scoped recording
webhook backstop is withheld because a delayed Start cannot prove which capture is currently active;
it receives urgent review evidence instead. Explicit authorized recording withdrawal operations
remain unchanged. One durable transcription attempt is reserved
before I/O; duplicate deliveries, process loss and unknown outcomes do not replay it. An ACK means
ACK_UNVERIFIED, never physical cessation. Failure/crash requires urgent operator review.

## HTTP and operator policy

HMAC/freshness rejection stays 403; malformed JSON/envelope without a safe supported event key is
400; body size is additionally bounded to 64 KiB. Unsupported syntactically valid events are
acknowledged without raw persistence. An authenticated supported event with a safe key but invalid
schema/identity is durably quarantined and acknowledged with the existing generic 200 response,
preventing endless provider retries. Acceptance is delivery acknowledgment, not resolution. Database
failure rolls back receipt/capture changes and propagates for retry, with no raw payload in messages.

The existing protected backend `ecounseling_capture_reconciliation_status --limit 20` readout is
extended with bounded webhook outcomes/anomalies, replay counts and binding quarantine handles.
Only local UUIDs and closed evidence appear; no provider identity or media access. Investigate the
original receipt/capture through authorized internal access; confirm current provider status and
targeting separately. No general Student/Counselor notification or new HTTP operator endpoint.

## Deployment and rollback

No deployment/provider operation is part of this PR. Pause media webhook ingress and drain provider
media workers during the separate rollout; apply the additive migration and upgrade all workers
and web instances before resuming processing or enabling replay Beat. Older code does not honor
the quarantine fence, so a mixed-version deployment must not process these new security outcomes.
Capture reconciliation remains disabled until its separate approved rollout.

Before rollback, pause media webhook processing and disable/drain replay, reconciliation and custody
workers. Retain the new receipt/anomaly/quarantine evidence while restoring prior code. The older
binary ignores the additive columns and security fences; do not resume it against quarantined work
without separately reviewed operational protection. Schema reversal is only tested in disposable
PostgreSQL; a live reversal erases operational evidence and requires a separately approved protected
export. No consent, audit, capture, storage binding or institutional artifact is erased by code rollback.
