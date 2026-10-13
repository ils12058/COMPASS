# Capture evidence, Stop intent and transcription storage (Slice 1C.1)

This correction uses the existing capture states, timestamps, authorization flags and audit actions.
It changes no schema, API response shape, policy version, capture restart policy or artifact retry.
Historical rows are not rewritten. A code merge is separate from a staging deployment.

## Evidence boundaries

Daily recording/transcription REST `sent` acknowledges a command. It does not confirm media Start
or Stop. Both Stop paths retain `STOP_REQUESTED`, the original `stop_requested_at`, reserved instance
and prior uncertainty. They do not synthesize `ended_at` or clear an error after an accepted command.
Repeated explicit Stop requests retain the existing provider-command policy and one original audit
intent; they do not automatically restart capture or create another instance.

The existing signed `*.ready-to-download` event can supply positive completion evidence for the
already associated provider artifact. The transition requires the exact bound artifact ID and any
known meeting-session ID. Supplied conflicting instance/room/session/artifact identity is rejected;
a supplied contradictory provider status is not terminal evidence. A room-only completion received
before the artifact was associated stays unresolved. No new provider metadata request is made.

For transcription, `READY` therefore describes observed job completion, even for live-only mode.
It does not establish a stored WebVTT copy or institutional custody. The existing ingestion worker
still requires exact provider provenance, `t_finished`, `isVttAvailable is True`, the supported storage
shape, a safe access link, bounded validated bytes and verified institutional custody before deletion.
A finished job without WebVTT availability cannot be ingested successfully.

`ready_at` retains the first completion observation and existing retention anchor. Daily describes
`event_ts` as webhook send time, so transcription completion does not use it to manufacture a media
end timestamp. Existing historical `ended_at` values remain intact. Recording retains its existing
provider `start_ts` plus duration calculation; no precise physical cutoff guarantee is added.

## Transition policy

The local reducer distinguishes provider observation from durable intent. `stop_requested_at` also
recognizes historical ERROR rows whose Stop request was obscured by older webhook handling. No
timestamp comparison decides whether a capture may become ACTIVE.

| Prior evidence | New observation | Result |
| --- | --- | --- |
| Start reserved / active, no Stop intent | Correlated started | ACTIVE; first observed start metadata retained. |
| STOP_REQUESTED, or ERROR with a persisted Stop timestamp | Started | STOP_REQUESTED; preserve original Stop timestamp and error. |
| STOP_REQUESTED, or ERROR with a persisted Stop timestamp | Provider error | STOP_REQUESTED with safe PROVIDER_ERROR; cessation remains unknown. |
| STOPPED | Started / error | Preserve terminal state and existing terminal evidence. |
| READY | Started / error / repeated ready | Preserve terminal state, first completion evidence and bindings. |
| Pending or stopping, bound artifact identity | Correlated ready | READY; keep Stop intent; job completion is separate from file/custody. |
| Pending or stopping, insufficient/conflicting identity | Ready | No terminal transition or artifact adoption. |
| Disposed capture/artifact or verified provider cleanup | Any late media event | Preserve tombstone/cleanup and provider reference; no resurrection. |

Webhook receipts remain idempotent. A delayed started event can fill absent historical start
metadata without reactivating stopping/terminal capture. Ineffective consent keeps nonterminal
capture stop-required, using the existing best-effort policy Stop; it never restores consent or
authorizes a second start. Terminal evidence is preserved even when consent was later withdrawn.

## Storage meanings and durable Start intent

- Effective live-media consent permits a deliberate counselor Start; it is not storage permission.
- `transcript_storage_authorized` records the selected storage mode under effective per-start consent.
  It is committed with `media_authorized_at`, the reserved instance and the existing attributable
  Start audit. The audit adds only `storage_selected`, a boolean. Storage consent approved but not
  selected leaves this historical flag false.
- `transcript_storage_enabled` records the last successfully acknowledged room-storage update that
  COMPASS could persist. It is independent of job completion and historical authorization. An uncertain
  configuration call/persistence outcome cannot certify current provider configuration.
- The ready handler writes neither storage flag. Successful withdrawal disablement preserves false;
  it does not erase the existing historical authority for a copy captured under that original consent.
- Existing V2 artifact eligibility requires historical media authorization and selected/authorized
  transcript storage. Live-only or unselected storage creates no eligible institutional transcript
  artifact. A PENDING artifact is not STORED custody or permission to bypass provenance.

Transcription Start uses three database boundaries:

1. Under room/consent/capture locks, validate effective consent, reserve the one Start, persist selected
   storage authorization and its audit, then commit before contacting Daily.
2. After the existing room update is acknowledged, recheck effective consent and the reserved capture
   under the same locks, persist the acknowledged configuration flag, and commit it independently of
   the external Start call.
3. Reacquire the same locks and recheck consent, status, instance and Stop intent before sending the
   one provider Start. Keep those locks through Start, as before. An accepted Start does not fabricate
   ACTIVE. A final transaction failure cannot roll back the earlier selection/configuration evidence.

The first two blocks use Django `atomic(durable=True)`. Production media requests run in autocommit;
an enclosing application transaction is rejected before a provider side effect, rather than silently
making durable intent a rollbackable savepoint. Django's TestCase wrapper remains supported.

Withdrawal locks the same room before consent and captures, commits its decision/Stop intent, then
performs provider mitigation. If withdrawal wins during room configuration or between the two later
transactions, the final consent check prevents Start. If Start wins the final lock, withdrawal waits,
then sees the committed reservation and issues the existing Stop/disable operations. A final Start
transaction rollback or lost commit acknowledgment does not erase that reservation or a later
committed withdrawal. Concurrent/repeated Start requests cannot reserve another instance or replay
the provider Start, including after a timeout or provider rejection.

A manual Stop in the configuration-commit gap also supersedes Start. The existing storage-disable
cleanup persists its successful acknowledgment as `transcript_storage_enabled=False`, without
erasing the original selected mode or issuing a replacement Start.

## Remaining uncertainty and scope

There is no atomic commit spanning PostgreSQL and Daily. The durable reservation can still represent
an unissued Start, a sent Start with an unknown outcome, or an accepted Start whose response/worker was
lost. A process crash or configuration acknowledgment/persistence failure can leave the last stored
configuration flag behind the actual room setting. This slice adds no durable command-dispatch/ACK
journal, outbox executor, provider command retry, metadata polling or liveness alert. Those cases stay
unresolved for the separately approved Slice 1C.2 reconciliation design; do not replay Start or infer
cessation from a timeout, disconnect, room expiry or no-active HTTP rejection.

The transition correlation guard is intentionally limited to existing bindings. Full EC-04 identity
validation, malformed payload/schema rejection, missing/foreign event anomaly records and unexpected
capture management (EC-06/EC-09) remain Slice 1C.3. In particular, unbound completion may be received
before its started event; the current receipt is accepted without terminal adoption, and this slice
adds no buffered event replay. Missing completion webhooks do not automatically become STOPPED.

The recording Stop HTTP 400 reason `room does not have an active recording` joins the exact semantic
allowlist. Matching remains recording-Stop-only, `invalid-request-error`, bounded to 4 KiB, and uses
only case/outer-space/final-period normalization. The raw response is never logged or persisted.
`STOP_PROVIDER_NO_ACTIVE_RECORDING` is a failure category, not Stop completion, a safe restart, proof
of missing artifacts or deletion permission.

## Official contracts reviewed on 2026-10-13

- [Transcription Stop](https://docs.daily.co/reference/rest-api/rooms/transcription/stop): command ACK.
- [Transcript started](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-started):
  transcript/room/meeting identifiers and `info.instanceId` in the documented example.
- [Transcript ready](https://docs.daily.co/reference/rest-api/webhooks/events/transcript-ready-to-download):
  finished-job event and independent webhook-send timestamp. Its file wording is not permission to
  override COMPASS's live-only storage choice or the worker's explicit metadata/file checks.
- [Transcript metadata](https://docs.daily.co/reference/rest-api/transcripts/get-transcript):
  job status and `isVttAvailable` are separate fields.
- [Recording ready](https://docs.daily.co/reference/rest-api/webhooks/events/recording-ready-to-download):
  exact artifact, provider start timestamp and duration.
- [Room update](https://docs.daily.co/reference/rest-api/rooms/update-room): storage configuration.

## Rollback and rollout

Revert the code through an owner-reviewed PR. Existing state values, field lengths, policy versions,
API schemas and historical diagnostic strings remain compatible; there is no migration or backfill.
Do not reset consent/capture evidence, erase Stop timestamps, fabricate provider completion, delete
stored artifacts or bypass custody/retention to perform rollback. Reverting would also restore the
old incorrect Stop-ACK/readiness interpretations; operators must continue treating those conservatively.

Deployment is a separate owner-approved operation. This implementation uses local synthetic tests
only, with no live provider media, staging database/Droplet, firewall change or incident recovery.
