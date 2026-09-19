from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core import mail
from django.db import close_old_connections, transaction
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.integrations.mail import Mailer
from compass.notifications.delivery import (
    deliver_email_delivery,
    due_email_delivery_ids,
    render_notification_email,
)
from compass.notifications.models import (
    EmailDelivery,
    EmailDeliveryStatus,
    Notification,
)
from compass.notifications.policy import NotificationEvent, NotificationPolicy
from compass.notifications.services import create_notification_for_event


def make_user(email: str, *, active: bool = True) -> User:
    role, _created = Role.objects.get_or_create(
        code="STUDENT",
        defaults={"name": "Student"},
    )
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=role,
        first_name="Synthetic",
        last_name="Student",
        is_active=active,
    )


def make_delivery(
    user: User,
    *,
    status: str = EmailDeliveryStatus.PENDING,
    next_attempt_at=None,
) -> EmailDelivery:
    source_id = uuid4()
    notification = Notification.objects.create(
        recipient=user,
        event_code=NotificationEvent.CALL_SLIP_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        title="New Call Slip",
        message="A Call Slip has been issued to you. Open COMPASS to review the details.",
        source_type="call_slip",
        source_id=source_id,
        target_type="CALL_SLIP",
        target_id=source_id,
    )
    return EmailDelivery.objects.create(
        notification=notification,
        status=status,
        next_attempt_at=next_attempt_at if next_attempt_at is not None else timezone.now(),
    )


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS=300,
    NOTIFICATION_EMAIL_MAX_ATTEMPTS=3,
    NOTIFICATION_EMAIL_RETRY_BASE_SECONDS=10,
)
@pytest.mark.django_db
def test_email_delivery_success_is_durable_and_duplicate_task_is_harmless():
    user = make_user("delivery-success@example.edu")
    delivery = make_delivery(user)
    mail.outbox.clear()

    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.SENT
    assert delivery.attempt_count == 1
    assert delivery.last_attempt_at is not None
    assert delivery.sent_at is not None
    assert delivery.next_attempt_at is None
    assert delivery.claim_token is None
    assert delivery.claim_expires_at is None
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == "New COMPASS Call Slip"
    assert message.to == [user.email]
    assert "Sign in to COMPASS to review the details." in message.body
    assert len(message.alternatives) == 1
    assert message.alternatives[0].mimetype == "text/html"

    assert deliver_email_delivery(delivery.pk) == "skipped"
    assert len(mail.outbox) == 1


@override_settings(
    NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS=300,
    NOTIFICATION_EMAIL_MAX_ATTEMPTS=2,
    NOTIFICATION_EMAIL_RETRY_BASE_SECONDS=10,
)
@pytest.mark.django_db
def test_transport_failure_retries_with_safe_code_then_becomes_terminal(monkeypatch):
    user = make_user("delivery-failure@example.edu")
    delivery = make_delivery(user)
    sensitive = "SMTP recipient@example.edu password=SECRET provider traceback detail"

    def fail_send(*args, **kwargs):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(Mailer, "send", fail_send)

    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempt_count == 1
    assert delivery.failure_code == "transport_error"
    assert delivery.next_attempt_at is not None
    assert sensitive not in " ".join(str(value) for value in vars(delivery).values())

    EmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.FAILED
    assert delivery.attempt_count == 2
    assert delivery.next_attempt_at is None
    assert delivery.notification.__class__.objects.filter(pk=delivery.notification_id).exists()


@pytest.mark.django_db
def test_inactive_recipient_is_cancelled_without_sending(monkeypatch):
    user = make_user("inactive-delivery@example.edu", active=False)
    delivery = make_delivery(user)
    calls = []

    monkeypatch.setattr(Mailer, "send", lambda *args, **kwargs: calls.append(kwargs) or 1)
    assert deliver_email_delivery(delivery.pk) == "skipped"
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.CANCELLED
    assert delivery.failure_code == "recipient_inactive"
    assert delivery.attempt_count == 0
    assert calls == []


@pytest.mark.django_db
def test_recovery_selects_due_retry_and_expired_claim_only():
    user = make_user("recovery-select@example.edu")
    now = timezone.now()
    due = make_delivery(user, next_attempt_at=now - timedelta(seconds=1))
    retry = make_delivery(user, next_attempt_at=now - timedelta(seconds=1))
    retry.attempt_count = 1
    retry.save(update_fields=["attempt_count", "updated_at"])
    future = make_delivery(user, next_attempt_at=now + timedelta(minutes=5))
    sent = make_delivery(user, status=EmailDeliveryStatus.SENT, next_attempt_at=None)
    failed = make_delivery(user, status=EmailDeliveryStatus.FAILED, next_attempt_at=None)
    expired = make_delivery(user, status=EmailDeliveryStatus.PROCESSING, next_attempt_at=None)
    expired.claim_token = uuid4()
    expired.claim_expires_at = now - timedelta(seconds=1)
    expired.save(update_fields=["claim_token", "claim_expires_at", "updated_at"])
    active_claim = make_delivery(user, status=EmailDeliveryStatus.PROCESSING, next_attempt_at=None)
    active_claim.claim_token = uuid4()
    active_claim.claim_expires_at = now + timedelta(minutes=5)
    active_claim.save(update_fields=["claim_token", "claim_expires_at", "updated_at"])

    selected = set(due_email_delivery_ids(now=now))
    assert selected == {due.pk, retry.pk, expired.pk}
    assert future.pk not in selected
    assert sent.pk not in selected
    assert failed.pk not in selected
    assert active_claim.pk not in selected


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS=300,
    NOTIFICATION_EMAIL_MAX_ATTEMPTS=3,
    NOTIFICATION_EMAIL_RETRY_BASE_SECONDS=10,
)
@pytest.mark.django_db(transaction=True)
def test_enqueue_failure_keeps_durable_intent_and_recovery_can_send(monkeypatch):
    user = make_user("enqueue-recovery@example.edu")

    def fail_enqueue(*args, **kwargs):
        raise RuntimeError("BROKER-SENSITIVE-DETAIL")

    monkeypatch.setattr(
        "compass.notifications.tasks.deliver_notification_email.delay",
        fail_enqueue,
    )
    with transaction.atomic():
        notification = create_notification_for_event(
            recipient=user,
            event=NotificationEvent.CALL_SLIP_ISSUED,
            source_type="call_slip",
            source_id=uuid4(),
            target_type="CALL_SLIP",
            target_id=uuid4(),
        )

    notification.refresh_from_db()
    delivery = EmailDelivery.objects.get(notification=notification)
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.pk in due_email_delivery_ids()
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.SENT


@pytest.mark.django_db
def test_post_commit_kick_passes_only_delivery_identifier(
    monkeypatch, django_capture_on_commit_callbacks
):
    user = make_user("task-args@example.edu")
    captured = []

    monkeypatch.setattr(
        "compass.notifications.tasks.deliver_notification_email.delay",
        lambda *args, **kwargs: captured.append((args, kwargs)),
    )
    with django_capture_on_commit_callbacks(execute=True):
        notification = create_notification_for_event(
            recipient=user,
            event=NotificationEvent.CALL_SLIP_ISSUED,
            source_type="call_slip",
            source_id=uuid4(),
            target_type="CALL_SLIP",
            target_id=uuid4(),
        )

    delivery = EmailDelivery.objects.get(notification=notification)
    assert captured == [((str(delivery.pk),), {})]
    serialized = repr(captured)
    assert user.email not in serialized
    assert notification.message not in serialized


@pytest.mark.django_db
def test_delivery_resolves_current_canonical_account_email(monkeypatch):
    user = make_user("old-email@example.edu")
    delivery = make_delivery(user)
    user.email = "new-email@example.edu"
    user.save(update_fields=["email", "updated_at"])
    captured = []

    monkeypatch.setattr(
        Mailer,
        "send",
        lambda self, subject, body, recipients, **kwargs: captured.append(recipients) or 1,
    )
    deliver_email_delivery(delivery.pk)
    assert captured == ["new-email@example.edu"]


@override_settings(
    NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS=300,
    NOTIFICATION_EMAIL_MAX_ATTEMPTS=3,
    NOTIFICATION_EMAIL_RETRY_BASE_SECONDS=10,
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_delivery_claim_sends_once(monkeypatch):
    user = make_user("concurrent-delivery@example.edu")
    delivery = make_delivery(user)
    entered_send = threading.Event()
    release_send = threading.Event()
    send_count = 0
    guard = threading.Lock()

    def blocking_send(*args, **kwargs):
        nonlocal send_count
        with guard:
            send_count += 1
        entered_send.set()
        assert release_send.wait(timeout=10)
        return 1

    monkeypatch.setattr(Mailer, "send", blocking_send)

    def worker():
        close_old_connections()
        try:
            return deliver_email_delivery(delivery.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        assert entered_send.wait(timeout=10)
        second = pool.submit(worker)
        second_result = second.result(timeout=10)
        release_send.set()
        first_result = first.result(timeout=10)

    assert first_result == EmailDeliveryStatus.SENT
    assert second_result == "skipped"
    assert send_count == 1
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.SENT


def test_call_slip_email_is_minimal_and_contains_no_invented_frontend_url():
    rendered = render_notification_email(NotificationEvent.CALL_SLIP_ISSUED)
    combined = f"{rendered.subject}\n{rendered.text_body}\n{rendered.html_body}"
    assert "New COMPASS Call Slip" in combined
    assert "Sign in to COMPASS to review the details." in combined
    assert "http://" not in combined
    assert "https://" not in combined
    for forbidden in (
        "Referral reason",
        "Referral remarks",
        "course/year",
        "custom destination",
        "counseling",
    ):
        assert forbidden not in combined
