# Vault Community live-staging operator runbook

This repository foundation is not a completed live migration. PR #170 merged into staging as
`27587181acb2f1e4a9122e251a2e6a930e3ea4e7`. Fetch staging before execution and inspect subsequent
changes to settings, Compose, deployment assets/workflow, and Vault documentation. Resolve staging
again immediately before dispatch; an old recorded SHA is not deployment authorization.
Read [ADR-077](decisions/ADR-077-vault-runtime-secret-delivery.md) with
[ADR-007](decisions/ADR-007-environment-strategy.md). Non-secret assets are in `be/deploy/vault/`.

## Preconditions and boundary

Vault and Agent are separate host systemd services, outside Compose/releases. This uses Community,
single-node Raft, KV v2, verified TLS, loopback 8200/8201, and Shamir manual unseal. Never add Vault
to Caddy or public firewall rules. Root compromise of the same Droplet defeats this boundary.
Running processes retain plaintext in memory; this reduces `.env` and Docker metadata exposure.

Preserve all existing credentials, keyring order, VAPID pair, TOTP/Push storage keys, and ciphertext.
Do not generate replacement application keys, rotate, or re-encrypt. Only infrastructure TLS and
Vault identities are new. Ordinary configuration/public material stays outside Vault. GitHub
DigitalOcean/SSH deployment credentials stay in Actions Secrets; frontend needs no integration.

Read-only DigitalOcean inventory and pinned SSH inspection on 2026-10-05 confirmed Droplet
`602091909` (`compass-staging-api-01`, Singapore), **Ubuntu 24.04.4 LTS (Noble), x86_64**, and
Python 3.12.3. Its plan has 2 vCPUs, 4 GB RAM and an 80 GB disk. The guest snapshot showed
3.8 GiB RAM total / 2.4 GiB available, 25 GiB available on the 77 GiB root filesystem, and no
swap. No Vault executable/package was found; `vault.service` and `vault-agent.service` were
not found. All six COMPASS containers were running; web, proxy, PostgreSQL and Redis were healthy.
The protected `/opt/compass/.env` remained mode 0600, owned by `compass:compass`; its contents
were not read. These are inspection-time observations, not a Vault installation or capacity guarantee.

The initial SSH timeout matched the current client IP being outside the firewall's SSH allowlist.
Temporary current-client /32 access to TCP 22 enabled inspection and was removed afterward;
the original firewall was verified restored, with no public 8200/8201 rule. The deployment user
`compass` could not execute `sudo -n true`, and the tested local bootstrap key could not log in as root.
**Establish an authorized administrator session before installation.** Recheck `cat /etc/os-release`,
`uname -m`, `vault version` if installed, `free -h`, `df -h`, and `swapon --show` at execution time.
Take a PostgreSQL backup and a verified, encrypted, off-host operator recovery copy of the original
`.env`; never print/upload it. Keep live `.env` mode 0600.

Build/deploy code support first using the previous manifest if necessary. The **new manifest is
file-only**; its workflow refuses to deploy until Vault is provisioned, unsealed, rendered, compared,
and the environment converted. Do not dispatch the new workflow before completing these steps.

## Installation on the verified OS

On 2026-10-05 the official [Community install page](https://developer.hashicorp.com/vault/install)
advertised 2.1.1, and the Noble/amd64 repository listed package `2.1.1-1`. Neither observation
means Vault is installed on the Droplet. Recheck support/advisories and pin an exact approved
Community version at execution time; record it and use its matching docs. Do not silently upgrade
an existing cluster. The package signing key is separate from the binary-release signing key:
the [official security page](https://www.hashicorp.com/en/trust/security) currently identifies
`D55C 0D1A C78A 8D81 26CB 631C FC9C A96A CA02 6560`. Verify the current published fingerprint
and repository signatures; do not trust an older cached fingerprint after a key rotation.
On a confirmed supported Ubuntu/Debian system, as an administrator:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg openssl python3
curl -fsSL https://apt.releases.hashicorp.com/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
gpg --show-keys --fingerprint /usr/share/keyrings/hashicorp-archive-keyring.gpg
# Verify this fingerprint against HashiCorp's official signing-key guidance before trusting it.
. /etc/os-release
vault_codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
test -n "$vault_codename"
printf 'deb [arch=%s signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com %s main\n' \
  "$(dpkg --print-architecture)" "$vault_codename" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null
sudo apt-get update
apt-cache policy vault
read -r -p 'Approved exact apt package version: ' compass_vault_version
sudo apt-get install "vault=$compass_vault_version"
vault version
sudo systemctl stop vault.service
```

No `apt-key`. For another OS use its official supported package procedure and deliberately adjust
unit binary paths. Disable host swap through the approved OS procedure and persist/verify it:
Raft uses `disable_mlock=true` per official guidance. Assess RAM/disk for Vault and the existing
application/database load. A single staging node provides no HA.

## Host ownership, TLS, and systemd

Set `vault_assets` to the absolute reviewed asset directory copied to the host. The package should
provide `/usr/bin/vault` and a dedicated `vault` account; create a system account without login if
absent. Inspect existing identities on reruns; do not silently reuse unrelated numeric GID 1900.

```bash
getent passwd vault
getent group 1900
# Stop if 1900 is assigned to an unrelated group.
sudo groupadd --gid 1900 compass-secrets
sudo useradd --system --no-create-home --shell /usr/sbin/nologin \
  --gid compass-secrets compass-vault-agent
sudo usermod -aG compass-secrets compass
sudo install -d -o vault -g vault -m 0700 /var/lib/vault/raft /var/log/vault
sudo install -d -o root -g vault -m 0750 /etc/vault.d/tls
sudo install -d -o root -g compass-secrets -m 0750 /etc/vault-agent.d
sudo install -d -o compass-vault-agent -g compass-secrets -m 0700 \
  /etc/vault-agent.d/credentials
```

Use an explicitly pinned self-signed local TLS certificate as the initial loopback trust anchor.
An existing internal CA is also acceptable with matching loopback SANs and verified trust. Generate
only infrastructure TLS material, with shell tracing/terminal recording disabled:

```bash
sudo openssl req -x509 -newkey rsa:3072 -sha256 -days 365 -nodes \
  -keyout /etc/vault.d/tls/server.key -out /etc/vault.d/tls/server.crt \
  -subj '/CN=compass-vault-local' \
  -addext 'subjectAltName=IP:127.0.0.1,DNS:localhost' \
  -addext 'basicConstraints=critical,CA:FALSE' -addext 'extendedKeyUsage=serverAuth'
sudo chown root:vault /etc/vault.d/tls/server.key /etc/vault.d/tls/server.crt
sudo chmod 0640 /etc/vault.d/tls/server.key
sudo chmod 0644 /etc/vault.d/tls/server.crt
sudo install -o root -g root -m 0644 /etc/vault.d/tls/server.crt /etc/vault.d/tls/ca.crt
sudo chmod 0755 /etc/vault.d /etc/vault.d/tls
openssl verify -CAfile /etc/vault.d/tls/ca.crt /etc/vault.d/tls/server.crt
sudo install -o root -g vault -m 0640 "$vault_assets/vault.hcl.example" /etc/vault.d/vault.hcl
sudo install -o root -g compass-secrets -m 0640 \
  "$vault_assets/vault-agent.hcl.example" /etc/vault-agent.d/agent.hcl
sudo install -m 0644 "$vault_assets/vault.service" /etc/systemd/system/vault.service
sudo install -m 0644 "$vault_assets/vault-agent.service" /etc/systemd/system/vault-agent.service
sudo install -m 0644 "$vault_assets/vault.logrotate" /etc/logrotate.d/compass-vault
sudo systemctl daemon-reload
sudo systemctl enable --now vault.service
```

Copy only the public trust certificate to operators over pinned SSH; verify its fingerprint. Track
expiry and rehearse trust renewal before expiry. Never use permanent TLS bypass/disable or public
Vault DNS/proxy/firewall exposure. Agent owns runtime directory 0710; files are 0440/shared GID 1900.
Compose adds that supplementary GID to applications. The deployment user needs a fresh login for
its new group; Agent's bootstrap credential directory is owner-only, inaccessible to that group.

## Initialization, shares, and identities

Initialize once from a trusted operator laptop through pinned SSH forwarding:
`ssh -N -L 18200:127.0.0.1:8200 compass@<verified-droplet>`. Set laptop
`VAULT_ADDR=https://127.0.0.1:18200` and `VAULT_CACERT` to the verified public certificate.
The certificate's 127.0.0.1 SAN remains valid through the tunnel.

```bash
umask 077
vault operator init -key-shares=5 -key-threshold=3 \
  -pgp-keys=custodian1.asc,custodian2.asc,custodian3.asc,custodian4.asc,custodian5.asc \
  -root-token-pgp-key=bootstrap-operator.asc -format=json > vault-init.encrypted.json
```

Output is protected **off-Droplet**. Separate custodians keep encrypted shares and private PGP keys
off-host. Never store plaintext shares in Git/GitHub, `.env`, systemd, Agent, or Docker volumes.
Custodians decrypt locally and enter shares into the hidden `vault operator unseal` prompt, never
as arguments or in a recorded terminal. Repeat to threshold; verify `vault status` unsealed/Raft.

The bootstrap operator privately reads the decrypted root token into laptop memory only:
`read -rs VAULT_TOKEN; export VAULT_TOKEN`. Do not log it, `vault login` with it, or store it in a
token helper. On the laptop, with its own copy of the reviewed assets:

```bash
vault secrets enable -path=kv -version=2 kv >/dev/null
vault audit enable -path=compass-file file file_path=/var/log/vault/audit.json mode=0600 >/dev/null
vault policy write compass-live-staging-runtime \
  "$vault_assets/policies/compass-live-staging-runtime.hcl" >/dev/null
vault policy write compass-live-staging-operator \
  "$vault_assets/policies/compass-live-staging-operator.hcl" >/dev/null
vault auth enable approle >/dev/null
vault write auth/approle/role/compass-live-staging-runtime \
  bind_secret_id=true token_policies=compass-live-staging-runtime \
  token_no_default_policy=true token_type=service token_period=1h \
  secret_id_ttl=720h secret_id_num_uses=0 \
  secret_id_bound_cidrs=127.0.0.1/32 token_bound_cidrs=127.0.0.1/32 >/dev/null
vault auth enable userpass >/dev/null
vault write auth/userpass/users/compass-operator \
  password=@/operator-private/new-vault-operator-password \
  token_policies=compass-live-staging-operator \
  token_ttl=1h token_max_ttl=8h >/dev/null
```

These are the supported [Userpass token fields](https://developer.hashicorp.com/vault/api-docs/auth/userpass).
Read back `token_policies`, `token_ttl` (3600 seconds), and `token_max_ttl` (28800 seconds) from
`auth/userpass/users/compass-operator` before login. A successful write alone is insufficient:
check that no parameter was ignored, and that the login token has the intended policy and TTL.
Do not use the older `policies`, `ttl`, or `max_ttl` names for this example.

The human password file is protected off-host infrastructure identity material. Use an existing
approved human auth method instead if available. In a second laptop shell without `VAULT_TOKEN`,
`vault login -no-print -method=userpass username=compass-operator` privately prompts and stores a
bounded human token on that laptop only. Prove its permissions, then revoke bootstrap root with
`vault token revoke -self >/dev/null; unset VAULT_TOKEN` in the first shell. Root is never supplied
to COMPASS. The operator policy is privileged, never assigned to Agent. Later audit/policy/auth
changes require an approved administrative identity or exceptional root-generation ceremony.

As administrator prepare Agent credential files owned by Agent/mode 0600, receive the following
through the approved private SSH channel, then make them 0400. Never add arbitrary passwordless
root/tee permissions merely for these examples:

```bash
vault read -field=role_id auth/approle/role/compass-live-staging-runtime/role-id | \
  ssh compass@<verified-droplet> 'sudo -u compass-vault-agent tee /etc/vault-agent.d/credentials/role-id >/dev/null'
vault write -field=secret_id -f auth/approle/role/compass-live-staging-runtime/secret-id | \
  ssh compass@<verified-droplet> 'sudo -u compass-vault-agent tee /etc/vault-agent.d/credentials/secret-id >/dev/null'
```

Agent uses persistent Secret ID read mode to permit re-authentication; its TTL is 30 days. Record
the accessor privately, replace before expiry, verify re-authentication, and destroy the old accessor.
A renewable token does not let an expired Secret ID log in after reboot. Agent has no token sink,
listener, proxy/cache, or environment templates. It reads eleven explicit KV v2 data paths and may
only lookup/renew its own token. No list/write/delete/admin or demo/production grants exist.

## Domain values, export, and import

Keep the previous image/manifest and original `.env` unchanged until equality is proven. Do not
source `.env`, scrape credentials from URLs, or paste secret values into command arguments. On the
host create a root-only tmpfs import directory and export through the current image's actual helper:

```bash
sudo install -d -o root -g root -m 0700 /run/compass-vault-import
# Export COMPASS_IMAGE from /opt/compass/.deploy.env; never modify that image-state file.
# Run from the previous current release, with its original .env and previous manifest.
docker compose -f compose.staging.yaml run --rm --no-deps --pull never -T --user 0 \
  -e PYTHONPATH=/app \
  -v "$vault_assets/migrate-runtime-secrets.py:/migration-tool.py:ro" \
  -v /run/compass-vault-import:/migration \
  web python /migration-tool.py export /migration
```

This exports domain JSON, never values to stdout, preserving Compose quoting and `_FILE` semantics.
Unexpected CR, trailing LF, or NUL fails rather than silently changing a value. Resolve such delivery
semantics before migration. Disabled optional integrations keep existing empty strings. Source
credentials are not modified. Use a scoped human token to import privately over verified TLS, from
host root-only tmpfs or after secure transfer to laptop private tmpfs. No Actions/runtime token:

```bash
for domain in core database/postgres database/redis storage/s3 mail/smtp authentication/totp \
  confidential-data/routine-interview integrations/daily integrations/turnstile integrations/psgc \
  notifications/web-push; do
  vault kv put -mount=kv "compass/live-staging/$domain" "@$import_dir/$domain.json" >/dev/null
done
```

| Logical path under `kv/compass/live-staging/` | Fields | Runtime files |
| --- | --- | --- |
| `core` | `secret_key` | `django_secret_key` |
| `database/postgres` | `password` | `postgres_password` |
| `database/redis` | `password` | `redis_password` |
| `storage/s3` | `access_key_id`, `secret_access_key` | `s3_access_key_id`, `s3_secret_access_key` |
| `mail/smtp` | `username`, `password` | `smtp_username`, `smtp_password` |
| `authentication/totp` | `encryption_key` | `auth_totp_encryption_key` |
| `confidential-data/routine-interview` | `encryption_keys` (original ordered string) | `routine_interview_encryption_keys` |
| `integrations/daily` | `api_key`, `webhook_hmac` | `daily_api_key`, `daily_webhook_hmac` |
| `integrations/turnstile` | `secret_key` | `turnstile_secret_key` |
| `integrations/psgc` | `api_token` | `psgc_api_token` |
| `notifications/web-push` | `private_key`, `storage_key` | `web_push_private_key`, `web_push_storage_key` |

KV CLI uses logical paths; policy/templates use `kv/data/...`. `demo/accounts` is reserved for
operator-only use and excluded from runtime rendering. Future `confidential-data/counseling`,
`referrals`, and `exit-interviews` fit naturally. Do not use one giant record.

## Render, compare, and cut over

```bash
sudo systemctl enable --now vault-agent.service
# Wait for all fifteen files, then compare actual bytes, not just file names or key validity.
sudo python3 "$vault_assets/migrate-runtime-secrets.py" compare /run/compass-vault-import
sh "$vault_assets/check-runtime-secrets.sh"
```

Comparison covers every value/keyring order without printing values/hashes. Resolve any mismatch
before changing `.env`. Verify ownership/modes and no unrelated access. In a maintenance window,
stop application services through the previous manifest. Convert protected `/opt/compass/.env`
using `runtime.env.example`: preserve ordinary configuration, remove all fifteen direct secret
forms, add their exact `_FILE` pointers, and remove all six Redis/Celery URL overrides including
their `_FILE` variants. Do not append duplicate sources. Redis host stays `redis`, port 6379;
DBs remain broker 0, cache/results 1, rate limit 2, idempotency 3. Public Push key/contact stay config.
Remove demo password/pointer from the long-running file. Keep mode 0600 and leave `.deploy.env` alone.

Inspect names, duplicates, permissions, and application consumption without values. Never run
unsuppressed Compose config, inspect/printenv, diffsettings, or shell tracing on the old environment.
Confirm zero long-lived secret material in the converted `.env`. Only now deploy the reviewed
exact staging SHA with explicit merge/deploy authorization, `--ref staging`, and resolved full
`expected_staging_sha`. Workflow preflight checks active services, unsealed TLS health and files
before Django check/migrations; enabled-feature settings validation stays authoritative. Optional
disabled files may be empty but must exist/read correctly.

Web/worker/beat mount the directory read-only. PostgreSQL/Redis bind only their respective file;
proxy receives none. PostgreSQL uses official `POSTGRES_PASSWORD_FILE`; it does not change a role
password in an existing volume. Redis writes hex-escaped config on container tmpfs and uses a
transient `REDISCLI_AUTH` healthcheck, without persistent environment/password arguments. Agent
replaces files atomically: force-recreate database containers after single-file bind changes.

## Verification and acceptance

Require successful Actions plus matching public `/api/v1/meta` SHA and readiness. Verify web,
worker, Beat, PostgreSQL, Redis, and proxy status, Django check/migrations, existing database role
authentication, Redis PING, and cache/rate-limit/idempotency/broker/results separation. Inspect Docker
environment **names only** to confirm absence of secret values/credential URLs. Check SMTP delivery,
Turnstile sign-in, configured Daily behavior/webhook verification, PSGC lookup, and Push on an
existing browser where enabled. Disabled features remain disabled. Reopen an authorized existing
Routine Interview without editing/exporting it; prove old content decrypts. Verify an existing TOTP
factor safely: new enrollment alone cannot prove old factors readable. Prove an existing encrypted
Push subscription still works. Record pass/failure only, no confidential content.

After comparison/service checks remove private import copies. Keep the encrypted off-host recovery
copy for the bounded rollback window. Take a Vault snapshot and complete the restart drill. Final
operational acceptance requires zero live `.env` secrets, unchanged keys/ciphertext, verified
services, and a recorded restart drill; repository/local synthetic tests cannot prove those facts.

## Restart, seal, audit, and backup

Reboot removes `/run/compass-secrets`; Vault starts sealed, Agent cannot authenticate/render.
Docker may attempt restarts, but missing binds/required `_FILE` reads must fail with no fallback.
Verify sealed workflow preflight rejects startup. Custodians unseal through the laptop tunnel;
Agent authenticates/renders, preflight passes, then recreate the deployed services with
`docker compose up -d --force-recreate`. Recheck readiness, worker/Beat, database/Redis, and old
encrypted data. Never reset volumes or initialize again.

For a deliberate seal without reboot, stop applications and Agent **before** sealing; verify
systemd removed the runtime directory. Static files can remain while a running Agent retries an
outage, and existing processes retain memory credentials: seal is not application revocation.
New workflow deployments reject unavailable/sealed health even with files present. After unseal
start Agent, preflight, and force-recreate containers whose binds referenced removed/replaced inodes.
This phase provides no automatic application reload or credential rotation.

Keep `compass-file` auditing at `/var/log/vault/audit.json`, Vault-owned mode 0600. Preserve default
HMAC protection; never enable `log_raw`. Logs contain operational metadata and stay protected.
The logrotate asset rotates/creates and sends SIGHUP; test continued audit writing. Monitor free
disk/log growth: an unwritable sole audit device can block requests. Starting 14-day/50MB limits
need review against capacity/policy, not an invented institutional retention rule.

Use a scoped human snapshot token through laptop TLS, never an unattended privileged credential:

```bash
umask 077
vault operator raft snapshot save /operator-private/compass-vault.snap
vault operator raft snapshot inspect /operator-private/compass-vault.snap
# Encrypt, checksum ciphertext, and copy to independent protected off-host backup storage.
```

PostgreSQL backup != Vault backup. Vault backup != encryption-key escrow. Historic encryption keys
must remain independently recoverable for old database backup retention, even after active-key
retirement. Snapshots, original seal shares, certificate trust, and recovery knowledge stay off-host.
Rehearse restoration in isolation with the matching supported version. Stop apps/Agent; snapshot
current state where possible; use authorized `vault operator raft snapshot restore <snapshot>`.
It checks seal compatibility. `-force` is an exceptional restore from another initialized cluster,
requiring that snapshot's original unseal shares and an administrative recovery identity; do not
use it casually. After restore unseal as required, verify KV/policy/audit, replace bootstrap identity
if needed, render/compare, recreate apps, and prove old data readable before returning traffic.
Never overwrite the live cluster merely to test backups.

## Emergency rollback and demo-only delivery

Stop the candidate services if delivery fails. Restore the recorded **previous image and previous
plaintext-compatible manifest**, plus exact original runtime values/URLs from the operator's verified
secure backup to `.env` mode 0600; remove conflicting pointers for the temporary method. The new
file-only manifest cannot be rolled back simply by restoring plaintext. Recreate previous services
without deleting database/Redis volumes and verify readiness/decryption. Record the temporary
exception and arrange another deliberate cutover. Never commit secrets or add runtime fallback.
Delete old live plaintext copies after acceptance; expire rollback material under approved backup/
key-retention rules, preserving keys needed for old backups.

Normal startup does not require demo password/domain/onboarding email. Runtime policy/templates
exclude `demo/accounts`. Supply a separate ephemeral file mounted only for the one-off seeder,
using `DEMO_ACCOUNT_PASSWORD_FILE`. Email domain/onboarding mailbox remain configuration. No demo Vault workflow is
implemented here. Local Compose/Mailpit/MinIO/direct development values and test keys need no Vault.

Deferred: separate Vault host, per-process access minimization, HA/auto-unseal, rotation, dynamic
database credentials with lease/connection renewal, shared crypto/new domain encryption.

## Current primary references

- [CLI and package verification record](vault-live-cutover-validation.md)
- [Userpass API fields](https://developer.hashicorp.com/vault/api-docs/auth/userpass)
- [AppRole API fields](https://developer.hashicorp.com/vault/api-docs/auth/approle)
- [CLI write/file/stdin semantics](https://developer.hashicorp.com/vault/docs/commands/write)
- [Community installation](https://developer.hashicorp.com/vault/install)
- [Integrated Storage deployment](https://developer.hashicorp.com/vault/tutorials/day-one-raft/raft-deployment-guide)
- [Raft](https://developer.hashicorp.com/vault/docs/configuration/storage/raft)
- [TLS listener](https://developer.hashicorp.com/vault/docs/configuration/listener/tcp)
- [Agent AppRole](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/methods/approle)
- [AppRole](https://developer.hashicorp.com/vault/docs/auth/approle)
- [Agent templates](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/template)
- [Audit rotation](https://developer.hashicorp.com/vault/docs/audit/file)
- [PGP initialization](https://developer.hashicorp.com/vault/docs/commands/operator/init)
- [Login output controls](https://developer.hashicorp.com/vault/docs/commands/login)
- [Raft snapshot operations](https://developer.hashicorp.com/vault/docs/commands/operator/raft)
- [KV file import](https://developer.hashicorp.com/vault/docs/commands/kv/put)
