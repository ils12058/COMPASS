"""Minimal ASGI application for COMPASS realtime hints (ADR-100). Run with Uvicorn.

One WebSocket route and two health routes, without a web framework:

1. The exact Origin must be allowlisted, and the socket path carries no query string.
2. The client sends one ``authenticate`` frame with a one-time ticket within the auth timeout.
3. The ticket is consumed atomically from Redis; the socket subscribes only to its own user and
   session channels, which the server derives from the ticket.
4. The server sends ``{"v":1,"type":"ready"}``. After that the socket only receives hints; any
   client frame is a policy violation. The socket closes at its bounded lifetime, on session
   revocation, or with 1013 when Redis is lost.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import secrets
from contextlib import suppress
from typing import Any

from realtime_service import log, protocol, store
from realtime_service.config import RealtimeConfig, load_config

Scope = dict[str, Any]
Message = dict[str, Any]

_MAX_ORIGIN_CHARS = 256


class RedisSubscriptionLost(Exception):
    """The socket's Redis subscription stopped answering liveness pings."""


class _ClientGone(Exception):
    """Sending to the socket failed because the client already disconnected."""


class RealtimeApp:
    def __init__(self, config: RealtimeConfig | None = None, *, redis_client=None) -> None:
        self.config = config
        self.redis = redis_client
        self.active_connections = 0

    # ASGI entry point ------------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive, send) -> None:
        kind = scope["type"]
        if kind == "lifespan":
            await self._lifespan(receive, send)
        elif kind == "http":
            await self._http(scope, send)
        elif kind == "websocket":
            await self._websocket(scope, receive, send)

    def _ensure_started(self) -> None:
        if self.config is None:
            self.config = load_config()
        if self.redis is None:
            self.redis = store.create_client(self.config)

    async def _lifespan(self, receive, send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    log.configure()
                    self._ensure_started()
                except Exception as exc:
                    # Configuration errors name settings only; values are never included.
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                log.event("realtime_started", allowed_origin_count=len(self.config.allowed_origins))
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if self.redis is not None:
                    with suppress(*store.REDIS_ERRORS):
                        await self.redis.aclose()
                log.event("realtime_stopped")
                await send({"type": "lifespan.shutdown.complete"})
                return

    # Health ----------------------------------------------------------------------------------

    async def _http(self, scope: Scope, send) -> None:
        path, method = scope["path"], scope["method"]
        if path not in (protocol.HEALTH_LIVE_PATH, protocol.HEALTH_READY_PATH):
            status, body = 404, {"status": "not_found"}
        elif method not in ("GET", "HEAD"):
            status, body = 405, {"status": "method_not_allowed"}
        elif path == protocol.HEALTH_LIVE_PATH:
            status, body = 200, {"status": "ok"}
        elif await self._redis_reachable():
            status, body = 200, {"status": "ok"}
        else:
            status, body = 503, {"status": "unavailable"}
        payload = json.dumps(body, separators=(",", ":")).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(payload)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"" if method == "HEAD" else payload})

    async def _redis_reachable(self) -> bool:
        try:
            self._ensure_started()
            return bool(
                await asyncio.wait_for(self.redis.ping(), self.config.redis_timeout_seconds)
            )
        except Exception:
            return False

    # WebSocket -------------------------------------------------------------------------------

    def _handshake_rejection(self, scope: Scope) -> str | None:
        if scope["path"] != protocol.SOCKET_PATH:
            return "path_unknown"
        # Tickets never travel in URLs. Refusing any query string keeps clients from starting to.
        if scope.get("query_string"):
            return "query_string_present"
        origins = [value for name, value in scope["headers"] if name == b"origin"]
        if not origins:
            return "origin_missing"
        if len(origins) != 1 or len(origins[0]) > _MAX_ORIGIN_CHARS:
            return "origin_malformed"
        try:
            origin = origins[0].decode("ascii")
        except UnicodeDecodeError:
            return "origin_malformed"
        if origin not in self.config.allowed_origins:
            return "origin_rejected"
        return None

    async def _websocket(self, scope: Scope, receive, send) -> None:
        message = await receive()
        if message["type"] != "websocket.connect":
            return
        self._ensure_started()
        rejection = self._handshake_rejection(scope)
        if rejection is not None:
            log.event("socket_rejected", level=logging.WARNING, reason=rejection)
            # Closing before accepting makes the server answer the upgrade with HTTP 403.
            await send({"type": "websocket.close", "code": protocol.CloseCode.POLICY_VIOLATION})
            return
        connection = _Connection(self, receive, send)
        if self.active_connections >= self.config.max_connections:
            await send({"type": "websocket.accept"})
            await connection.close(protocol.CloseCode.TRY_AGAIN_LATER, "capacity")
            return
        self.active_connections += 1
        try:
            await send({"type": "websocket.accept"})
            await connection.serve()
        finally:
            self.active_connections -= 1


class _Connection:
    """One accepted socket: bounded pre-authentication, then server-to-client hints only."""

    def __init__(self, app: RealtimeApp, receive, send) -> None:
        self.app = app
        self.config: RealtimeConfig = app.config
        self.receive = receive
        self._send = send
        self.connection_id = secrets.token_hex(4)
        self.loop = asyncio.get_running_loop()
        self.started = self.loop.time()
        self.closed = False

    async def send_text(self, text: str) -> None:
        try:
            await self._send({"type": "websocket.send", "text": text})
        except Exception as exc:
            raise _ClientGone from exc

    async def close(self, code: int, reason: str) -> None:
        if not self.closed:
            self.closed = True
            with suppress(Exception):
                await self._send({"type": "websocket.close", "code": int(code), "reason": reason})
        self._log_closed(reason, code)

    def _log_closed(self, reason: str, code: int | None = None) -> None:
        log.event(
            "socket_closed",
            reason=reason,
            close_code=code,
            connection_id=self.connection_id,
            duration_seconds=round(self.loop.time() - self.started, 1),
            active_connections=self.app.active_connections,
        )

    async def serve(self) -> None:
        identity = await self._authenticate()
        if identity is None:
            return
        pubsub = self.app.redis.pubsub()
        try:
            await self._subscribe(pubsub, identity)
        except protocol.TicketRejected as exc:
            await self.close(protocol.CloseCode.SESSION_REVOKED, exc.reason)
        except store.REDIS_ERRORS + (RedisSubscriptionLost,) as exc:
            log.event("redis_unavailable", level=logging.WARNING, error_type=type(exc).__name__)
            await self.close(protocol.CloseCode.TRY_AGAIN_LATER, "redis_unavailable")
        else:
            await self._run(pubsub)
        finally:
            with suppress(Exception):
                await pubsub.aclose()

    async def _authenticate(self) -> protocol.SocketIdentity | None:
        try:
            message = await asyncio.wait_for(self.receive(), self.config.auth_timeout_seconds)
        except TimeoutError:
            await self.close(protocol.CloseCode.AUTHENTICATION_TIMEOUT, "authentication_timeout")
            return None
        if message["type"] == "websocket.disconnect":
            self.closed = True
            self._log_closed("client_closed")
            return None
        ticket = protocol.parse_authenticate_frame(message)
        if ticket is None:
            await self.close(protocol.CloseCode.POLICY_VIOLATION, "authentication_malformed")
            return None
        try:
            identity = await store.consume_ticket(self.app.redis, ticket)
        except protocol.TicketRejected as exc:
            code = (
                protocol.CloseCode.SESSION_REVOKED
                if exc.reason == "session_revoked"
                else protocol.CloseCode.AUTHENTICATION_FAILED
            )
            log.event("ticket_rejected", level=logging.WARNING, reason=exc.reason)
            await self.close(code, exc.reason)
            return None
        except store.REDIS_ERRORS as exc:
            log.event("redis_unavailable", level=logging.WARNING, error_type=type(exc).__name__)
            await self.close(protocol.CloseCode.TRY_AGAIN_LATER, "redis_unavailable")
            return None
        return identity

    async def _subscribe(self, pubsub, identity: protocol.SocketIdentity) -> None:
        """Subscribe to the server-derived channels, then confirm the session is still live.

        The revocation marker is checked again after Redis confirms both subscriptions, so a
        revocation that lands between ticket consumption and subscription is never missed: it is
        either already marked or its control message arrives on the active subscription.
        """

        self.user_channel = protocol.user_channel(identity.user_id)
        self.session_channel = protocol.session_channel(identity.session_id)
        await pubsub.subscribe(self.user_channel, self.session_channel)
        pending: set[str] = {self.user_channel, self.session_channel}
        self.early_messages: list[Message] = []
        deadline = self.loop.time() + self.config.redis_timeout_seconds
        while pending:
            remaining = deadline - self.loop.time()
            if remaining <= 0:
                raise RedisSubscriptionLost("subscription was not confirmed")
            message = await pubsub.get_message(timeout=remaining)
            if message is None:
                continue
            if message["type"] == "subscribe":
                pending.discard(message["channel"])
            elif message["type"] == "message":
                self.early_messages.append(message)
        if await store.session_revoked(self.app.redis, identity.session_id):
            raise protocol.TicketRejected("session_revoked")

    async def _run(self, pubsub) -> None:
        early = [self._decode(message) for message in self.early_messages]
        if any(decoded == "session_revoked" for decoded in early):
            await self.close(protocol.CloseCode.SESSION_REVOKED, "session_revoked")
            return
        try:
            await self.send_text(protocol.READY_FRAME)
            # Hints published while subscribing are delivered after ``ready``, never before it.
            for frame in early:
                if frame is not None:
                    await self.send_text(frame)
        except _ClientGone:
            self.closed = True
            self._log_closed("client_closed")
            return
        log.event(
            "socket_authenticated",
            connection_id=self.connection_id,
            active_connections=self.app.active_connections,
        )
        lifetime = self.config.connection_max_seconds - random.uniform(
            0, self.config.connection_jitter_seconds
        )
        client_task = asyncio.create_task(self._watch_client())
        relay_task = asyncio.create_task(self._relay(pubsub))
        try:
            done, _ = await asyncio.wait(
                {client_task, relay_task},
                timeout=max(0.0, lifetime - (self.loop.time() - self.started)),
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in (client_task, relay_task):
                task.cancel()
            await asyncio.gather(client_task, relay_task, return_exceptions=True)

        if relay_task in done:
            error = relay_task.exception()
            if error is None:
                outcome = relay_task.result()
                if outcome == "session_revoked":
                    log.event("session_revoked_close", connection_id=self.connection_id)
                    await self.close(protocol.CloseCode.SESSION_REVOKED, "session_revoked")
                else:
                    self.closed = True
                    self._log_closed("client_closed")
                return
            if isinstance(error, store.REDIS_ERRORS + (RedisSubscriptionLost,)):
                log.event(
                    "redis_unavailable", level=logging.WARNING, error_type=type(error).__name__
                )
                await self.close(protocol.CloseCode.TRY_AGAIN_LATER, "redis_unavailable")
                return
            raise error
        if client_task in done:
            if client_task.result() == "unexpected_frame":
                await self.close(protocol.CloseCode.POLICY_VIOLATION, "unexpected_client_frame")
            else:
                self.closed = True
                self._log_closed("client_closed")
            return
        await self.close(protocol.CloseCode.RECONNECT, "lifetime_expired")

    async def _watch_client(self) -> str:
        message = await self.receive()
        if message["type"] == "websocket.disconnect":
            return "client_closed"
        # The authentication frame was the only client frame this protocol allows.
        return "unexpected_frame"

    async def _relay(self, pubsub) -> str:
        """Forward hints until a revocation arrives or Redis is lost."""

        interval = self.config.redis_ping_interval_seconds
        pong_deadline: float | None = None
        while True:
            wait = interval if pong_deadline is None else max(0.0, pong_deadline - self.loop.time())
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=wait)
            if message is None:
                if pong_deadline is None:
                    await pubsub.ping()
                    pong_deadline = self.loop.time() + self.config.redis_timeout_seconds
                elif self.loop.time() >= pong_deadline:
                    raise RedisSubscriptionLost("ping was not answered")
                continue
            if message["type"] == "pong":
                pong_deadline = None
                continue
            decoded = self._decode(message)
            if decoded == "session_revoked":
                return decoded
            if decoded is not None:
                try:
                    await self.send_text(decoded)
                except _ClientGone:
                    return "client_closed"

    def _decode(self, message: Message) -> str | None:
        """Return ``"session_revoked"``, a public frame to forward, or ``None`` to drop."""

        if message.get("type") != "message":
            return None
        decoded = protocol.decode_channel_message(message.get("data"))
        if decoded is None:
            log.event("event_dropped", level=logging.WARNING, reason="invalid")
            return None
        if decoded.control is None:
            return decoded.frame
        if (
            decoded.control == protocol.CONTROL_SESSION_REVOKED
            and message.get("channel") == self.session_channel
        ):
            return "session_revoked"
        log.event("event_dropped", level=logging.WARNING, reason="control_misrouted")
        return None


app = RealtimeApp()
