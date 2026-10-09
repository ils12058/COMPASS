"""Realtime ticket issuance, consumption, and session-revocation hooks (ADR-100).

These tests use the dedicated realtime Redis database from the test settings, because the
single-use guarantee is Redis's atomic GETDEL, not anything a fake could prove.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

import pytest
import redis
import redis.asyncio as aioredis
from django.core.management import call_command
from django.db import transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.authentication.models import AuthSession
from compass.authentication.security import (
    invalidate_auth_state_after_authority_change,
    invalidate_reusable_auth_state,
)
from compass.authentication.sessions import create_auth_session, revoke_auth_session
from compass.realtime import connection, publish, tickets
from realtime_service import protocol, store

BACKEND = Path(__file__).parents[1]
TICKETS = "/api/v1/realtime/tickets"


@pytest.fixture
def realtime_redis(settings):
    settings.REALTIME_ENABLED = True
    connection._client.cache_clear()
    client = redis.Redis.from_url(settings.REDIS_REALTIME_URL, decode_responses=True)

    def clear():
        for key in client.scan_iter(match=f"{protocol.KEY_PREFIX}:*"):
            client.delete(key)

    clear()
    yield client
    clear()
    client.close()
    connection._client.cache_clear()


def make_user(email: str, *, active: bool = True) -> User:
    role, _ = Role.objects.get_or_create(code="STUDENT", defaults={"name": "Student"})
    return User.objects.create_user(
        email=email,
        password="a-test-password-long-enough",
        role=role,
        first_name="Realtime",
        last_name="Test",
        is_active=active,
    )


def session_client(user: User, *, enforce_csrf: bool = False):
    issued = create_auth_session(user, now=timezone.now())
    client = Client(enforce_csrf_checks=enforce_csrf)
    client.cookies["compass_session"] = issued.token
    return client, issued.session


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def issue(client: Client):
    return client.post(TICKETS, **csrf(client))


def _url() -> str:
    from django.conf import settings

    return settings.REDIS_REALTIME_URL


def consume(url: str, ticket: str):
    async def run():
        client = aioredis.Redis.from_url(url, decode_responses=True)
        try:
            return await store.consume_ticket(client, ticket)
        finally:
            await client.aclose()

    return asyncio.run(run())


def realtime_keys(client) -> list[str]:
    return sorted(client.scan_iter(match=f"{protocol.KEY_PREFIX}:*"))


@pytest.mark.django_db
def test_authenticated_session_receives_a_short_lived_digest_only_ticket(realtime_redis, settings):
    user = make_user("ticket@example.edu")
    client, session = session_client(user)

    response = issue(client)

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == {"ticket", "expires_in_seconds", "user_id"}
    assert body["user_id"] == str(user.pk)
    assert body["expires_in_seconds"] == settings.REALTIME_TICKET_TTL_SECONDS == 30
    ticket = body["ticket"]
    # secrets.token_urlsafe(32): 256 random bits as 43 URL-safe characters.
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", ticket)

    digest = hashlib.sha256(ticket.encode()).hexdigest()
    assert realtime_keys(realtime_redis) == [f"compass:realtime:ticket:{digest}"]
    key = realtime_keys(realtime_redis)[0]
    assert 0 < realtime_redis.ttl(key) <= 30
    stored = realtime_redis.get(key)
    assert ticket not in stored and ticket not in key
    metadata = json.loads(stored)
    assert set(metadata) == {"v", "user_id", "session_id", "expires_at"}
    assert metadata["user_id"] == str(user.pk)
    assert metadata["session_id"] == str(session.pk)
    assert user.email not in stored and "Realtime" not in stored
    assert time.time() < metadata["expires_at"] <= time.time() + 30


@pytest.mark.django_db
def test_every_ticket_is_new_randomness(realtime_redis):
    client, _session = session_client(make_user("random@example.edu"))
    tickets = {issue(client).json()["ticket"] for _ in range(20)}
    assert len(tickets) == 20
    assert len(realtime_keys(realtime_redis)) == 20


@pytest.mark.django_db
def test_ticket_endpoint_requires_an_active_session_and_post(realtime_redis):
    anonymous = Client()
    assert anonymous.post(TICKETS, **csrf(anonymous)).status_code == 401

    user = make_user("revoked@example.edu")
    client, session = session_client(user)
    revoke_auth_session(session_id=session.pk, context=AuditContext.system())
    assert issue(client).status_code == 401

    inactive_client, _ = session_client(make_user("inactive@example.edu"))
    User.objects.filter(email="inactive@example.edu").update(is_active=False)
    assert issue(inactive_client).status_code == 401

    live_client, _ = session_client(make_user("method@example.edu"))
    assert live_client.get(TICKETS).status_code == 405
    assert realtime_keys(realtime_redis) == []


@pytest.mark.django_db
def test_ticket_endpoint_keeps_csrf_protection(realtime_redis):
    client, _session = session_client(make_user("csrf@example.edu"), enforce_csrf=True)

    missing = client.post(TICKETS)

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"
    assert realtime_keys(realtime_redis) == []
    assert client.post(TICKETS, **csrf(client)).status_code == 200


@pytest.mark.django_db
def test_ticket_endpoint_ignores_any_requested_identity(realtime_redis):
    user = make_user("self@example.edu")
    other = make_user("other@example.edu")
    client, session = session_client(user)

    response = client.post(
        f"{TICKETS}?user_id={other.pk}",
        data=json.dumps({"user_id": str(other.pk), "session_id": str(session.pk)}),
        content_type="application/json",
        **csrf(client),
    )

    assert response.status_code == 200
    identity = consume(_url(), response.json()["ticket"])
    assert identity == protocol.SocketIdentity(user_id=str(user.pk), session_id=str(session.pk))


@pytest.mark.django_db
def test_disabled_realtime_issues_nothing_and_never_contacts_redis(
    settings, monkeypatch, django_capture_on_commit_callbacks
):
    settings.REALTIME_ENABLED = False

    def forbidden():
        pytest.fail("realtime Redis must not be used while realtime is disabled")

    monkeypatch.setattr(tickets, "realtime_redis", forbidden)
    monkeypatch.setattr(publish, "realtime_redis", forbidden)
    client, session = session_client(make_user("disabled@example.edu"))

    response = issue(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "realtime_disabled"
    assert response["Cache-Control"] == "no-store"
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post("/api/v1/auth/logout", **csrf(client))
    assert response.status_code == 200
    assert callbacks == []
    assert AuthSession.objects.get(pk=session.pk).revoked_at is not None


@pytest.mark.django_db
def test_unavailable_realtime_redis_does_not_break_http(settings):
    settings.REALTIME_ENABLED = True
    settings.REDIS_REALTIME_URL = "redis://127.0.0.1:1/4"
    settings.REDIS_SOCKET_TIMEOUT = 0.2
    connection._client.cache_clear()
    try:
        client, session = session_client(make_user("down@example.edu"))

        response = issue(client)

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "realtime_unavailable"
        assert "127.0.0.1" not in response.content.decode()
        assert client.get("/api/v1/auth/session").status_code == 200

        # Session invalidation stays authoritative when realtime Redis is down.
        logout = client.post("/api/v1/auth/logout", **csrf(client))
        assert logout.status_code == 200
        assert AuthSession.objects.get(pk=session.pk).revoked_at is not None
    finally:
        connection._client.cache_clear()


@pytest.mark.django_db
def test_a_ticket_authenticates_exactly_once(realtime_redis):
    user = make_user("once@example.edu")
    client, session = session_client(user)
    ticket = issue(client).json()["ticket"]

    identity = consume(_url(), ticket)

    assert identity == protocol.SocketIdentity(user_id=str(user.pk), session_id=str(session.pk))
    with pytest.raises(protocol.TicketRejected) as second:
        consume(_url(), ticket)
    assert second.value.reason == "ticket_unknown"
    assert realtime_keys(realtime_redis) == []


@pytest.mark.django_db
def test_concurrent_consumption_authenticates_only_one_socket(realtime_redis):
    client, _session = session_client(make_user("race@example.edu"))
    ticket = issue(client).json()["ticket"]

    async def race():
        clients = [aioredis.Redis.from_url(_url(), decode_responses=True) for _ in range(8)]
        try:
            return await asyncio.gather(
                *(store.consume_ticket(clients[i % 8], ticket) for i in range(32)),
                return_exceptions=True,
            )
        finally:
            for redis_client in clients:
                await redis_client.aclose()

    outcomes = asyncio.run(race())
    successes = [item for item in outcomes if isinstance(item, protocol.SocketIdentity)]
    rejections = [item for item in outcomes if isinstance(item, protocol.TicketRejected)]
    assert len(successes) == 1
    assert len(rejections) == 31
    assert {item.reason for item in rejections} == {"ticket_unknown"}


@pytest.mark.django_db
def test_unknown_malformed_expired_and_invalid_tickets_fail(realtime_redis):
    with pytest.raises(protocol.TicketRejected) as unknown:
        consume(_url(), "A" * 43)
    assert unknown.value.reason == "ticket_unknown"
    for malformed in ("short", "A" * 44, "A" * 42 + "!", ""):
        with pytest.raises(protocol.TicketRejected) as error:
            consume(_url(), malformed)
        assert error.value.reason == "ticket_malformed"

    user_id, session_id = (
        "1b7e4c55-3f61-4c3c-9d36-2ad5f3f0a111",
        "5d3f2b8e-77aa-4a8e-a0c4-0d4d2e1b9222",
    )
    identity = protocol.SocketIdentity(user_id=user_id, session_id=session_id)
    expired = "B" * 43
    realtime_redis.set(
        protocol.ticket_key(expired),
        protocol.encode_ticket_metadata(identity, expires_at=int(time.time()) - 1),
        ex=30,
    )
    with pytest.raises(protocol.TicketRejected) as error:
        consume(_url(), expired)
    assert error.value.reason == "ticket_expired"

    lapsed = "C" * 43
    realtime_redis.set(
        protocol.ticket_key(lapsed),
        protocol.encode_ticket_metadata(identity, expires_at=int(time.time()) + 30),
        px=50,
    )
    time.sleep(0.2)
    with pytest.raises(protocol.TicketRejected) as error:
        consume(_url(), lapsed)
    assert error.value.reason == "ticket_unknown"

    for raw in ("not json", json.dumps({"v": 1, "user_id": user_id}), json.dumps([1])):
        invalid = "D" * 43
        realtime_redis.set(protocol.ticket_key(invalid), raw, ex=30)
        with pytest.raises(protocol.TicketRejected) as error:
            consume(_url(), invalid)
        assert error.value.reason == "ticket_invalid"


def _revocations(redis_client, sessions) -> dict[str, bool]:
    return {
        str(session.pk): bool(redis_client.exists(protocol.revoked_session_key(session.pk)))
        for session in sessions
    }


@pytest.mark.django_db
def test_revoked_session_ticket_and_socket_hook_fire_after_commit(
    realtime_redis, django_capture_on_commit_callbacks
):
    user = make_user("logout@example.edu")
    client, session = session_client(user)
    _other_client, other_session = session_client(user)
    ticket = issue(client).json()["ticket"]
    subscriber = realtime_redis.pubsub()
    subscriber.subscribe(protocol.session_channel(session.pk))
    subscriber.get_message(timeout=1)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post("/api/v1/auth/logout", **csrf(client))

    assert response.status_code == 200
    assert len(callbacks) == 1
    message = subscriber.get_message(ignore_subscribe_messages=True, timeout=2)
    subscriber.close()
    assert message["data"] == '{"v":1,"control":"session_revoked"}'
    assert _revocations(realtime_redis, [session, other_session]) == {
        str(session.pk): True,
        str(other_session.pk): False,
    }
    ttl = realtime_redis.ttl(protocol.revoked_session_key(session.pk))
    assert 30 < ttl <= 3600
    with pytest.raises(protocol.TicketRejected) as error:
        consume(_url(), ticket)
    assert error.value.reason == "session_revoked"


@pytest.mark.django_db
def test_revocation_that_rolls_back_publishes_nothing(realtime_redis):
    user = make_user("rollback@example.edu")
    _client, session = session_client(user)

    with pytest.raises(RuntimeError), transaction.atomic():
        revoke_auth_session(session_id=session.pk, context=AuditContext.system())
        raise RuntimeError("roll back")

    assert AuthSession.objects.get(pk=session.pk).revoked_at is None
    assert realtime_keys(realtime_redis) == []


@pytest.mark.django_db
def test_every_session_invalidating_path_triggers_the_realtime_hook(
    realtime_redis, django_capture_on_commit_callbacks
):
    call_command("sync_identity_policy", verbosity=0)
    user = make_user("paths@example.edu")
    client, current = session_client(user)
    _c1, other = session_client(user)

    # Self-service: revoke one other session, then all others.
    with django_capture_on_commit_callbacks(execute=True):
        response = client.delete(f"/api/v1/auth/sessions/{other.pk}", **csrf(client))
    assert response.status_code == 200
    assert _revocations(realtime_redis, [current, other]) == {
        str(current.pk): False,
        str(other.pk): True,
    }
    _c2, second = session_client(user)
    _c3, third = session_client(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/api/v1/auth/sessions/revoke-others", **csrf(client))
    assert response.status_code == 200
    assert _revocations(realtime_redis, [current, second, third]) == {
        str(current.pk): False,
        str(second.pk): True,
        str(third.pk): True,
    }

    # Password change keeps the current session and revokes the rest.
    _c4, kept_elsewhere = session_client(user)
    with django_capture_on_commit_callbacks(execute=True):
        invalidate_reusable_auth_state(
            user_id=user.pk,
            context=AuditContext.system(),
            reason="password_changed",
            exclude_auth_session_id=current.pk,
        )
    assert _revocations(realtime_redis, [current, kept_elsewhere]) == {
        str(current.pk): False,
        str(kept_elsewhere.pk): True,
    }

    # Authority changes and account disablement revoke every session.
    with django_capture_on_commit_callbacks(execute=True):
        invalidate_auth_state_after_authority_change(
            user_id=user.pk, context=AuditContext.system(), reason="account_disabled"
        )
    assert _revocations(realtime_redis, [current])[str(current.pk)] is True


def test_only_the_hooked_helper_ever_revokes_an_auth_session():
    """A new code path that sets ``revoked_at`` would bypass the realtime close hook."""

    assignment = re.compile(r"\.revoked_at\s*=(?!=)|\.update\([^)]*\brevoked_at\s*=")
    writers = set()
    for path in (BACKEND / "compass").rglob("*.py"):
        if "migrations" in path.parts:
            continue
        if assignment.search(path.read_text(encoding="utf-8")):
            writers.add(path.relative_to(BACKEND).as_posix())
    # sessions.py revokes AuthSession and TrustedSession rows; Exit Interview opportunities
    # have their own unrelated ``revoked_at``.
    assert writers == {
        "compass/authentication/sessions.py",
        "compass/exit_interviews/opportunities.py",
    }
    source = (BACKEND / "compass/authentication/sessions.py").read_text(encoding="utf-8")
    locked = source[source.index("def _revoke_auth_session_locked") :]
    locked = locked[: locked.index("\ndef ")]
    assert "session.revoked_at = now" in locked
    assert "close_session_sockets_on_commit(session.pk)" in locked
    assert source.count("session.revoked_at = now") == 1


@pytest.mark.django_db
def test_publish_helper_is_content_free_best_effort_and_after_commit(
    realtime_redis, settings, monkeypatch, django_capture_on_commit_callbacks
):
    user = make_user("publish@example.edu")
    with pytest.raises(ValueError, match="not registered"):
        publish.publish_to_user(user.pk, "unregistered.changed")

    monkeypatch.setattr(
        protocol,
        "PUBLIC_EVENT_FIELDS",
        {"test.changed": frozenset(), "test.thread_changed": frozenset({"thread_id"})},
    )
    with pytest.raises(ValueError):
        publish.publish_to_user(user.pk, "test.thread_changed", {"thread_id": "Message body"})
    with pytest.raises(ValueError):
        publish.publish_to_user(user.pk, "test.changed", {"title": "Session notes"})

    subscriber = realtime_redis.pubsub()
    subscriber.subscribe(protocol.user_channel(user.pk))
    subscriber.get_message(timeout=1)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        publish.publish_to_user_on_commit(user.pk, "test.changed")
    assert subscriber.get_message(ignore_subscribe_messages=True, timeout=0.2) is None
    for callback in callbacks:
        callback()
    message = subscriber.get_message(ignore_subscribe_messages=True, timeout=2)
    assert message["data"] == '{"v":1,"type":"test.changed"}'
    subscriber.close()

    settings.REDIS_REALTIME_URL = "redis://127.0.0.1:1/4"
    settings.REDIS_SOCKET_TIMEOUT = 0.2
    connection._client.cache_clear()
    assert publish.publish_to_user(user.pk, "test.changed") is False

    settings.REALTIME_ENABLED = False
    assert publish.publish_to_user(user.pk, "test.changed") is False
