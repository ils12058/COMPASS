# Realtime transport: deployment and operation (ADR-100)

Realtime is dark by default and optional. Merging or deploying this code changes nothing until an
operator enables all three parts below. COMPASS works normally with realtime off or down.

## Parts

| Part | Where | Off by default because |
| --- | --- | --- |
| Ticket endpoint and revocation hook | Django `web` (and `worker`/`beat` settings) | `REALTIME_ENABLED=false` |
| Realtime service (`uvicorn realtime_service.app:app`, port 8001) | Compose service `realtime` | It is in the `realtime` profile |
| Portal runtime | Vercel frontend build | `NEXT_PUBLIC_REALTIME_ENABLED` unset |

Caddy always routes `/api/realtime/*` to `realtime:8001`. While the service is not running that
route answers 502, and nothing calls it. `/api/v1/realtime/tickets` is a Django route and always
goes to `web`.

## Operator prerequisites (not verifiable from the repository)

Confirm each item on the live environment before enabling. None of them was verified by the
implementation work.

1. **Cloudflare WebSockets** are enabled for the API hostname's zone
   (`staging-api.compass-gco.com`), and no WAF, cache, or page rule interferes with
   `/api/realtime/*` upgrades or long-lived connections.
2. **Exact frontend Origin(s)** for `REALTIME_ALLOWED_ORIGINS`, for example
   `https://staging.compass-gco.com`. Use the exact browser origin: lowercase, no path or trailing
   slash, no default port, no wildcards. Add a production origin separately when it exists.
3. **Public socket URL** for Vercel: `wss://staging-api.compass-gco.com/api/realtime/v1/socket`.
4. **Redis database 4** is unused on the live Redis (DB 0 broker, 1 cache/results, 2 rate limit,
   3 idempotency) and no other software uses `compass:realtime:*` keys or channels.
5. **Memory headroom** on the Droplet for one more Python process (the realtime service idles at
   tens of MB, plus one Redis connection per open socket) and Redis client capacity for up to
   `REALTIME_MAX_CONNECTIONS` (default 1000) subscriber connections.
6. The deploy workflow's `pull` step lists services explicitly; `realtime` reuses the `web` image,
   which is already pulled.

## Enable (live-staging)

1. Add to the host `.env` (ordinary configuration; no new secret file):

   ```sh
   REALTIME_ENABLED=true
   REALTIME_ALLOWED_ORIGINS=https://staging.compass-gco.com
   COMPOSE_PROFILES=realtime
   ```

   The realtime container receives only `APP_ENV`, `REDIS_HOST`, `REDIS_PORT`,
   `REDIS_PASSWORD_FILE` (the existing `redis_password` grant), `REDIS_SOCKET_TIMEOUT`, and the
   `REALTIME_*` values. It never receives the `.env` file, database credentials, `SECRET_KEY`, or
   content keyrings.
2. Deploy the exact staging revision through the normal workflow. `up -d` starts `realtime` when
   the profile is active.
3. Verify:
   - `curl -fsS https://staging-api.compass-gco.com/api/realtime/v1/health/live` returns
     `{"status":"ok"}`, and `/ready` returns `{"status":"ok"}` (Redis reachable).
   - `docker compose -f compose.staging.yaml ps realtime` reports healthy.
   - `docker compose -f compose.staging.yaml logs realtime` shows `realtime_started` with the
     expected `allowed_origin_count`, and no configuration errors.
4. In Vercel, set `NEXT_PUBLIC_REALTIME_ENABLED=true` and `NEXT_PUBLIC_REALTIME_URL` to the socket
   URL, then redeploy the frontend (the values are build-time).
5. Sign in, open the portal, and confirm in the browser's network panel: one
   `POST /api/v1/realtime/tickets` (200), one socket to the API host (101) whose first client
   frame is the `authenticate` frame, a `ready` frame, and no ticket in any URL.

## Observe

The service logs JSON lines on stdout with only closed codes and counts: `realtime_started`,
`socket_rejected` (`reason`: `origin_missing`, `origin_rejected`, `origin_malformed`,
`path_unknown`, `query_string_present`), `ticket_rejected` (`ticket_unknown`, `ticket_expired`,
`ticket_invalid`, `ticket_malformed`, `session_revoked`), `socket_authenticated`,
`session_revoked_close`, `redis_unavailable` (`error_type`), `event_dropped`, and `socket_closed`
(`reason`, `close_code`, `duration_seconds`, `active_connections`). Tickets, frames, Origins,
client addresses, and user or session IDs are never logged. Uvicorn runs at warning level without
access logs. Django logs `realtime_ticket_unavailable`, `realtime_publish_failed`, and
`realtime_revocation_publish_failed`.

## Disable or roll back

1. Unset `NEXT_PUBLIC_REALTIME_ENABLED` in Vercel and redeploy the frontend (clients stop
   connecting).
2. Stop the service: `docker compose -f compose.staging.yaml stop realtime`, and remove
   `COMPOSE_PROFILES=realtime` so the next deploy does not start it.
3. Then set `REALTIME_ENABLED=false` and recreate `web`, `worker`, and `beat`.

Stop the service before step 3: once Django is disabled it no longer publishes revocations, so a
still-running service would keep a revoked session's socket open until its lifetime ends.

## Restarts

Every deploy or restart of `realtime` closes open sockets with 1012; browsers reconnect with a new
ticket and backoff. Ordinary HTTP keeps working throughout, and `web` readiness does not depend on
the realtime service or realtime Redis.
