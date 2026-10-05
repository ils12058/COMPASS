# ADR-075: Vault Community runtime secret delivery

## Context

ADR-007 establishes one environment-driven settings module and a mutually exclusive `NAME` /
`NAME_FILE` boundary. Live staging currently duplicates long-lived credentials in the protected
host `.env`, container environments, and Redis/Celery URLs. Encryption expansion needs a durable
secret-management boundary before any new encryption or rotation work.

## Decision

Use self-hosted HashiCorp Vault Community as independent host infrastructure on the existing
DigitalOcean Droplet. A dedicated `vault.service` uses single-node Integrated Storage/Raft under
`/var/lib/vault`, TLS verified by a deliberately trusted local certificate, and loopback listeners
on 8200/8201. There is no Caddy route or public firewall opening. This is a staging cost/capacity
choice, not high availability.

Use KV v2 at `kv/compass/live-staging/`, split by domain. The runtime policy grants explicit data
reads and self-token lookup/renewal only. A separate privileged human policy handles migration,
AppRole bootstrap renewal, and manual snapshots. `demo/accounts` is excluded from the runtime
policy and renderer; one-off seeding retains its own operator-only delivery.

A dedicated `vault-agent.service` authenticates through a scoped AppRole with a renewable service
token, no token sink/proxy, and protected bootstrap files. Its Secret ID has a finite lifetime and
must be replaced by an operator before expiry. No application container receives a Vault token.
Root tokens are bootstrap-only and revoked after a human operator login is proven. Shamir shares
remain with off-host custodians. No same-host automatic unseal is implemented.

Agent renders fifteen individual files atomically into ephemeral `/run/compass-secrets`, with
mode 0440 and a shared numeric GID 1900. The directory is removed on Agent stop and reboot.
Web/worker/beat mount the directory read-only with that supplementary group because settings
load eagerly. PostgreSQL and Redis mount only their own credential. Proxy mounts no secrets.
The staging manifest forces `RUNTIME_SECRETS_MODE=files`; settings reject direct secret values,
incorrect pointers, and Redis/Celery URL overrides. Missing files fail through ADR-007 helpers.
Enabled integration validation remains unchanged. There is no application Vault SDK or API call.

Redis URLs are constructed in settings from host/port and the file-backed password, percent-encoded
with DB 0 for broker, 1 for cache/results, 2 for rate limiting, and 3 for idempotency. Explicit URL
overrides remain available outside files mode for local/CI and the pre-cutover deployment.
PostgreSQL uses its official `POSTGRES_PASSWORD_FILE` entrypoint mechanism, without changing the
existing database role/password. Redis builds its escaped configuration on container tmpfs and
uses file-backed healthcheck authentication, without a persistent environment password or password
argument. Local Compose and synthetic test settings continue to run without Vault.

Ordinary hostnames, ports, flags, limits, SMTP/S3 configuration, Web Push public key/contact, and
frontend public configuration stay outside Vault. GitHub deployment/SSH bootstrap secrets stay
in Actions Secrets. Demo credentials are absent from the long-running runtime environment.

The deploy workflow checks host services, unsealed TLS health, and required files before Django
checks/migrations. Following reboot, Vault starts sealed; custodians unseal, Agent authenticates,
files render, and an operator deploys/recreates application containers. Existing application
processes retain secrets in memory during an outage; Vault is not a revocation switch for running
processes. Static files can also remain while a running Agent retries a temporary outage. New
deployments fail the unsealed health check; deliberate sealing stops applications and Agent first.

## Scope and consequences

The initial cutover preserves every credential byte, keyring order, VAPID pair, encryption key,
and ciphertext. It changes storage/delivery only. No model/API/frontend or crypto behavior changes.
Operators need a maintenance window, secure recovery copy, equality checks, and a restart drill.
The file audit device remains enabled with secure host logging, rotation/SIGHUP, and capacity
monitoring. Manual Raft snapshots are encrypted and moved off-host. PostgreSQL backup is not Vault
backup; Vault backup is not independent encryption-key escrow for old database backups.

The design improves secret sprawl, `.env`/Docker metadata exposure, version management, policies,
and operator visibility. It does not defend against Droplet root compromise: root controls Vault,
Docker, databases, Agent credentials, and runtime files. PostgreSQL's entrypoint briefly exports its
file value during bootstrap; Redis healthchecks use a transient `REDISCLI_AUTH`. Process-memory/root
access is outside this boundary. This is not a claim that runtime plaintext never exists.

Agent replacement and atomic file updates require application restarts and forced container
recreation for single-file database bind mounts. Rotation, per-process minimization, and availability
automation require separate design. A future separate Vault host changes Agent connection/trust/auth
configuration, not Django. Dynamic database credentials need lease-aware Django/Gunicorn/Celery
connection design first. Shared crypto extraction, new domain encryption, key rotation, multi-node
HA, cloud KMS/HSM/Enterprise, and a dedicated Vault Droplet are deferred.

See [live-staging operator runbook](../vault-live-staging.md) for installation, TLS, bootstrap,
cutover, verification, rollback, reboot, auditing, snapshots, and remaining operational acceptance.
