"""Durable, concurrency-safe email delivery processing for Notifications."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from compass.common.correlation import get_current_request_id
from compass.integrations.mail import Mailer

from .models import EmailDelivery, EmailDeliveryStatus
from .policy import get_event_definition

logger = logging.getLogger("compass.notifications")
DELIVERY_BATCH_SIZE = 100


@dataclass(frozen=True, slots=True)
class ClaimedEmailDelivery:
    delivery_id: UUID
    notification_id: UUID
    event_code: str
    recipient_email: str
    attempt_number: int
    claim_token: UUID


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    text_body: str
    html_body: str


def _clear_claim(delivery: EmailDelivery) -> None:
    delivery.claim_token = None
    delivery.claim_expires_at = None


def claim_email_delivery(
    delivery_id: UUID,
    *,
    now=None,
) -> ClaimedEmailDelivery | None:
    current = now or timezone.now()
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update()
            .select_related("notification__recipient")
            .filter(pk=delivery_id)
            .first()
        )
        if delivery is None:
            return None
        if delivery.status in {
            EmailDeliveryStatus.SENT,
            EmailDeliveryStatus.FAILED,
            EmailDeliveryStatus.CANCELLED,
        }:
            return None
        if (
            delivery.status == EmailDeliveryStatus.PROCESSING
            and delivery.claim_expires_at is not None
            and delivery.claim_expires_at > current
        ):
            return None
        if (
            delivery.status == EmailDeliveryStatus.PENDING
            and delivery.next_attempt_at is not None
            and delivery.next_attempt_at > current
        ):
            return None

        recipient = delivery.notification.recipient
        if not recipient.is_active:
            delivery.status = EmailDeliveryStatus.CANCELLED
            delivery.failure_code = "recipient_inactive"
            delivery.next_attempt_at = None
            _clear_claim(delivery)
            delivery.save(
                update_fields=[
                    "status",
                    "failure_code",
                    "next_attempt_at",
                    "claim_token",
                    "claim_expires_at",
                    "updated_at",
                ]
            )
            return None

        token = uuid.uuid4()
        delivery.status = EmailDeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        delivery.last_attempt_at = current
        delivery.next_attempt_at = None
        delivery.failure_code = ""
        delivery.claim_token = token
        delivery.claim_expires_at = current + timedelta(
            seconds=settings.NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS
        )
        delivery.save(
            update_fields=[
                "status",
                "attempt_count",
                "last_attempt_at",
                "next_attempt_at",
                "failure_code",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )
        return ClaimedEmailDelivery(
            delivery_id=delivery.pk,
            notification_id=delivery.notification_id,
            event_code=delivery.notification.event_code,
            recipient_email=recipient.email,
            attempt_number=delivery.attempt_count,
            claim_token=token,
        )


def render_notification_email(event_code: str) -> RenderedEmail:
    definition = get_event_definition(event_code)
    template_root = f"notifications/email/{definition.email_template}"
    return RenderedEmail(
        subject=definition.email_subject,
        text_body=render_to_string(f"{template_root}.txt", {}).strip() + "\n",
        html_body=render_to_string(f"{template_root}.html", {}),
    )


def _retry_delay_seconds(attempt_number: int) -> int:
    exponent = max(0, attempt_number - 1)
    return settings.NOTIFICATION_EMAIL_RETRY_BASE_SECONDS * (2**exponent)


def _record_success(claim: ClaimedEmailDelivery, *, now=None) -> None:
    current = now or timezone.now()
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().filter(pk=claim.delivery_id).first()
        if (
            delivery is None
            or delivery.status != EmailDeliveryStatus.PROCESSING
            or delivery.claim_token != claim.claim_token
        ):
            return
        delivery.status = EmailDeliveryStatus.SENT
        delivery.sent_at = current
        delivery.next_attempt_at = None
        delivery.failure_code = ""
        _clear_claim(delivery)
        delivery.save(
            update_fields=[
                "status",
                "sent_at",
                "next_attempt_at",
                "failure_code",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )


def _record_failure(
    claim: ClaimedEmailDelivery,
    *,
    failure_code: str,
    retryable: bool,
    now=None,
) -> None:
    current = now or timezone.now()
    with transaction.atomic():
        delivery = EmailDelivery.objects.select_for_update().filter(pk=claim.delivery_id).first()
        if (
            delivery is None
            or delivery.status != EmailDeliveryStatus.PROCESSING
            or delivery.claim_token != claim.claim_token
        ):
            return
        delivery.failure_code = failure_code
        terminal = not retryable or delivery.attempt_count >= settings.NOTIFICATION_EMAIL_MAX_ATTEMPTS
        if terminal:
            delivery.status = EmailDeliveryStatus.FAILED
            delivery.next_attempt_at = None
        else:
            delivery.status = EmailDeliveryStatus.PENDING
            delivery.next_attempt_at = current + timedelta(
                seconds=_retry_delay_seconds(delivery.attempt_count)
            )
        _clear_claim(delivery)
        delivery.save(
            update_fields=[
                "status",
                "failure_code",
                "next_attempt_at",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )


def _log_delivery_result(
    claim: ClaimedEmailDelivery,
    *,
    status: str,
    failure_code: str = "",
) -> None:
    logger.info(
        "notification email delivery processed",
        extra={
            "event": "notification_email_delivery_processed",
            "email_delivery_id": str(claim.delivery_id),
            "notification_id": str(claim.notification_id),
            "notification_event_code": claim.event_code,
            "attempt_number": claim.attempt_number,
            "delivery_status": status,
            "failure_code": failure_code,
            "request_id": get_current_request_id(),
        },
    )


def deliver_email_delivery(delivery_id: UUID) -> str:
    claim = claim_email_delivery(delivery_id)
    if claim is None:
        return "skipped"

    try:
        rendered = render_notification_email(claim.event_code)
    except Exception:
        _record_failure(claim, failure_code="template_error", retryable=False)
        _log_delivery_result(claim, status=EmailDeliveryStatus.FAILED, failure_code="template_error")
        return EmailDeliveryStatus.FAILED

    try:
        sent = Mailer().send(
            subject=rendered.subject,
            body=rendered.text_body,
            recipients=claim.recipient_email,
            html_body=rendered.html_body,
        )
    except Exception:
        _record_failure(claim, failure_code="transport_error", retryable=True)
        _log_delivery_result(claim, status="retry_or_failed", failure_code="transport_error")
        return "retry_or_failed"

    if sent < 1:
        _record_failure(claim, failure_code="send_returned_zero", retryable=True)
        _log_delivery_result(claim, status="retry_or_failed", failure_code="send_returned_zero")
        return "retry_or_failed"

    _record_success(claim)
    _log_delivery_result(claim, status=EmailDeliveryStatus.SENT)
    return EmailDeliveryStatus.SENT


def due_email_delivery_ids(*, now=None, limit: int = DELIVERY_BATCH_SIZE) -> tuple[UUID, ...]:
    current = now or timezone.now()
    queryset = EmailDelivery.objects.filter(
        Q(
            status=EmailDeliveryStatus.PENDING,
            next_attempt_at__lte=current,
        )
        | Q(
            status=EmailDeliveryStatus.PROCESSING,
            claim_expires_at__lte=current,
        )
    ).order_by("created_at", "id")
    return tuple(queryset.values_list("id", flat=True)[:limit])


__all__ = [
    "ClaimedEmailDelivery",
    "RenderedEmail",
    "claim_email_delivery",
    "deliver_email_delivery",
    "due_email_delivery_ids",
    "render_notification_email",
]
