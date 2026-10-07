# ADR-092: E-Counseling media governance v2, artifact custody and disposition

- Status: Proposed
- Date: 2026-10-08
- Refines: [ADR-026](ADR-026-ecounseling-media-consent.md) and
  [ADR-072](ADR-072-operational-retention-and-disposition.md), for persisted V2 sessions only
- Preserves: historical V1 evidence, ADR-024 Daily Prebuilt, ADR-005 S3-compatible storage,
  ADR-011 append-only audit, ADR-025 human-authored shared summaries, ADR-091 contextual Help

## Authority and version boundary

New `ECounselingRoom` bindings have `media_policy_version=2`. The additive migration assigns **1**
to every existing room and then changes the application default to **2**. It does not transform,
infer, combine, delete or recreate any consent, capture, rule, case, approval or provider evidence.
Historical capture authorization fields remain null/false; historical media is not automatically
ingested. Consent-only bindings count as existing rooms. No active V2 rule or institutional period
is seeded, and migrations make no provider/storage calls.

V1 retains `AUDIO_VIDEO_RECORDING`, `LIVE_TRANSCRIPTION`, and `TRANSCRIPT_STORAGE`. V2 uses one
`SESSION_MEDIA_CAPTURE` permission for recording and live transcription, with a separate
`TRANSCRIPT_STORAGE` permission. The server rejects a scope from the wrong persisted version with
`ecounseling_consent_scope_incompatible`. A current Student decides their own permission; denial
and withdrawal remain terminal. Approval never starts capture, cancels an Appointment, completes
an Encounter or changes access to Counseling.

Recording and transcription retain their independent capture state machines. Start intent records
the authorization time, and a stored transcription records its separate storage authorization.
Both controls recheck consent after provider room configuration. Withdrawal commits first, then
attempts each affected stop independently and separately attempts storage disablement. One failure
cannot skip the other stop or erase withdrawal. Provider uncertainty remains visible. Historical
storage authorization is distinct from the last confirmed provider storage setting, so a file
captured before withdrawal can be prepared without falsely claiming renewed consent.

## Artifact custody

One `ECounselingMediaArtifact` belongs to one capture. Its closed states are `PENDING`, `PROCESSING`,
`STORED`, `FAILED`, `DISPOSED`. Capture `READY` means provider readiness, not local file availability.
Internal metadata includes an opaque room/capture/artifact UUID key, size, MIME type, SHA-256,
storage/disposal timestamps, an opaque storage-namespace fingerprint, independent provider-cleanup
evidence, bounded retry timing and a
claim token. Workspaces expose only state, availability and disposition time. Provider IDs, keys,
bucket/endpoint names, hashes, content and links are excluded.

Eligible V2 READY webhooks commit an artifact row and dispatch on transaction commit. The row is
the durable outbox when broker dispatch fails. Celery uses late acknowledgement; Beat scans bounded
pages of pending/failed work, interrupted claims older than 30 minutes, and pending provider cleanup.
Ingestion has a 30-minute soft and 35-minute hard worker limit; interrupted work remains recoverable.
A PostgreSQL session advisory lock fences duplicate uploads, cleanup and disposition without holding
an SQL transaction across those external operations. A live worker retains its lock; a crashed
worker releases it. At-least-once dispatch converges on the same precommitted key and digest.

The worker verifies exact provider artifact/room/session provenance and the supported Daily storage
shape, obtains a temporary link server-side, streams into a disk-only temporary file using 64 KiB
reads, and validates size, MIME and file signature. Reads use a 30-second socket timeout, 15-minute
read budget and a configurable byte limit (10 GiB default, technical bound 1 MiB–100 GiB). S3 upload
uses bounded multipart buffers and two SDK retries. Workers need adequate temporary disk space;
concurrency must be sized against this per-job bound. No media bytes or provider links enter Celery
arguments/results, audit metadata, persistent state, logs or frontend state.

Only HTTPS default Daily recording/transcript S3 hosts, port 443, are accepted. Redirects, embedded
credentials, unexpected hosts and contradictory link fields fail closed. No Daily bearer token is
forwarded to storage. Recording access links require a future documented expiry. Transcript access
links accept either documented `link` or `download_link`, rejecting conflicting values. Metadata
rejects custom transcript `outParams` and unsupported storage providers. A different Daily-owned host
or storage shape requires an explicit reviewed adapter change; it is not silently accepted.

### Official provider evidence

The following official REST references were checked on 2026-10-08:

- [Recording access link](https://docs.daily.co/reference/rest-api/recordings/get-recording-link):
  `GET /recordings/{id}/access-link?valid_for_secs=900`, `download_link`, `expires`.
- [Transcript access link](https://docs.daily.co/reference/rest-api/transcripts/get-transcript-link):
  `GET /transcript/{id}/access-link`; the reference describes both `link` and `download_link`.
- [Recording metadata](https://docs.daily.co/reference/rest-api/recordings/get-recording) and
  [transcript metadata](https://docs.daily.co/reference/rest-api/transcripts/get-transcript): exact
  identity, terminal readiness, room/session identity and storage shape.
- [Recording deletion](https://docs.daily.co/reference/rest-api/recordings/delete-recording): matching
  `id` and `deleted=true`; `storage_provider` on deletion denotes a customer-managed copy.
- [Transcript deletion](https://docs.daily.co/reference/rest-api/transcripts/delete-transcript):
  matching `transcriptId`, `t_deleted`, with no custom `outParams`.

Daily default custody is the supported source. This design does not assume Daily can directly write
to DigitalOcean Spaces or treat Daily custom AWS bucket configuration as Spaces-compatible.

### Storage policy

`ObjectStorage(alias="ecounseling_media")` uses `SensitiveMediaStorage`. It reuses deployment-owned
S3 endpoint/credentials/region settings, optionally selects `ECOUNSELING_MEDIA_BUCKET_NAME`, and
uses the private `e-counseling` namespace. Keys contain UUIDs only; filenames contain media kind and
institutional session date, never Student identity. The backend pins private ACL, signed access,
no custom/CDN domain, deterministic overwrite and `Cache-Control: private, no-store`.

[Spaces S3 compatibility](https://docs.digitalocean.com/products/spaces/reference/s3-compatibility/)
documents API-supported versioning, private ACLs and presigned URLs. Therefore this slice requires
an **unversioned sensitive bucket**, not a claim that Spaces lacks versioning. Both Enabled and
Suspended versioning are rejected, since a delete marker cannot prove all governed versions absent.
Bucket policy/ACL must be private. Overlapping enabled lifecycle expiration is rejected so it cannot
bypass institutional approval or holds. CDN/public endpoint configuration also needs deployment
verification outside S3 policy reads. A dedicated bucket is necessary when an existing bucket cannot
meet these constraints. No other storage feature gains these restrictions.

An upload is read back and its size/digest verified before `STORED` and the custody audit commit.
A precommitted digest and stable key allow recovery after upload succeeds but acknowledgement/DB
commit is lost. The namespace fingerprint excludes credentials and fences endpoint/bucket/prefix changes during
ingestion, access and disposition. An absence check in a different namespace cannot prove deletion
of the original copy; restore the correct configuration or reconcile a separately authorized move.
The configured backend overwrites that same key rather than generating renamed
copies. Digest mismatch preserves evidence for retry/reconciliation; it never deletes the provider
source. Multipart infrastructure must abort abandoned incomplete uploads without applying an
age-based expiration policy to completed governed media.

Provider cleanup occurs only after verified local custody commits and is reverified on retry.
Cleanup failure leaves the local file `STORED`, keeps the provider reference, and schedules another
attempt. Only an exact documented deletion result clears the reference and records cleanup time.
A documented already-deleted transcript can reconcile a lost acknowledgement. Recording 404 alone
is not treated as verified deletion; missing/uncertain recording evidence requires operator
reconciliation. Operators must never fabricate provider-cleanup evidence to make a case complete.
A missing provider locator without the artifact's verified cleanup timestamp also blocks disposition;
absence of a reference cannot stand in for evidence that the provider copy was deleted.

A worker that loses its database connection while external IO remains in flight must be terminated
before recovery proceeds: a PostgreSQL lock cannot fence a disconnected process at an external
storage service. Recovery and immutable claim checks prevent normal crash/duplicate resurrection;
operator reconciliation is required for that exceptional split-connection scenario.

## Assigned access

`ecounseling.access_media_assigned` depends on `ecounseling.view_assigned`. Only the Counselor role
receives a baseline grant. Effective authority still requires an active Counselor who is the saved
Appointment provider for ONLINE canonical Counseling. An unrelated Head, DPO, IT Admin, Guidance
Services Staff, Student or exceptional capability grant cannot bypass that relationship.
Retention authority never grants media access.

`GET /e-counseling/appointments/{appointment_id}/media/{kind}/access` issues a fresh, private,
short-lived attachment URL only for a stored, non-disposed artifact. The access response is
`no-store, private`; the default URL TTL is 300 seconds, bounded 60–600. A second disposition check
runs before issuance. Authorization uses saved Appointment provenance, not current booking
configuration, service availability or SCHEDULED status. Existing-room workspaces remain readable
after completion/cancellation/configuration changes, with joining closed when no longer eligible.

The frontend uses the generated imperative client on each click with `cache: no-store`; links never
enter TanStack query/mutation caches or saved application state. It shows preparation, availability,
failure and approved deletion separately from capture state. V1 retains three consent meanings;
V2 shows two. Help explains withdrawal, saved files, retention and the limits of downloaded copies.
Only `DOWNLOAD` is implemented; inline preview/playback and Student download remain deferred.

The access audit records authority issuance, not proof that bytes were downloaded. URLs are bearer
capabilities until expiry; copies already downloaded to a user device cannot be recalled. Object
removal invalidates existing links to that live object. No per-link revocation registry is introduced.

## Versioned retention and verified disposition

Rules and cases persist `contract_version`. Existing rules/cases become 1 without changing action,
approval, claim, state, source membership or timestamps. PostgreSQL uniqueness is now one ACTIVE
rule per `(category, contract_version)`. Graduate Tracer remains contract 1; V1 media keeps
`DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE`; V2 media uses `DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE`.
The DPO creates and activates each policy separately using existing recent-MFA/revision checks.

Discovery filters by persisted room version, never artifact presence. Cases keep their original
contract and one frozen member. `MEDIA_READY_AT` remains the original provider readiness anchor;
storage completion does not restart the clock. Incomplete custody, missing local evidence or an
active cleanup claim blocks V2 execution. A remaining provider copy after failed cleanup can be
handled by reviewed disposition once there is no active cleanup claim.

The V1 executor is unchanged. V2 claims a case locally, acquires the shared artifact guard, snapshots
source/artifact revisions, and performs external deletion outside SQL transactions. It validates the
unversioned private storage policy, deletes the live object if present, verifies its absence, and
verifies deletion of any remaining Daily copy. Only after every governed live copy is verified absent
does the final transaction minimize key/hash/content metadata, mark artifact/capture disposed,
clear the provider reference, complete the case and append the disposition audit.

Storage error, uncertain absence, uncertain provider deletion or changed source produces a truthful
blocker/reconciliation outcome, never `COMPLETED`. Location/evidence remain for explicit reviewed
retry. Existing holds revoke queued approval; releasing a hold requires a new approval. No pending
or late webhook, ingestion or cleanup job can restore a disposed artifact. Delayed V2 READY receipts
cannot replace the provider artifact or move the original readiness anchor; verified provider cleanup
also fences late reference resurrection.

Live disposition makes no promise about database/object backups or previously downloaded files.
Backups follow actual infrastructure policy, not an invented duration. Restoring a backup requires
reconciling completed cases against the live-copy namespace before enabling workers, access or
provider processing. See the deployment/runbook additions for the controlled restoration procedure.

## Explicit next slice

`Daily.createFrame()` remains. No custom Call Object UI, browser recording/transcription authority,
live caption display, media-derived Encounter/Shared Summary text, playback library, Student media
access, broad supervisory access, archive/version purger or new backup-retention subsystem is added.
A future Call Object slice can consume the same independent capture/artifact projections and
backend consent/access contracts without changing historical policy or institutional records.
