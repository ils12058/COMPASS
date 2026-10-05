# Host-managed live-staging runtime secrets

This is the operator runbook for ADR-078. Repository validation proves the delivery mechanism;
live cutover requires separate authorization, exact-value comparison and service verification.
Do not deploy the new manifest before the host is provisioned. There is no daemon or external
secret-management service.

## Host directory and service grants

`/opt/compass/secrets` is persistent outside `/opt/compass/releases`, owned by `compass:compass`,
mode `0700`. All 16 source files must be regular files, not symlinks, owned by `compass`, mode
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
| `WEB_PUSH_PRIVATE_KEY` | `web_push_private_key` | when enabled |
| `WEB_PUSH_STORAGE_KEY` | `web_push_storage_key` | when enabled |

| Service | Explicit grants |
| --- | --- |
| `web`, `worker`, `beat` | all 16, because Django loads settings eagerly |
| `postgres` | `postgres_password` only |
| `redis` | `redis_password` only |
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

The original ADR-078 cutover below migrated 15 existing values. ADR-080 adds a **new** required
16th value; the current inventory/checker/exporter includes it. The numbered 15-value steps
are historical, not a recipe to rerun export on an already converted host. They describe the
original 15-value helper/inventory shipped with ADR-078. Current utilities expect all 16.
An old 15-secret runtime has no Shared Summary key to export. Provision the new independently generated keyring using the
separate cutover below before using current-inventory utilities. The exporter never generates
keys and cannot recover an absent value. Preserve the original values and ordered keyrings.
Do not rerun export on the file-backed host; follow the ADR-080 cutover section instead.

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
`ROUTINE_INTERVIEW_ENCRYPTION_KEYS`, `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS`, and
`WEB_PUSH_STORAGE_KEY`, including older keys while retained
backups depend on them. Future application encryption keyrings follow the same rule. An approved
password manager or encrypted offline archive is sufficient; no escrow service is part of this slice.

`DEMO_ACCOUNT_PASSWORD` remains one-off operator input. It is never a long-running Compose grant;
existing `_FILE` support can be used only when an operator explicitly mounts it for the seeding
command. See [staging-demo-seeding.md](staging-demo-seeding.md).


## ADR-080: one-time Shared Summary encryption cutover (separate authorization)

This repository change does not provision a live key or start deployment. The currently provisioned
host may still have 15 source files. The new manifest requires 16; preflight fails until the new
mandatory file and pointer exist. Do not dispatch the ordinary deployment workflow prematurely.

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
