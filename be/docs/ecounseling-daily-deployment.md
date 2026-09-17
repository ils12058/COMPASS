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

## Daily webhook subscription

Create the Daily webhook subscription as part of deployment configuration, not application startup.
Configure the public COMPASS endpoint:

```text
POST https://<compass-host>/api/v1/integrations/daily/webhook
```

Subscribe only to:

```text
meeting.started
meeting.ended
```

Use the deployment-owned Base64 HMAC secret configured as `DAILY_WEBHOOK_HMAC`. COMPASS verifies the
provider signature and timestamp against the exact raw request body before accepting an event.

A Daily setup/test callback is acknowledged only after signature verification. Duplicate supported
events are idempotently acknowledged. Unknown rooms are retained only as minimal provider telemetry;
they never create a COMPASS room or Counseling Encounter.

Manual local webhook testing requires an externally reachable HTTPS endpoint or tunnel because Daily
must call the webhook URL. Automated tests do not need a tunnel and must never contact Daily.

## Privacy and provider boundary

COMPASS sends Daily only what is needed for meeting access: an opaque room name, the participant's
COMPASS UUID as `user_id`, and a minimal display name. A display name is personal information, so do
not describe the integration as sending "no PII" to Daily. No Inventory answers, Routine answers,
Counselor Evaluation content, clinical notes, diagnosis, transcript, or media artifact is sent by
this foundation.

Private room URLs are provider metadata, not authorization. The browser receives the room URL and a
short-lived room-scoped meeting token separately. Tokens are not persisted or audited.

The provider configuration disables chat, screen sharing, live captions UI, transcription storage,
recording UI, automatic transcription, and automatic recording controls used by this foundation.
Student and Counselor tokens are non-owner and non-admin. Recording/consent/transcription are a
future privacy/media slice and must not be enabled operationally before that policy exists.

## Operational behavior

An eligible workspace is an existing `SCHEDULED`, `ONLINE`, canonical `COUNSELING` Appointment with
the authenticated Student or its assigned active Counselor. The first authorized join lazily
provisions one private Daily room; read-only workspace requests do not provision anything.

If Daily is unavailable, COMPASS returns a controlled provider-unavailable response and preserves the
Appointment and any existing local room binding. Cancellation prevents new token issuance but does
not delete the historical binding. Already-issued provider tokens remain bounded by their short TTL
and room lifetime.

Daily `meeting.started` and `meeting.ended` callbacks are telemetry only. They do not mark the
Appointment complete, create a `CounselingEncounter`, finalize a Routine Interview, infer attendance,
or create a Case Record.
