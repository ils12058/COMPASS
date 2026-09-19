from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.authentication.sessions import create_auth_session
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.notifications.policy import (
    _EVENT_CATALOG,
    NotificationChannel,
    NotificationEvent,
    NotificationPolicy,
    email_allowed_for_policy,
)



def test_notification_event_catalog_is_complete_renderable_and_privacy_safe():
    assert set(_EVENT_CATALOG) == set(NotificationEvent)
    sensitive_sentinels = (
        "COUNSELING-SENSITIVE-SENTINEL",
        "REFERRAL-REASON-SENTINEL",
        "EXIT-ANSWER-SENTINEL",
        "GOOD-MORAL-RECEIPT-SENTINEL",
        "REPORT-DATA-SENTINEL",
        "OTP-123456",
        "RECOVERY-CODE-SENTINEL",
        "PASSWORD-SENTINEL",
        "DAILY-ROOM-TOKEN-SENTINEL",
        "SESSION-ID-SENTINEL",
        "AUDIT-METADATA-SENTINEL",
        "OVERRIDE-REASON-SENTINEL",
    )

    for event in NotificationEvent:
        definition = _EVENT_CATALOG[event]
        assert definition.event == event
        assert definition.policy in NotificationPolicy
        assert NotificationChannel.IN_APP in definition.channels
        if NotificationChannel.EMAIL not in definition.channels:
            continue

        rendered = render_notification_email(event.value)
        combined = "\n".join(
            (rendered.subject, rendered.text_body, rendered.html_body)
        )
        assert rendered.text_body.strip()
        assert rendered.html_body.strip()
        assert "http://" not in combined
        assert "https://" not in combined
        for sentinel in sensitive_sentinels:
            assert sentinel not in combined



def make_user(email: str, role_code: str = "STUDENT") -> User:
    role, _created = Role.objects.get_or_create(
        code=role_code,
        defaults={"name": role_code.replace("_", " ").title()},
    )
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=role,
        first_name="Synthetic",
        last_name="User",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_notification(
    recipient: User,
    *,
    event_code: str = "call_slip.issued",
    source_id=None,
) -> Notification:
    identifier = source_id or uuid4()
    return Notification.objects.create(
        recipient=recipient,
        event_code=event_code,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        title="New Call Slip",
        message="A Call Slip has been issued to you. Open COMPASS to review the details.",
        source_type="call_slip",
        source_id=identifier,
        target_type="CALL_SLIP",
        target_id=identifier,
    )


@pytest.mark.django_db
def test_notification_model_has_uuid_identity_safe_source_target_and_durable_dedupe():
    user = make_user("notification-model@example.edu")
    source_id = uuid4()
    item = make_notification(user, source_id=source_id)

    assert item.pk.version == 4
    assert item.recipient_id == user.pk
    assert item.event_code == "call_slip.issued"
    assert item.policy == NotificationPolicy.MANDATORY_OPERATIONAL
    assert item.source_type == "call_slip"
    assert item.source_id == source_id
    assert item.target_type == "CALL_SLIP"
    assert item.target_id == source_id
    assert item.read_at is None
    assert item.is_read is False
    assert "metadata" not in {field.name for field in Notification._meta.get_fields()}

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            make_notification(user, source_id=source_id)


@pytest.mark.django_db
def test_optional_email_preference_defaults_true_and_policy_classes_are_code_owned():
    user = make_user("preference-default@example.edu")

    assert NotificationPreference.objects.filter(user=user).exists() is False
    from compass.notifications.services import optional_email_enabled_for

    assert optional_email_enabled_for(user) is True
    assert (
        email_allowed_for_policy(
            NotificationPolicy.MANDATORY_SECURITY,
            optional_email_enabled=False,
        )
        is True
    )
    assert (
        email_allowed_for_policy(
            NotificationPolicy.MANDATORY_OPERATIONAL,
            optional_email_enabled=False,
        )
        is True
    )
    assert (
        email_allowed_for_policy(
            NotificationPolicy.OPTIONAL_INFORMATIONAL,
            optional_email_enabled=False,
        )
        is False
    )


@pytest.mark.django_db
def test_notification_self_service_list_unread_mark_read_and_ownership():
    owner = make_user("notification-owner@example.edu")
    other = make_user("notification-other@example.edu")
    older = make_notification(owner)
    newer = make_notification(owner)
    other_item = make_notification(other)
    now = timezone.now()
    Notification.objects.filter(pk=older.pk).update(created_at=now - timedelta(minutes=2))
    Notification.objects.filter(pk=newer.pk).update(created_at=now - timedelta(minutes=1))

    client = auth_client(owner)
    page = client.get("/api/v1/notifications", {"page": 1, "page_size": 1})
    assert page.status_code == 200
    assert [row["id"] for row in page.json()["items"]] == [str(newer.pk)]
    assert page.json()["has_next"] is True
    assert str(other_item.pk) not in page.content.decode()

    unread = client.get("/api/v1/notifications/unread-count")
    assert unread.status_code == 200
    assert unread.json()["unread_count"] == 2

    first = client.patch(
        f"/api/v1/notifications/{newer.pk}/read",
        data="{}",
        content_type="application/json",
    )
    assert first.status_code == 200
    first_read_at = first.json()["read_at"]
    assert first.json()["is_read"] is True

    repeated = client.patch(
        f"/api/v1/notifications/{newer.pk}/read",
        data="{}",
        content_type="application/json",
    )
    assert repeated.status_code == 200
    assert repeated.json()["read_at"] == first_read_at
    assert client.get("/api/v1/notifications/unread-count").json()["unread_count"] == 1

    denied = client.patch(
        f"/api/v1/notifications/{other_item.pk}/read",
        data="{}",
        content_type="application/json",
    )
    assert denied.status_code == 404
    other_item.refresh_from_db()
    assert other_item.read_at is None

    assert Client().get("/api/v1/notifications").status_code == 401


@pytest.mark.django_db
def test_notification_list_pagination_is_bounded():
    user = make_user("notification-page@example.edu")
    make_notification(user)

    client = auth_client(user)
    assert client.get("/api/v1/notifications", {"page": 0}).status_code == 422
    assert client.get("/api/v1/notifications", {"page_size": 51}).status_code == 422


@pytest.mark.django_db
def test_preference_api_is_self_only_and_does_not_mutate_mandatory_delivery():
    owner = make_user("preference-owner@example.edu")
    other = make_user("preference-other@example.edu")
    mandatory = make_notification(owner)
    delivery = EmailDelivery.objects.create(notification=mandatory)

    client = auth_client(owner)
    default = client.get("/api/v1/notifications/preferences")
    assert default.status_code == 200
    assert default.json()["optional_email_enabled"] is True

    disabled = client.patch(
        "/api/v1/notifications/preferences",
        data=json.dumps({"optional_email_enabled": False}),
        content_type="application/json",
    )
    assert disabled.status_code == 200
    assert disabled.json()["optional_email_enabled"] is False
    assert NotificationPreference.objects.get(user=owner).optional_email_enabled is False
    assert NotificationPreference.objects.filter(user=other).exists() is False

    delivery.refresh_from_db()
    assert delivery.status == "PENDING"

    enabled = client.patch(
        "/api/v1/notifications/preferences",
        data=json.dumps({"optional_email_enabled": True}),
        content_type="application/json",
    )
    assert enabled.status_code == 200
    assert enabled.json()["optional_email_enabled"] is True
