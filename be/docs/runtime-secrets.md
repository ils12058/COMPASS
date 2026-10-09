# Host-managed live-staging runtime secrets

Current repository target: **22** sources (ADR-085/086). All older numbered cutover sections
are historical domain procedures; the final combined ADR-085/086 gates govern the current target.
No implementation merge establishes live readiness.


This is the operator runbook for ADR-078. Repository validation proves the delivery mechanism;
live cutover requires separate authorization, exact-value comparison and service verification.
Do not deploy the new manifest before the host is provisioned. There is no daemon or external
secret-management service.

## Host directory and service grants

`/opt/compass/secrets` is persistent outside `/opt/compass/releases`, owned by `compass:compass`,
mode `0700`. All 22 source files must be regular files, not symlinks, owned by `compass`, mode
`0444`. Never put this directory in Git, a checkout, an image, or a release symlink.

The host parent directory is the confidentiality boundary: other unprivileged users cannot traverse
it. Compose bind-mounts individual files read-only into authorized containers. Their `0444` mode
lets the existing non-root application user read granted mounts without host/container UID matching,
`group_add`, or a secret-specific service account. Compose cannot reliably apply `uid`, `gid` or
`mode` remapping to file-backed secrets. Docker, root and the Docker-controlling deployment user
remain trusted. A compromised authorized process can read its own grants.

| Setting | Source filename | Must be non-empty |
| --- | --- | --- |
| `SECRET_KEY` | `django_secret_key` | yes |
| `POSTGRES_PASSWORD` | `postgres_password` | yes |
| `REDIS_PASSWORD` | `redis_password` | yes |
| `S3_ACCESS_KEY_ID` | `s3_access_key_id` | yes |
| `S3_SECRET_ACCESS_KEY` | `s3_secret_access_key` | yes |
| `SMTP_USERNAME` | `smtp_username` | according to SMTP configuration |
| `SMTP_PASSWORD` | `smtp_password` | according to SMTP configuration |
| `TURNSTILE_SECRET_KEY` | `turnstile_secret_key` | when enabled |
| `DAILY_API_KEY` | `daily_api_key` | when enabled |
| `DAILY_WEBHOOK_HMAC` | `daily_webhook_hmac` | when enabled |
| `PSGC_API_TOKEN` | `psgc_api_token` | optional; dependent operations enforce availability |
| `AUTH_TOTP_ENCRYPTION_KEY` | `auth_totp_encryption_key` | yes |
| `ROUTINE_INTERVIEW_ENCRYPTION_KEYS` | `routine_interview_encryption_keys` | yes |
| `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS` | `counseling_shared_summary_encryption_keys` | yes |
| `REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `referral_confidential_content_encryption_keys` | yes |
| `EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `exit_interview_confidential_content_encryption_keys` | yes |
| `INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `inventory_confidential_content_encryption_keys` | yes |
| `GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `graduate_tracer_confidential_content_encryption_keys` | yes |
| `ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `account_profile_confidential_content_encryption_keys` | yes |
| `FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` | `feedback_confidential_content_encryption_keys` | yes |
| `WEB_PUSH_PRIVATE_KEY` | `web_push_private_key` | when enabled |
| `WEB_PUSH_STORAGE_KEY` | `web_push_storage_key` | when enabled |

| Service | Explicit grants |
| --- | --- |
| `web`, `worker`, `beat` | all 22, because Django loads settings eagerly |
| `postgres` | `postgres_password` only |
| `redis` | `redis_password` only |
| `realtime` (optional `realtime` profile, ADR-100) | `redis_password` only; no `.env` file |
| `proxy` | none |

Keep all optional files present, even when empty. Django retains existing enabled-feature checks;
preflight does not reimplement them. Names, hostnames, feature flags, public VAPID keys, SMTP
host/port, S3 bucket/endpoint/region, timeouts and limits remain ordinary configuration.
`COMPASS_SECRETS_DIR` defaults to `/opt/compass/secrets`; synthetic validation can override it.
The deployment workflow pins that path to `$DEPLOY_PATH/secrets` and checks any `.env` assignment
agrees with it.

Use [runtime.env.example](../deploy/runtime-secrets/runtime.env.example) as a pointer fragment,
not a complete environment. Each `NAME_FILE=/run/secrets/<filename>` replaces its direct `NAME`
assignment. Remove direct forms entirely, including optional empty assignments. Generic `_FILE`
behavior remains unchanged: two non-empty sources fail; file reads normalize CR/CRLF to LF and
strip trailing line endings, but preserve other whitespace. Runtime preflight requires literal
pointers; quoted paths and trailing comments are supported, shell expansion is not. Use single-line
assignments for the live `.env`; unsupported multiline syntax and duplicates fail safely.

## Redis and PostgreSQL

Live `.env` uses `REDIS_HOST=redis`, `REDIS_PORT=6379` and `REDIS_PASSWORD_FILE`. Remove
`REDIS_URL`, `REDIS_CACHE_URL`, `REDIS_RATE_LIMIT_URL`, `REDIS_IDEMPOTENCY_URL`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` and their `_FILE` forms. Django builds percent-encoded
URIs in memory: 0 primary/broker, 1 cache/results, 2 limiter, 3 idempotency. URI validation errors
never disclose passwords or generated URLs. Local/CI may retain explicit compatibility overrides;
local Compose does not require the host secret directory.

Redis's official image has no equivalent password-file startup setting for this manifest.
`redis-start.sh` reads the granted file, matches the generic reader's newline handling and escapes
all password bytes using Redis quoted hexadecimal escapes. It rejects missing/empty/NUL passwords,
keeps `appendonly yes`, and writes mode `0600` configuration owned by Redis into verified
`/run/redis-config` tmpfs only. UTF-8 text passwords may contain punctuation, whitespace, quotes,
backslashes and internal newlines. The wrapper starts the official entrypoint; password values do
not enter persistent environment metadata or server arguments. Health checks read the file at
execution time and use transient `REDISCLI_AUTH`. Do not enable shell tracing or log the config.

The official PostgreSQL image receives only `POSTGRES_PASSWORD_FILE`. On an existing initialized
volume, replacing this file does **not** alter the database role password. Preserve the exact current
password during initial migration; a future password change requires coordinated SQL and application
credential changes. Do not delete/reinitialize the database volume.

## Original ADR-078 migration: historical operator reference

The original ADR-078 cutover below migrated 15 existing values. ADR-080 adds the new required
16th value, ADR-081 adds the 17th, ADR-082 adds the required 18th value, ADR-083 adds the required 19th value, ADR-084 adds the required 20th value, and ADR-085/086 add the required 21st/22nd values. The current
inventory/checker/exporter expects all 22. The numbered 15-value steps remain historical instructions for the original
helper/inventory, not a recipe to rerun export on an already converted host. An old runtime has
no new domain keys to export; the exporter never generates keys or recovers absent values.
Preserve every existing value and ordered keyring. Resolve the actual starting state and follow
the combined deferred cutover gates below before using current-inventory utilities.

1. Record the current public `/api/v1/meta` build and release manifest, database identity, current
   service health and an encrypted rollback copy of the current `.env`/deployment state. Take and
   verify a restorable database backup. Protect the TOTP key, full ordered Routine Interview keyring
   and Web Push storage key in independent approved off-host storage. A copy on this Droplet or in
   its database backup is insufficient. Do not print values, hashes or ciphertext.
2. As `compass`, create `/opt/compass/secrets` securely. If it already contains files, stop and inspect
   metadata; the exporter deliberately refuses to overwrite any inventory file.

   ```sh
   install -d -m 0700 /opt/compass/secrets
   ```

3. Use the **current effective deployment environment**, not a newly generated example, to export.
   The utility does not parse dotenv, Git history or external services. Its input is the process
   environment through the existing generic configuration helper. Run from `be/` with Python 3.13,
   or use the current application image and current release's Compose environment. Confirm no
   running-container override differs from that environment before exporting. Do not dump
   `docker inspect` or `env` to a terminal to do this.

   For a current release that still uses direct values, install this PR's operator helper directory
   outside the checkout/release, e.g. `/opt/compass/operator/runtime-secrets` (scripts only).
   After resolving/exporting `COMPASS_IMAGE` from the existing `.deploy.env`, set `OLD_RELEASE`
   to the verified current release. The following one-off process uses the old manifest's runtime
   environment, the current immutable image and the host deployment UID; it does not start services:

   ```bash
   helpers=/opt/compass/operator/runtime-secrets
   migrate_runtime_secrets() {
     docker compose -f "$OLD_RELEASE/compose.staging.yaml" run --rm --no-deps --pull never -T \
       --user "$(id -u):$(id -g)" --entrypoint python \
       -v "$helpers:/migration:ro" -v /opt/compass/secrets:/host-secrets:rw \
       web /migration/migrate-runtime-secrets.py "$1" --secrets-dir /host-secrets
   }
   migrate_runtime_secrets export && migrate_runtime_secrets compare
   ```

   The helper directory contains `migrate-runtime-secrets.py` and `runtime_secrets.py`; the current
   image supplies `compass.common.config`. One-off container metadata temporarily contains the old
   env inputs, as the old deployment already does; `--rm` removes it. Continue only when `compare`
   reports all 15 values match and exits zero. A failed export may leave partial files: preserve
   evidence, privately compare/recover them, and do not rerun export over existing files.

4. Export writes exact effective UTF-8 bytes, mode `0444`, using private temporary files and atomic
   publication without overwriting. Required values must already exist; absent optional values become
   empty files. `compare` checks exact bytes, including complete keyring order. Output is equality
   status and setting names only, never values, digests, keys or ciphertext. Unrepresentable direct
   values (CR, trailing newline, NUL) fail before export, because `_FILE` would change them. Resolve
   such a mismatch separately; do not trim or rotate credentials during this cutover.
5. Stop on any mismatch. Privately verify filenames, ownership and modes. With protected rollback
   material already recoverable, prepare a mode `0600` replacement `.env`: preserve ordinary
   configuration, replace all 15 direct forms with the pointer fragment, remove all six Redis/Celery
   URL assignments, and remove long-running `DEMO_ACCOUNT_PASSWORD` / `_FILE`. Do not change keys
   or their order. Atomically replace `.env`. Never use `cat`, shell tracing or diff output on it.
6. Run the new checker on the host before deployment. It reads secret metadata only, then `.env`
   assignment names and literal paths; it never reads secret file contents. Errors name known
   settings/filenames and safe reasons only.

   ```sh
   python3 /opt/compass/operator/runtime-secrets/check-runtime-secrets.py \
     --secrets-dir /opt/compass/secrets --env-file /opt/compass/.env --owner compass
   ```

   Include `check-runtime-secrets.py` alongside the shared inventory helper. Validate the new
   manifest with the intended `COMPASS_IMAGE` exported and the release `.env` link in place:
   `docker compose -f compose.staging.yaml config >/dev/null`. Do not use the old direct-password
   manifest with the converted `.env`.
7. Deploy the exact reviewed staging revision through the normal workflow. It uploads manifests,
   Redis wrapper and metadata checker/inventory, runs preflight and quiet Compose validation before
   candidate containers, then follows the existing migration/synchronization and health steps.
   Actions never provisions or reads host secret values. Infrastructure token/SSH credentials stay
   in GitHub Actions Secrets; application runtime secrets do not move there.
8. Inspect every service and its non-secret configuration: web/Postgres/Redis/proxy health, worker
   and Beat activity, matching public build identity and readiness. Verify Redis authentication and
   original DB routing without printing URIs. Verify existing Routine ciphertext through authorized
   reads or `rotate_routine_interview_encryption --dry-run` (counts only, no writes), existing TOTP
   usability where safely testable, and Web Push delivery where enabled. Confirm encrypted recovery
   material can still recover the original keys. Repository tests cannot prove these live checks.
9. Remove any temporary **plaintext** migration material and one-off container remnants. Keep
   approved encrypted rollback/recovery copies under the retention policy. Do not destroy encryption
   keys needed by old database backups. Rollback uses the old immutable image/manifest and protected
   original environment as a coordinated pair; verify health/build afterward. Do not run a direct
   password manifest against a pointer-only env, or a file-only manifest against an unconverted env.

Initial migration changes storage/delivery only: no credential rotation, encryption-key replacement,
Routine ciphertext rewrite, new schema migration or shared crypto extraction.

## Later replacement and recovery

For an ordinary provider credential, write a private temporary file **inside the restricted directory**,
validate privately, set ownership/mode `0444`, then atomically rename over the target. Recreate every
service with that grant (`docker compose up -d --force-recreate <services>`), verify the new value,
and revoke the old provider credential where applicable. A restart can retain the old mounted inode.
No scheduler or automatic rotation is provided.

Encryption keys require their own transition/readability plan. Follow ADR-066 for the Routine ordered
keyring; TOTP and Web Push storage keys require their specific migration procedures. Never replace
one with a newly generated key as routine secret-file maintenance. Keep independently protected
recovery copies of `AUTH_TOTP_ENCRYPTION_KEY`, the complete ordered
`ROUTINE_INTERVIEW_ENCRYPTION_KEYS`, `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS`,
`REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`,
`EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`, and `WEB_PUSH_STORAGE_KEY`, including older keys while retained
backups depend on them. Future application encryption keyrings follow the same rule. An approved
password manager or encrypted offline archive is sufficient; no escrow service is part of this slice.

`DEMO_ACCOUNT_PASSWORD` remains one-off operator input. It is never a long-running Compose grant;
existing `_FILE` support can be used only when an operator explicitly mounts it for the seeding
command. See [staging-demo-seeding.md](staging-demo-seeding.md).


## ADR-080: one-time Shared Summary encryption cutover (separate authorization)

This repository change does not provision a live key or start deployment. The currently provisioned
host may still have 15 source files. ADR-080 originally required 16, ADR-081 required 17, and
the ADR-083 manifest required 19 and ADR-084 required 20. The current ADR-085/086 target requires
22; apply its final combined gates below,
provisioning each missing independent domain keyring if necessary. Do not dispatch the ordinary deployment workflow prematurely.

1. Record the exact current build/image/manifest, migration state and non-secret Summary counts.
   Take a verified restorable encrypted database backup and protected rollback environment/manifest
   copy. Generate a fresh independent ordered Fernet keyring through a protected operator process,
   without terminal/CI output. Never reuse Django, TOTP, Web Push storage or any Routine key. Keep an
   independently protected off-host recovery copy of the complete keyring before proceeding. A
   Droplet-only copy or database backup is insufficient: ciphertext is unrecoverable without keys.
2. Provision `/opt/compass/secrets/counseling_shared_summary_encryption_keys`, regular/non-symlink,
   `0444 compass:compass`, beneath the existing `0700 compass:compass` directory, without changing
   the other 15 values. Add exactly
   `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS_FILE=/run/secrets/counseling_shared_summary_encryption_keys`
   to protected `/opt/compass/.env`; remove the direct assignment. Use the new inventory/checker and
   intended immutable image for preflight, quiet Compose validation and settings validation. The
   declared grants are web/worker/beat only; PostgreSQL/Redis/proxy do not receive this key.
3. Coordinate a maintenance window: stop old web, worker and Beat, drain in-flight requests/tasks,
   and prevent old processes or scheduled/operator jobs from restarting/writing during migration.
   The normal workflow runs candidate migrations **before** fully replacing old services. Phase B
   removes `content`, which old code requires. Its table lock cannot make old code compatible after
   commit. Confirm old writers remain stopped through candidate activation; maintain this downtime
   if a workflow fails. Deploy the exact reviewed staging SHA with `--ref staging` and
   `expected_staging_sha=<full SHA>` only after these gates.
4. `counseling.0004_encrypt_shared_summary_content` backfills nullable ciphertext while plaintext
   remains authoritative. `0005_remove_plaintext_shared_summary_content` locks the table, validates
   each current plaintext body, verifies binding/schema/content of each present token, re-encrypts
   missing or readable-but-stale tokens from the latest plaintext, and verifies again. Corrupt,
   rebound, unsupported or invalid content aborts the atomic Phase B transaction before the column
   drop. Only then does it remove `content`, require non-null ciphertext and add the non-empty
   constraint. Neither migration emits Audit/notifications or changes timestamps/publication.
5. Verify actual applied migrations, no plaintext column, non-null/non-empty ciphertext, counts,
   all existing bodies through approved explicit reads and
   `rotate_counseling_shared_summary_encryption --dry-run`. Verify authorized Counselor, owning
   Student published-only and time-bounded Counseling Context reads, public build/readiness, worker
   and Beat. Compare business metadata/content privately to pre-cutover evidence; print counts and
   safe context only. Do not remove older recovery keys while retained backups depend on them.
6. Controlled rollback requires the same downtime and readable keyring. With old services stopped,
   reverse Counseling to `0003_service_name_snapshot` using the candidate image/keyring. Phase B
   reverse restores the plaintext column from verified ciphertext in one transaction; unreadable
   content aborts without blank restoration. Reverse Phase A removes ciphertext only after plaintext
   has been restored. Activate the compatible previous immutable image/manifest/environment pair,
   verify health/build, and retain the new key for encrypted backups. If verification cannot succeed,
   use the approved tested backup recovery plan; do not launch old code against the ciphertext-only
   schema. Restored plaintext and old backups remain sensitive and require restricted storage.

For later key rotation, provision `[new_primary, previous_keys...]`, preserve its off-host recovery
copy, recreate all granted services so they consume the new file inode, then run
`rotate_counseling_shared_summary_encryption --dry-run --batch-size 100` and real rotation during an
approved operation. The command verifies every selected binding/payload, rewraps only previous-key
tokens with the original Fernet timestamp, commits bounded batches and preserves business metadata.
A rerun resumes safely; failures remain unchanged and produce non-success with safe UUID/reason
output. It refuses both real and dry runs while the plaintext column remains. It does not replace
provider credentials, change Routine keys, schedule rotation or delete older keys.


## ADR-081: deferred Referral and Shared Summary cutover

Repository implementation only: live cutovers are explicitly deferred. Merged code is not evidence
that ADR-080 Shared Summary encryption or ADR-081 Referral encryption is active on the host.
Before any future deployment, resolve the actual running image, manifest, applied migrations,
source-file inventory and pointers using safe metadata only. The live starting state may still
be the original 15-secret/schema runtime. This ADR-081 procedure originally targeted 17 files;
the ADR-083 target required all 19 and ADR-084 required 20. The current ADR-085/086 target needs
22 and the additional Exit/Inventory/Tracer/Account Profile/Feedback steps below.

1. Obtain separate cutover authorization. Record exact live/target build identity, database/schema
   state, Referral/action/Summary counts and operational metadata. Take and privately verify a
   restorable encrypted database backup and compatible previous image/manifest/environment pair.
2. Independently generate each absent ordered keyring through a protected operator process, never
   terminal/CI output: `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS` and
   `REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`. Never reuse Django, TOTP, Web Push, any Routine
   entry or any Shared Summary entry for Referral. Escrow the **complete ordered keyrings** in
   independently protected off-host recovery before migration. A database/Droplet backup alone
   cannot restore confidential ciphertext. Retain old keys while retained backups require them.
   `migrate-runtime-secrets.py` cannot export an absent new key and must not generate one.
3. Provision missing sources beneath the existing `0700 compass:compass` directory; each must be
   regular/non-symlink, `0444 compass:compass`. Add the exact `_FILE` pointers from the current
   example to protected `/opt/compass/.env`, with direct assignments absent. The Referral filename
   is `referral_confidential_content_encryption_keys`; only web/worker/Beat receive it. Preserve
   existing credentials/order. For the current target use the 22-file checker and ADR-085/086 gates,
   quiet Compose validation and candidate settings checks against the intended immutable image before dispatch.
4. Coordinate maintenance downtime: stop/drain old web, worker, Beat and every old scheduled or
   operator writer; prevent restarts until candidate activation. The ordinary workflow migrates
   candidate code before replacing all old services. Table locks protect verification but cannot
   make old code compatible with removed plaintext columns after commit. Keep old services stopped
   if activation fails. Deploy only the exact reviewed staging SHA with `--ref staging` and
   `expected_staging_sha=<full SHA>` after every gate is satisfied.
5. Apply missing ADR-080 migrations as described above and Referral `0003_encrypt_confidential_content`
   then `0004_remove_plaintext_confidential_content`. Phase A adds nullable ciphertext and backfills
   Referral's four-field payload and each action's separate remarks. Phase B locks Referral then
   ReferralAction in one transaction, validates latest plaintext/lifecycle, authenticates every
   present token/context/schema/content, reconciles only absent or readable stale tokens, verifies
   replacements, then removes five plaintext columns and enforces non-null/non-empty ciphertext.
   An old writer may have voided a formerly active Referral; an authenticated old active payload
   is reconciled to the latest authoritative void state. Present unverifiable tokens abort the
   entire phase, including earlier rewrites; no corruption replacement or blank fallback.
6. Verify actual migration/schema state, unchanged row counts/business metadata, all historical
   content privately, authorized list/detail/PDF and Call Slip source-action reconciliation,
   metadata-only Context history, both domain rotation dry runs, build/readiness and all services.
   Use `rotate_referral_confidential_content --dry-run --batch-size 100`; output is counts and
   bounded UUID/action-type/reason context only. Repository tests do not prove live readiness.
7. Controlled rollback uses the same downtime and the complete readable keyrings. With candidate
   code/keyrings, reverse Referrals to `0002_void_provenance` and, if it was newly activated, reverse
   Counseling to `0003_service_name_snapshot` before running old code. Referral reverse first
   adds temporarily nullable plaintext columns, verifies/decrypts and restores every payload,
   then reinstates original nullability/defaults and the void-shape constraint. Corruption aborts
   schema/data restoration atomically. Phase A reverse drops ciphertext only after successful
   plaintext restoration. Activate the matching previous image/manifest/environment pair and
   verify build/services; preserve new keys for encrypted backups. Never launch old code against
   a ciphertext-only schema. Restored plaintext/older backups remain restricted sensitive data.

Later Referral rotation is separately operated: provision `[new_primary, previous_keys...]`, keep
protected off-host recovery, recreate web/worker/Beat so they consume the new inode, run dry-run then
`rotate_referral_confidential_content --batch-size 100`. Both envelope types are fully verified;
previous-key tokens are rewrapped with ADR-079 MultiFernet.rotate, preserving bytes/timestamps.
Each bounded batch commits separately and can resume after interruption; only ciphertext changes.
Counts are separate for Referrals/actions. Failures are left untouched and cause non-success.
Both real and dry runs refuse any remaining legacy Referral plaintext column. No scheduled
rotation, key deletion, provider credential change, provisioning or deployment occurs automatically.

## ADR-082: deferred combined Shared Summary, Referral and Exit Interview cutover

This implementation performs no live provisioning, migration or deployment. Earlier merges do not
prove that any confidential-content migration or new keyring is active on the host. The **ADR-082
candidate inventory was 18**; actual starting state may be the original 15-secret/schema deployment,
an intermediate deployment, or already partly provisioned. The ADR-080/081 instructions above
preserve their historical domain procedures; use the ADR-084 combined gates below for the current
candidate.

1. Obtain separate live-cutover authorization. Inspect actual public build, immutable image/release
   manifest, applied migration graph, runtime source/pointer metadata and non-secret row counts for
   Summary, Referral/actions and Exit Interview/opportunities/reopen events. Record metadata/ratings
   and privately verifiable historical-content evidence. Secure and test a restorable encrypted
   database backup and matching prior immutable image/manifest/protected environment rollback pair.
2. Independently provision **each absent** ordered keyring through a protected operator process,
   never terminal/CI output: `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS`,
   `REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` and
   `EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`. Preserve any existing value/order. No
   domain may reuse Django, TOTP, Web Push storage or any entry from another content keyring.
   Escrow the complete ordered keyrings in independently protected approved off-host recovery
   before migration; retain older keys while backups need them. A database/Droplet-only backup is
   insufficient. The runtime exporter cannot export or generate an absent new key.
3. Use the existing `0700 compass:compass` parent and regular/non-symlink `0444 compass:compass`
   files. The new source is `exit_interview_confidential_content_encryption_keys`; its exact pointer
   in protected `/opt/compass/.env` is
   `EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/exit_interview_confidential_content_encryption_keys`.
   Remove direct assignments and use the current example for all 18 pointers. Only web/worker/Beat
   receive new domain sources; PostgreSQL/Redis/proxy grants stay narrow. Preflight all 18 files,
   quiet Compose and candidate settings against the reviewed immutable image, without exposing
   values/hashes/tokens. Do not dispatch ordinary deployment before provisioning succeeds.
4. Coordinate maintenance downtime: stop/drain old web, worker, Beat, every old scheduled/operator
   job and any other database writer; prevent restart through migrations and activation. Ordinary
   workflow migrations run before complete service replacement. Phase-B table locks fence current
   writes but cannot make old code compatible with removed columns after commit. Keep old processes
   stopped if migration/activation fails. Activate only the exact reviewed full staging SHA with
   `--ref staging` and `expected_staging_sha=<full SHA>` after all gates are satisfied.
5. Apply any missing Summary/Referral phases using their procedures, plus Exit Interview
   `0003_encrypt_confidential_content` then `0004_remove_plaintext_confidential_content`. Exit Phase A
   leaves plaintext authoritative and nullable ciphertext in three tables. Phase B locks response,
   opportunity, then reopen tables before verification, validates latest plaintext, authenticates
   every present v1/binding/payload, reconciles only missing or readable stale tokens (including old
   edits, changed Other choices/text, revoked-opportunity reopen notes and late rows), verifies again,
   removes 15 confidential plaintext columns and requires non-null/non-empty ciphertext. Corrupt
   present tokens abort atomically, including earlier writes. Never repair from plaintext or substitute
   blanks. Metadata, timestamps, ratings, IDs and side effects must remain unchanged.
6. Verify actual applied migrations and final columns, row counts/provenance/rating equality and
   historical content privately. Run all three domain rotation dry runs, including
   `rotate_exit_interview_confidential_content --dry-run --batch-size 100`. Exercise authorized
   owner DRAFT/SUBMITTED detail/edit, Head SUBMITTED detail/PDF and reopened-DRAFT denial, GSS
   opportunity-note-only access, metadata search/status and graduation Good Moral. Confirm saved
   contact snapshots/PDF fidelity, content-free Audit/notifications, exact public build/readiness and
   web/worker/Beat health. Print only sanitized counts/UUID/reason context. Repository evidence alone
   cannot establish live readiness. Resume service only with compatible candidate code.
7. Controlled rollback requires the same stopped/drained writers and complete readable keyrings.
   With the candidate image/keyrings, reverse Exit Interview to
   `0002_exitinterviewopportunity_exitinterview_opportunity_and_more` before launching old code.
   Reverse any newly activated Referral to `0002_void_provenance` and Summary to
   `0003_service_name_snapshot` if the prior image needs those plaintext columns too. Exit reverse
   temporarily re-adds nullable/default-compatible columns, fences writers, verifies/decrypts all
   13 response fields plus every note/reason, restores exact plaintext, then restores historical
   field state. Corruption aborts all restoration atomically. Phase A reverse drops tokens only after
   successful plaintext restoration. Verify schema compatibility with the actual previous release
   before activating its immutable image/manifest/environment pair; retain keys for encrypted backups.
   If verification cannot succeed, follow the tested backup recovery plan. Never start old code on
   a ciphertext-only schema. Restored plaintext and historical plaintext backups remain sensitive.

Later Exit Interview rotation is a separately operated transition: provision
`[new_primary, previous_keys...]`, preserve full protected off-host recovery and recreate all three
application services so mounts consume the new inode. Run dry-run followed by real rotation with
`--batch-size 100`. The command authenticates every envelope/schema/domain field, rotates only old-key
tokens through ADR-079, preserves token timestamps/plaintext bytes and all business metadata, commits
bounded row-locked batches and resumes after interruption. Output separates the three families and
lists at most 20 safe failure contexts; failed rows remain untouched and cause non-success. Both
modes refuse legacy plaintext columns. No scheduled rotation, key deletion or live action is automatic.


## ADR-083: deferred combined Summary, Referral, Exit Interview and Inventory cutover

Repository work only. No live key, host change, deployment or migration is authorized by this
implementation. The ADR-083 candidate required **19** runtime sources; ADR-084 requires **20** and its
additional gates below. Inspect actual live
build/schema and provisioned sources; it may still have 15, 16, 17 or 18. Existing domain procedures
above describe their historical migrations; these gates also cover the new Inventory boundary.

1. Obtain separate live-cutover authorization. Record actual live/target immutable images, public
   build, migration graph, protected manifest/environment pair and non-secret counts for all four
   domains, including Inventory's seven tables and StudentSupportProfile. Secure and test an
   encrypted database rollback backup. Keep existing secrets/order intact.
2. Provision each absent **independent** ordered domain keyring through a protected operator
   process. Never print keys or tokens. Inventory requires
   `INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`; its regular `0444 compass:compass` source is
   `/opt/compass/secrets/inventory_confidential_content_encryption_keys`, inside the existing
   `0700 compass:compass` directory. Protected `/opt/compass/.env` must contain only its pointer:
   `INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/inventory_confidential_content_encryption_keys`.
   Reject decoded-byte reuse with Django, TOTP, Web Push storage and every current/previous content
   domain key. Escrow complete ordered keyrings in approved independently protected off-host
   storage; retain older keys as long as backups need them. The exporter cannot generate absent keys.
3. For this historical target, preflight all 20 sources, exact pointers, quiet Compose and candidate settings. Web, worker and
   Beat get the Inventory source; PostgreSQL, Redis and proxy do not. Recreate application containers
   after source inode changes. Ordinary workflow deployment must wait until these gates succeed.
4. Stop/drain old web, worker, Beat, scheduled jobs, operator jobs and all other database writers.
   Prevent restart through migration and compatible-code activation. Table fencing blocks current
   writers but cannot make old code compatible with dropped columns after commit. Keep old code
   stopped after a failure. Use the exact reviewed full staging SHA and `--ref staging` only after
   provisioning, backup and maintenance readiness are verified.
5. Apply missing earlier domain phases using their own procedures. Inventory Phase A is
   `0006_encrypt_confidential_content`: add seven nullable ciphertext columns, backfill exact
   authenticated v1 payloads while plaintext remains authoritative. Phase B is
   `0007_remove_plaintext_confidential_content`: lock root, family, sibling, education, organization,
   transportation and reopen tables in that order before reads/updates. Validate latest plaintext,
   authenticate every present schema/binding/payload, retain equal tokens and reconcile missing or
   valid stale tokens. Late child replacements/creates/reasons use their actual new UUIDs; deleted
   rows stay deleted. A corrupt present token aborts all changes atomically. Only then remove the 82
   selected plaintext columns and enforce non-null/non-empty ciphertext. No business metadata,
   StudentSupportProfile, profiling dimensions, audit or notification side effects may change.
6. Verify actual schema/migration state, row counts, relationships and metadata equality; compare
   confidential content privately against protected evidence. Run all four domain rotation dry
   runs, including `rotate_inventory_confidential_content --dry-run --batch-size 100`. Exercise
   owner draft/submitted/historical detail, correction reason and PDF; scoped Counselor submitted
   detail/PDF and draft denial; metadata-only roster/search/history, Profiling/PDF/XLSX, Student
   Support and Routine/prerequisites. Confirm exact public build, readiness and three-service health.
   Resume only with compatible code. Output sanitized counts/UUIDs/reasons only.
7. Controlled rollback requires the same stopped/drained writers, candidate image and complete
   readable keyrings. Reverse Inventory to `0005_submission_history_reopen` before old code starts:
   temporary nullable/default-compatible fields are restored, all seven tables fenced, every token
   authenticated/decrypted and exact values restored, then historical definitions reinstated.
   Corruption aborts the reverse atomically; Phase A drops ciphertext only after plaintext has been
   restored. Reverse newly activated earlier domains if the prior image needs those columns too.
   Verify exact prior-image schema compatibility and activate its reviewed rollback pair. If
   verification fails, use the tested encrypted backup recovery procedure; never substitute blanks.
   Restored plaintext and historical plaintext backups remain sensitive.

Later Inventory rotation is separately operated: provision `[new_primary, previous_keys...]`,
update protected recovery and recreate application containers. Dry-run, then run
`rotate_inventory_confidential_content --batch-size 100` (valid range 1–1000). The command refuses
legacy plaintext columns in both modes, verifies seven families separately, rotates only previous-key
rows using ADR-079, preserves authenticated bytes/token timestamps and business data, row-locks
bounded transactional batches and resumes without rewrapping already-current rows. It lists at most
20 structural failure contexts, leaves failed rows unchanged and exits nonzero on unreadable content.


## ADR-084 combined deferred cutover: historical 20-file target

Use [ADR-084](decisions/ADR-084-graduate-tracer-confidential-content-encryption.md) with the
ADR-080–083 gates above. Establish actual live state first; historical repository merges do not
prove key provisioning or migration. The required Graduate Tracer pointer is
`GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/graduate_tracer_confidential_content_encryption_keys`.
Store its independent ordered keyring in a regular 0444 file inside the persistent 0700 host
directory. Only web/worker/beat receive it; Postgres, Redis and proxy do not.

An old runtime may lack any Shared Summary, Referral, Exit Interview, Inventory or Graduate Tracer
keyring. Provision each absent domain under separate live authorization; preserve all existing
current/previous keys exactly and escrow complete rings in approved independent off-host storage.
Current exporter utilities reject absent values and never generate keys. Protect and verify
encrypted database and host rollback backups before destructive migration. Drain old web/worker/beat,
in-flight and queued retention work, and all operator writers. Deploy only the approved full staging
SHA. Table locks protect Phase B, but old code must stay stopped until compatible activation.
Validate authorized raw reads, aggregate JSON/XLSX with decrypt forbidden, and no-decrypt
anonymization including anonymous ciphertext NULL/no children.

Before retiring any key, run dry-run for each of the five affected domains using the release's
Shared Summary, Referral, Exit Interview, Inventory and Graduate Tracer rotation commands:
`rotate_counseling_shared_summary_encryption --dry-run`,
`rotate_referral_confidential_content --dry-run`,
`rotate_exit_interview_confidential_content --dry-run`,
`rotate_inventory_confidential_content --dry-run`, and
`rotate_graduate_tracer_confidential_content --dry-run`.
Resolve every unreadable row and prove all surviving envelopes use the primary key. Controlled
rollback keeps writers drained, retains needed full keyrings, reverses affected domains to the exact
previous migration graph, verifies restored identifiable plaintext and anonymous minimized defaults,
and only then activates the previous exact SHA. Never restore personal content to an anonymous row.
No live cutover was performed here.


## ADR-085/086 combined deferred cutover: current 22-file inventory

This repository implementation authorizes no live key, host secret, migration or deployment.
Earlier merges do not establish actual live provisioning/schema readiness. The current target is
**22 required/optional sources**, with seven potentially absent content-domain keyrings: Summary,
Referral, Exit Interview, Inventory, Graduate Tracer, Account Profile and Feedback. Historical
15–20-file procedures above retain their domain migration/recovery details; use these combined
current gates before any separately authorized live operation.

1. Obtain explicit live-cutover authorization. Inspect actual backend public build, immutable image,
   release manifest, protected environment metadata, applied migration graph and source/pointer
   metadata. Record non-secret row counts and business metadata for all seven domains, Accounts
   identities and both Feedback families; privately prepare historical-content comparison evidence.
   Preserve every existing credential/key entry and order. Secure and **test restore** a restorable
   encrypted database backup plus encrypted host rollback backup and matching previous immutable
   image/manifest/environment pair, with approved off-host recovery. Verify the exact previous graph.
2. Independently provision each absent domain ring in a protected operator process; never expose
   values/hashes/tokens to terminal/CI. Reject decoded-byte reuse across all current/previous content
   rings, Django SECRET_KEY, TOTP and Web Push storage. Escrow **complete ordered keyrings**, including
   previous entries, in independently protected approved off-host storage before migration.
   Database/Droplet backups alone cannot recover ciphertext. Retain old keys while any retained
   backup requires them. Exporter tools cannot export/generate absent new values.
3. Account source: `/opt/compass/secrets/account_profile_confidential_content_encryption_keys`;
   Feedback source: `/opt/compass/secrets/feedback_confidential_content_encryption_keys`. Keep the
   persistent compass-owned parent at 0700; sources must be regular/non-symlink 0444 compass-owned
   files. Protected `/opt/compass/.env` must contain only exact pointers:
   `ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/account_profile_confidential_content_encryption_keys`
   and `FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/feedback_confidential_content_encryption_keys`.
   Use the current example for all 22 sources; direct assignments are forbidden. Only web/worker/beat
   get new grants; Postgres/Redis/proxy do not. Preflight all 22 file metadata/pointers, quiet Compose
   and candidate settings against the reviewed immutable image. Recreate application containers
   after source inode changes. Never dispatch ordinary deployment before these gates pass.
4. Coordinate maintenance: stop/drain old web, worker, beat, queued/in-flight jobs, every old scheduled
   or operator writer and any other database writer; prevent restart through all destructive phases
   and compatible activation. Ordinary workflow migrations happen before full service replacement.
   PostgreSQL fences protect verification but cannot make old code compatible with removed columns
   after commit. Keep old processes stopped if migration/activation fails. Activate only the reviewed
   exact full staging SHA, `--ref staging`, `expected_staging_sha=<full SHA>` after every gate passes.
5. Apply missing Summary/Referral/Exit/Inventory/Tracer phases using their frozen domain procedures.
   Accounts: `0007_encrypt_confidential_content`, then `0008_remove_plaintext_confidential_content`.
   Feedback: `0003_encrypt_confidential_content`, then `0004_remove_plaintext_confidential_content`.
   Phase A leaves plaintext authoritative. Phase B fences accounts_user and independently Customer
   Feedback then CSM before verification/destruction. Authenticate every present envelope, reconcile
   only missing/valid stale tokens against latest plaintext (including late old writers/inserts),
   verify, remove exactly five Accounts plus seven Feedback fields and require non-empty tokens.
   Present unreadable/rebound/unsupported/malformed tokens abort atomically; never repair or blank.
   Identity/security/photo state, timestamps, Feedback revision/ratings/dimensions and side effects
   must remain unchanged. Confirm actual applied migrations and final schema privately.
6. Verify historical plaintext equivalence privately, row counts/business metadata and content-free
   side effects. Exercise active self-profile GET/partial/no-op PATCH and required-corrupt errors;
   identity/search/admin/capability/photo operations with profile decryption forbidden; form prefill
   and independent saved snapshots; Student Feedback submission/one-shot provenance; Head detail
   plus metadata-only list/search/pagination; unauthorized role denial before decryption. Verify
   exact build/readiness and all three application services. Run all seven content-domain dry runs:
   Summary, Referral, Exit, Inventory, Tracer commands above plus
   `rotate_account_profile_confidential_content --dry-run --batch-size 100` and
   `rotate_feedback_confidential_content --dry-run --batch-size 100`. Resolve every unreadable row
   before retiring keys. Log sanitized counts/UUIDs/bounded reasons only; repository tests alone
   cannot establish live readiness. Resume only with compatible candidate code.
7. Controlled rollback keeps all writers drained and full readable ordered rings available. With the
   candidate image reverse Accounts to `0006_rename_reference_capabilities` and Feedback to
   `0002_feedback_opportunity` if those are the exact prior image's required leaves. Reverse other
   newly activated domains to the verified previous graph as necessary. Fences execute before
   restored-column DDL; temporary nullable columns are filled with exact verified plaintext, then
   historical definitions reinstated. Unreadable content rolls back the complete reverse atomically.
   Phase A removes tokens only after restoration. Verify schema compatibility before activating the
   previous immutable image/manifest/environment pair. If verification fails, follow tested backup
   recovery; never launch old code against ciphertext-only columns or replace lost content with
   blanks. Restored plaintext and historical plaintext backups remain sensitive.

Later rotation is separately operated: provision `[new_primary, previous_keys...]` independently for
Accounts/Feedback, update complete protected off-host recovery, recreate web/worker/beat to consume
new inodes, dry-run, then real commands with batches 1–1000 (default 100). Verify bindings/schema/
payloads and preserve plaintext bytes/Fernet timestamps. Batches lock real rows and commit separately;
resume after interruption, current-primary rows are no-ops, failures remain untouched and exit nonzero.
Only token columns change; no User.updated_at/security/session/photo/Audit or Feedback metadata change.
No scheduled rotation, automatic key deletion or live action is introduced here.
