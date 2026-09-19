from __future__ import annotations

import json
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command

from compass.accounts.models import Role, User
from compass.audit.actions import (
    NOTIFICATION_EMAIL_RETRY_REQUESTED,
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
)
from compass.audit.context import AuditContext
from compass.audit.metadata import validate_metadata
from compass.audit.models import ACTION_RE, AuditEvent
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.notifications.policy import NotificationPolicy
from compass.platform_ops.email_operations import retry_email_delivery
from compass.platform_ops.services import enable_manual_maintenance


RUNTIME_ACTIONS = (
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    NOTIFICATION_EMAIL_RETRY_REQUESTED,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code="STUDENT"),
        first_name="Audit",
        last_name="Target",
    )


@pytest.mark.parametrize("action", RUNTIME_ACTIONS)
def test_runtime_operation_action_codes_match_canonical_audit_format(action):
    assert ACTION_RE.fullmatch(action)


def test_runtime_audit_metadata_keys_remain_compatible_with_sensitive_key_restrictions():
    assert validate_metadata(
        {
            "expected_end_at": "2026-09-19T20:00:00+08:00",
            "starts_at": "2026-09-19T21:00:00+08:00",
            "ends_at": "2026-09-19T22:00:00+08:00",
            "previous_failure_code": "transport_error",
            "attempt_count": 3,
            "event_code": "call_slip.issued",
        }
    )
    with pytest.raises(ValueError):
        validate_metadata({"recipient_password": "must-not-enter-audit"})


@pytest.mark.django_db
def test_maintenance_message_never_enters_runtime_audit_metadata():
    sentinel = "SENTINEL PRIVATE MAINTENANCE OPERATOR MESSAGE"
    enable_manual_maintenance(
        message=sentinel,
        expected_end_at=None,
        context=AuditContext.system(),
    )

    event = AuditEvent.objects.get(action=PLATFORM_MAINTENANCE_ENABLED)
    assert sentinel not in json.dumps(event.metadata)
    assert event.metadata == {}


@pytest.mark.django_db
def test_email_retry_audit_excludes_recipient_and_notification_content():
    sync_policy()
    sentinel_email = "SENTINEL-PRIVATE-RECIPIENT@example.edu"
    sentinel_title = "SENTINEL PRIVATE TITLE"
    sentinel_message = "SENTINEL PRIVATE EMAIL CONTENT"
    recipient = make_user(sentinel_email)
    notification = Notification.objects.create(
        recipient=recipient,
        event_code="call_slip.issued",
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        title=sentinel_title,
        message=sentinel_message,
        source_type="call_slip",
        source_id=uuid4(),
        target_type="CALL_SLIP",
        target_id=uuid4(),
    )
    delivery = EmailDelivery.objects.create(
        notification=notification,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
        attempt_count=4,
        next_attempt_at=None,
    )

    retry_email_delivery(
        delivery_id=delivery.pk,
        context=AuditContext.system(),
    )

    event = AuditEvent.objects.get(action=NOTIFICATION_EMAIL_RETRY_REQUESTED)
    serialized = json.dumps(event.metadata)
    assert sentinel_email not in serialized
    assert sentinel_title not in serialized
    assert sentinel_message not in serialized
    assert event.metadata == {
        "previous_failure_code": "transport_error",
        "attempt_count": 4,
        "event_code": "call_slip.issued",
    }
