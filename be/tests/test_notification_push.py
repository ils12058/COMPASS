from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone
from pywebpush import WebPushException

from compass.accounts.models import Role, User
from compass.authentication.sessions import create_auth_session
from compass.notifications.models import (
    Notification,
    PushDelivery,
    PushDeliveryStatus,
    PushSubscription,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.push import (
    deliver_push_delivery,
    due_push_delivery_ids,
    register_subscription,
)
from compass.notifications.push_policy import PUSH_POLICY, PushDecision, push_body_for
from compass.notifications.services import create_notification_for_event

STORAGE_KEY = Fernet.generate_key().decode()
PUSH_SETTINGS = override_settings(
    WEB_PUSH_ENABLED=True,
    WEB_PUSH_PUBLIC_KEY="test-public-key",
    WEB_PUSH_PRIVATE_KEY="test-private-key",
    WEB_PUSH_CONTACT="mailto:ops@example.edu",
    WEB_PUSH_STORAGE_KEY=STORAGE_KEY,
)


def user(email: str, *, active=True) -> User:
    role, _ = Role.objects.get_or_create(code="STUDENT", defaults={"name": "Student"})
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=role,
        first_name="Synthetic",
        last_name="Student",
        is_active=active,
    )


def client_for(account: User):
    issued = create_auth_session(account, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client, issued.session


def payload(endpoint: str):
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": base64.urlsafe_b64encode(b"\x04" + b"p" * 64).decode().rstrip("="),
            "auth": base64.urlsafe_b64encode(b"a" * 16).decode().rstrip("="),
        },
    }


def event(account, code=NotificationEvent.CALL_SLIP_ISSUED):
    return create_notification_for_event(
        recipient=account, event=code, source_type="test", source_id=uuid4()
    )


@PUSH_SETTINGS
@pytest.mark.django_db
def test_push_api_is_self_only_idempotent_and_supports_multiple_devices():
    owner, other = user("push-owner@example.edu"), user("push-other@example.edu")
    client, session = client_for(owner)
    other_client, _ = client_for(other)
    first = payload("https://fcm.googleapis.com/fcm/send/first")
    second = payload("https://web.push.apple.com/example/second")

    assert (
        Client()
        .post(
            "/api/v1/notifications/push/subscription",
            data=json.dumps(first),
            content_type="application/json",
        )
        .status_code
        == 401
    )
    assert client.get("/api/v1/notifications/push/config").json()["public_key"] == "test-public-key"
    assert (
        client.post(
            "/api/v1/notifications/push/subscription",
            data=json.dumps(first),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/notifications/push/subscription",
            data=json.dumps(first),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/notifications/push/subscription",
            data=json.dumps(second),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert PushSubscription.objects.filter(user=owner, active=True).count() == 2
    assert PushSubscription.objects.filter(session=session).count() == 2
    item = event(owner)
    assert PushDelivery.objects.filter(notification=item).count() == 2
    assert (
        first["endpoint"]
        not in PushSubscription.objects.filter(user=owner).first().encrypted_endpoint
    )

    status = other_client.post(
        "/api/v1/notifications/push/status",
        data=json.dumps({"endpoint": first["endpoint"]}),
        content_type="application/json",
    )
    assert status.json()["enabled_on_this_device"] is False
    other_client.delete(
        "/api/v1/notifications/push/subscription",
        data=json.dumps({"endpoint": first["endpoint"]}),
        content_type="application/json",
    )
    assert PushSubscription.objects.filter(user=owner, active=True).count() == 2
    removed = client.delete(
        "/api/v1/notifications/push/subscription",
        data=json.dumps({"endpoint": first["endpoint"]}),
        content_type="application/json",
    )
    assert removed.status_code == 200
    assert PushSubscription.objects.filter(user=owner, active=True).count() == 1
    assert (
        PushDelivery.objects.filter(notification=item, status=PushDeliveryStatus.CANCELLED).count()
        == 1
    )


@PUSH_SETTINGS
@pytest.mark.django_db
def test_same_browser_switching_accounts_cannot_push_old_users_records(monkeypatch):
    first, second = user("push-switch-first@example.edu"), user("push-switch-second@example.edu")
    _client, first_session = client_for(first)
    _other_client, second_session = client_for(second)
    data = payload("https://fcm.googleapis.com/fcm/send/shared-browser")
    register_subscription(
        user=first, session=first_session, endpoint=data["endpoint"], **data["keys"]
    )
    old_item = event(first)
    old_delivery = PushDelivery.objects.get(notification=old_item)
    register_subscription(
        user=second, session=second_session, endpoint=data["endpoint"], **data["keys"]
    )
    monkeypatch.setattr(
        "compass.notifications.push._send",
        lambda *_args: pytest.fail("must not send old account data"),
    )
    old_delivery.refresh_from_db()
    assert old_delivery.status == PushDeliveryStatus.CANCELLED
    assert deliver_push_delivery(old_delivery.pk) == "skipped"
    assert PushSubscription.objects.filter(user=first, active=True).count() == 0
    assert PushSubscription.objects.filter(user=second, active=True).count() == 1


@PUSH_SETTINGS
@pytest.mark.django_db
def test_invalid_push_endpoints_and_keys_are_rejected():
    client, _ = client_for(user("push-invalid@example.edu"))
    for endpoint in (
        "http://127.0.0.1/secret",
        "https://example.org/push",
        "https://fcm.googleapis.com:123/push",
        "https://[bad",
    ):
        bad = payload(endpoint)
        assert (
            client.post(
                "/api/v1/notifications/push/subscription",
                data=json.dumps(bad),
                content_type="application/json",
            ).status_code
            == 422
        )
    bad = payload("https://fcm.googleapis.com/fcm/send/bad")
    bad["keys"]["auth"] = "not-valid"
    assert (
        client.post(
            "/api/v1/notifications/push/subscription",
            data=json.dumps(bad),
            content_type="application/json",
        ).status_code
        == 422
    )
    assert PushSubscription.objects.count() == 0


@pytest.mark.django_db
def test_disabled_push_keeps_notification_api_usable_without_exposing_keys():
    client, _ = client_for(user("push-disabled@example.edu"))
    config = client.get("/api/v1/notifications/push/config")
    assert config.status_code == 200
    assert config.json() == {"enabled": False, "public_key": ""}
    response = client.post(
        "/api/v1/notifications/push/subscription",
        data=json.dumps(payload("https://fcm.googleapis.com/fcm/send/disabled")),
        content_type="application/json",
    )
    assert response.status_code == 503
    assert client.get("/api/v1/notifications/unread-count").status_code == 200


@PUSH_SETTINGS
@pytest.mark.django_db
def test_push_policy_is_complete_and_only_safe_generic_data_is_sent(monkeypatch):
    assert set(PUSH_POLICY) == set(NotificationEvent)
    assert PUSH_POLICY[NotificationEvent.FEEDBACK_INVITATION][0] == PushDecision.IN_APP_ONLY
    account = user("push-policy@example.edu")
    _client, session = client_for(account)
    data = payload("https://fcm.googleapis.com/fcm/send/policy")
    register_subscription(user=account, session=session, endpoint=data["endpoint"], **data["keys"])
    sent = []
    monkeypatch.setattr("compass.notifications.push.webpush", lambda **kwargs: sent.append(kwargs))
    created = event(account)
    delivery = PushDelivery.objects.get(notification=created)
    assert deliver_push_delivery(delivery.pk) == PushDeliveryStatus.SENT
    body = json.loads(sent[0]["data"])
    assert body == {
        "title": "COMPASS",
        "body": "You have a new Call Slip.",
        "path": "/portal/notifications",
    }
    assert "test-private-key" not in sent[0]["data"]
    assert "p256dh" not in sent[0]["data"]
    assert event(account, NotificationEvent.FEEDBACK_INVITATION)
    assert PushDelivery.objects.count() == 1
    assert push_body_for("unrecognized") is None


@PUSH_SETTINGS
@pytest.mark.django_db
def test_delivery_failure_is_bounded_gone_subscription_retired_and_inactive_user_skipped(
    monkeypatch,
):
    account = user("push-failure@example.edu")
    _client, session = client_for(account)
    data = payload("https://updates.push.services.mozilla.com/wpush/v2/failure")
    sub = register_subscription(
        user=account, session=session, endpoint=data["endpoint"], **data["keys"]
    )
    monkeypatch.setattr(
        "compass.notifications.push.webpush",
        lambda **_kwargs: (_ for _ in ()).throw(
            WebPushException("gone", response=SimpleNamespace(status_code=410))
        ),
    )
    item = event(account)
    delivery = PushDelivery.objects.get(notification=item)
    assert deliver_push_delivery(delivery.pk) == PushDeliveryStatus.CANCELLED
    sub.refresh_from_db()
    assert not sub.active
    assert Notification.objects.filter(pk=item.pk).exists()

    sub.active = True
    sub.save(update_fields=["active"])
    account.is_active = False
    account.save(update_fields=["is_active"])
    next_item = event(account)
    assert not PushDelivery.objects.filter(notification=next_item).exists()


@PUSH_SETTINGS
@pytest.mark.django_db
def test_revoked_session_cancels_pending_push_without_touching_notification(monkeypatch):
    account = user("push-logout@example.edu")
    _client, session = client_for(account)
    data = payload("https://fcm.googleapis.com/fcm/send/logout")
    register_subscription(user=account, session=session, endpoint=data["endpoint"], **data["keys"])
    item = event(account)
    delivery = PushDelivery.objects.get(notification=item)
    monkeypatch.setattr(
        "compass.notifications.push._send", lambda *_args: pytest.fail("must not send")
    )
    # Any session revocation path makes this subscription ineligible.
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])
    assert deliver_push_delivery(delivery.pk) == PushDeliveryStatus.CANCELLED
    assert Notification.objects.filter(pk=item.pk).exists()


@PUSH_SETTINGS
@pytest.mark.django_db
def test_transient_push_retries_stop_and_expired_claim_is_recovered(monkeypatch):
    account = user("push-retry@example.edu")
    _client, session = client_for(account)
    data = payload("https://fcm.googleapis.com/fcm/send/retry")
    register_subscription(user=account, session=session, endpoint=data["endpoint"], **data["keys"])
    item = event(account)
    delivery = PushDelivery.objects.get(notification=item)
    monkeypatch.setattr(
        "compass.notifications.push._send",
        lambda *_args: (_ for _ in ()).throw(
            WebPushException("unavailable", response=SimpleNamespace(status_code=503))
        ),
    )
    for attempt in range(1, 4):
        PushDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
        result = deliver_push_delivery(delivery.pk)
        delivery.refresh_from_db()
        assert delivery.attempt_count == attempt
        assert result == (PushDeliveryStatus.PENDING if attempt < 3 else PushDeliveryStatus.FAILED)
    assert delivery.pk not in due_push_delivery_ids()
    assert Notification.objects.filter(pk=item.pk).exists()


@PUSH_SETTINGS
@pytest.mark.django_db
def test_push_setup_error_cannot_roll_back_durable_notification(monkeypatch):
    account = user("push-setup@example.edu")
    monkeypatch.setattr(
        "compass.notifications.services.create_push_deliveries",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("transport setup failed")),
    )
    with transaction.atomic():
        item = event(account)
    assert Notification.objects.filter(pk=item.pk).exists()
    assert PushDelivery.objects.filter(notification=item).count() == 0
