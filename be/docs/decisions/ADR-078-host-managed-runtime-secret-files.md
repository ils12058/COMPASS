# ADR-078: Host-managed runtime secret files

- Status: Accepted
- Date: 2026-10-05
- Scope: Live-staging runtime secret storage and delivery

## Context

PR #170 introduced a Vault Community foundation; PR #174 reverted it. Vault's initialization,
independent custody, seal/unseal recovery, service operation and Agent delivery added more
operational responsibility than this live-staging/capstone deployment can sustain. The historical
experiment remains in Git. This decision does not reuse ADR-077 or revive its implementation.

Long-lived values in the host `.env` currently enter persistent Docker environment metadata.
Redis also duplicates one password across six URLs. COMPASS already has an explicit, mutually
exclusive `NAME` / `NAME_FILE` configuration interface (ADR-007).

## Decision

Store the 15 runtime secret files listed in [the operator runbook](../runtime-secrets.md) in
`/opt/compass/secrets`, outside releases, Git and image builds. The deployment user `compass`
owns the directory with mode `0700`; source files are regular, non-symlink files, mode `0444`.
Only directory metadata and assignment names/pointers enter deployment preflight output.

The restrictive host parent directory prevents other unprivileged host users traversing it.
Docker Compose bind-mounts individual files into `/run/secrets/<name>`, read-only, only for
explicitly granted services. File-backed Compose secrets do not remap ownership/mode reliably;
readable individual mounts support the existing non-root application image without pinning its
UID to the host or adding a secret-specific group. No GID synchronization is needed.

`web`, `worker` and `beat` receive all 15 application runtime secrets because Django settings
load eagerly. PostgreSQL receives only `postgres_password`; Redis receives only `redis_password`;
Caddy receives none. The host `.env` contains ordinary configuration and `_FILE` pointers,
including pointers for optional empty files. Existing enabled-feature validation remains in Django.

The official PostgreSQL image reads `POSTGRES_PASSWORD_FILE`. Initial delivery migration preserves
the existing database password; changing the file does not rotate a role in an initialized volume.
A deployment-owned Redis shell wrapper reads its password file and writes an escaped Redis
configuration only to a dedicated container tmpfs. It starts the official Redis entrypoint with
append-only persistence still enabled. Health checks supply `REDISCLI_AUTH` only to their transient
process. No Redis password is embedded in persistent environment metadata or server arguments.

Django derives percent-encoded Redis URLs from `REDIS_PASSWORD` (including its `_FILE` form),
`REDIS_HOST` and `REDIS_PORT`: DB 0 is primary/broker, DB 1 cache/results, DB 2 rate limiting,
DB 3 idempotency. Legacy URL overrides remain local/CI compatibility only. The live host preflight
rejects all six Redis/Celery URL assignments, direct secret assignments, and persistent demo
password inputs before candidate containers are created.

There is no secret-management daemon, external secret backend, automatic rotation or scheduler.
GitHub Actions retains infrastructure bootstrap credentials, and delivers code, manifests and
helpers only. Runtime provisioning and exact-value migration belong to the Droplet operator.
The one-time migration helper exports/compares effective configuration without values or digests.

## Recovery and rotation

Keep independent protected off-host recovery copies of TOTP, the complete ordered Routine Interview
keyring, and Web Push storage keys. Approved password-manager storage or an encrypted offline
archive is sufficient; no escrow service is introduced. Database backups alone cannot recover
content encrypted under lost keys. Preserve older keys while backups still depend on them.

Ordinary credential replacement uses a validated temporary file, mode `0444`, atomic rename,
container recreation, verification and provider revocation where applicable. Individual bind mounts
can retain the old inode, so a container restart is insufficient after atomic replacement.
Encryption-key rotation requires its domain-specific readability/migration plan (including ADR-066),
not this generic operational pattern. Initial migration changes storage/delivery only.

## Threat model and consequences

Long-lived deployment secrets are stored outside source control in access-restricted files on the
staging host. Docker Compose exposes each secret only to authorized services as read-only files,
while COMPASS reads them through its file-based configuration interface. The host operating system
and Docker daemon remain part of the trusted infrastructure boundary.

This reduces `.env` concentration, accidental environment inspection/log exposure, credential
duplication and unnecessary cross-service access. It does not protect against root or Docker
daemon compromise, the deployment user who controls Docker, or an authorized application process
that is compromised. Host files are plaintext at rest within this trust boundary, not an HSM or
external KMS. Encryption at rest, independent backups and controlled host access remain operator
responsibilities. Optional empty sources must still exist for Compose; missing required files fail
preflight. No frontend, API, schema, ciphertext or encryption behavior changes are required.

## References

- [Compose secrets and per-service grants](https://docs.docker.com/compose/how-tos/use-secrets/)
- [File-backed ownership/mode limitation](https://docs.docker.com/reference/compose-file/services/#secrets)
- [Official PostgreSQL password-file convention](https://hub.docker.com/_/postgres)
