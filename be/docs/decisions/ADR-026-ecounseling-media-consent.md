# ADR-026: E-Counseling Media Consent and Provider Capture

## Context

COMPASS already provides Appointment-backed ONLINE Counseling through Daily.co while preserving
Appointment, Routine Interview, Counseling Encounter, and Shared Summary as separate institutional
truths. ADR-024 deliberately excluded recording and transcription until an explicit privacy policy
existed. ADR-025 also keeps Shared Summary human-authored and independent from provider media.

Recording and transcription are materially different from merely joining a video call. They process
or retain highly sensitive counseling communication and therefore require an explicit session-scoped
Student decision before COMPASS may request provider capture. Consent to media capture is not consent
to receive Counseling, and declining media capture must never cancel or degrade access to Counseling.

Current Daily REST and webhook documentation was rechecked before implementation. Recording is
started with `POST /rooms/{name}/recordings/start` and a caller-supplied `instanceId`; recording stop
uses `POST /rooms/{name}/recordings/stop` without an instance body. Transcription start and stop use
`POST /rooms/{name}/transcription/start` and `/transcription/stop`; both use an `instanceId` for the
capture instance. The selected media webhook events are `recording.started`,
`recording.ready-to-download`, `recording.error`, `transcript.started`,
`transcript.ready-to-download`, and `transcript.error`.

## Decision

### Media capture is off by default

Joining an E-Counseling room never starts recording or transcription. Daily meeting tokens retain the
existing least-privilege posture: Student and Counselor are non-owner, non-admin participants;
recording UI is disabled; automatic cloud recording is disabled; and automatic transcription is
disabled. A Counselor may request consent and, after effective approval, deliberately request media
start through COMPASS. The Student remains the only actor who decides their own consent.

Daily's current recording model requires recording to be enabled in provider room/token policy before
a cloud recording can start. COMPASS therefore enables only the documented room-level
`enable_recording="cloud"` property immediately before the backend recording-start command. This is
a provider requirement, not a grant of institutional media authority: COMPASS does not make the
Counselor or Student a Daily owner/admin, does not expose Daily recording UI, and does not set
automatic recording. Because provider room recording enablement creates a residual provider-level
capability beyond what COMPASS can cryptographically remove from an already joined browser
participant, the system does not claim that a participant token is incapable of all provider-native
recording invocation outside COMPASS. Product/UI authority remains backend-only in this foundation.
A future requirement for a stronger provider-enforced boundary would require a separate trusted
participant/bot design and is outside this slice.

### Session-scoped consent

`ECounselingConsent` belongs to one `ECounselingRoom` and one explicit scope:

- `AUDIO_VIDEO_RECORDING`
- `LIVE_TRANSCRIPTION`
- `TRANSCRIPT_STORAGE`

One row exists per `(room, scope)`. Decisions are `PENDING`, `APPROVED`, or `DENIED`; withdrawal is
represented by `withdrawn_at` on an originally approved decision. Effective consent therefore means
`decision = APPROVED` and `withdrawn_at IS NULL`. `DENIED` and withdrawn decisions are terminal for
the session in this foundation. COMPASS does not implement repeated consent-pressure cycles.

Live transcription and transcript storage remain separate decisions. Stored transcription is allowed
only when both live transcription and transcript-storage consent are effectively approved. A Student
may approve live transcription while declining storage; in that case COMPASS explicitly keeps Daily
transcript storage disabled.

No global, annual, remembered, timeout-based, join-implied, or default approval exists. Institutional
legal/notice copy is not invented by this backend and remains frontend/client-policy work unless an
approved notice is supplied separately.

### Local room binding before provider provisioning

Consent needs a durable session anchor before either participant necessarily joins. A Counselor
consent-request command may therefore create the local opaque `ECounselingRoom` binding for the
Appointment even when no Daily room has been provisioned yet. This intentionally refines ADR-024's
original join-only local-binding timing.

Creating the local binding does not contact Daily, start media, enable transcript storage, or make a
workspace GET stateful. Remote Daily provisioning remains join-driven. Read operations remain pure.

### Consent authorization and lifecycle

The Student capability is `ecounseling.consent_self`; the assigned Counselor media capability is
`ecounseling.manage_media_assigned`. Capability never replaces resource ownership. A Student may view,
decide, and withdraw only their own session consent. A Counselor may request consent and control media
only for their assigned Appointment. Head Guidance receives no designation-wide bypass; a Head who is
the assigned Counselor acts through ordinary Counselor authority. Guidance Services Staff, IT Admin,
and DPO receive no media-control or consent-decision authority by default.

A consent request is atomic across the requested scopes. Duplicate scopes are rejected. Existing
pending/approved rows are returned idempotently, while denied or withdrawn scopes cannot be silently
reopened. Transcript-storage consent must accompany or follow a viable live-transcription consent
request.

Declining recording, transcription, or transcript storage does not cancel the Appointment, eject the
Student, block a Counseling Encounter, block Routine Interview, or prevent a Shared Summary.

### Withdrawal is institutional truth before provider control

Withdrawal is committed in PostgreSQL, together with its safe Audit event, before COMPASS contacts
Daily. If provider stop subsequently fails, withdrawal is never rolled back. The related media capture
remains `STOP_REQUESTED` or otherwise explicitly unresolved and may be safely retried/reconciled.
COMPASS never reports a provider capture as stopped merely because consent was withdrawn.

Withdrawing live-transcription consent while transcription may be active requests transcription stop.
Withdrawing transcript-storage consent prevents future intentional stored transcription. If the active
transcription was using provider storage, COMPASS conservatively stops the current transcription,
disables room transcript storage, and does not automatically restart transcription. Withdrawal cannot
retroactively erase provider artifacts already produced; retention/deletion policy is a separate
future decision.

### Provider capture lifecycle

`ECounselingMediaCapture` stores one operational record per `(room, kind)` where kind is `RECORDING`
or `TRANSCRIPTION`. The lifecycle uses the small states `NOT_STARTED`, `START_REQUESTED`, `ACTIVE`,
`STOP_REQUESTED`, `STOPPED`, `READY`, and `ERROR`.

Before a provider start call, COMPASS locks the room, effective consent rows, and media capture;
persists `START_REQUESTED`; generates and persists a UUID-like provider `instanceId`; and records a
safe Audit event. The database transaction is committed before Daily HTTP begins. This prevents a
stale-approval start from racing past a concurrent withdrawal and gives webhook/provider
reconciliation a stable capture identity when an HTTP response is lost.

Recording stop follows Daily's current room-level stop REST contract and therefore does not send an
invented `instanceId`. Transcription stop sends the persisted transcription `instanceId` as currently
documented. No database transaction is held open across Daily network calls.

`STOPPED` means provider capture is no longer intentionally running and no artifact is required for
that mode. This is a normal terminal state for live transcription with storage disabled. `READY`
means a provider artifact is reported ready and applies to cloud recording or stored transcription.

`transcript_storage_enabled` records the last provider room-storage state that COMPASS successfully
confirmed, not merely the Student's consent state. Consent remains separate institutional truth.

### Webhook reconciliation and unexpected provider media

`DailyWebhookReceipt` remains the provider-event deduplication mechanism. Media events use
provider-event-specific parsers rather than pretending all Daily webhook payloads share the existing
meeting-event shape. Recording-started reconciliation uses the deterministic `instanceId` because the
current documented event does not contain the room name; ready/error events use their documented room
and provider identifiers.

Provider webhooks are truth about provider state only. They never create consent. If Daily reports
active recording/transcription without corresponding effective COMPASS consent, COMPASS records only
the minimum provider evidence, transitions the capture to a stop-required state, records a sanitized
policy-inconsistency code, and makes a best-effort provider stop. It never creates fake approval.

Out-of-order or duplicate provider deliveries must not regress a more advanced/terminal state.
Meeting/media telemetry never changes Appointment status, creates a Counseling Encounter, finalizes a
Routine Interview, or publishes/updates a Shared Summary.

### Data minimization

PostgreSQL stores lifecycle metadata only: local capture identity, provider instance/artifact/session
IDs where useful, safe timing/duration fields, provider-state flags, and a small sanitized error code.
It never stores recording bytes, audio, WebVTT transcript text, transcript snippets, captions,
screenshots, chat, or full provider webhook payloads.

Temporary provider access material is not persisted or audited, including Daily meeting tokens,
recording share tokens, signed URLs, S3 object/access details, bearer credentials, or download URLs.
Ready webhooks intentionally discard those fields.

No playback, recording download, transcript download/view, retention scheduler, deletion workflow,
MinIO copy, export, AI analysis, or automatic Shared Summary generation is included. Media remains
provider-side in this foundation and no retention duration is invented.

### Audit and deployment

Safe Audit events record consent request/approval/denial/withdrawal and media start/stop requests.
Metadata contains only identifiers, consent scope/decision, media kind, and provider label where
needed. It never includes counseling statements, transcript/recording content, media URLs, provider
access credentials, Routine Interview content, or Shared Summary text.

The code-controlled identity policy must be synchronized during deployment with:

```text
python manage.py sync_identity_policy
```

Daily webhook subscription remains deployment-owned. Application import, migration, and startup do
not mutate Daily webhook configuration. CI uses fake/capturing Daily clients and must not create real
provider rooms, recordings, transcriptions, downloads, or webhook subscriptions.

## Consequences

COMPASS gains an explicit, auditable Student-controlled privacy boundary for E-Counseling recording
and transcription while keeping Counseling available after refusal. The implementation deliberately
separates institutional consent truth from provider capture state, supports durable withdrawal across
provider failures, and stores only minimal lifecycle metadata.

The remaining provider-level recording-enablement limitation is documented rather than hidden. Media
access, retention, deletion, institutional object storage, DPO privacy-governance workflows, frontend
consent notice text, and any stronger trusted-participant/bot provider architecture remain separate
future decisions.
