"""Notification commit truth and the real Redis/socket/HTTP path (ADR-101)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
import redis
from django.db import connections, transaction

from compass.notifications import services
from compass.notifications.models import Notification
from compass.realtime import connection, publish
from realtime_service import protocol
from tests.test_notifications import auth_client, make_notification, make_user
from tests.test_realtime_service import Socket, run
from tests.test_realtime_tickets import issue

FRAME = '{"v":1,"type":"notifications.changed"}'


@pytest.fixture
def publications(settings, monkeypatch):
    settings.REALTIME_ENABLED = True
    messages = []

    class Publisher:
        failing = False

        def publish(self, channel, payload):
            if self.failing:
                raise redis.ConnectionError("synthetic Redis outage")
            messages.append((channel, payload))

    publisher = Publisher()
    monkeypatch.setattr(publish, "realtime_redis", lambda: publisher)
    # Delivery dispatch is independent of the hint; keep this proof local.
    monkeypatch.setattr(services, "_safe_kick_email_delivery", lambda value: None)
    monkeypatch.setattr(services, "_safe_kick_push_delivery", lambda value: None)
    return messages, publisher


def create(recipient, source_id=None):
    return services.create_notification_for_event(
        recipient=recipient,
        event="call_slip.issued",
        source_type="call_slip",
        source_id=source_id or uuid4(),
    )


@pytest.mark.django_db(transaction=True)
def test_new_notification_publishes_only_after_commit_and_duplicate_emits_nothing(publications):
    messages, _ = publications
    recipient = make_user("new-hint@example.edu")
    source = uuid4()
    with transaction.atomic():
        notification = create(recipient, source)
        assert Notification.objects.filter(pk=notification.pk).exists()
        assert messages == []
    assert messages == [(protocol.user_channel(recipient.pk), FRAME)]
    assert create(recipient, source).pk == notification.pk
    assert len(messages) == 1


@pytest.mark.django_db(transaction=True)
def test_read_transition_publishes_once_and_preserves_read_at(publications):
    messages, _ = publications
    recipient = make_user("read-hint@example.edu")
    item = make_notification(recipient)
    with transaction.atomic():
        read = services.mark_my_notification_read(actor=recipient, notification_id=item.pk)
        assert read.read_at is not None
        assert messages == []
    assert messages == [(protocol.user_channel(recipient.pk), FRAME)]
    repeated = services.mark_my_notification_read(actor=recipient, notification_id=item.pk)
    assert repeated.read_at == read.read_at
    assert len(messages) == 1
    other = make_user("wrong-hint@example.edu")
    for missing in (item.pk, uuid4()):
        with pytest.raises(services.NotificationNotFound):
            services.mark_my_notification_read(actor=other, notification_id=missing)
    assert len(messages) == 1


@pytest.mark.django_db(transaction=True)
def test_mark_all_emits_one_hint_for_n_rows_and_none_for_zero(publications):
    messages, _ = publications
    recipient = make_user("all-hint@example.edu")
    other = make_user("other-all-hint@example.edu")
    for _ in range(3):
        make_notification(recipient)
    other_item = make_notification(other)
    with transaction.atomic():
        assert services.mark_all_my_notifications_read(actor=recipient) == 3
        assert messages == []
    assert messages == [(protocol.user_channel(recipient.pk), FRAME)]
    assert services.unread_count_for(actor=recipient) == 0
    assert services.mark_all_my_notifications_read(actor=recipient) == 0
    assert len(messages) == 1
    other_item.refresh_from_db()
    assert other_item.read_at is None


def mutate(operation, recipient, item):
    if operation == "create":
        return create(recipient)
    if operation == "read":
        return services.mark_my_notification_read(actor=recipient, notification_id=item.pk)
    return services.mark_all_my_notifications_read(actor=recipient)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("operation", ["create", "read", "all"])
def test_rollback_emits_nothing_and_keeps_database_truth(publications, operation):
    messages, _ = publications
    recipient = make_user(f"rollback-{operation}@example.edu")
    item = make_notification(recipient)
    with pytest.raises(RuntimeError), transaction.atomic():
        mutate(operation, recipient, item)
        assert messages == []
        raise RuntimeError("rollback")
    assert messages == []
    assert Notification.objects.filter(recipient=recipient).count() == 1
    item.refresh_from_db()
    assert item.read_at is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("operation", ["create", "read", "all"])
def test_redis_failure_cannot_undo_notification_writes(publications, operation):
    messages, publisher = publications
    publisher.failing = True
    recipient = make_user(f"outage-{operation}@example.edu")
    item = make_notification(recipient)
    result = mutate(operation, recipient, item)
    assert messages == []
    if operation == "create":
        assert Notification.objects.filter(pk=result.pk).exists()
    else:
        item.refresh_from_db()
        assert item.read_at is not None
        if operation == "all":
            assert result == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("operation", ["create", "read", "all"])
def test_disabled_transport_keeps_notification_writes_working(publications, settings, operation):
    messages, _ = publications
    settings.REALTIME_ENABLED = False
    recipient = make_user(f"disabled-{operation}@example.edu")
    item = make_notification(recipient)
    mutate(operation, recipient, item)
    assert messages == []
    assert Notification.objects.filter(recipient=recipient).count() == (
        2 if operation == "create" else 1
    )
    if operation != "create":
        item.refresh_from_db()
        assert item.read_at is not None


@pytest.mark.django_db(transaction=True)
def test_email_preference_is_not_an_in_app_change(publications):
    messages, _ = publications
    recipient = make_user("preference-hint@example.edu")
    services.update_my_notification_preference(actor=recipient, optional_email_enabled=False)
    assert messages == []


@pytest.mark.django_db(transaction=True)
def test_committed_notification_and_http_read_reach_only_recipient_sockets(settings, monkeypatch):
    """Real tickets, Redis, ASGI sockets, DB commits, and authenticated HTTP reads/writes."""
    settings.REALTIME_ENABLED = True
    connection._client.cache_clear()
    monkeypatch.setattr(services, "_safe_kick_email_delivery", lambda value: None)
    recipient = make_user("socket-notification@example.edu")
    other = make_user("socket-notification-other@example.edu")
    clients = [auth_client(recipient), auth_client(recipient), auth_client(other)]

    async def database_call(function, *args, **kwargs):
        def call():
            try:
                return function(*args, **kwargs)
            finally:
                connections.close_all()

        return await asyncio.to_thread(call)

    async def test(app, _redis):
        sockets = [Socket(app) for _ in clients]
        try:
            for socket, client in zip(sockets, clients, strict=True):
                response = await database_call(issue, client)
                assert response.status_code == 200
                await socket.ready(response.json()["ticket"])

            def committed_create():
                with transaction.atomic():
                    return create(recipient)

            item = await database_call(committed_create)
            for socket in sockets[:2]:
                assert await socket.next() == {"type": "websocket.send", "text": FRAME}
            await sockets[2].nothing()
            page = await database_call(clients[0].get, "/api/v1/notifications")
            count = await database_call(clients[0].get, "/api/v1/notifications/unread-count")
            assert page.status_code == count.status_code == 200
            assert [row["id"] for row in page.json()["items"]] == [str(item.pk)]
            assert count.json() == {"unread_count": 1}
            read = await database_call(
                clients[0].patch,
                f"/api/v1/notifications/{item.pk}/read",
                data="{}",
                content_type="application/json",
            )
            assert read.status_code == 200
            for socket in sockets[:2]:
                assert await socket.next() == {"type": "websocket.send", "text": FRAME}
            await sockets[2].nothing()
            count = await database_call(clients[1].get, "/api/v1/notifications/unread-count")
            assert count.json() == {"unread_count": 0}
            other_page = await database_call(clients[2].get, "/api/v1/notifications")
            assert other_page.json()["items"] == []
        finally:
            for socket in sockets:
                await socket.disconnect()

    try:
        run(test)
    finally:
        connection._client.cache_clear()
