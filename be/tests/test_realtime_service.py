"""The standalone realtime ASGI service (ADR-100), driven in-process against the test Redis.

Sockets are simulated at the ASGI boundary, so every frame the service sends is visible. Tickets
are minted directly into Redis with the shared protocol helpers, as the Django endpoint does.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import uuid

import pytest
import redis.asyncio as aioredis

from realtime_service import protocol, store
from realtime_service.app import RealtimeApp
from realtime_service.config import RealtimeConfig, load_config, parse_allowed_origins

ORIGIN = "https://staging.compass-gco.com"
UNREACHABLE = "redis://127.0.0.1:1/4"


def redis_url() -> str:
    return os.environ["REDIS_REALTIME_URL"]


def config(**overrides) -> RealtimeConfig:
    values = {
        "redis_url": redis_url(),
        "allowed_origins": frozenset({ORIGIN}),
        "auth_timeout_seconds": 1.0,
        "connection_max_seconds": 30.0,
        "connection_jitter_seconds": 0.0,
        "redis_timeout_seconds": 1.0,
        "redis_ping_interval_seconds": 5.0,
    }
    values.update(overrides)
    return RealtimeConfig(**values)


class Socket:
    """One client connection at the ASGI boundary."""

    def __init__(self, app, *, origin=ORIGIN, path=protocol.SOCKET_PATH, query=b"", headers=None):
        self.to_app: asyncio.Queue = asyncio.Queue()
        self.from_app: asyncio.Queue = asyncio.Queue()
        if headers is None:
            headers = [(b"host", b"staging-api.compass-gco.com")]
            if origin is not None:
                headers.append((b"origin", origin.encode("latin-1")))
        scope = {
            "type": "websocket",
            "path": path,
            "query_string": query,
            "headers": headers,
        }
        self.to_app.put_nowait({"type": "websocket.connect"})
        self.task = asyncio.create_task(app(scope, self.to_app.get, self.from_app.put))

    async def next(self, timeout: float = 3.0) -> dict:
        return await asyncio.wait_for(self.from_app.get(), timeout)

    def send(self, payload) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        self.to_app.put_nowait({"type": "websocket.receive", "text": text})

    def authenticate(self, ticket: str) -> None:
        self.send({"type": "authenticate", "ticket": ticket})

    async def accepted(self) -> None:
        assert (await self.next()) == {"type": "websocket.accept"}

    async def ready(self, ticket: str) -> None:
        await self.accepted()
        self.authenticate(ticket)
        assert (await self.next()) == {"type": "websocket.send", "text": '{"v":1,"type":"ready"}'}

    async def closed(self, timeout: float = 3.0) -> tuple[int, str]:
        message = await self.next(timeout)
        assert message["type"] == "websocket.close", message
        await asyncio.wait_for(self.task, timeout)
        return message.get("code"), message.get("reason", "")

    async def nothing(self, timeout: float = 0.3) -> None:
        with pytest.raises(TimeoutError):
            await self.next(timeout)

    async def disconnect(self) -> None:
        self.to_app.put_nowait({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self.task, 3)


def run(test, **config_overrides):
    """Run ``test(app, redis)`` with a fresh service and Redis client in one event loop."""

    async def main():
        client = aioredis.Redis.from_url(redis_url(), decode_responses=True)
        for key in [key async for key in client.scan_iter(match=f"{protocol.KEY_PREFIX}:*")]:
            await client.delete(key)
        cfg = config(**config_overrides)
        service_redis = store.create_client(cfg)
        app = RealtimeApp(cfg, redis_client=service_redis)
        try:
            await test(app, client)
        finally:
            await service_redis.aclose()
            await client.aclose()

    asyncio.run(main())


def identity(user_id=None, session_id=None) -> protocol.SocketIdentity:
    return protocol.SocketIdentity(
        user_id=user_id or str(uuid.uuid4()), session_id=session_id or str(uuid.uuid4())
    )


async def mint(client, who: protocol.SocketIdentity, *, ttl: int = 30) -> str:
    ticket = secrets.token_urlsafe(protocol.TICKET_BYTES)
    metadata = protocol.encode_ticket_metadata(who, expires_at=int(time.time()) + ttl)
    assert await client.set(protocol.ticket_key(ticket), metadata, nx=True, ex=ttl)
    return ticket


@pytest.fixture
def test_events(monkeypatch):
    monkeypatch.setattr(
        protocol,
        "PUBLIC_EVENT_FIELDS",
        {"test.changed": frozenset(), "test.thread_changed": frozenset({"thread_id"})},
    )


# Origin and handshake -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "https://evil.example",
        "https://staging.compass-gco.com.evil.example",
        "https://evilstaging.compass-gco.com",
        "https://staging.compass-gco.co",
        "http://staging.compass-gco.com",
        "https://STAGING.compass-gco.com",
        "https://staging.compass-gco.com/",
        "https://staging.compass-gco.com:8443",
        "null",
        "",
        "https://staging.compass-gco.comé",
    ],
)
def test_websocket_requires_the_exact_allowed_origin(origin):
    async def test(app, client):
        socket = Socket(app, origin=origin)
        message = await socket.next()
        # Closing before accept answers the upgrade with HTTP 403; nothing else happens.
        assert message == {"type": "websocket.close", "code": 1008}
        await asyncio.wait_for(socket.task, 1)

    run(test)


def test_duplicate_origin_headers_wrong_path_and_query_strings_are_rejected():
    async def test(app, client):
        duplicate = Socket(
            app, headers=[(b"origin", ORIGIN.encode()), (b"origin", b"https://evil.example")]
        )
        assert (await duplicate.next())["type"] == "websocket.close"
        for socket in (
            Socket(app, path="/api/realtime/v1/socket/extra"),
            Socket(app, path="/api/v1/realtime/tickets"),
            Socket(app, query=b"ticket=" + b"A" * 43),
        ):
            assert (await socket.next()) == {"type": "websocket.close", "code": 1008}
        allowed = Socket(app)
        await allowed.accepted()
        await allowed.disconnect()

    run(test)


# Authentication -------------------------------------------------------------------------------


def test_socket_must_authenticate_within_the_timeout():
    async def test(app, client):
        socket = Socket(app)
        await socket.accepted()
        assert await socket.closed() == (4408, "authentication_timeout")

    run(test, auth_timeout_seconds=0.2)


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        "[]",
        json.dumps({"type": "authenticate"}),
        json.dumps({"type": "authenticate", "ticket": "x", "user_id": str(uuid.uuid4())}),
        json.dumps({"type": "subscribe", "ticket": "x"}),
        json.dumps({"type": "authenticate", "ticket": 42}),
        json.dumps({"type": "authenticate", "ticket": "A" * 400}),
    ],
)
def test_malformed_authentication_frames_violate_policy(frame):
    async def test(app, client):
        socket = Socket(app)
        await socket.accepted()
        socket.send(frame)
        assert await socket.closed() == (1008, "authentication_malformed")

    run(test)


def test_binary_authentication_frames_violate_policy():
    async def test(app, client):
        socket = Socket(app)
        await socket.accepted()
        socket.to_app.put_nowait({"type": "websocket.receive", "bytes": b'{"type":"x"}'})
        assert await socket.closed() == (1008, "authentication_malformed")

    run(test)


def test_valid_ticket_receives_ready_once_and_cannot_be_reused():
    async def test(app, client):
        ticket = await mint(client, identity())
        first = Socket(app)
        await first.ready(ticket)

        second = Socket(app)
        await second.accepted()
        second.authenticate(ticket)
        assert await second.closed() == (4401, "ticket_unknown")
        await first.disconnect()

    run(test)


def test_unknown_malformed_expired_and_revoked_tickets_fail():
    async def test(app, client):
        who = identity()
        expired = secrets.token_urlsafe(32)
        await client.set(
            protocol.ticket_key(expired),
            protocol.encode_ticket_metadata(who, expires_at=int(time.time()) - 5),
            ex=30,
        )
        revoked_who = identity()
        revoked = await mint(client, revoked_who)
        await client.set(protocol.revoked_session_key(revoked_who.session_id), "1", ex=60)
        cases = [
            (secrets.token_urlsafe(32), (4401, "ticket_unknown")),
            ("not-a-ticket", (4401, "ticket_malformed")),
            (expired, (4401, "ticket_expired")),
            (revoked, (4403, "session_revoked")),
        ]
        for ticket, expected in cases:
            socket = Socket(app)
            await socket.accepted()
            socket.authenticate(ticket)
            assert await socket.closed() == expected

    run(test)


def test_concurrent_sockets_presenting_one_ticket_authenticate_once():
    async def test(app, client):
        ticket = await mint(client, identity())
        sockets = [Socket(app) for _ in range(12)]
        for socket in sockets:
            await socket.accepted()
        for socket in sockets:
            socket.authenticate(ticket)
        outcomes = await asyncio.gather(*(socket.next() for socket in sockets))
        ready = [m for m in outcomes if m.get("text") == protocol.READY_FRAME]
        rejected = [m for m in outcomes if m.get("type") == "websocket.close"]
        assert len(ready) == 1
        assert len(rejected) == 11
        assert {(m["code"], m["reason"]) for m in rejected} == {(4401, "ticket_unknown")}
        for socket, message in zip(sockets, outcomes, strict=True):
            if message.get("text") == protocol.READY_FRAME:
                await socket.disconnect()

    run(test)


# After authentication: hints only ---------------------------------------------------------------


def test_client_frames_after_ready_are_a_policy_violation():
    async def test(app, client):
        other_user = str(uuid.uuid4())
        socket = Socket(app)
        await socket.ready(await mint(client, identity()))
        socket.send({"type": "subscribe", "channel": f"compass:realtime:user:{other_user}"})
        assert await socket.closed() == (1008, "unexpected_client_frame")

    run(test)


def test_socket_receives_only_its_own_server_derived_channels(test_events):
    async def test(app, client):
        me, other = identity(), identity()
        socket = Socket(app)
        await socket.ready(await mint(client, me))
        thread = str(uuid.uuid4())

        await client.publish(
            protocol.user_channel(other.user_id), protocol.encode_event("test.changed")
        )
        await client.publish(
            protocol.session_channel(other.session_id),
            protocol.encode_control(protocol.CONTROL_SESSION_REVOKED),
        )
        await socket.nothing()

        await client.publish(
            protocol.user_channel(me.user_id),
            protocol.encode_event("test.thread_changed", {"thread_id": thread}),
        )
        message = await socket.next()
        assert json.loads(message["text"]) == {
            "v": 1,
            "type": "test.thread_changed",
            "thread_id": thread,
        }
        await socket.disconnect()

    run(test)


def test_unregistered_or_content_bearing_payloads_are_never_forwarded(test_events):
    async def test(app, client):
        me = identity()
        socket = Socket(app)
        await socket.ready(await mint(client, me))
        channel = protocol.user_channel(me.user_id)
        for payload in (
            "plain text",
            json.dumps({"v": 1, "type": "notifications.changed"}),
            json.dumps({"v": 1, "type": "test.changed", "body": "Counseling notes"}),
            json.dumps({"v": 1, "type": "test.thread_changed", "thread_id": "Message body"}),
            json.dumps({"v": 2, "type": "test.changed"}),
            json.dumps({"v": 1, "type": "test.changed", "padding": "x" * 600}),
            # A control on the user channel cannot close sessions it does not name.
            protocol.encode_control(protocol.CONTROL_SESSION_REVOKED),
        ):
            await client.publish(channel, payload)
        await socket.nothing()
        await client.publish(channel, protocol.encode_event("test.changed"))
        assert (await socket.next())["text"] == '{"v":1,"type":"test.changed"}'
        await socket.disconnect()

    run(test)


def test_session_revocation_closes_only_the_revoked_sessions_socket(test_events):
    async def test(app, client):
        user_id = str(uuid.uuid4())
        revoked, kept = identity(user_id), identity(user_id)
        revoked_socket, kept_socket = Socket(app), Socket(app)
        await revoked_socket.ready(await mint(client, revoked))
        await kept_socket.ready(await mint(client, kept))

        await client.publish(
            protocol.session_channel(revoked.session_id),
            protocol.encode_control(protocol.CONTROL_SESSION_REVOKED),
        )

        assert await revoked_socket.closed() == (4403, "session_revoked")
        await kept_socket.nothing()
        await client.publish(protocol.user_channel(user_id), protocol.encode_event("test.changed"))
        assert (await kept_socket.next())["text"] == '{"v":1,"type":"test.changed"}'
        await kept_socket.disconnect()

    run(test)


def test_authenticated_sockets_have_a_bounded_lifetime():
    async def test(app, client):
        socket = Socket(app)
        await socket.ready(await mint(client, identity()))
        started = time.monotonic()
        assert await socket.closed() == (4000, "lifetime_expired")
        assert time.monotonic() - started < 2

    run(test, connection_max_seconds=0.6)


# Redis failure ------------------------------------------------------------------------------------


def test_unreachable_redis_closes_with_try_again_later():
    async def test(app, client):
        socket = Socket(app)
        await socket.accepted()
        socket.authenticate(secrets.token_urlsafe(32))
        assert await socket.closed() == (1013, "redis_unavailable")

    run(test, redis_url=UNREACHABLE, redis_timeout_seconds=0.3)


def test_losing_the_redis_subscription_closes_with_try_again_later():
    async def test(app, client):
        socket = Socket(app)
        await socket.ready(await mint(client, identity()))
        await client.execute_command("CLIENT", "KILL", "TYPE", "pubsub")
        assert await socket.closed() == (1013, "redis_unavailable")

    run(test, redis_ping_interval_seconds=0.2)


def test_an_unanswered_subscription_ping_closes_the_socket(monkeypatch):
    async def test(app, client):
        socket = Socket(app)
        await socket.ready(await mint(client, identity()))
        assert await socket.closed() == (1013, "redis_unavailable")

    async def silent_ping(self, message=None):
        return None

    monkeypatch.setattr("redis.asyncio.client.PubSub.ping", silent_ping)
    run(test, redis_ping_interval_seconds=0.1, redis_timeout_seconds=0.2)


def test_connection_cap_rejects_with_try_again_later():
    async def test(app, client):
        first = Socket(app)
        await first.accepted()
        second = Socket(app)
        await second.accepted()
        assert await second.closed() == (1013, "capacity")
        await first.disconnect()

    run(test, max_connections=1)


# Health, logging, configuration --------------------------------------------------------------


async def http(app, path: str, method: str = "GET") -> tuple[int, dict, dict]:
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app({"type": "http", "path": path, "method": method, "headers": []}, receive, send)
    headers = dict(sent[0]["headers"])
    return sent[0]["status"], headers, json.loads(sent[1]["body"] or b"null")


def test_health_separates_liveness_from_redis_readiness_without_leaking_configuration():
    async def test(app, client):
        assert await http(app, protocol.HEALTH_LIVE_PATH) == (
            200,
            {
                b"content-type": b"application/json",
                b"cache-control": b"no-store",
                b"content-length": b"15",
            },
            {"status": "ok"},
        )
        assert (await http(app, protocol.HEALTH_READY_PATH))[::2] == (200, {"status": "ok"})
        assert (await http(app, "/api/realtime/v1/other"))[::2] == (404, {"status": "not_found"})
        assert (await http(app, protocol.HEALTH_LIVE_PATH, "POST"))[::2] == (
            405,
            {"status": "method_not_allowed"},
        )

    run(test)

    async def down(app, client):
        assert (await http(app, protocol.HEALTH_LIVE_PATH))[::2] == (200, {"status": "ok"})
        status, _headers, body = await http(app, protocol.HEALTH_READY_PATH)
        assert (status, body) == (503, {"status": "unavailable"})

    run(down, redis_url=UNREACHABLE, redis_timeout_seconds=0.3)


@pytest.fixture
def realtime_logs(caplog):
    """``compass`` loggers do not propagate to the root handler under the Django settings."""

    logger = logging.getLogger("compass.realtime")
    caplog.set_level(logging.INFO, logger="compass.realtime")
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def test_logs_are_structural_and_never_contain_tickets_origins_or_identities(realtime_logs):
    caplog = realtime_logs
    who = identity()
    tickets: list[str] = []

    async def test(app, client):
        tickets.append(await mint(client, who))
        socket = Socket(app)
        await socket.ready(tickets[0])
        await client.publish(
            protocol.session_channel(who.session_id),
            protocol.encode_control(protocol.CONTROL_SESSION_REVOKED),
        )
        await socket.closed()
        rejected = Socket(app, origin="https://evil.example")
        await rejected.next()
        reused = Socket(app)
        await reused.accepted()
        reused.authenticate(tickets[0])
        await reused.closed()

    run(test)
    events = [record.event for record in caplog.records if record.name == "compass.realtime"]
    assert "socket_authenticated" in events
    assert "session_revoked_close" in events
    assert "socket_rejected" in events
    assert "ticket_rejected" in events
    rendered = "\n".join(
        f"{record.getMessage()} {json.dumps(record.__dict__, default=str)}"
        for record in caplog.records
    )
    for secret in (tickets[0], protocol.ticket_key(tickets[0]), who.user_id, who.session_id):
        assert secret not in rendered
    assert "evil.example" not in rendered
    assert "staging.compass-gco.com" not in rendered


def test_lifespan_fails_closed_without_origins_and_names_no_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "live-staging")
    monkeypatch.setenv("REDIS_PASSWORD", "password-sentinel")
    monkeypatch.delenv("REDIS_REALTIME_URL", raising=False)
    for name in ("REDIS_URL", "REDIS_CACHE_URL", "REDIS_RATE_LIMIT_URL", "REDIS_IDEMPOTENCY_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("REALTIME_ALLOWED_ORIGINS", raising=False)

    async def lifespan():
        app = RealtimeApp()
        sent: list[dict] = []
        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait({"type": "lifespan.startup"})
        await app({"type": "lifespan"}, queue.get, lambda m: _append(sent, m))
        return sent

    sent = asyncio.run(lifespan())
    assert sent[0]["type"] == "lifespan.startup.failed"
    assert "REALTIME_ALLOWED_ORIGINS" in sent[0]["message"]
    assert "password-sentinel" not in sent[0]["message"]

    monkeypatch.setenv("REALTIME_ALLOWED_ORIGINS", ORIGIN)
    loaded = load_config()
    assert loaded.allowed_origins == frozenset({ORIGIN})
    assert loaded.redis_url.endswith("@redis:6379/4")
    monkeypatch.setenv("REDIS_REALTIME_URL", "redis://override:6379/4")
    with pytest.raises(ValueError, match="overrides are not allowed in live-staging"):
        load_config()


async def _append(sent: list[dict], message: dict) -> None:
    sent.append(message)


def test_allowed_origins_are_exact_canonical_origins():
    accepted = [
        "https://staging.compass-gco.com",
        "https://compass.example.edu",
        "https://staging.compass-gco.com:8443",
    ]
    assert parse_allowed_origins(accepted, allow_http=False) == frozenset(accepted)
    assert parse_allowed_origins(["http://localhost:3000"], allow_http=True) == frozenset(
        {"http://localhost:3000"}
    )
    for rejected in (
        "*",
        "https://*.compass-gco.com",
        "compass-gco.com",
        "https://staging.compass-gco.com/",
        "https://staging.compass-gco.com/path",
        "https://staging.compass-gco.com?x=1",
        "https://user@staging.compass-gco.com",
        "https://Staging.compass-gco.com",
        "https://staging.compass-gco.com:443",
        "http://staging.compass-gco.com",
        "wss://staging.compass-gco.com",
    ):
        with pytest.raises(ValueError):
            parse_allowed_origins([rejected], allow_http=False)
    with pytest.raises(ValueError):
        config(allowed_origins=frozenset())


def test_public_events_are_registered_and_carry_only_opaque_identifiers(test_events):
    assert protocol.encode_event("test.changed") == '{"v":1,"type":"test.changed"}'
    thread = str(uuid.uuid4())
    assert json.loads(protocol.encode_event("test.thread_changed", {"thread_id": thread})) == {
        "v": 1,
        "type": "test.thread_changed",
        "thread_id": thread,
    }
    for event_type, fields in (
        ("notifications.changed", {}),
        ("test.changed", {"title": str(uuid.uuid4())}),
        ("test.thread_changed", {}),
        ("test.thread_changed", {"thread_id": "Message body"}),
        ("test.thread_changed", {"thread_id": thread.upper()}),
        ("Test.Changed", {}),
    ):
        with pytest.raises(ValueError):
            protocol.encode_event(event_type, fields)


def test_phase_one_defines_no_public_events_beyond_ready():
    assert dict(protocol.PUBLIC_EVENT_FIELDS) == {}
    assert json.loads(protocol.READY_FRAME) == {"v": 1, "type": "ready"}
