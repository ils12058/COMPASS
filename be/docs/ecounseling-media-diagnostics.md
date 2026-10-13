# Safe Daily and media custody diagnostics (EC-10 / EC-11)

These diagnostics identify an operation that could not be verified. They do not establish provider
capture state, grant access, change consent, or authorize a retry/deletion. They are backend-only:
ordinary application responses retain the existing safe messages and media-state projection.

## Capture, custody and cleanup are separate

Read capture status and artifact status separately. Capture `READY` does not mean that institutional
custody succeeded. Before custody, an unsuccessful attempt remains `FAILED` and has a scheduled
retry. After custody, cleanup failure retains `STORED`, its committed size/digest/binding, and the
provider reference. The reference and `provider_deleted_at` change only in the existing verified
cleanup transaction.

`STORED` records committed custody evidence. A later `CANONICAL_INTEGRITY_UNVERIFIED` requires
authorized investigation; the status alone does not prove that a subsequently damaged/moved object
is currently healthy. A transaction failure can lose its acknowledgment after committing. The retry
boundary re-reads the row, so a committed `STORED` copy remains `STORED`; an uncommitted copy is not
promoted. `CUSTODY_COMMIT_UNVERIFIED` therefore does not prove that the transaction rolled back.

No command acknowledgment or error category proves cessation. In particular, no-active-recording
rejection does not exclude a delayed earlier start. EC-01's legacy transcription `STOPPED` projection
is still not independent cessation evidence. This slice preserves existing lifecycle transitions
for valid acknowledgments and does not reconcile provider state.

## Provider classification

Capture command failures use `START_PROVIDER_<code>` / `STOP_PROVIDER_<code>` in the existing capture
`error_code` when they reach the existing command-failure handler. The Daily client uses the same
closed code as `failure_code`; artifact logs may include it as `provider_failure_code`. Errors that
occur before a capture handler, or when persistence is unavailable, cannot promise a durable capture
diagnostic. Classification never selects a lifecycle transition or automatically retries a command.

| Code suffix | Meaning | Does not prove | Retry / persistence |
| --- | --- | --- | --- |
| `NOT_CONFIGURED` | Existing client configuration check failed. | Which secret/configuration value is wrong, or whether capture ceased. | Existing caller policy; code/property or operational log, durable only at a capture handler. |
| `NO_ACTIVE_RECORDING` | Recording Stop received HTTP 400 with a recognized short, exact reason hint. | Completed cessation, no pending start, or no recording artifact. | No automatic start/stop retry; existing capture field and safe client log. |
| `INVALID_REQUEST` | HTTP 400 without that recognized hint. | The exact invalid field or configuration defect. | Same command policy; existing capture field and safe client log. |
| `AUTHORIZATION_REJECTED` | Provider HTTP 401/403. | Loss of the user's COMPASS account/resource authorization. | Same command policy; public API retains its existing provider-unavailable response. |
| `RATE_LIMITED` | Provider HTTP 429. | Capture rejection/cessation or a safe time to replay a command. | No new command retry or rate schedule. |
| `SERVER_FAILURE` | Provider HTTP 5xx. | That an operation had no side effect. | Existing lifecycle/command policy, including the existing HTTP-error branch. |
| `TRANSPORT_FAILURE` | A connection/OS/URL transport exception. | Provider receipt or rejection. | Existing policy; outcome may be unknown. |
| `TIMEOUT` | Typed timeout, including a timeout wrapped by the URL library. | Provider rejection or no side effect. | Existing policy; outcome remains unknown. |
| `INVALID_RESPONSE` | Invalid JSON/response shape or an existing response validation failure. | That a command did not execute. | Existing policy; no successful transition is invented. |
| `INVALID_ACKNOWLEDGMENT` | Missing, malformed or conflicting media command acknowledgment. | Capture start/stop completion. | Existing unconfirmed branch; capture diagnostic when its handler owns the row. |
| `UNCLASSIFIED` | No allowlisted category fits. | Any more specific reason or state. | Existing policy; never substitute provider prose. |

The no-active hint is a conservative compatibility allowlist, not a versioned Daily machine code.
Only a bounded 4 KiB error envelope's documented `error`/`info` fields are considered, and only at
recording Stop with HTTP 400 / `invalid-request-error`. Five exact short phrases (case/outer-space
and final-period normalization only) are recognized; longer or unknown variants remain
`INVALID_REQUEST`. The added phrase is `room does not have an active recording`. The raw envelope
and `info` are never retained or logged. This cannot establish
the exact message/category of any historical incident response that was not safely recorded.

Valid acknowledgments remain `status: sent`, or `sent: true` (documented string form and existing
boolean compatibility). Numeric truthiness, unhashable fields, contradictory fields and a response
with an error are now controlled invalid acknowledgments instead of accidental acceptance or an
unclassified type error. The validation adjustment does not establish capture completion. Slice 1C.1
now keeps both accepted Stop commands unresolved until correlated positive completion; see
[capture state correctness](ecounseling-capture-state-correctness.md). See the current official
[recording Start](https://docs.daily.co/reference/rest-api/rooms/recordings/start),
[recording Stop](https://docs.daily.co/reference/rest-api/rooms/recordings/stop),
[transcription Start](https://docs.daily.co/reference/rest-api/rooms/transcription/start) and
[transcription Stop](https://docs.daily.co/reference/rest-api/rooms/transcription/stop) references.

## Artifact stage codes

The existing artifact `error_code` (40 characters) records the last unsuccessful owned attempt.
It stays available during the next processing attempt and is cleared at the existing successful
custody/cleanup boundaries. A newer owned failure replaces it. Superseded/disposed claims do not
rewrite another owner's state. There is no migration or per-attempt history/backfill.

All durable stages below use the unchanged retry schedule: `min(3600, 60 * 2 ** min(attempts, 6))`
seconds. Attempts increment only after the existing claim reservation; the first failed owned
attempt waits 120 seconds. Beat still runs recovery every 60 seconds, with the existing 100-row
batch and 30-minute stale-claim threshold. A code does not guarantee that a retry will succeed.

| Safe code | Stage / meaning | Does not prove | Persistence |
| --- | --- | --- | --- |
| `STORAGE_POLICY_UNVERIFIED` | Sensitive storage initialization/preflight failed. | The exact rejected policy clause. | Durable, existing retry. |
| `STORAGE_BINDING_UNVERIFIED` | Namespace lookup, immutable binding check or binding commit failed. | An authorized namespace move or absence of the original copy. | Durable, existing retry. |
| `PROVIDER_METADATA_FAILED` | Client construction, metadata retrieval/JSON failed. | A provider API defect or artifact absence. | Durable, existing retry. |
| `PROVIDER_IDENTITY_UNVERIFIED` | Artifact/room/session provenance check failed. | Which upstream field is wrong, or that ingestion may bypass identity. | Durable, existing retry. |
| `ACCESS_LINK_FAILED` | Existing provider access-link acquisition failed. | That no link was issued upstream. | Durable, existing retry. |
| `ACCESS_LINK_UNVERIFIED` | Link destination, expiry or identity validation failed. | Permission to use a different host/URL. | Durable, existing retry. |
| `MEDIA_TRANSFER_FAILED` | Transfer/protected-spool IO, timeout or finalization failed. | A more specific transport cause or provider data loss. | Durable, existing retry. |
| `DOWNLOAD_UNVERIFIED` | Content type/signature/length/size validation failed. | That invalid bytes may be uploaded. | Durable, existing retry. |
| `PRE_CUSTODY_COMMIT_UNVERIFIED` | Preparation metadata transaction failed. | That the transaction definitely rolled back. | Durable if retry transaction succeeds. |
| `CANONICAL_UPLOAD_UNVERIFIED` | Upload preparation, save or returned-key validation failed. | That no canonical object was written. | Durable, existing retry/adoption. |
| `CANONICAL_INTEGRITY_UNVERIFIED` | Existing-object lookup/read-back integrity verification failed. | Current verified bytes, or authority to delete the provider copy. | Durable; retains prior `STORED` custody if present. |
| `CUSTODY_COMMIT_UNVERIFIED` | `STORED`/audit transaction could not be acknowledged. | No durable custody; re-read actual status. | Durable if retry transaction succeeds; never downgrade actual `STORED`. |
| `PROVIDER_CLEANUP_UNVERIFIED` | Post-custody provider metadata/deletion/ack verification failed. | Provider deletion, cessation, or loss of institutional custody. | Durable, `STORED` retained, existing cleanup retry. |
| `CLEANUP_COMMIT_UNVERIFIED` | Cleanup-evidence/ref-clear transaction failed. | That deletion did not occur upstream or that it was durably recorded. | Durable when still owning the claim; `STORED` retained. |
| `RETRY_COMMIT_UNVERIFIED` | Retry-state transaction could not be confirmed. | A committed schedule or custody outcome. | Log/Celery failure only if DB persistence unavailable. |
| `TASK_DISPATCH_FAILED` | Broker dispatch failed; row remains the outbox. | A worker outage or successful dispatch. | Log only; no extra retry or row rewrite. |
| `RECOVERY_UNVERIFIED` | Recovery scan failed outside a verifiable outcome. | Which database/infrastructure cause applies. | Log/Celery failure only; Beat schedule unchanged. |
| `INTERNAL_UNVERIFIED` | Unclassified task failure outside the pipeline (including lock finalizers). | An exact stage, root cause, schedule or custody outcome. | Log/sanitized Celery failure only. |

`CLAIM_COMMIT_UNVERIFIED` is the closed fallback for an explicitly identified `CLAIM` diagnostic;
current task-boundary exceptions use `INTERNAL_UNVERIFIED` because the wrapper cannot establish
whether reservation or lock finalization failed. Neither is a claim of transaction rollback.

Successful/control outcomes are log-only: `PROCESSING`, `STALE_CLAIM_RECLAIMED`, `LOCK_BUSY`,
`INELIGIBLE`, `RETRY_NOT_DUE`, `ALREADY_CLEANED`, `SUPERSEDED`, `PROVIDER_CLEANED`, `DISPATCHED` and
`RECOVERY_SCAN_COMPLETE`. Dispatch/scan completion never proves worker execution. Processing is
logged only after the claim transaction completes; reclaim requires the advisory lock to be free.

## Safe operational evidence

The `ecounseling_media_diagnostic` JSON event permits only task name, closed pipeline/outcome/provider
codes, attempt number, retry boolean/interval, duration in milliseconds and custody boolean.
Absent retry/custody fields mean **unknown**, not false. Existing normalized UUID request correlation
is used when available; no provider/artifact/Student identifiers or storage locations are added.

With existing operator authorization, inspect only the needed capture/artifact statuses, safe error
codes, attempts, claim-present flag, `claimed_at`, `next_attempt_at`, `stored_at`,
`provider_deleted_at`, and presence/validity of required custody size/digest/binding evidence.
Keep timestamps timezone-aware. Do not export provider references, room/session identities, actual
hashes/bindings, object keys, signed URLs, credentials, or counseling content as diagnostic context.

`FAILED`/`PENDING` with a future `next_attempt_at` is scheduled waiting. `PROCESSING` with a current
claim indicates an owned attempt; a claim older than 30 minutes is a recovery candidate, not proof
of an outage. `LOCK_BUSY` means another session retained the lock. A stored row with incomplete
provider cleanup has a separate cleanup obligation and remains institutionally stored.

## Short procedure for a future READY / FAILED incident

1. Obtain an authorized, minimized metadata snapshot; do not open the recording/transcript.
2. Separate capture readiness from institutional custody and provider-cleanup evidence.
3. Read the artifact's last stage code and attempt/next-attempt/claim timestamps. A historical
   `CUSTODY_OR_CLEANUP_UNVERIFIED` cannot identify the earlier failing operation.
4. Check for scheduled waiting, active ownership or a stale candidate; correlate the safe log event
   if available. Dispatch failure is distinct from ingestion failure and does not prove an outage.
5. For provider metadata/link/cleanup stages, use only the allowlisted provider category. For storage
   stages, use the existing authorized policy/binding diagnostics; never weaken host, provenance,
   encryption, namespace or integrity checks to make a retry pass.
6. If `STORED`, preserve custody and provider references until the existing verified cleanup commit.
   A 404, no-active Stop rejection or transaction exception is not deletion/cessation evidence.
7. Record the safe code/timestamps and the remaining uncertainty for owner review. Do not force an
   immediate retry, reset state, start/stop capture, download media, delete a provider copy, change
   storage/retention policy, or perform staging/production operations without separate authorization.

Raw provider bodies, free-form `info`, exception prose, media bytes, signed links and credentials
are prohibited debugging shortcuts. **These diagnostics cannot retrospectively establish the
precise cause of earlier attempts unless equivalent safe evidence was already recorded.**

Rollback is a reviewed code revert. Existing unconstrained diagnostic string fields accept old/new
codes; no capture reset, artifact deletion, consent change, migration or storage-policy weakening is
needed. Historical `PROVIDER_REJECTED`, `PROVIDER_STATE_UNCERTAIN`, `STOP_PROVIDER_FAILED`,
`PROVIDER_ERROR`, `CONSENT_CLEANUP_UNCERTAIN` and `CUSTODY_OR_CLEANUP_UNVERIFIED` remain interpretable
as generic evidence, with no backfill. Slice 1C.1 addresses EC-01/05/08 and the exact no-active phrase;
EC-02 is implemented by [Slice 1C.2 capture reconciliation](ecounseling-capture-reconciliation.md),
with its own bounded schedule and durable operator escalation. EC-04/06/09 are covered by
[Slice 1C.3 webhook security](ecounseling-webhook-security.md).

## Slice 1C.3 webhook outcomes

The [webhook security runbook](ecounseling-webhook-security.md) covers EC-04, EC-06 and EC-09.
The protected capture-reconciliation operator command also shows bounded webhook anomalies,
replay schedules and unverified/quarantined binding counts. Original evidence remains durable;
current capture risk is distinguished from historical escalation. A room-scoped recording
backstop is withheld; authorized consent withdrawal remains unchanged, and the existing
targeted transcription backstop records one attempt with an unverified ACK/failure outcome.
