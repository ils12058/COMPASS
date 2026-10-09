# ADR-100: Realtime transport foundation

## Status

Accepted. Phase 1: transport, authentication, and runtime only. It refines the WebSocket remark in
[ADR-071](ADR-071-pwa-notification-freshness-and-web-push.md) ("WebSocket would require an ASGI
deployment"), which is now satisfied by a separate tier. No Notification, Guidance Messages, or
other domain behavior uses it yet, and Notification polling is unchanged.

## Context

The HTTP application is Django on Gunicorn with two synchronous WSGI workers. A long-lived
connection held by a WSGI worker would starve ordinary requests, so streaming needs a separate
process. The frontend (Vercel) and API (behind Cloudflare and Caddy) are different origins. The
browser reaches the API through the Next `/api/v1` rewrite, so the HttpOnly session cookie is
host-only on the frontend host: a socket opened directly to the API host cannot rely on it.
WebSocket upgrades through Vercel's external rewrites are not a documented path, so the socket
goes to the API host directly. Django Channels would move the whole backend to ASGI, which this
slice deliberately avoids.

## Decision

### Topology

- Django HTTP stays on Gunicorn/WSGI. `config/asgi.py` is unused and unchanged.
- A separate **Django-free ASGI application**, `be/realtime_service/`, runs under Uvicorn
  (`websockets-sansio` protocol). It reuses the backend image but is its own Compose service and
  process. It has no web framework: one WebSocket route and two health routes.
- Redis carries the realtime state: Pub/Sub for hints and controls, and dedicated database 4 for
  ticket digests and revoked-session markers. Pub/Sub channels are server-wide, so every key and
  channel uses the `compass:realtime:` prefix.
- PostgreSQL stays the only source of truth. HTTP stays authoritative for every read and write.
- The service imports only the standard library, `redis`, and the Django-free helpers
  `compass.common.config` and `compass.common.redis_config`. It does not import Django or any
  model, does not connect to PostgreSQL, and receives no database credentials, `SECRET_KEY`, or
  content keyring. Its container gets only Redis settings, the `redis_password` file, and the
  allowed Origins. A test starts it in exactly that environment.

### Authentication: one-time tickets

1. The portal calls `POST /api/v1/realtime/tickets`, an ordinary Django route with the session
   cookie and CSRF. It accepts no identity input: the user and AuthSession come from the request.
2. Django returns `secrets.token_urlsafe(32)` (256 bits) once, with `Cache-Control: no-store`.
   Redis stores only `SHA-256(ticket)` with `SET NX EX 30` and the minimum metadata:
   `{v, user_id, session_id, expires_at}`.
3. The browser opens `wss://<api-host>/api/realtime/v1/socket`. The service accepts the upgrade
   only for an exactly allowlisted `Origin`, and only with no query string. A missing,
   duplicated, malformed, or unlisted Origin gets HTTP 403 before any Redis work.
4. Within 5 seconds the client sends its one frame, `{"type":"authenticate","ticket":"…"}`.
   Tickets never appear in URLs, so they never reach access logs or history.
5. The service consumes the ticket with `GETDEL`, which is atomic: one ticket authenticates at
   most one socket, even under concurrent presentation. It then checks the revoked-session marker,
   subscribes to `compass:realtime:user:<user>` and `compass:realtime:session:<session>`, waits
   for Redis to confirm both, checks the marker again, and sends `{"v":1,"type":"ready"}`.

Cookies play no part in socket authentication. The ticket response also names the ticket's
`user_id`, so a tab never connects one account's runtime with another account's session.

### Server-to-client hints only

After `ready` the socket is not an API. Clients cannot choose channels; any client frame closes
the socket (1008). Mutations stay on HTTP. A hint only says that something may have changed, and
the browser re-reads canonical data over HTTP. Public events are a closed registry in
`realtime_service.protocol.PUBLIC_EVENT_FIELDS` (empty in Phase 1). A hint carries a version, a
type, and only canonical UUID fields; the service re-validates every Redis message against the
registry before forwarding it. Names, email addresses, Notification titles or bodies, message
text, counseling or referral content, Inventory or Exit Interview answers, and Good Moral content
never travel. `compass.realtime.publish` validates events, publishes after commit with a short
timeout, and logs and drops Redis failures. There is no outbox: lost hints are healed by polling
and by consumers reconciling on each new `ready` generation.

### Lifetime and close codes

Sockets close at about 15 minutes (minus up to 60 s of jitter) with 4000, so authentication is
re-established through the session-checked HTTP endpoint. Uvicorn sends WebSocket pings every
20 s. Codes: 1008 policy violation, 1012 server restart, 1013 Redis unavailable or capacity,
4000 reconnect, 4401 ticket rejected, 4403 session revoked, 4408 authentication timeout.

### Session revocation

Every AuthSession revocation (logout, single or other-session revocation, administrator
revocation, password and email changes, authority changes, account disablement) passes through
`_revoke_auth_session_locked`. After the revocation commits, it writes the session's revoked
marker (1 hour, longer than any ticket) and publishes an internal control on that session's
channel in one Redis transaction. The socket for that session closes with 4403; other sessions
of the same user are unaffected. Tickets minted before the revocation fail at consumption. The
database revocation is authoritative even when Redis is down.

### Redis failure

Realtime is optional. A Redis failure returns `503 realtime_unavailable` from the ticket endpoint
and never fails other HTTP requests or session revocation. An established socket whose
subscription errors or stops answering pings closes with 1013. The subscription client disables
redis-py retries, so a lost subscription can never silently resubscribe and miss a revocation.
Realtime health (`/api/realtime/v1/health/live` and `/ready`) is separate from web readiness.

### Frontend runtime

One `RealtimeProvider` in `PortalBoundary` owns the tab's only socket and connects only for the
confirmed account. An account change, a session being checked again, sign-out, or unmount closes
the socket before anything starts for the next account. Each visible tab has its own socket; a
tab hidden for 30 s closes it and reconnects with a fresh ticket when shown. Offline stops
attempts; online retries at once. Failures back off exponentially with jitter (1 s base, 60 s
cap) and reset after 60 s of live connection or a 4000 close. Features use `useRealtimeStatus`
(`disabled`, `idle`, `connecting`, `live`, `reconnecting`, `offline`, plus a `generation` that
increases on each `ready`) and `useRealtimeEvent`; they never construct a WebSocket. The provider
fetches no feature data.

### Dark launch

Off by default everywhere: `REALTIME_ENABLED=false` (Django issues no tickets and never contacts
realtime Redis), the `realtime` Compose profile (the service does not run), and
`NEXT_PUBLIC_REALTIME_ENABLED` unset (no ticket request, no socket). No feature depends on it.

## Consequences

- One Redis subscriber connection per authenticated socket, bounded by
  `REALTIME_MAX_CONNECTIONS` (1000). A shared, multiplexed subscriber is a later optimization if
  connection counts warrant it.
- If Redis is reachable from the realtime service but not from Django at the moment of a
  revocation, that session's socket can survive until its lifetime ends (at most 15 minutes) and
  receives only content-free hints. Its tickets cannot be renewed, because the HTTP session is
  already revoked.
- Disabling realtime safely means stopping the realtime service before setting
  `REALTIME_ENABLED=false`, because Django stops publishing revocations once it is disabled.
- A deploy restarts the service and closes every socket (1012); clients reconnect with backoff.
  There is no socket migration.
- Not included: Notification hints, Guidance Messages, presence, typing, read receipts,
  cross-tab socket sharing, client subscriptions, an event bus, or an outbox.


Phase 3 refinement (ADR-102): the closed registry additionally permits
`messages.thread_changed` with exactly one UUID `thread_id`; Messages-domain authorization selects
commit-time recipients and private read-state hints go only to the same user. Realtime never
receives Message content or its encryption key.
