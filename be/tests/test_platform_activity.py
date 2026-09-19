from __future__ import annotations

from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.actions import (
    COUNSELING_ENCOUNTER_CREATED,
    NOTIFICATION_EMAIL_RETRY_REQUESTED,
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
    REFERRAL_CREATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.authentication.sessions import create_auth_session


TECHNICAL_ACTIONS = {
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    NOTIFICATION_EMAIL_RETRY_REQUESTED,
}


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str = "IT_ADMIN") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Technical",
        last_name="Operator",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def record_technical(
    *,
    actor: User,
    action: str,
    occurred_at,
    target_type: str = "platform.maintenance",
    target_id: str = "1",
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    return record_event(
        context=AuditContext.user(actor),
        action=action,
        outcome="SUCCESS",
        target_type=target_type,
        target_id=target_id,
        occurred_at=occurred_at,
        metadata=metadata or {},
    )


@pytest.mark.django_db
def test_platform_activity_requires_view_capability():
    sync_policy()
    student = make_user("activity-student@example.edu", "STUDENT")
    assert Client().get("/api/v1/platform/activity").status_code == 401
    assert auth_client(student).get("/api/v1/platform/activity").status_code == 403


@pytest.mark.django_db
def test_platform_activity_is_strict_curated_projection_not_global_audit_browser():
    sync_policy()
    admin = make_user("activity-admin@example.edu")
    actor = make_user("activity-actor@example.edu")
    now = timezone.now()

    included = [
        record_technical(
            actor=actor,
            action=PLATFORM_MAINTENANCE_ENABLED,
            occurred_at=now,
            metadata={"internal_note": "SENTINEL_METADATA_MUST_NOT_LEAK"},
        ),
        record_technical(
            actor=actor,
            action=PLATFORM_MAINTENANCE_SCHEDULED,
            occurred_at=now - timedelta(minutes=1),
        ),
        record_technical(
            actor=actor,
            action=NOTIFICATION_EMAIL_RETRY_REQUESTED,
            occurred_at=now - timedelta(minutes=2),
            target_type="notifications.emaildelivery",
            target_id=str(uuid4()),
            metadata={
                "previous_failure_code": "transport_error",
                "attempt_count": 4,
                "event_code": "call_slip.issued",
                "internal_note": "SENTINEL_PRIVATE_RECIPIENT@example.edu",
            },
        ),
    ]
    record_event(
        context=AuditContext.user(actor),
        action=COUNSELING_ENCOUNTER_CREATED,
        outcome="SUCCESS",
        target_type="counseling.encounter",
        target_id=uuid4(),
        occurred_at=now - timedelta(minutes=3),
        metadata={},
    )
    record_event(
        context=AuditContext.user(actor),
        action=REFERRAL_CREATED,
        outcome="SUCCESS",
        target_type="referral.record",
        target_id=uuid4(),
        occurred_at=now - timedelta(minutes=4),
        metadata={},
    )
    record_event(
        context=AuditContext.user(actor),
        action="identity.policy.synced",
        outcome="SUCCESS",
        occurred_at=now - timedelta(minutes=5),
        metadata={},
    )

    response = auth_client(admin).get("/api/v1/platform/activity")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(item.id) for item in included]
    assert {item["type"] for item in body["items"]} <= TECHNICAL_ACTIONS
    assert body["items"][0]["actor_type"] == "USER"
    assert body["items"][0]["actor_display_name"] == "Technical Operator"

    serialized = response.content.decode()
    assert "metadata" not in serialized
    assert "SENTINEL_METADATA_MUST_NOT_LEAK" not in serialized
    assert "SENTINEL_PRIVATE_RECIPIENT@example.edu" not in serialized
    assert actor.email not in serialized
    assert "counseling" not in serialized.lower()
    assert "referral" not in serialized.lower()
    assert "identity.policy.synced" not in serialized


@pytest.mark.django_db
def test_platform_activity_presenters_render_safe_code_owned_descriptions():
    sync_policy()
    admin = make_user("presenter-admin@example.edu")
    actor = make_user("presenter-actor@example.edu")
    now = timezone.now()
    delivery_id = uuid4()

    record_technical(
        actor=actor,
        action=PLATFORM_MAINTENANCE_ENABLED,
        occurred_at=now,
    )
    record_technical(
        actor=actor,
        action=PLATFORM_MAINTENANCE_DISABLED,
        occurred_at=now - timedelta(seconds=1),
    )
    record_technical(
        actor=actor,
        action=PLATFORM_MAINTENANCE_SCHEDULED,
        occurred_at=now - timedelta(seconds=2),
    )
    record_technical(
        actor=actor,
        action=PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
        occurred_at=now - timedelta(seconds=3),
    )
    record_technical(
        actor=actor,
        action=NOTIFICATION_EMAIL_RETRY_REQUESTED,
        occurred_at=now - timedelta(seconds=4),
        target_type="notifications.emaildelivery",
        target_id=str(delivery_id),
        metadata={"previous_failure_code": "transport_error"},
    )

    response = auth_client(admin).get("/api/v1/platform/activity")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["title"] for item in items] == [
        "Maintenance Mode enabled",
        "Maintenance Mode disabled",
        "Maintenance scheduled",
        "Maintenance schedule cancelled",
        "Email delivery retry requested",
    ]
    assert str(delivery_id) in items[-1]["description"]
    assert "transport_error" not in items[-1]["description"]


@pytest.mark.django_db
def test_platform_activity_pagination_is_bounded_and_deterministically_newest_first():
    sync_policy()
    admin = make_user("pagination-admin@example.edu")
    actor = make_user("pagination-actor@example.edu")
    base = timezone.now()
    events = [
        record_technical(
            actor=actor,
            action=PLATFORM_MAINTENANCE_ENABLED,
            occurred_at=base - timedelta(minutes=index),
        )
        for index in range(4)
    ]
    client = auth_client(admin)

    first = client.get("/api/v1/platform/activity?page=1&page_size=2")
    second = client.get("/api/v1/platform/activity?page=2&page_size=2")
    invalid = client.get("/api/v1/platform/activity?page_size=51")

    assert first.status_code == second.status_code == 200
    assert first.json()["has_next"] is True
    assert second.json()["has_next"] is False
    assert [item["id"] for item in first.json()["items"]] == [
        str(events[0].id),
        str(events[1].id),
    ]
    assert [item["id"] for item in second.json()["items"]] == [
        str(events[2].id),
        str(events[3].id),
    ]
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_pagination"


@pytest.mark.django_db
def test_registered_action_with_wrong_target_or_malformed_delivery_id_fails_closed():
    sync_policy()
    admin = make_user("fail-closed-admin@example.edu")
    actor = make_user("fail-closed-actor@example.edu")
    now = timezone.now()

    record_technical(
        actor=actor,
        action=PLATFORM_MAINTENANCE_ENABLED,
        occurred_at=now,
        target_type="platform.other",
        target_id="1",
    )
    record_technical(
        actor=actor,
        action=NOTIFICATION_EMAIL_RETRY_REQUESTED,
        occurred_at=now - timedelta(seconds=1),
        target_type="notifications.emaildelivery",
        target_id="not-a-uuid",
    )

    response = auth_client(admin).get("/api/v1/platform/activity")

    assert response.status_code == 200
    assert response.json()["items"] == []
