# ADR-024: Appointment-backed E-Counseling with Daily.co

## Context

COMPASS needs a secure online counseling workspace without inventing a second counseling service or
letting provider telemetry become institutional business truth. The existing model already separates
Appointment reservations, Routine Interview intake/evaluation, annual Individual Inventory context,
and completed Counseling Encounters.

Daily.co is used only as external audio/video infrastructure. COMPASS remains authoritative for
identity, authorization, counselor assignment, appointment status, Routine Interview state, actual
Counseling Encounter records, and future consent decisions.

Current Daily REST documentation was rechecked for room creation, meeting tokens, and webhook HMAC
verification before implementation. The integration therefore uses the current documented private
room, room-scoped token, participant permission, expiration, and webhook-signature properties rather
than copying stale provider examples.

## Decision

### E-Counseling is Counseling + ONLINE

E-Counseling is not a separate `Service`. An eligible workspace is backed by a `SCHEDULED`
Appointment whose canonical service is `COUNSELING`, whose `delivery_mode` is `ONLINE`, whose
Student and assigned provider still match the resource, and whose provider remains an active
Counselor eligible for the Counseling service.

`Appointment` remains scheduling truth. `CounselingEncounter` remains the truth that counseling
actually occurred. A Daily room existing, starting, or ending does not create or complete a
Counseling Encounter and does not finalize a Routine Interview.

A committed Appointment is not revalidated against the current Individual Inventory prerequisite
when joining. Routine Interview is optional context and is never a video-join gate. Counselor
workspace projection preserves the existing Routine draft privacy boundary.

### Provider binding

`ECounselingRoom` is a small provider-binding record with a one-to-one `PROTECT` link to Appointment,
an opaque deterministic Daily room name, optional provider room ID/URL, room expiry, and provisioning
timestamp. It does not duplicate Student, Counselor, service, delivery mode, schedule, or appointment
status.

Room provisioning is lazy and occurs only on an authorized join request. Read-only workspace GETs do
not create local or remote rooms. The opaque room name is derived from the local room UUID and does
not contain an Appointment reference code, email, name, or other human identity data.

Provisioning uses a two-phase strategy so no long database transaction is held open around Daily
HTTP. PostgreSQL one-to-one uniqueness provides the logical-room authority. If a provider create
retry reports a conflict, COMPASS retrieves the deterministic room name and adopts it only after
verifying the expected private configuration rather than treating every conflict as success.

### Room and participant security

Daily rooms are private, limited to two participants, use bounded expiry, enforce unique user IDs
where supported, and disable chat, screen sharing, live captions UI, and transcription storage.
Recording is not implemented by this foundation. COMPASS does not send an invented room-level
recording property; instead, server-issued participant tokens explicitly disable recording UI,
cloud-recording start, and automatic transcription.

Meeting tokens are generated server-side on demand and are never stored in PostgreSQL, Redis replay,
Audit, Activity, logs, URLs, or `ECounselingRoom`. Each token is scoped to the exact Daily room,
contains the COMPASS user UUID as `user_id`, carries only a minimal participant display name, has a
short bounded expiry, uses `is_owner=false`, and explicitly sets `permissions.canAdmin=false`.
Student and Counselor therefore receive the same least-privilege provider posture. Counselor is not
made Daily owner/admin merely because they are the assigned institutional counselor.

The join response returns `room_url` and `meeting_token` as separate fields and is marked
`Cache-Control: no-store`. A room URL alone is never authorization.

Join issuance starts at the Appointment start time by default. Deployments may configure a bounded
early-join window and bounded rejoin grace. Room expiry follows Appointment end plus rejoin grace;
new token issuance is denied after that horizon or after cancellation. Daily token expiry does not
forcibly eject an already connected participant. Already-issued tokens cannot be individually
revoked by a COMPASS database flag, so the residual cancellation window is mitigated with private
rooms, short token TTL, bounded room lifetime, and refusal to mint new tokens after cancellation.

### Authorization

The narrow capabilities are:

- `ecounseling.view_self` and `ecounseling.join_self` for Student
- `ecounseling.view_assigned` and `ecounseling.join_assigned` for Counselor

Capabilities never replace the Appointment relationship. Head Guidance receives no additional
blanket workspace or join access from the designation; a Head who is actually the assigned Counselor
uses normal assigned-Counselor authority. Guidance Services Staff, IT Admin, and DPO receive no
E-Counseling content or join capability by default.

Student workspace output contains safe appointment/provider readiness and optional safe Routine
state only. It does not expose Counselor Evaluation, Inventory answers, internal Encounter content,
Daily token, or room URL. Counselor workspace similarly contains only assigned safe context and
reuses Routine visibility rules so draft Student Intake content remains private.

### Provider failures and audit

Daily transport/provider failures do not cancel or rewrite Appointments, create fake Counseling
Encounters, complete Routine Interviews, or otherwise alter institutional truth. They return a
controlled provider-unavailable response and leave the deterministic room binding available for a
safe retry.

Successful provider room provisioning and join authorization use safe Audit events only. Audit
metadata may contain identifiers and delivery context but never Daily API keys, webhook HMAC,
meeting tokens, room URLs, Routine answers, Inventory answers, Counselor Evaluation content,
participant media, or transcripts.

### Webhooks

Daily webhook registration is deployment-owned and never runs during app import, migration, startup,
or ordinary requests. The deployment configures the public COMPASS webhook URL, subscribes only to
`meeting.started` and `meeting.ended`, and supplies the same Base64 HMAC secret configured in
COMPASS.

Webhook requests are provider-authenticated, not user-session authenticated. COMPASS verifies the
current Daily HMAC-SHA256 scheme over the exact raw body and timestamp, checks bounded timestamp
freshness, and rejects invalid signatures without exposing secret details.

`DailyWebhookReceipt` stores only a unique provider event ID, event type, optional matched
`ECounselingRoom`, optional provider session ID, provider occurrence time, and receipt time. The full
provider payload is not retained. Duplicate deliveries return success without duplicate effects;
out-of-order `meeting.started`/`meeting.ended` receipts are safe. Unknown rooms are acknowledged as
provider telemetry without creating a local room binding. Meeting telemetry never mutates
Appointment status, creates a Counseling Encounter, or finalizes a Routine Interview.

### Configuration and testing

Daily configuration is environment-owned: `DAILY_ENABLED`, `DAILY_API_KEY`,
`DAILY_API_BASE_URL`, `DAILY_WEBHOOK_HMAC`, `DAILY_HTTP_TIMEOUT_SECONDS`,
`DAILY_MEETING_TOKEN_TTL_SECONDS`, `DAILY_WEBHOOK_MAX_AGE_SECONDS`,
`ECOUNSELING_JOIN_EARLY_SECONDS`, and `ECOUNSELING_REJOIN_GRACE_SECONDS`.

Disabled mode must allow the rest of COMPASS to start and operate normally. Enabled mode fails fast
when required Daily credentials are absent or timing values are invalid. Secrets are never stored in
application tables or exposed by API/OpenAPI.

Automated tests use fake or capturing Daily clients only. CI performs no real room creation, token
issuance, webhook registration, or other Daily network activity.

## Consequences

This foundation supplies a narrow, auditable bridge from an eligible ONLINE Counseling Appointment
to private Daily access while preserving COMPASS business truth and privacy boundaries. It does not
implement frontend video embedding, recording consent, recording, transcription, transcript/media
storage, Daily chat, guest/group participation, observer modes, Shared Summary, automatic attendance,
or an integration-management dashboard. Those remain separate future decisions.
