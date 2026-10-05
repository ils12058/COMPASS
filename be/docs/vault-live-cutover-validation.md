# Live-staging Vault cutover execution record

Execution date: 2026-10-05. Status: **stopped before provisioning because required administrator
access and recovery custody are not established**. No live cutover or recovery drill is claimed.

## Repository and corrective change

Fetched `origin/staging`: `27587181acb2f1e4a9122e251a2e6a930e3ea4e7`, still the supplied foundation
merge. There are no intervening commits affecting settings, deployment, Compose, or Vault assets.
Corrections are isolated on `codex/vault-live-cutover` in
`/Users/reynantlntno/.codex/worktrees/vault-live-cutover/COMPASS`. The primary checkout was not edited.

The runbook now uses `token_policies`, `token_ttl`, and `token_max_ttl` for Userpass creation,
requires policy/TTL readback before bootstrap-root revocation, records the current package candidate
and separate package-signing key, and resolves staging before execution/dispatch. No runtime,
frontend, contract, model, migration, dependency, or encryption implementation changed.

## Version and command verification

The [Community installation page](https://developer.hashicorp.com/vault/install) advertises
Vault 2.1.1. The [Noble/amd64 package index](https://apt.releases.hashicorp.com/dists/noble/main/binary-amd64/Packages.gz)
lists Community package `2.1.1-1`. This is availability evidence only: no package was installed on
the Droplet, and host APT signature verification remains a prerequisite to installation.
The [official signing guidance](https://www.hashicorp.com/en/trust/security) publishes package-key
fingerprint `D55C 0D1A C78A 8D81 26CB 631C FC9C A96A CA02 6560`, distinct from the binary-release key.

The runbook's Vault command families were checked against current official documentation and
the 2.1.1 CLI. The table records supported syntax, not completed live operations.

| Command family | Verification/reference |
| --- | --- |
| `server -config`, `agent -config` | 2.1.1 CLI help; [server](https://developer.hashicorp.com/vault/docs/commands/server), [Agent](https://developer.hashicorp.com/vault/docs/commands/agent). |
| `version`, `status` | Disposable server identifies itself as 2.1.1; sealed status returns 2 and unsealed status returns 0. [Status](https://developer.hashicorp.com/vault/docs/commands/status). |
| `operator init` | CLI recognizes shares/threshold, PGP recipients, root-token recipient, and JSON format. [Initialization](https://developer.hashicorp.com/vault/docs/commands/operator/init). 5-share/3-threshold live custody was not exercised. |
| `operator unseal` | Hidden interactive input remains the live procedure; never place shares in arguments. [Unseal](https://developer.hashicorp.com/vault/docs/commands/operator/unseal). |
| `secrets enable -path=kv -version=2 kv` | Executed against the disposable 2.1.1 server. [Enable secrets](https://developer.hashicorp.com/vault/docs/commands/secrets/enable). |
| `audit enable -path=compass-file file ... mode=0600` | Executed; audit file mode 0600 verified. [Audit enable](https://developer.hashicorp.com/vault/docs/commands/audit/enable), [file device](https://developer.hashicorp.com/vault/docs/audit/file). |
| `policy write`, `auth enable` | Operator policy and Userpass auth installed in the disposable server. [Policy](https://developer.hashicorp.com/vault/docs/commands/policy/write), [auth](https://developer.hashicorp.com/vault/docs/commands/auth/enable). |
| AppRole role write / Role ID read / Secret ID generation | [AppRole API](https://developer.hashicorp.com/vault/api-docs/auth/approle) confirms binding, finite Secret ID TTL/uses, service-token period, policies, and CIDRs; CLI recognizes field/force output controls. Earlier foundation smoke is separately recorded in the foundation report. |
| Userpass write / read / login | Corrected token fields and protected file-password syntax executed; readback verified 3600/28800-second TTLs and operator policy. `login -no-print` verified silent. [Userpass](https://developer.hashicorp.com/vault/api-docs/auth/userpass), [login](https://developer.hashicorp.com/vault/docs/commands/login). |
| `read -field`, `write -field/-f`, `password=@file` | CLI help and [write/file/stdin](https://developer.hashicorp.com/vault/docs/commands/write), [read](https://developer.hashicorp.com/vault/docs/commands/read). |
| `token revoke -self` | Disposable bootstrap root revoked; root lookup then denied; human token remained usable. [Revoke](https://developer.hashicorp.com/vault/docs/commands/token/revoke). |
| `kv put -mount=kv logical/path @record.json` | JSON file import succeeded using the bounded human identity after root revocation. [KV import](https://developer.hashicorp.com/vault/docs/commands/kv/put). |
| `operator raft snapshot save/inspect/restore` | Bounded human snapshot save/inspect succeeded in the disposable server; restore's `-force` option checked in CLI help only. No live snapshot restore performed. [Raft commands](https://developer.hashicorp.com/vault/docs/commands/operator/raft). |

The exact [2.1.1 Userpass source](https://github.com/hashicorp/vault/blob/v2.1.1/builtin/credential/userpass/path_users.go)
registers token fields. The exact [PGP file parser](https://github.com/hashicorp/vault/blob/v2.1.1/helper/pgpkeys/flag.go)
accepts a single armored public key per file as well as binary/base64 public material, so the runbook's
`.asc` filenames are supported. Supplied custodian fingerprints and key usability still need verification.

The smoke used synthetic credentials and a disposable TLS/Raft container, not dev mode. It did
not use live secrets, host systemd, five real custodians, a production restore, or a live restart.
Its container and temporary fixtures were removed. Script and output are operator-local evidence
under `/Users/reynantlntno/.codex/artifacts/vault-live-cutover/`.

## Current host and access evidence

`doctl` inventory and pinned SSH confirmed Droplet `602091909`, `compass-staging-api-01`, active
in Singapore. Guest OS is Ubuntu 24.04.4 LTS (Noble), x86_64. Its 2-vCPU/4-GB/80-GB plan currently
has 2.3 GiB available RAM, 25 GiB free root disk, and no swap. Vault executable/package is absent;
both Vault systemd services report `LoadState=not-found`, inactive/dead. GID 1900 and the proposed
Vault/Agent users were not present during inspection.

All six COMPASS containers are running. Web, proxy, PostgreSQL, and Redis report healthy; worker
and Beat report running. Web/worker/Beat use the existing image tagged
`3fd847adeabcf644f3cf297a001f0e9f51982fda`. Public metadata matches that build and readiness reports
application, database, and canonical services OK. This existing deployment is not the Vault merge.

Both pinned native SSH and `doctl compute ssh` reach the deployment user `compass`, UID 1000,
with Docker group membership. `sudo -n true` fails because a password is required. Root login with
the tested `bootstrap_ed25519` and `ci_ed25519` keys is refused (`Permission denied (publickey)`). No privileged container,
host-root mount, root-key injection, sudoers change, or root-password reset was used to substitute
for an approved administrator session. The inspected [doctl SSH implementation](https://github.com/digitalocean/doctl/blob/v1.168.0/pkg/ssh/ssh.go)
executes SSH; it does not confer root privileges. [Account SSH-key management](https://docs.digitalocean.com/reference/doctl/reference/compute/ssh-key/)
does not add a key to an existing guest. The opened DigitalOcean access page requires dashboard login.

The current client `/32` was temporarily allowed on TCP 22 for bounded inspection and doctl probes.
After both sessions the original inbound/outbound rules, attached Droplet, and tags were restored;
the final verification showed no pending changes. The original SSH source remains
`136.158.101.248/32`; only HTTP/HTTPS have public inbound rules. No public Vault port was added.

`/opt/compass/.env` remains 0600, `compass:compass`. Neither its contents nor live secret values were
read, exported, printed, or changed. `/opt/compass/.deploy.env` was not changed.
Only backup metadata was inspected: `/opt/compass/backups` contains a protected historical
`retention-policy-before-0004-d6e3cf68.dump` dated 2026-10-03 (4152 bytes). That file is not evidence
of a complete/current PostgreSQL backup or a restore check. No fresh database backup or encrypted
configuration/key-escrow copy was created because the operator's recovery recipient/location and
custodian public keys have not been supplied.

## Validation and live acceptance

- Fresh focused backend tests: **49 passed in 0.16s** for common config, Redis config, and
  runtime-secret migration/preflight. Only documentation changed in the repository.
- Exact-version Userpass smoke passed, including bounded human access after root revocation,
  KV JSON-file import, snapshot save/inspect, and audit mode. CLI option checks passed for all
  runbook command families with nontrivial flags.
- Whole-backend Ruff format/check passed (508 files); Django system check reported zero issues;
  migration dry-run reported no changes with the task's local PostgreSQL fixture on port 5436.
  An initial dry-run without that fixture warned that migration history could not be checked;
  the connected rerun passed without that warning. The task-owned fixture was stopped again.
- Foundation [backend CI](https://github.com/ils12058/COMPASS/actions/runs/37264475876) completed
  with **17 failed, 1599 passed, 17 setup errors** (8 warnings) on head
  `5436fbc1fabbed46fb05e00746886109c10bbf02`. No failures were reported in common config, Redis
  config, or runtime-secret migration/preflight. The additional authentication assertion expects
  a user projection without `exit_interview_workspace_available`; that field and the old assertion
  both already exist in pre-Vault staging `3f951cfd`, and the Vault merge changes neither file.
  The independently verified inherited lock defect and other appointment/scheduling/demo/contract
  failures are recorded in the foundation report. The full suite is not green; this slice does
  not modify unrelated tests or claim every failure has been reproduced against a clean base.

| Required final-report item | Live result |
| --- | --- |
| Staging SHA | `27587181acb2f1e4a9122e251a2e6a930e3ea4e7` fetched and unchanged at execution start. Re-resolve before dispatch. |
| Corrective change | Documentation correction on `codex/vault-live-cutover`; see its corrective PR. |
| Installed Vault version | None. Available candidate: Community 2.1.1 / APT `2.1.1-1`. |
| Droplet OS | Ubuntu 24.04.4 LTS, Noble, x86_64. |
| Vault service | Not found; not provisioned. |
| Agent service | Not found; not provisioned. |
| Vault TLS | Not provisioned; fingerprint, expiry and renewal acceptance pending. |
| Raft | Not provisioned. |
| Audit | Not provisioned; rotation/reopen acceptance pending. |
| KV paths | None provisioned; reviewed eleven-domain inventory unchanged. |
| AppRole | Not provisioned; reviewed scoped 1h-period service token, 720h Secret ID, loopback bindings unchanged. Expiry/accessor/replacement record pending. |
| Rendered files | None; fifteen-file 0440/GID 1900 live acceptance pending. |
| Live equality | Not performed; no live values exported/imported. |
| `.env` secret removal | Not performed; original environment preserved for the running application. |
| Redis | Existing container healthy; file-only authentication/metadata/DB routing acceptance pending. |
| PostgreSQL | Existing container healthy; unchanged-password file-only authentication acceptance pending. |
| Web/worker/Beat/proxy | Existing web/proxy healthy and worker/Beat running; no new deployment started. |
| Old Routine Interview ciphertext | Not opened/decrypted for this cutover. |
| Existing TOTP | Not tested for this cutover. |
| Existing Web Push encrypted data | Not tested for this cutover. |
| SMTP/Turnstile/Daily/PSGC/S3 | Cutover acceptance not performed; providers were not enabled/disabled or contacted for this check. |
| Public build ID | Existing live build `3fd847adeabcf644f3cf297a001f0e9f51982fda`; readiness OK. |
| Snapshot | No live snapshot or encrypted off-host copy; only synthetic snapshot validation. |
| Restart/seal/unseal/reboot | No live drill or Droplet reboot. |
| Rollback readiness | Existing deployment preserved; exact previous manifest/image, verified full DB backup, original env recovery and independent key escrow must be captured before installation/cutover. |
| Remaining limitations | Single node/no HA; manual Shamir unseal; same-host root boundary; finite Agent Secret ID lifecycle; secrets in app memory; eager shared app secret set; no dynamic DB credentials or automatic rotation. |

Resume only after an approved administrator session, the five custodian plus bootstrap-operator
public keys, encrypted off-host recovery destination/recipient, and a usable custodian unseal
procedure are established. Then take and verify the required backups before installing Vault.
Initialization, equality, environment conversion, exact-SHA deployment, service/encrypted-data
acceptance, snapshot escrow, restart/seal/unseal drill, and plaintext cleanup all remain required.

No live secret value was printed or committed. No existing credential was rotated. No encryption
key was replaced. No Routine Interview ciphertext was changed. No shared crypto extraction was
performed. No new encrypted domain was introduced. No dynamic database credential engine was enabled.
