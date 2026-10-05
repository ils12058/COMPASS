# Vault foundation validation and operator handoff

Branch: `codex/vault-secrets-foundation`. Worktree:
`/Users/reynantlntno/.codex/worktrees/vault-secrets-foundation/COMPASS`.
Base: `2ed4a9aad6cf23a311b53ab031e556157c0ba9dd` (`staging` fetched before edits).
The prompt's audited `6a6bb887` base had moved through PRs #168/#169; their backend delta is scoped
record retrieval, with no deployment/settings changes. The primary checkout was left untouched.

## Delivered architecture

[ADR-075](decisions/ADR-075-vault-runtime-secret-delivery.md) and the complete
[operator runbook](vault-live-staging.md) establish host `vault.service` and `vault-agent.service`,
Community TLS on loopback 8200/8201, Integrated Storage/Raft in `/var/lib/vault/raft`, Shamir
off-host custody, and protected rotating file auditing. Vault is independent of application releases.

KV v2 uses eleven domain records under `kv/compass/live-staging/`: core; database/postgres and
redis; storage/s3; mail/smtp; authentication/totp; confidential-data/routine-interview;
integrations/daily, turnstile, psgc; notifications/web-push. Demo/accounts is reserved and excluded
from workload access. Future confidential-data domain paths fit without changing Django.

Runtime policy grants explicit data reads and self-token lookup/renewal only; no broad/list/write/
delete/admin or other environment access. Agent uses scoped AppRole, a renewable service token,
finite 30-day bootstrap Secret ID, no token sink/proxy, and strict host ownership. The separate
human operator policy is privileged and must never be assigned to Agent or containers.

Fifteen files are rendered atomically, without backups, in ephemeral `/run/compass-secrets` mode
0440/GID 1900. Web/worker/beat share a read-only directory at `/run/secrets/compass` with that
supplementary group. PostgreSQL/Redis receive only their own file; proxy receives none.
Files-only mode rejects direct values, incorrect pointers, and Redis/Celery overrides. Host
deployment checks reject secret-bearing assignment names before Docker creates containers, then
check active Vault/Agent, verified unsealed TLS health, required files, and permissions before
Django checks/migrations. Optional disabled-integration files can be empty; enabled validation
remains unchanged.

The existing env/_FILE helper remains authoritative. All fifteen inventory settings use it:
SECRET_KEY; PostgreSQL/Redis passwords; S3 and SMTP credential pairs; Turnstile, Daily API/HMAC,
PSGC; TOTP, ordered Routine Interview keyring; Push private/storage keys. The migration tool
exports the current helper's values into private domain JSON and compares actual rendered bytes.
It rejects values that would change under file semantics and never logs values or hashes.

Redis derives percent-encoded URLs from host/port and the file password: broker=0, cache/results=1,
rate limit=2, idempotency=3. Celery defaults preserve routing. Legacy explicit URLs remain outside
files mode for local/CI/pre-cutover compatibility. PostgreSQL uses official password-file bootstrap;
existing database credentials are unchanged. Redis's escaped config exists only on container tmpfs,
without a persistent environment password or password argument; healthcheck auth is transient.
Local Compose/Mailpit/MinIO and ephemeral CI crypto keys remain independent of Vault.

## Files changed

- Backend settings, `.env.example`, README; two narrow common configuration helpers.
- Staging Compose and `deploy-staging.yml` file mounts/preflight uploads and checks.
- `deploy/vault/`: server/Agent HCL, two systemd units, runtime/human policies, logrotate,
  pointer overlay, Redis wrapper, file/env preflights, and operator export/comparison utility.
- ADR-075, live operator runbook, this evidence report, and Daily/Push/demo documentation links.
- Common helper, Redis routing/source-guard, and migration/preflight tests.

No frontend, OpenAPI/client, model/migration, dependency lock, or crypto implementation changes.

## Validation results

- Broad focused backend command: **141 passed, 7 deselected** in 74.71s. Modules: common config,
  Redis config, Routine Interview encryption, authentication, Push, Daily E-Counseling, PSGC
  integration/reference, Turnstile, and storage. Rotation/migration tests were excluded because
  neither behavior was touched. One test-database teardown warning reported two open connections;
  no test failed. This is not a whole-repository suite result.
- After the final routing/export/preflight changes: **49 passed** for common config, Redis config,
  and runtime-secret migration/preflight. This covers special-character encoding, required
  credentials, exact DB routing, Celery defaults, local compatibility, IPv6/authority rejection,
  source conflicts, unavailable/invalid files, source restrictions, exact export/comparison,
  metadata-only errors, and host rejection before Docker.
- Whole-backend Ruff format/check passed; Django check reports zero issues; migration dry-run
  reports no changes; locked dependencies check passes; shell syntax and diff whitespace pass.
- Both Compose manifests parse with the installed Docker Compose provider through Podman,
  using only examples/synthetic configuration and `--no-env-resolution --quiet`.
- Real local **Vault Community 2.1.1** smoke: normal TLS/Raft server (not dev), audit writing,
  AppRole authentication/renewal, runtime denial of demo/production/admin/write operations,
  all fifteen exact template renders with 0440/GID 1900, authorized group access and denied
  unrelated UID/GID access, snapshot save/inspect, sealed no-render after cleanup, unseal/render
  recovery. Server/Agent ran in a disposable Linux container; this does not verify host systemd.
- Real local staging-version Redis and PostgreSQL containers: escaped synthetic password with
  special characters/Unicode authenticates, Redis healthcheck passes, credential absent from
  Docker configuration and Redis process arguments, PostgreSQL file authentication succeeds.
  File-only Django settings import succeeds with the frozen dependencies, valid synthetic
  TOTP/Routine/Push keys and enabled Daily/Turnstile/Push integrations.

All fixture credentials and keys were synthetic. Local disposable service fixtures were cleaned
up/stopped; existing local application services were not changed. Logs and manual smoke scripts
are local evidence under `/Users/reynantlntno/.codex/artifacts/vault-secrets-foundation/`.

## Read-only live host inspection

DigitalOcean `doctl` inventory and pinned SSH inspection on 2026-10-05 verified:

- Droplet `602091909`, `compass-staging-api-01`, active in Singapore; 2 vCPUs / 4 GB RAM / 80 GB disk.
- Guest OS Ubuntu 24.04.4 LTS (Noble), x86_64; Python 3.12.3.
- Guest snapshot: 3.8 GiB RAM total / 2.4 GiB available; root filesystem 77 GiB total / 25 GiB
  available; no swap. These measurements do not establish capacity under future Vault load.
- No Vault executable/package found; both planned Vault systemd units report `not-found`.
- All six COMPASS containers running; web/proxy/PostgreSQL/Redis healthy.
- `/opt/compass/.env` mode 0600 and ownership `compass:compass`; its contents were not read.
- Deployment user `compass` could not execute `sudo -n true`; the tested local bootstrap SSH key was
  refused for root. Administrator access remains an installation prerequisite.
- The first timeout matched an SSH firewall /32 allowlist excluding the current client IP.
  Temporary current-client TCP 22 access was removed after inspection; the original rules were
  verified restored. Public TCP 8200/8201 remain unallowed.

No package, application configuration, runtime value, container, or Vault data was changed.

## Live steps still required

Vault TLS/Agent health, live value equality, encrypted-data readability, backups and live cutover
remain unverified. The new manifest/workflow requires provisioning before deployment. Do not
treat merge or synthetic validation as a completed live cutover.

The operator must establish administrator access and recheck OS/version/capacity/swap; take
verified PostgreSQL and encrypted off-host configuration/key recovery backups; install the approved Community package;
install host identities/TLS/Raft/units; initialize with off-host share custody; unseal and enable
KV/audit; establish human/runtime identities and revoke root; export/import exact current values;
start Agent; compare every rendered value; convert protected `.env` to pointers/remove direct
secrets and legacy URLs; deploy the authorized exact staging SHA; verify Django, all six services,
SMTP/Turnstile/Daily/PSGC/Push as enabled and existing Routine/TOTP/Push data readability; confirm
zero long-lived `.env` secrets; snapshot; and perform the documented restart drill.

Emergency rollback requires the previous image **and previous plaintext-compatible manifest**,
plus the secure operator backup restored mode 0600 with exact old values. Remove conflicting
pointers, recreate without deleting volumes, and verify readiness/decryption. No automatic
fallback exists; document/expire the temporary rollback exception and repeat deliberate cutover.

Known limits: one node/no HA, manual unseal and finite Secret ID replacement, same-host root
compromise, eager shared app access, in-memory secrets in running processes, static files during
temporary Agent retries, and forced recreation after atomic bind-file replacement. A deliberate
seal stops apps/Agent first; seal alone is not revocation. PostgreSQL briefly exports file values
inside its official bootstrap process; Redis healthcheck uses transient auth environment. These
do not place secrets in persistent Docker configuration. Snapshot restore, true Droplet reboot,
live key equality and live ciphertext/readability remain operator acceptance work.

## Explicit invariants

No live secret values were committed. No existing encryption key was rotated. No Routine Interview
ciphertext was changed. No Vault root token was provided to COMPASS. No unseal key was stored in
the repository. No frontend secret was introduced. No dynamic database credentials were
implemented. No shared crypto extraction was performed. No merge/deployment is authorized by
this foundation request alone; review precedes a separate explicit merge instruction.
