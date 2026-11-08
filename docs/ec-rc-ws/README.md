# EC-RC-0/1/2 and EC-WS-1/2 — Recording-only E-Counseling and read-only workspaces

Delivered together on `integration/ux15-modernization` on 2026-11-08.

**Owner decision (2026-11-08):** no cutover, no drain, nothing retained. Transcription is removed
**completely and destructively**. This replaces the proposal's staged retirement (§11.3–11.6: a
temporary drain, reconciliation of the in-flight backlog, and retained historical records under
legal hold). None of those safeguards was built. Nothing here is GCO-, DPO- or UCN-approved.

## EC-RC-0 — what existed (preflight inventory)

| Area | Transcription surface found | Outcome |
|---|---|---|
| Models | `MediaPolicyVersion` (V1 granular, V2 combined); scopes `SESSION_MEDIA_CAPTURE`, `LIVE_TRANSCRIPTION`, `TRANSCRIPT_STORAGE`; capture kind `TRANSCRIPTION`; `transcript_storage_enabled` / `_authorized`; `ec_media_storage_transcription_ck`, `ec_room_media_policy_valid` | Removed |
| Services | `start_transcription`, `stop_transcription`, transcript-storage consent rules, storage-disable on withdrawal, policy-version branches | Removed |
| API | `POST …/transcription/start`, `POST …/transcription/stop`, `TranscriptionStartRequest`, `TranscriptionWorkspaceState`, `media_policy_version`, `storage_enabled` | Removed (old clients get 404) |
| Daily client | `start_transcription`, `stop_transcription`, `get_transcript`, `delete_transcript`, `transcript_access_link`, transcript metadata collection | Removed |
| Webhooks | `transcript.*` events, the transcription-only automatic policy Stop (`_run_policy_stop`) | Removed; `transcript.*` is now unsupported and acknowledged without processing |
| Reconciliation and custody | Transcript identity, `t_*` statuses, VTT checks, Daily-owned transcript bucket allowlist, WebVTT download validation, transcript provider deletion | Removed |
| Audit and retention | `ecounseling.transcription_start/stop_requested` actions; `ECOUNSELING_TRANSCRIPT` retention category | Removed from code (existing audit rows untouched) |
| Frontend | Transcript tile and dialog, transcript-storage choice, V1/V2 consent copy, transcript Help, Session files transcript row, dock/indicator/warning wording, Daily `transcription-*` subscriptions | Removed |

The explicit "off" switches sent to Daily stay as a safeguard: `enable_transcription_storage: False`
on rooms and `auto_start_transcription: False` on tokens.

## EC-RC-1 — destructive removal

`be/compass/ecounseling/migrations/0002_recording_only.py`, registered in
`canonical_migrations.json`, is irreversible:

1. Deletes every stored transcript file in private object storage (best effort). Any key it cannot
   delete is printed so an operator can remove it.
2. Deletes every transcription capture together with its artifact, reconciliation and webhook
   receipts, and every `transcript.*` receipt.
3. Deletes `LIVE_TRANSCRIPTION` and `TRANSCRIPT_STORAGE` consents. `SESSION_MEDIA_CAPTURE` consents
   become `AUDIO_VIDEO_RECORDING`: that permission always covered recording, so existing recordings
   keep a valid consent.
4. Drops the policy-version column and the transcript columns and constraints.
5. Adds `ec_consent_recording_only_ck` and `ec_media_recording_only_ck`, so no transcription row can
   exist again.

**Not touched:**
- Existing audit events.
- Any transcript Daily still holds on its side: COMPASS no longer has a client for it. Check the
  Daily dashboard.

## EC-RC-2 — recording-only contract, consent copy and UI

- **One consent scope:** `AUDIO_VIDEO_RECORDING`. **One capture kind:** `RECORDING`.
  `MediaWorkspaceState` is `{recording}` only.
- **Student consent copy** follows the proposal's §7.6 wording:
  - recording is optional;
  - allowing doesn't start it;
  - the student can withdraw;
  - what was already recorded stays subject to University privacy and records requirements.
- **Counselor tray:** one Record control and one recording-permission row. The start confirmation
  says only that audio and video will be recorded.
- **Help** now has five sections: Recording permission, Recording, Private files, Encounter records,
  and Call and devices. It states that recording doesn't document the session.
- **Not in scope:** re-consent after withdrawal (EC-RC-3) and multiple recording segments
  (EC-RC-4). A withdrawn or denied recording permission is still final for that session.

## EC-WS-1 — read-only Counseling context, Routine Interview owns its forms

- The Counseling workspace's Routine tab no longer embeds the editable Counselor Evaluation.
  - A draft evaluation shows a link instead: **Open Routine Interview**.
  - Finalized or view-only evaluations still render read-only.
- Neither workspace embeds the editable Student Intake.
- The Counselor Evaluation editor on the Routine Interview detail page already registers the shared
  unsaved-changes guard (the proposal's §3.5 finding was outdated).

## EC-WS-2 — Encounter authoring on its own page

- **New page: Record Counseling Encounter.**
  - Addresses:
    - `/portal/counseling/encounters/new/appointment/{id}[?from=ecounseling]`
    - `/portal/counseling/encounters/new/routine-interview/{id}`
  - It builds its origin from the same server-checked Counseling context the workspaces read, so the
    id in the address is only a reference and the backend validates the link again on create.
  - It warns before discarding entered times.
  - After saving it opens the new Encounter.
  - It handles "already recorded" and shows a fixed Back link: to the session, or to the Counseling
    workspace.
- **Workspaces link instead of embedding.** Both workspaces' `Record encounter` now link to this
  page. `RecordEncounterDialog` is deleted.
  - In E-Counseling, the call stays connected in the portal call dock while the page is open.
- **Kept on purpose:** **Finish counseling** (CENC-1/3) stays as a confirmation dialog. It is the
  atomic finish that Proposal #9 deliberately placed in the session, and moving it would need that
  proposal's owners.
- **Already in place:** Student Session Summary authoring already lives only on the Encounter detail
  page (CONT-1B). No change.

## Validation (targeted only)

- **Backend:**
  - After updating them for recording-only, the E-Counseling, Daily, disposition, retention, student
    actions, OpenAPI contract, canonical baseline and continuity tests all pass (882).
  - Tests that only exercised transcription were deleted.
  - Generic start-protocol checks that had been written against transcription start (durable intent,
    concurrent starts, audit failure) went with them. Recording start keeps its own coverage in
    `test_ecounseling_media.py`.
- **Contract and frontend build checks:**
  - `export_openapi --check` reports no transcription path or schema.
  - `makemigrations --check` passes, as do typecheck and ESLint.
- **Frontend unit tests:**
  - 300 counseling, E-Counseling and Routine Interview tests pass.
  - 4 new tests for form ownership (`tests/ec-ws-form-ownership.test.mjs`) pass.
- **Not run, and known stale:** the E-Counseling browser specs still expect transcription UI and
  must be updated before the browser layer runs:
  - `ecounseling-call`
  - `ecounseling-safety-access`
  - `ecounseling-consent-realtime`
  - `ecounseling-runtime`
  - `ecounseling-media-realtime`
  - `ecounseling-timing`
  - `support/fake-daily.mjs`
- **Not run at all:** the full backend suite, `pnpm test` as a whole, browser regressions and UAT.
