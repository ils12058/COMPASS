"""Closed content-free events, commit privacy, and real DB/Redis/socket/HTTP proof."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
import redis
from django.db import connections, transaction

from compass.guidance_messages import services
from compass.guidance_messages.models import GuidanceMessage, GuidanceThread
from compass.realtime import connection, publish
from realtime_service import protocol
from tests.test_guidance_messages import BASE, BODY, counseling, office, post, world  # noqa: F401
from tests.test_notifications import auth_client
from tests.test_realtime_service import Socket, run
from tests.test_realtime_tickets import issue

# Imported fixture names are intentionally consumed by pytest injection.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def publications(settings, monkeypatch):
    settings.REALTIME_ENABLED = True
    messages = []
    monkeypatch.setattr(
        publish,
        "_publish",
        lambda channel, frame: messages.append((channel, json.loads(frame))) or True,
    )
    return messages


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"thread_id": "bad"},
        {"thread_id": 1},
        {"thread_id": str(uuid4()), "body": BODY},
        {"thread_id": str(uuid4()), "title": "unsafe"},
        {"thread_id": str(uuid4()), "sender_name": "unsafe"},
        {"thread_id": str(uuid4()), "sequence": 1},
    ],
)
def test_exact_event_fields_and_revalidation_reject_content(fields):
    with pytest.raises(ValueError):
        protocol.encode_event("messages.thread_changed", fields)
    assert (
        protocol.decode_channel_message(
            json.dumps({"v": 1, "type": "messages.thread_changed", **fields})
        )
        is None
    )


def test_exact_thread_id_event_accepted():
    thread_id = str(uuid4())
    frame = protocol.encode_event("messages.thread_changed", {"thread_id": thread_id})
    assert json.loads(frame) == {"v": 1, "type": "messages.thread_changed", "thread_id": thread_id}
    assert protocol.decode_channel_message(frame).frame == frame


@pytest.mark.parametrize("kind", ["OFFICE", "COUNSELING"])
def test_commit_targets_current_authorized_recipients_only(world, publications, kind):
    with transaction.atomic():
        thread, _ = office(world) if kind == "OFFICE" else counseling(world)
        assert publications == []
    expected = (
        [world.student, world.counselor, world.gss]
        if kind == "OFFICE"
        else [world.student, world.counselor]
    )
    assert {channel for channel, _ in publications} == {
        protocol.user_channel(user.pk) for user in expected
    }
    assert all(
        frame == {"v": 1, "type": "messages.thread_changed", "thread_id": str(thread.pk)}
        for _, frame in publications
    )


def test_rollback_emits_nothing_and_never_records_success(world, publications):
    with pytest.raises(RuntimeError), transaction.atomic():
        office(world)
        raise RuntimeError("synthetic rollback")
    assert publications == []
    assert not GuidanceThread.objects.exists() and not GuidanceMessage.objects.exists()


def test_read_state_hint_is_only_for_readers_own_sessions(world, publications):
    thread, _ = office(world)
    publications.clear()
    services.mark_read(actor=world.student, thread_id=thread.pk, sequence=1)
    assert publications == [
        (
            protocol.user_channel(world.student.pk),
            {"v": 1, "type": "messages.thread_changed", "thread_id": str(thread.pk)},
        )
    ]
    publications.clear()
    services.mark_read(actor=world.student, thread_id=thread.pk, sequence=0)
    assert publications == []


@pytest.mark.parametrize("operation", ["create", "send", "resolve", "reopen", "assign", "read"])
def test_actual_redis_connection_failure_never_undoes_writes(
    world, settings, monkeypatch, operation
):
    settings.REALTIME_ENABLED = False
    thread, _ = office(world)
    if operation == "reopen":
        services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    # A real refused TCP connection, independent of the CI Redis service used by other suites.
    failing = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1)
    monkeypatch.setattr(publish, "realtime_redis", lambda: failing)
    settings.REALTIME_ENABLED = True
    if operation == "create":
        result = counseling(world)[0]
    elif operation == "send":
        result = services.send_message(
            actor=world.student, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    elif operation in ["resolve", "reopen"]:
        result = services.set_status(
            actor=world.counselor, thread_id=thread.pk, resolved=operation == "resolve"
        )
    elif operation == "assign":
        result = services.assign_handler(
            actor=world.counselor, thread_id=thread.pk, handler_id=world.gss.pk
        )
    else:
        result = services.mark_read(actor=world.student, thread_id=thread.pk, sequence=1)
    assert type(result).objects.filter(pk=result.pk).exists()
    thread.refresh_from_db()
    if operation == "send":
        assert thread.last_sequence == 2
    if operation == "resolve":
        assert thread.status == "RESOLVED"
    if operation == "reopen":
        assert thread.status == "OPEN"
    if operation == "assign":
        assert thread.assigned_to_id == world.gss.pk


@pytest.mark.parametrize("kind", ["OFFICE", "COUNSELING"])
def test_real_sockets_authenticated_http_commits_and_private_read_freshness(world, settings, kind):
    settings.REALTIME_ENABLED = True
    connection._client.cache_clear()
    users = [
        world.student,
        world.student,
        world.counselor,
        world.gss,
        world.other_student,
        world.head,
        world.head_gss,
    ]
    clients = [auth_client(user) for user in users]

    async def database_call(function, *args, **kwargs):
        def call():
            try:
                return function(*args, **kwargs)
            finally:
                connections.close_all()

        return await asyncio.to_thread(call)

    async def proof(app, _redis):
        sockets = []
        try:
            for client in clients:
                ticket = await database_call(issue, client)
                assert ticket.status_code == 200, ticket.content
                socket = Socket(app)
                sockets.append(socket)
                await socket.ready(ticket.json()["ticket"])
            path = (
                "/office-thread"
                if kind == "OFFICE"
                else f"/appointments/{world.appointment.pk}/counseling-thread"
            )
            idempotency = redis.Redis.from_url(settings.REDIS_IDEMPOTENCY_URL)
            before = set(idempotency.scan_iter())
            response = await database_call(
                post, clients[0], path, {"body": BODY, "client_message_id": str(uuid4())}
            )
            assert response.status_code == 200, response.content
            thread_id = response.json()["thread"]["id"]
            frame = {"v": 1, "type": "messages.thread_changed", "thread_id": thread_id}
            recipients = 4 if kind == "OFFICE" else 3
            for socket in sockets[:recipients]:
                assert json.loads((await socket.next())["text"]) == frame
            for socket in sockets[recipients:]:
                await socket.nothing()
            assert set(idempotency.scan_iter()) == before
            reply = await database_call(
                post,
                clients[2],
                f"/threads/{thread_id}/messages",
                {"body": "Synthetic staff reply", "client_message_id": str(uuid4())},
            )
            assert reply.status_code == 200, reply.content
            for socket in sockets[:recipients]:
                assert json.loads((await socket.next())["text"]) == frame
            for socket in sockets[recipients:]:
                await socket.nothing()
            history = await database_call(clients[0].get, f"{BASE}/threads/{thread_id}/messages")
            assert [item["body"] for item in history.json()["items"]] == [
                BODY,
                "Synthetic staff reply",
            ]
            read = await database_call(
                clients[0].patch,
                f"{BASE}/threads/{thread_id}/read",
                data=json.dumps({"sequence": 2}),
                content_type="application/json",
            )
            assert read.status_code == 200
            for socket in sockets[:2]:
                assert json.loads((await socket.next())["text"]) == frame
            for socket in sockets[2:]:
                await socket.nothing()
        finally:
            for socket in sockets:
                await socket.disconnect()

    try:
        run(proof)
    finally:
        connection._client.cache_clear()


def test_commit_time_supervision_changes_do_not_signal_revoked_staff(world, publications):
    from compass.organization.models import StaffSupervision

    with transaction.atomic():
        thread, _ = office(world)
        StaffSupervision.objects.filter(staff=world.gss).delete()
    assert {channel for channel, _ in publications} == {
        protocol.user_channel(world.student.pk),
        protocol.user_channel(world.counselor.pk),
    }
    assert all(frame["thread_id"] == str(thread.pk) for _, frame in publications)
