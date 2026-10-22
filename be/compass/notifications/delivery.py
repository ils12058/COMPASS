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
from django.utils import timezone

from compass.appointments.email_presentation import (
    APPOINTMENT_EMAIL_EVENTS,
    AppointmentEmailDetail,
    AppointmentEmailFacts,
)
from compass.common.correlation import get_current_request_id
from compass.common.email import RenderedEmail, render_email
from compass.integrations.mail import Mailer

from .current import notification_is_current
from .email_disclosure import (
    APPOINTMENT_EMAIL_FIELD_POLICY,
    APPROVED_EMAIL_EVENTS,
    APPROVED_OPERATIONAL_POLICY,
    OPERATIONAL_EMAIL_EVENTS,
    OPERATIONAL_EMAIL_TARGETS,
    email_disclosure_policy,
)
from .email_links import NotificationEmailTarget, build_notification_email_link
from .email_presentation import (
    EmailPresentationReason,
    NotificationEmailPresentation,
    resolve_notification_email_presentation,
)
from .models import EmailDelivery, EmailDeliveryStatus, Notification
from .operational_email_rendering import operational_email_context
from .policy import NotificationEvent, NotificationTargetType, get_event_definition

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
            EmailDelivery.objects.select_for_update(of=("self",))
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
        if not recipient.is_active or not notification_is_current(
            delivery.notification, now=current
        ):
            delivery.status = EmailDeliveryStatus.CANCELLED
            delivery.failure_code = (
                "recipient_inactive" if not recipient.is_active else "source_ineligible"
            )
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


def render_notification_email(
    event_code: str, *, presentation: NotificationEmailPresentation | None = None
) -> RenderedEmail:
    """Fixed-copy previews remain context-free; approved plans add controlled values.

    Subjects, templates, action wording and all body text stay code-owned. The
    URL is rebuilt from a closed target. Detail rows are typed, allowlisted and
    institutionally gated; raw models and arbitrary mappings are never accepted.
    """

    definition = get_event_definition(event_code)
    context = {}
    if presentation is not None:
        if not isinstance(presentation, NotificationEmailPresentation):
            raise ValueError("invalid notification email presentation")
        if presentation.event_code != event_code or presentation.suppress:
            raise ValueError("ineligible notification email presentation")
        if (presentation.target is not None) != (
            presentation.reason
            in {EmailPresentationReason.LINK_AVAILABLE, EmailPresentationReason.RICH_AVAILABLE}
        ):
            raise ValueError("inconsistent notification email action")
        if presentation.target is not None:
            if (
                event_code not in APPROVED_EMAIL_EVENTS
                or (
                    presentation.reason == EmailPresentationReason.LINK_AVAILABLE
                    and event_code in APPOINTMENT_EMAIL_EVENTS
                    and event_code != NotificationEvent.APPOINTMENT_SCHEDULED
                )
                or not isinstance(presentation.target, NotificationEmailTarget)
                or presentation.target.target_type
                != OPERATIONAL_EMAIL_TARGETS.get(event_code, NotificationTargetType.APPOINTMENT)
            ):
                raise ValueError("unsupported notification email action")
            link = build_notification_email_link(presentation.target)
            if presentation.validated_link is not None and presentation.validated_link != link:
                raise ValueError("notification email link changed")
            if link.url is not None:
                context["action_url"] = link.url
        if presentation.appointment_facts is not None:
            facts = presentation.appointment_facts
            fields = APPOINTMENT_EMAIL_FIELD_POLICY.get(presentation.recipient_class, frozenset())
            if (
                event_code not in APPOINTMENT_EMAIL_EVENTS
                or type(facts) is not AppointmentEmailFacts
                or presentation.reason != EmailPresentationReason.RICH_AVAILABLE
                or presentation.disclosure_policy != APPROVED_OPERATIONAL_POLICY
                or presentation.validated_link is None
                or email_disclosure_policy() != APPROVED_OPERATIONAL_POLICY
                or presentation.target is None
                or facts.event_code != event_code
                or facts.appointment_id != presentation.target.target_id
                or facts.recipient_class != presentation.recipient_class
                or not facts.rows
                or type(facts.rows) is not tuple
                or any(
                    type(row) is not AppointmentEmailDetail or row.field not in fields
                    for row in facts.rows
                )
                or len({row.field for row in facts.rows}) != len(facts.rows)
            ):
                raise ValueError("unapproved appointment email facts")
            if "action_url" in context:
                context["appointment_details"] = facts.rows
        elif (
            presentation.reason == EmailPresentationReason.RICH_AVAILABLE
            and event_code not in OPERATIONAL_EMAIL_EVENTS
        ):
            raise ValueError("missing appointment email facts")
        context.update(operational_email_context(event_code, presentation))
    return render_email(
        definition.email_subject, f"notifications/email/{definition.email_template}", context
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
        terminal = (
            not retryable or delivery.attempt_count >= settings.NOTIFICATION_EMAIL_MAX_ATTEMPTS
        )
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
    presentation_reason: str = "",
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
            "presentation_reason": presentation_reason,
            "request_id": get_current_request_id(),
        },
    )


def _cancel_delivery(delivery, *, failure_code):
    delivery.status = EmailDeliveryStatus.CANCELLED
    delivery.failure_code = failure_code
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


def _cancel_claim(claim, *, failure_code):
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update()
            .filter(
                pk=claim.delivery_id,
                claim_token=claim.claim_token,
                status=EmailDeliveryStatus.PROCESSING,
            )
            .first()
        )
        if delivery is not None:
            _cancel_delivery(delivery, failure_code=failure_code)


def _email_claim_is_current(claim, presentation):
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update(of=("self",))
            .select_related("notification__recipient")
            .filter(
                pk=claim.delivery_id,
                claim_token=claim.claim_token,
                status=EmailDeliveryStatus.PROCESSING,
            )
            .first()
        )
        if delivery is None:
            return False
        if (
            delivery.notification.recipient.is_active
            and notification_is_current(delivery.notification)
            and delivery.notification.recipient.email == claim.recipient_email
            and delivery.claim_expires_at is not None
            and delivery.claim_expires_at > timezone.now()
            # Re-query source-owned eligibility and current capabilities/scope.
            # A change after rendering cancels this attempt without sending stale links.
            and resolve_notification_email_presentation(delivery.notification) == presentation
        ):
            return True
        _cancel_delivery(delivery, failure_code="source_or_recipient_changed")
        return False


def deliver_email_delivery(delivery_id: UUID) -> str:
    claim = claim_email_delivery(delivery_id)
    if claim is None:
        return "skipped"

    try:
        notification = Notification.objects.get(pk=claim.notification_id)
        presentation = resolve_notification_email_presentation(notification)
    except Exception:
        # Keep the existing terminal render-phase failure classification, with a
        # bounded stage code. Never expose exceptions or raw source context.
        _record_failure(claim, failure_code="template_error", retryable=False)
        _log_delivery_result(
            claim,
            status=EmailDeliveryStatus.FAILED,
            failure_code="template_error",
            presentation_reason="resolution_error",
        )
        return EmailDeliveryStatus.FAILED
    if presentation.suppress:
        _cancel_claim(claim, failure_code="source_ineligible")
        _log_delivery_result(
            claim,
            status=EmailDeliveryStatus.CANCELLED,
            failure_code="source_ineligible",
            presentation_reason=presentation.reason,
        )
        return EmailDeliveryStatus.CANCELLED

    try:
        rendered = render_notification_email(claim.event_code, presentation=presentation)
    except Exception:
        _record_failure(claim, failure_code="template_error", retryable=False)
        _log_delivery_result(
            claim, status=EmailDeliveryStatus.FAILED, failure_code="template_error"
        )
        return EmailDeliveryStatus.FAILED

    try:
        if not _email_claim_is_current(claim, presentation):
            return EmailDeliveryStatus.CANCELLED
    except Exception:
        _record_failure(claim, failure_code="template_error", retryable=False)
        _log_delivery_result(
            claim,
            status=EmailDeliveryStatus.FAILED,
            failure_code="template_error",
            presentation_reason="revalidation_error",
        )
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
    _log_delivery_result(
        claim, status=EmailDeliveryStatus.SENT, presentation_reason=presentation.reason
    )
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
