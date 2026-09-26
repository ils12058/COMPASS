"""Read-only EmailDelivery operations plus one controlled manual retry."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from uuid import UUID

from django.db import transaction
from django.db.models import Count, F, Min, Q
from django.utils import timezone

from compass.audit.actions import NOTIFICATION_EMAIL_RETRY_REQUESTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.correlation import get_current_request_id
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000
RETRYABLE_MANUAL_FAILURE_CODES = frozenset({"transport_error", "send_returned_zero"})
SAFE_FAILURE_CODES = frozenset(
    {
        "transport_error",
        "template_error",
        "send_returned_zero",
        "recipient_inactive",
    }
)
EMAIL_DELIVERY_TARGET_TYPE = "notifications.emaildelivery"


class EmailDeliveryFailureCode(StrEnum):
    """Closed, provider-neutral failure classification exposed to operators."""

    TRANSPORT_ERROR = "transport_error"
    TEMPLATE_ERROR = "template_error"
    SEND_RETURNED_ZERO = "send_returned_zero"
    RECIPIENT_INACTIVE = "recipient_inactive"
    UNKNOWN_FAILURE = "unknown_failure"


class EmailDeliveryRetryBlocker(StrEnum):
    """Why a delivery is not currently eligible for one manual retry."""

    NOT_FAILED = "NOT_FAILED"
    FAILURE_NOT_RETRYABLE = "FAILURE_NOT_RETRYABLE"
    RECIPIENT_INACTIVE = "RECIPIENT_INACTIVE"


logger = logging.getLogger("compass.platform_ops")


class EmailDeliveryOperationsError(RuntimeError):
    """Base class for expected EmailDelivery operator failures."""


class EmailDeliveryNotFound(EmailDeliveryOperationsError):
    """The requested delivery does not exist."""


class EmailDeliveryNotRetryable(EmailDeliveryOperationsError):
    """The requested delivery is not eligible for manual retry."""


class EmailDeliveryPaginationError(EmailDeliveryOperationsError):
    """The requested page or filter is invalid."""


@dataclass(frozen=True, slots=True)
class EmailDeliverySummary:
    pending_count: int
    processing_count: int
    failed_count: int
    cancelled_count: int
    sent_today: int
    oldest_pending_at: datetime | None
    due_pending_count: int


@dataclass(frozen=True, slots=True)
class EmailDeliveryItem:
    id: UUID
    event_code: str
    status: str
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    sent_at: datetime | None
    failure_code: EmailDeliveryFailureCode | None
    manual_retry_allowed: bool
    manual_retry_blocker: EmailDeliveryRetryBlocker | None


@dataclass(frozen=True, slots=True)
class EmailDeliveryPage:
    items: tuple[EmailDeliveryItem, ...]
    page: int
    page_size: int
    has_next: bool


def _safe_failure_code(value: str) -> EmailDeliveryFailureCode | None:
    if not value:
        return None
    if value in SAFE_FAILURE_CODES:
        return EmailDeliveryFailureCode(value)
    return EmailDeliveryFailureCode.UNKNOWN_FAILURE


def manual_retry_blocker(
    *,
    status: str,
    failure_code: str,
    recipient_active: bool,
) -> EmailDeliveryRetryBlocker | None:
    """Return the backend-owned reason a delivery cannot be manually retried, if any."""

    if status != EmailDeliveryStatus.FAILED:
        return EmailDeliveryRetryBlocker.NOT_FAILED
    if failure_code not in RETRYABLE_MANUAL_FAILURE_CODES:
        return EmailDeliveryRetryBlocker.FAILURE_NOT_RETRYABLE
    if not recipient_active:
        return EmailDeliveryRetryBlocker.RECIPIENT_INACTIVE
    return None


def _validate_page(*, page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1 or page > MAX_PAGE_NUMBER:
        raise EmailDeliveryPaginationError(
            f"page must be an integer between 1 and {MAX_PAGE_NUMBER}"
        )
    if type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise EmailDeliveryPaginationError(
            f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}"
        )
    return page, page_size


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized not in EmailDeliveryStatus.values:
        raise EmailDeliveryPaginationError("status must be a valid EmailDelivery status")
    return normalized


def get_email_delivery_summary(*, now: datetime | None = None) -> EmailDeliverySummary:
    current = now or timezone.now()
    local_date = timezone.localtime(current).date()
    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(local_date, time.min), tz)
    next_day = day_start + timedelta(days=1)

    aggregate = EmailDelivery.objects.aggregate(
        pending_count=Count("id", filter=Q(status=EmailDeliveryStatus.PENDING)),
        processing_count=Count("id", filter=Q(status=EmailDeliveryStatus.PROCESSING)),
        failed_count=Count("id", filter=Q(status=EmailDeliveryStatus.FAILED)),
        cancelled_count=Count("id", filter=Q(status=EmailDeliveryStatus.CANCELLED)),
        sent_today=Count(
            "id",
            filter=Q(
                status=EmailDeliveryStatus.SENT,
                sent_at__gte=day_start,
                sent_at__lt=next_day,
            ),
        ),
        oldest_pending_at=Min(
            "created_at",
            filter=Q(status=EmailDeliveryStatus.PENDING),
        ),
        due_pending_count=Count(
            "id",
            filter=Q(
                status=EmailDeliveryStatus.PENDING,
                next_attempt_at__lte=current,
            ),
        ),
    )
    return EmailDeliverySummary(**aggregate)


def _serialize_item(delivery: EmailDelivery, *, recipient_active: bool) -> EmailDeliveryItem:
    blocker = manual_retry_blocker(
        status=delivery.status,
        failure_code=delivery.failure_code,
        recipient_active=recipient_active,
    )
    return EmailDeliveryItem(
        id=delivery.pk,
        event_code=delivery.notification.event_code,
        status=delivery.status,
        attempt_count=delivery.attempt_count,
        created_at=delivery.created_at,
        updated_at=delivery.updated_at,
        last_attempt_at=delivery.last_attempt_at,
        next_attempt_at=delivery.next_attempt_at,
        sent_at=delivery.sent_at,
        failure_code=_safe_failure_code(delivery.failure_code),
        manual_retry_allowed=blocker is None,
        manual_retry_blocker=blocker,
    )


def list_email_deliveries(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = None,
) -> EmailDeliveryPage:
    page, page_size = _validate_page(page=page, page_size=page_size)
    normalized_status = _normalize_status(status)

    queryset = (
        EmailDelivery.objects.select_related("notification")
        .annotate(recipient_active=F("notification__recipient__is_active"))
        .order_by("-created_at", "-id")
    )
    if normalized_status is not None:
        queryset = queryset.filter(status=normalized_status)

    offset = (page - 1) * page_size
    records = list(queryset[offset : offset + page_size + 1])
    has_next = len(records) > page_size
    return EmailDeliveryPage(
        items=tuple(
            _serialize_item(item, recipient_active=item.recipient_active)
            for item in records[:page_size]
        ),
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


def _safe_enqueue_retry(delivery_id: UUID) -> None:
    from compass.notifications.tasks import deliver_notification_email

    try:
        deliver_notification_email.delay(str(delivery_id))
    except Exception:
        logger.warning(
            "manual notification email retry enqueue failed",
            extra={
                "event": "manual_notification_email_retry_enqueue_failed",
                "email_delivery_id": str(delivery_id),
                "request_id": get_current_request_id(),
            },
        )


def retry_email_delivery(
    *,
    delivery_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> EmailDeliveryItem:
    current = now or timezone.now()

    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update(of=("self",))
            .select_related("notification__recipient")
            .filter(pk=delivery_id)
            .first()
        )
        if delivery is None:
            raise EmailDeliveryNotFound("the requested EmailDelivery was not found")
        recipient_active = delivery.notification.recipient.is_active
        blocker = manual_retry_blocker(
            status=delivery.status,
            failure_code=delivery.failure_code,
            recipient_active=recipient_active,
        )
        if blocker == EmailDeliveryRetryBlocker.RECIPIENT_INACTIVE:
            raise EmailDeliveryNotRetryable("the requested EmailDelivery recipient is not active")
        if blocker is not None:
            raise EmailDeliveryNotRetryable(
                "the requested EmailDelivery is not eligible for manual retry"
            )

        previous_failure_code = delivery.failure_code
        delivery.status = EmailDeliveryStatus.PENDING
        delivery.next_attempt_at = current
        delivery.failure_code = ""
        delivery.claim_token = None
        delivery.claim_expires_at = None
        delivery.save(
            update_fields=[
                "status",
                "next_attempt_at",
                "failure_code",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=NOTIFICATION_EMAIL_RETRY_REQUESTED,
            outcome=AuditOutcome.SUCCESS,
            target_type=EMAIL_DELIVERY_TARGET_TYPE,
            target_id=delivery.pk,
            metadata={
                "previous_failure_code": previous_failure_code,
                "attempt_count": delivery.attempt_count,
                "event_code": delivery.notification.event_code,
            },
        )
        transaction.on_commit(lambda: _safe_enqueue_retry(delivery.pk))
        return _serialize_item(delivery, recipient_active=recipient_active)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "EMAIL_DELIVERY_TARGET_TYPE",
    "EmailDeliveryFailureCode",
    "EmailDeliveryItem",
    "EmailDeliveryNotFound",
    "EmailDeliveryNotRetryable",
    "EmailDeliveryOperationsError",
    "EmailDeliveryPage",
    "EmailDeliveryPaginationError",
    "EmailDeliveryRetryBlocker",
    "EmailDeliverySummary",
    "MAX_PAGE_NUMBER",
    "MAX_PAGE_SIZE",
    "RETRYABLE_MANUAL_FAILURE_CODES",
    "get_email_delivery_summary",
    "list_email_deliveries",
    "manual_retry_blocker",
    "retry_email_delivery",
]
