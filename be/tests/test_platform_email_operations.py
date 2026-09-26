from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.integrations.mail import Mailer
from compass.notifications.delivery import due_email_delivery_ids
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.notifications.policy import NotificationPolicy
from compass.platform_ops.email_operations import (
    EmailDeliveryNotRetryable,
    retry_email_delivery,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str = "STUDENT", *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Delivery",
        last_name="User",
        is_active=active,
    )


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    issued = create_auth_session(
        user,
        mfa_verified_at=timezone.now() if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def make_delivery(
    recipient: User,
    *,
    status: str = EmailDeliveryStatus.PENDING,
    failure_code: str = "",
    attempt_count: int = 0,
    event_code: str = "call_slip.issued",
) -> EmailDelivery:
    notification = Notification.objects.create(
        recipient=recipient,
        event_code=event_code,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        title="SENTINEL NOTIFICATION TITLE",
        message="SENTINEL PRIVATE NOTIFICATION MESSAGE",
        source_type="call_slip",
        source_id=uuid4(),
        target_type="CALL_SLIP",
        target_id=uuid4(),
    )
    return EmailDelivery.objects.create(
        notification=notification,
        status=status,
        failure_code=failure_code,
        attempt_count=attempt_count,
        next_attempt_at=(timezone.now() if status == EmailDeliveryStatus.PENDING else None),
    )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_email_delivery_summary_counts_and_sent_today_use_application_timezone():
    sync_policy()
    admin = make_user("summary-admin@example.edu", "IT_ADMIN")
    recipient = make_user("summary-recipient@example.edu")
    now = timezone.now()

    pending_oldest = make_delivery(recipient, status=EmailDeliveryStatus.PENDING)
    pending_newer = make_delivery(recipient, status=EmailDeliveryStatus.PENDING)
    make_delivery(recipient, status=EmailDeliveryStatus.PROCESSING)
    make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
    )
    make_delivery(
        recipient,
        status=EmailDeliveryStatus.CANCELLED,
        failure_code="recipient_inactive",
    )
    sent_today = make_delivery(recipient, status=EmailDeliveryStatus.SENT)
    sent_yesterday = make_delivery(recipient, status=EmailDeliveryStatus.SENT)

    EmailDelivery.objects.filter(pk=pending_oldest.pk).update(
        created_at=now - timedelta(hours=5),
        next_attempt_at=now - timedelta(minutes=5),
    )
    EmailDelivery.objects.filter(pk=pending_newer.pk).update(
        created_at=now - timedelta(hours=1),
        next_attempt_at=now + timedelta(minutes=5),
    )
    EmailDelivery.objects.filter(pk=sent_today.pk).update(sent_at=now)
    local_today = timezone.localtime(now).date()
    local_tz = timezone.get_current_timezone()
    local_day_start = timezone.make_aware(datetime.combine(local_today, time.min), local_tz)
    EmailDelivery.objects.filter(pk=sent_yesterday.pk).update(
        sent_at=local_day_start - timedelta(seconds=1)
    )

    response = auth_client(admin).get("/api/v1/platform/email-deliveries/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["pending_count"] == 2
    assert body["processing_count"] == 1
    assert body["failed_count"] == 1
    assert body["cancelled_count"] == 1
    assert body["sent_today"] == 1
    assert body["due_pending_count"] == 1
    assert body["oldest_pending_at"] is not None


@pytest.mark.django_db
def test_email_delivery_summary_and_list_require_view_capability():
    sync_policy()
    student = make_user("delivery-student@example.edu")
    client = auth_client(student)

    assert Client().get("/api/v1/platform/email-deliveries/summary").status_code == 401
    assert client.get("/api/v1/platform/email-deliveries/summary").status_code == 403
    assert client.get("/api/v1/platform/email-deliveries").status_code == 403


@pytest.mark.django_db
def test_email_delivery_list_is_bounded_filterable_and_pii_safe():
    sync_policy()
    admin = make_user("delivery-list-admin@example.edu", "IT_ADMIN")
    recipient = make_user("SENTINEL-RECIPIENT@example.edu")
    failed = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
        attempt_count=3,
    )
    failed.claim_token = uuid4()
    failed.claim_expires_at = timezone.now() + timedelta(minutes=5)
    failed.save(update_fields=["claim_token", "claim_expires_at", "updated_at"])
    make_delivery(recipient, status=EmailDeliveryStatus.PENDING)

    client = auth_client(admin)
    response = client.get("/api/v1/platform/email-deliveries?status=FAILED&page_size=1")

    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == str(failed.pk)
    assert item["event_code"] == "call_slip.issued"
    assert item["status"] == "FAILED"
    assert item["attempt_count"] == 3
    assert item["failure_code"] == "transport_error"
    assert "notification" not in item
    assert "claim_token" not in item
    assert "claim_expires_at" not in item

    serialized = response.content.decode()
    assert recipient.email not in serialized
    assert "SENTINEL NOTIFICATION TITLE" not in serialized
    assert "SENTINEL PRIVATE NOTIFICATION MESSAGE" not in serialized
    assert str(failed.claim_token) not in serialized

    assert client.get("/api/v1/platform/email-deliveries?page_size=51").status_code == 422
    invalid = client.get("/api/v1/platform/email-deliveries?status=NOT_A_STATUS")
    assert invalid.status_code == 422


@pytest.mark.django_db
def test_email_delivery_list_projects_backend_owned_manual_retry_eligibility():
    sync_policy()
    admin = make_user("retry-projection-admin@example.edu", "IT_ADMIN")
    active = make_user("retry-projection-active@example.edu")
    inactive = make_user("retry-projection-inactive@example.edu")
    retryable = make_delivery(
        active, status=EmailDeliveryStatus.FAILED, failure_code="send_returned_zero"
    )
    template_failure = make_delivery(
        active, status=EmailDeliveryStatus.FAILED, failure_code="template_error"
    )
    unknown_failure = make_delivery(
        active, status=EmailDeliveryStatus.FAILED, failure_code="smtp said something private"
    )
    inactive_recipient = make_delivery(
        inactive, status=EmailDeliveryStatus.FAILED, failure_code="transport_error"
    )
    pending = make_delivery(active, status=EmailDeliveryStatus.PENDING)
    inactive.is_active = False
    inactive.save(update_fields=["is_active", "updated_at"])

    client = auth_client(admin)
    response = client.get("/api/v1/platform/email-deliveries?page_size=50")

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[str(retryable.pk)]["manual_retry_allowed"] is True
    assert items[str(retryable.pk)]["manual_retry_blocker"] is None
    assert items[str(template_failure.pk)]["manual_retry_allowed"] is False
    assert items[str(template_failure.pk)]["manual_retry_blocker"] == "FAILURE_NOT_RETRYABLE"
    assert items[str(unknown_failure.pk)]["failure_code"] == "unknown_failure"
    assert items[str(unknown_failure.pk)]["manual_retry_blocker"] == "FAILURE_NOT_RETRYABLE"
    assert items[str(inactive_recipient.pk)]["manual_retry_allowed"] is False
    assert items[str(inactive_recipient.pk)]["manual_retry_blocker"] == "RECIPIENT_INACTIVE"
    assert items[str(pending.pk)]["failure_code"] is None
    assert items[str(pending.pk)]["manual_retry_blocker"] == "NOT_FAILED"

    serialized = response.content.decode()
    assert inactive.email not in serialized
    assert "smtp said something private" not in serialized

    recent = auth_client(admin, recent_mfa=True)
    retried = recent.post(
        f"/api/v1/platform/email-deliveries/{retryable.pk}/retry",
        **csrf(recent),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "PENDING"
    assert retried.json()["failure_code"] is None
    assert retried.json()["manual_retry_allowed"] is False
    assert retried.json()["manual_retry_blocker"] == "NOT_FAILED"


@pytest.mark.django_db
def test_email_delivery_list_query_count_does_not_grow_per_row(django_assert_max_num_queries):
    sync_policy()
    admin = make_user("retry-query-admin@example.edu", "IT_ADMIN")
    for index in range(12):
        recipient = make_user(f"retry-query-recipient-{index}@example.edu")
        make_delivery(recipient, status=EmailDeliveryStatus.FAILED, failure_code="transport_error")
    client = auth_client(admin)
    client.get("/api/v1/platform/email-deliveries?page_size=1")

    with django_assert_max_num_queries(6):
        response = client.get("/api/v1/platform/email-deliveries?page_size=50")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 12


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "failure_code"),
    [
        (EmailDeliveryStatus.PENDING, ""),
        (EmailDeliveryStatus.PROCESSING, ""),
        (EmailDeliveryStatus.SENT, ""),
        (EmailDeliveryStatus.CANCELLED, "recipient_inactive"),
        (EmailDeliveryStatus.FAILED, "template_error"),
    ],
)
def test_manual_retry_rejects_ineligible_delivery_states(status, failure_code):
    sync_policy()
    admin = make_user(f"retry-admin-{status.lower()}@example.edu", "IT_ADMIN")
    recipient = make_user(f"retry-recipient-{status.lower()}@example.edu")
    delivery = make_delivery(recipient, status=status, failure_code=failure_code)
    client = auth_client(admin, recent_mfa=True)

    response = client.post(
        f"/api/v1/platform/email-deliveries/{delivery.pk}/retry",
        **csrf(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_delivery_not_retryable"


@pytest.mark.django_db
def test_manual_retry_requires_manage_recent_mfa_and_known_delivery():
    sync_policy()
    counselor = make_user("retry-counselor@example.edu", "COUNSELOR")
    admin = make_user("retry-no-mfa@example.edu", "IT_ADMIN")
    recipient = make_user("retry-known-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
    )

    counselor_client = auth_client(counselor, recent_mfa=True)
    denied = counselor_client.post(
        f"/api/v1/platform/email-deliveries/{delivery.pk}/retry",
        **csrf(counselor_client),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    no_mfa = auth_client(admin)
    step_up = no_mfa.post(
        f"/api/v1/platform/email-deliveries/{delivery.pk}/retry",
        **csrf(no_mfa),
    )
    assert step_up.status_code == 403
    assert step_up.json()["error"]["code"] == "recent_mfa_required"

    recent = auth_client(admin, recent_mfa=True)
    unknown = recent.post(
        f"/api/v1/platform/email-deliveries/{uuid4()}/retry",
        **csrf(recent),
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "email_delivery_not_found"


@pytest.mark.django_db
def test_manual_retry_rejects_inactive_recipient():
    sync_policy()
    admin = make_user("inactive-retry-admin@example.edu", "IT_ADMIN")
    recipient = make_user("inactive-retry-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
    )
    recipient.is_active = False
    recipient.save(update_fields=["is_active", "updated_at"])

    client = auth_client(admin, recent_mfa=True)
    response = client.post(
        f"/api/v1/platform/email-deliveries/{delivery.pk}/retry",
        **csrf(client),
    )
    assert response.status_code == 409
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.FAILED


@pytest.mark.django_db
@pytest.mark.parametrize("failure_code", ["transport_error", "send_returned_zero"])
def test_eligible_manual_retry_preserves_attempt_history_audits_and_enqueues_after_commit(
    failure_code,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    sync_policy()
    admin = make_user(f"accepted-{failure_code}-admin@example.edu", "IT_ADMIN")
    recipient = make_user(f"accepted-{failure_code}-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code=failure_code,
        attempt_count=5,
    )
    delivery.claim_token = uuid4()
    delivery.claim_expires_at = timezone.now() - timedelta(minutes=1)
    delivery.save(update_fields=["claim_token", "claim_expires_at", "updated_at"])

    queued: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        "compass.notifications.tasks.deliver_notification_email.delay",
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    monkeypatch.setattr(
        Mailer,
        "send",
        lambda *args, **kwargs: pytest.fail("HTTP retry must not send SMTP synchronously"),
    )

    client = auth_client(admin, recent_mfa=True)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/api/v1/platform/email-deliveries/{delivery.pk}/retry",
            **csrf(client),
        )

    assert response.status_code == 200
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempt_count == 5
    assert delivery.next_attempt_at is not None
    assert delivery.failure_code == ""
    assert delivery.claim_token is None
    assert delivery.claim_expires_at is None
    assert queued == [((str(delivery.pk),), {})]

    event = AuditEvent.objects.get(action="notification.email.retry_requested")
    assert event.target_type == "notifications.emaildelivery"
    assert event.target_id == str(delivery.pk)
    assert event.metadata == {
        "previous_failure_code": failure_code,
        "attempt_count": 5,
        "event_code": "call_slip.issued",
    }
    assert recipient.email not in json.dumps(event.metadata)


@pytest.mark.django_db
def test_retry_audit_failure_rolls_back_delivery_reset(monkeypatch):
    sync_policy()
    recipient = make_user("rollback-retry-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
        attempt_count=4,
    )

    monkeypatch.setattr(
        "compass.platform_ops.email_operations.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit failed")),
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        retry_email_delivery(
            delivery_id=delivery.pk,
            context=AuditContext.system(),
        )

    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.FAILED
    assert delivery.failure_code == "transport_error"
    assert delivery.attempt_count == 4


@pytest.mark.django_db
def test_retry_enqueue_failure_leaves_durable_pending_for_existing_beat_recovery(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    sync_policy()
    recipient = make_user("enqueue-failure-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="send_returned_zero",
        attempt_count=3,
    )

    monkeypatch.setattr(
        "compass.notifications.tasks.deliver_notification_email.delay",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("broker secret detail")),
    )
    with django_capture_on_commit_callbacks(execute=True):
        retry_email_delivery(
            delivery_id=delivery.pk,
            context=AuditContext.system(),
        )

    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.pk in due_email_delivery_ids()


@pytest.mark.django_db(transaction=True)
def test_concurrent_manual_retry_creates_only_one_durable_retry_intent(monkeypatch):
    sync_policy()
    recipient = make_user("concurrent-retry-recipient@example.edu")
    delivery = make_delivery(
        recipient,
        status=EmailDeliveryStatus.FAILED,
        failure_code="transport_error",
        attempt_count=3,
    )
    barrier = threading.Barrier(2)
    queued: list[str] = []
    guard = threading.Lock()

    def fake_delay(delivery_id: str):
        with guard:
            queued.append(delivery_id)

    monkeypatch.setattr(
        "compass.notifications.tasks.deliver_notification_email.delay",
        fake_delay,
    )

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                retry_email_delivery(
                    delivery_id=delivery.pk,
                    context=AuditContext.system(),
                )
                return "retried"
            except EmailDeliveryNotRetryable:
                return "conflict"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: worker(), (1, 2)))

    assert sorted(results) == ["conflict", "retried"]
    assert queued == [str(delivery.pk)]
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempt_count == 3
    assert (
        AuditEvent.objects.filter(
            action="notification.email.retry_requested",
            target_id=str(delivery.pk),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_no_bulk_retry_route_exists():
    sync_policy()
    admin = make_user("no-bulk-retry-admin@example.edu", "IT_ADMIN")
    client = auth_client(admin, recent_mfa=True)

    response = client.post(
        "/api/v1/platform/email-deliveries/retry",
        **csrf(client),
    )
    assert response.status_code in {404, 422}
