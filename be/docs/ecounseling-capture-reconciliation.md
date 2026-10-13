# Capture reconciliation (Slice 1C.2 / EC-02)

## Verified provider evidence and identity

Contract review: 2026-10-13. This design precedes the implementation. Operations are
backend-only metadata GETs for an already bound artifact; no list/adoption, command replay,
access link, media transfer or deletion is part of reconciliation.

| Capture | Documented metadata operation | Identity and evidence | Safe interpretation |
| --- | --- | --- | --- |
| Recording with bound ID | `GET /recordings/{recording_id}` | Exact `id`, expected `room_name`, exact `mtgSessionId` when already known; reject any supplied conflicting instance identity. | `in-progress` is an active snapshot; `finished` confirms artifact completion. `canceled` supplies insufficient cessation evidence for this policy. |
| Transcript with bound ID | `GET /transcript/{transcriptId}` | Exact `transcriptId`, expected provider `roomId`, exact `mtgSessionId` when already known; reject any supplied conflicting instance identity. | `t_in_progress` is an active snapshot; `t_finished` confirms job completion. `t_error`/`t_deleted` do not establish the requested completion/custody boundary. |
| Either kind without bound artifact | Recording list supports room filtering; transcript list supports room/session filtering. Neither documents reserved-instance lookup/association. | Room/session coincidence cannot bind a candidate to COMPASS's reserved instance. | No listing or foreign artifact adoption. Preserve uncertainty, allow bounded opportunities for a started webhook to establish the binding, then escalate. |
| Transcript job completed | `isVttAvailable` is separate from job status. | A live-only job can finish without a stored WebVTT file; selected historical authorization remains independent. | Preserve both storage flags. No file/custody claim from completion, absent VTT or omitted optional metadata. |
| Any current snapshot | These GETs have no documented command-delivery journal. | They cannot distinguish an unissued command from a sent command with lost acknowledgment, or certify an exact physical cutoff. | Never replay Start/Stop or infer cessation from a timeout, missing object, room expiry or prior HTTP 400. |

Sources: [recording metadata](https://docs.daily.co/reference/rest-api/recordings/get-recording),
[recording list](https://docs.daily.co/reference/rest-api/recordings/list-recordings),
[transcript metadata](https://docs.daily.co/reference/rest-api/transcripts/get-transcript),
[transcript list](https://docs.daily.co/reference/rest-api/transcripts/list-transcripts),
[Stop acknowledgment](https://docs.daily.co/reference/rest-api/rooms/transcription/stop),
[recording completion event](https://docs.daily.co/reference/rest-api/webhooks/events/recording-ready-to-download),
[transcript completion event](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-ready-to-download).

The GET contracts do not return a guaranteed instance identifier. Recovery therefore requires
the existing artifact binding established by the current signed webhook path. Known session
identity is mandatory in the response when present locally; its absence cannot relax that check.
Capture kind is fixed by the endpoint and expected artifact identifier field. No provider
identity is assigned or changed by this worker. Full upstream webhook provenance remains 1C.3.

The reviewed [room presence contract](https://docs.daily.co/reference/rest-api/rooms/get-room-presence)
returns participant/session snapshots, not recording or transcription instance state. It cannot
prove capture cessation or supply the missing reserved-instance binding, and is not queried here.
The official REST index and recording/transcript references expose no documented instance lookup
used by this design. A room permission/configuration switch is also not active capture evidence.

## Recovery design

An additive one-to-one reconciliation record holds the independent claim token/expiry,
attempt count, next eligible check, uncertainty origin, last check/evidence and durable
escalation. Capture failure codes, consent, historical authorization, artifact retries and
custody remain separate. Discovery reads committed unresolved capture evidence and uses a
unique insert to survive duplicate Beat dispatch. No historical capture is rewritten by migration.

Initial defaults: enabled only by an explicit deployment setting; Beat interval 60 seconds;
60-second initial grace; six charged claim opportunities per capture lifetime; exponential
60/120/240/480/900-second retry delays; one-hour maximum age per uncertainty phase;
20 claim candidates and at most 100 discovery candidates per run; metadata timeout at most
five seconds and response body at most 64 KiB; 180-second claim lease. These follow the current
60-second artifact/email recovery cadence and five-second Daily timeout. They allow normal
webhooks to win and cap provider requests without relying on Redis for retry state.

A claim is committed before external I/O. A crashed or redelivered claim consumes its reserved
budget; it can be reclaimed after its lease expires. A verified active Start ends polling;
a later explicit Stop may reopen that record with the remaining lifetime budget. Reopening
never resets attempts or prior escalation evidence. Missing identity also consumes a bounded
opportunity but causes no HTTP request.

Transactions lock room → consent rows (scope order) → capture → existing artifact →
reconciliation row. Provider I/O runs after the claim transaction commits. Apply reacquires
the same locks and checks token, lease, current identity, consent, terminal state and
disposition/cleanup/custody fences. Stop/withdrawal changes are evaluated from current state;
identity drift and stale responses are superseded. The existing Slice 1C.1 transition helper
preserves Stop intent and terminal evidence.

Provider completion can set READY without inventing `ready_at` or `ended_at`. The GET metadata
does not supply a documented artifact-ready timestamp. A missing start may be filled only from
documented recording start time or transcript creation time. Reconciliation's own confirmation
timestamp is an observation, not media time. Existing retention discovery continues to fail
closed when its required media-ready anchor is absent; operators must investigate rather than
substitute polling time or reset retention. Existing correctly sourced capture times survive.

Completion uses the existing idempotent pending-artifact eligibility path, preserving the Media V2
policy for historically authorized media captured before withdrawal. This restores neither
effective consent nor the provider storage switch and never authorizes future capture. This
worker never marks STORED. That
separate pipeline still verifies provider identity, VTT availability and private custody before
any cleanup. Live-only/unselected transcript storage cannot generate an artifact here.

Legacy STOPPED rows are excluded: the old persisted shape cannot safely distinguish an ACK
from independently confirmed cessation. Operator diagnostics count unanchored transcription
STOPPED rows without changing historical state. READY, disposal, verified provider cleanup and
verified institutional custody also exclude repetitive checks.

Active evidence after withdrawn/ineffective applicable consent is an immediate privacy escalation,
preserving consent and Stop intent. Metadata-only recovery cannot stop a provider. Exhaustion
and maximum age also escalate durably, without converting unresolved capture to terminal ERROR.
The read-only management command exposes closed operational evidence and local capture UUIDs
only to operators already authorized to execute backend management commands. It has no HTTP
surface or Student/Counselor notification, and cannot replay or reset work.

Operator readout (authorized backend command access only):

```sh
python manage.py ecounseling_capture_reconciliation_status --limit 20
```

The bounded response includes state counts, priority-ordered escalations with local capture UUIDs,
closed outcome/failure codes and numeric attempt evidence. It also counts legacy unanchored STOPPED
transcriptions and confirmed completions without a media-ready time. UUIDs are lookup handles for
authorized investigation, not provider identities. No provider request, replay, reset or media
access occurs. The command must not be published as a general HTTP endpoint or ordinary notification.

## Deployment and rollback

Deployment is separate from this PR. Keep reconciliation disabled during upgrade; apply the
additive migration before activating new workers; upgrade/drain all old workers before enabling
the new Beat entry. Existing artifact task names/schedules remain compatible and independent.
Enable reconciliation only after the operator reviews the historical backlog and confirms the
bounded defaults. Do not run the new task against a live environment as part of implementation.

For code rollback, disable the new Beat entry first, drain reconciliation tasks, and retain the
additive table and its evidence while restoring the prior worker/web code. The prior code ignores
the extra table. Reverse schema migration is appropriate only for a disposable test database or
after an explicitly approved protected export; it would delete reconciliation evidence. Never
erase consent, audit, capture history or institutional media, reset attempts, or replay commands
as rollback. Migration tests verify fresh upgrade, repeat application and disposable reversal.

## Deferred 1C.3

EC-04 full webhook identity/provenance, EC-06 unexpected/unauthorized provider capture handling,
and EC-09 malformed webhook validation remain separate. Existing binding correctness is a
prerequisite; metadata recovery neither fixes foreign bindings nor buffers/replays old webhook
receipts. Missing identity and ambiguous provider outcomes stay unresolved with escalation.
