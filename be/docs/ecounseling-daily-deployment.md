# E-Counseling / Daily.co deployment notes

This foundation keeps Daily.co configuration deployment-owned. COMPASS does not register or mutate
Daily webhooks automatically during startup, migrations, or ordinary requests.

## Environment variables

`DAILY_ENABLED=false` keeps the provider integration disabled while the rest of COMPASS remains
usable. To enable E-Counseling, provide deployment secrets through the environment or secret manager:

```text
DAILY_ENABLED=true
DAILY_API_KEY=<daily-api-key>
DAILY_API_BASE_URL=https://api.daily.co/v1
DAILY_WEBHOOK_HMAC=<base64-hmac-secret>
DAILY_HTTP_TIMEOUT_SECONDS=5
DAILY_MEETING_TOKEN_TTL_SECONDS=300
DAILY_WEBHOOK_MAX_AGE_SECONDS=300
ECOUNSELING_JOIN_EARLY_SECONDS=0
ECOUNSELING_REJOIN_GRACE_SECONDS=0
```

Do not commit real API keys or webhook secrets. COMPASS validates positive/bounded timeout and timing
settings at application startup. When Daily is enabled, the API key and webhook HMAC secret are
required.

The meeting-token TTL is intentionally short. `ECOUNSELING_JOIN_EARLY_SECONDS` controls how early a
new join credential may be minted before the Appointment starts. `ECOUNSELING_REJOIN_GRACE_SECONDS`
extends the room/new-token horizon after Appointment end. Both default to zero.

## Identity policy synchronization

The E-Counseling media slice adds the code-controlled capabilities `ecounseling.consent_self` and
`ecounseling.manage_media_assigned`. After deploying code/migrations, synchronize the canonical
identity policy before exposing the new endpoints:

```text
python manage.py sync_identity_policy
```

This keeps Student consent authority and assigned-Counselor media authority consistent with the
version-controlled policy. Guidance Services Staff, IT Admin, and DPO receive no media-control grant,
and Head Guidance receives no designation-wide confidential-session bypass.

## Daily feature/account prerequisites

Daily recording and transcription availability depends on the deployed Daily account/product
configuration. Verify that the deployment's Daily account supports cloud recording and transcription
before enabling those workflows operationally. COMPASS treats provider feature rejection as a
sanitized provider failure and does not change Appointment or Counseling truth in response.

Current Daily recording semantics require provider recording enablement before the backend can start
a cloud recording. COMPASS keeps ordinary rooms media-off by default and, only after current Student
recording consent and a deliberate assigned-Counselor start action, sets the room-level
`enable_recording="cloud"` property immediately before calling the recording-start REST endpoint.
Participant meeting tokens remain non-owner/non-admin with recording UI, automatic cloud recording,
and automatic transcription disabled. See ADR-026 for the residual provider-level recording
capability limitation; do not describe the browser token as cryptographically incapable of every
provider-native recording invocation once room recording has been enabled.

Live transcription and transcript storage are separately controlled. `enable_transcription_storage`
is changed only at the individual room level. Stored transcription requires effective approval for
both live transcription and transcript storage. No domain-wide Daily transcript-storage setting is
needed for COMPASS.

## Daily webhook subscription

Create the Daily webhook subscription as part of deployment configuration, not application startup.
Configure the public COMPASS endpoint:

```text
POST https://<compass-host>/api/v1/integrations/daily/webhook
```

Subscribe only to the provider events used by COMPASS:

```text
meeting.started
meeting.ended
recording.started
recording.ready-to-download
recording.error
transcript.started
transcript.ready-to-download
transcript.error
```

Use the deployment-owned Base64 HMAC secret configured as `DAILY_WEBHOOK_HMAC`. COMPASS verifies the
provider signature and timestamp against the exact raw request body before accepting an event.

A Daily setup/test callback is acknowledged only after signature verification. Duplicate supported
events are idempotently acknowledged. Meeting events for unknown rooms remain minimal provider
telemetry. Media events never create a local room, consent, Counseling Encounter, Routine Interview
state, or Shared Summary.

Manual local webhook testing requires an externally reachable HTTPS endpoint or tunnel because Daily
must call the webhook URL. Automated tests do not need a tunnel and must never contact Daily.

## Privacy and provider boundary

COMPASS sends Daily only what is needed for meeting/media operations: an opaque room name, the
participant's COMPASS UUID as `user_id`, a minimal display name, and provider media-control parameters
that do not contain counseling content. A display name is personal information, so do not describe
the integration as sending "no PII" to Daily. No Inventory answers, Routine answers, Counselor
Evaluation content, Shared Summary text, clinical notes, diagnosis, or transcript text is sent by
this foundation.

Private room URLs are provider metadata, not authorization. The browser receives the room URL and a
short-lived room-scoped meeting token separately. Tokens are not persisted or audited.

Participant tokens keep chat, screen sharing, live captions UI, recording UI, automatic
transcription, and automatic recording disabled. Student and Counselor remain non-owner and
non-admin. Media capture is instead requested by COMPASS backend REST calls only after explicit
session-scoped consent and assigned-Counselor authorization.

COMPASS persists only media lifecycle metadata. It does not retain recording bytes, audio, WebVTT
transcript text, transcript snippets, full webhook payloads, Daily recording share tokens, signed
URLs, temporary S3 URLs, S3 object details, meeting tokens, or bearer credentials. Provider-ready
artifacts remain provider-side; playback/download and retention/deletion policy are not part of this
slice.

## Operational behavior

An eligible workspace is an existing `SCHEDULED`, `ONLINE`, canonical `COUNSELING` Appointment with
the authenticated Student or its assigned active Counselor. A Counselor consent request may create a
local opaque `ECounselingRoom` binding before anyone joins so consent has a stable session anchor.
That local action performs no Daily network call. The first authorized join still lazily provisions
the remote private Daily room; read-only workspace requests remain side-effect free.

If Daily is unavailable, COMPASS returns a controlled provider-unavailable response and preserves the
Appointment and any existing local room binding. Cancellation prevents new join-token issuance but
does not delete the historical binding. Already-issued provider tokens remain bounded by their short
TTL and room lifetime.

Media start is always deliberate and consent-gated. Before contacting Daily, COMPASS atomically
verifies current effective consent, persists `START_REQUESTED`, creates a deterministic provider
`instanceId`, and records a safe Audit event. The network request runs after that transaction commits.
Provider webhooks then reconcile provider state without changing institutional consent truth.

Student withdrawal is also committed before provider control. If a recording/transcription stop call
fails, withdrawal remains effective in COMPASS and the capture remains explicitly stop-required or
unresolved for safe retry/reconciliation. Transcript-storage withdrawal cannot promise deletion of
provider output already produced; retention/deletion requires a separate institutional policy.

Daily meeting and media callbacks are provider telemetry only. They do not mark the Appointment
complete, create a `CounselingEncounter`, finalize a Routine Interview, infer attendance, populate or
publish a Shared Summary, or create a Case Record.
