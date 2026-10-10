# ADR-043: Platform Operations Diagnostics Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: read-only platform health, resolved-configuration diagnostics, operator CLI diagnostics, and curated command guidance

## Context

COMPASS already has public process liveness and PostgreSQL-backed readiness endpoints used by
Docker and Caddy. It also has Redis-backed cache/rate-limit/idempotency/Celery infrastructure,
S3-compatible object storage, SMTP delivery, Daily.co, Turnstile, one harmless Celery diagnostic
task, and a real notification-email recovery Beat schedule.

Those boundaries are not equivalent to one another. In particular:

- a reachable Redis broker does not prove that a Celery worker executed a task;
- a configured Beat schedule does not prove that Beat is currently running;
- an SMTP or external-provider outage should not remove an otherwise usable web process from
  Docker/Caddy service;
- Django settings already fail fast during import, so an HTTP or management-command diagnostic
  cannot explain configuration that prevents Django from starting at all.

Operators need safe observability without creating a browser control plane.

## Decision

Introduce a small `compass.platform_ops` Django app with no database models.

This slice follows **observe + diagnose + explain**. It does not add runtime mutation controls,
automatic repair, a generic monitoring framework, or arbitrary command execution.

## Public health contracts remain unchanged

`GET /api/v1/health/live` remains process-only.

`GET /api/v1/health/ready` remains application + PostgreSQL readiness using `SELECT 1`.

Public readiness does not depend on SMTP, object storage, Redis, Celery worker, Celery Beat,
Daily.co, Turnstile, or Notification delivery state. Docker and Caddy therefore retain their
existing infrastructure semantics.

## Authorization

Add canonical capability:

- `platform_operations.view`

Only the IT_ADMIN baseline Role receives it.

Counselor, Guidance Services Staff, Student, Institutional Officer, DPO, and Head Guidance do not
receive it from their baseline Role or Designation.

Routes use the existing effective capability resolver rather than checking role names. Existing
explicit capability overrides therefore remain authoritative.

No `platform_operations.manage` capability is introduced.

## Authenticated Platform Health

Add:

- `GET /api/v1/platform/health`

The response uses a deliberately small status vocabulary:

- `HEALTHY`
- `DEGRADED`
- `UNAVAILABLE`
- `DISABLED`
- `NOT_CHECKED`

The shared diagnostic engine performs isolated, sanitized passive checks for:

- PostgreSQL using the existing `SELECT 1` readiness semantics;
- Redis cache via bounded `PING`;
- Redis rate limiter via bounded `PING`;
- Redis idempotency via bounded `PING`;
- Celery broker Redis connectivity via bounded `PING`;
- object storage through the existing read-only existence boundary against a fixed reserved key;
- SMTP by opening and closing the configured transport without sending a message.

Object-storage `False` for the reserved nonexistent key is a successful connectivity response.
No diagnostic uploads, deletes, lists confidential objects, or generates user URLs.

SMTP diagnostics send zero email.

Probe failures return sanitized summaries and log only stable check identifiers, status, and
exception class. Raw exception strings, URLs, credentials, hosts, bucket names, and provider
payloads are not returned.

One probe failure does not stop later probes.

## Celery worker and Beat truthfulness

Passive HTTP health does not claim worker liveness.

The Celery worker component is `NOT_CHECKED` with guidance to run the explicit worker smoke check.

Celery Beat is also `NOT_CHECKED`. Presence of
`notification-email-recovery` in `CELERY_BEAT_SCHEDULE` is configuration posture only, not a
runtime heartbeat.

No worker or Beat heartbeat model/table is added.

## External SaaS providers

Daily.co and Cloudflare Turnstile are not contacted by normal Platform Health.

If disabled, each reports `DISABLED`.

If enabled/configured, each reports `NOT_CHECKED` because this slice does not create outbound
provider traffic solely to manufacture a green dashboard indicator.

## Overall health

Required passive dependencies are PostgreSQL, the three Redis concerns, the Celery broker, object
storage, and SMTP.

If one or more required checked dependencies are unavailable, overall status is `DEGRADED`.

Optional disabled/not-checked provider/runtime checks do not by themselves make required passive
dependencies unhealthy. The overall summary explicitly states when some runtime/provider checks
were intentionally not performed.

## Resolved environment diagnostics

Add:

- `GET /api/v1/platform/environment`

The endpoint reads resolved Django settings only. It does not reread arbitrary environment
variables and does not implement a second .env parser.

The safe projection covers:

- application environment mode, debug posture, and API docs posture;
- database configured/not-configured state;
- Redis cache/rate-limit/idempotency and Celery broker configured state;
- object-storage configured state, addressing mode, and TLS-verification posture;
- SMTP configured state, TLS/SSL/plain transport mode, and authentication configured state;
- authentication-cookie security, SameSite mode, TOTP encryption configured state, and Turnstile
  enabled/configured state;
- Daily enabled/credentials-configured state;
- Notification email retry-policy and recovery-schedule configured state.

It never returns secret values, secret prefixes, secret lengths, raw Redis URLs, database
credentials, S3 bucket/endpoint/credentials, SMTP host/user/password, Daily secrets, Turnstile
secret, TOTP key, cookies, tokens, or OTP material.

This diagnostic surface exists only after Django settings import succeeds. If configuration prevents
settings from loading, startup/deployment logs remain the source of the fail-fast error. Neither the
HTTP endpoint nor `compass_doctor` can diagnose a Django process that could not import settings.

## Shared diagnostics and compass_doctor

Add:

- `python manage.py compass_doctor`
- `python manage.py compass_doctor --configuration-only`
- `python manage.py compass_doctor --worker-smoke`

Default behavior prints safe resolved-configuration posture followed by the same passive runtime
diagnostics used by HTTP health.

`--configuration-only` skips runtime network probes.

`--worker-smoke` is explicit operator intent. It enqueues the existing
`compass.infrastructure.noop` task and waits for its result with a small bounded timeout. A
successful result proves broker/worker/result-path execution at that moment only; it is not a
persistent heartbeat.

Worker smoke accepts a bounded timeout with a default of five seconds and a hard maximum of ten
seconds.

The doctor raises a command error/non-zero result when required passive diagnostics fail or an
explicit worker smoke fails.

The command creates no domain or audit records and prints no raw secrets or connection strings.

## Command Catalog

Add:

- `GET /api/v1/platform/commands`

The catalog is static, deliberate, and source-controlled. Browser execution is explicitly
unsupported.

Initial entries cover:

- `create_it_admin`
- `sync_identity_policy`
- `python manage.py migrate --noinput`
- `python manage.py check --deploy`
- `python manage.py export_openapi --check`
- `python manage.py compass_doctor`
- `python manage.py compass_doctor --configuration-only`
- `python manage.py compass_doctor --worker-smoke`

Mutating deployment/bootstrap commands are clearly marked. Examples use placeholders rather than
real credentials.

The catalog does not dynamically enumerate installed Django commands and deliberately excludes
shell, dbshell, arbitrary SQL, flush/destructive operations, secret printing, Redis manipulation,
Celery purge, backup/restore, and arbitrary command templates.

There is no HTTP command-run endpoint, subprocess wrapper, shell executor, or allowlist executor.

## Deferred work

This slice deliberately defers:

- Maintenance Mode and downtime controls;
- Notification/Email delivery administration and queue metrics;
- manual retry/retry-all/cancellation;
- operational admin history/runtime mutation feed;
- `platform_operations.manage`;
- worker/Beat persistent heartbeat infrastructure;
- backup/snapshot/restore functionality.

Backup, point-in-time recovery, snapshots, and disaster recovery remain deployment/infrastructure
responsibilities.

## Consequences

Platform diagnostics are useful without changing the public web readiness contract or turning
COMPASS into an infrastructure control plane.

Some runtime state remains intentionally unknowable from passive HTTP diagnostics. COMPASS reports
that limitation instead of fabricating green status.
