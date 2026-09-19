"""Transactional Notification intent creation and authenticated self-service operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.common.correlation import get_current_request_id

from .models import EmailDelivery, Notification, NotificationPreference
from .policy import (
    NotificationChannel,
    NotificationEvent,
    email_allowed_for_policy,
    get_event_definition,
)

logger = logging.getLogger("compass.notifications")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class NotificationError(RuntimeError):
    pass


class NotificationNotFound(NotificationError):
    pass


class InvalidNotificationInput(NotificationError):
    pass


@dataclass(frozen=True, slots=True)
class NotificationPage:
    items: tuple[Notification, ...]
    page: int
    page_size: int
    has_next: bool


def _safe_kick_email_delivery(delivery_id: str) -> None:
    try:
        from .tasks import deliver_notification_email

        deliver_notification_email.delay(delivery_id)
    except Exception:
        logger.warning(
            "notification email enqueue failed; durable delivery remains recoverable",
            extra={
                "event": "notification_email_enqueue_failed",
                "email_delivery_id": delivery_id,
                "request_id": get_current_request_id(),
            },
        )


def optional_email_enabled_for(user: User) -> bool:
    stored = (
        NotificationPreference.objects.filter(user=user)
        .values_list(
            "optional_email_enabled",
            flat=True,
        )
        .first()
    )
    return True if stored is None else bool(stored)


def create_notification_for_event(
    *,
    recipient: User,
    event: NotificationEvent | str,
    source_type: str,
    source_id: UUID,
    target_type: str = "",
    target_id: UUID | None = None,
) -> Notification:
    definition = get_event_definition(event)
    notification, _created = Notification.objects.get_or_create(
        recipient=recipient,
        event_code=definition.event.value,
        source_type=source_type,
        source_id=source_id,
        defaults={
            "policy": definition.policy.value,
            "title": definition.title,
            "message": definition.message,
            "target_type": target_type,
            "target_id": target_id,
        },
    )

    if NotificationChannel.EMAIL not in definition.channels:
        return notification

    email_enabled = email_allowed_for_policy(
        definition.policy,
        optional_email_enabled=optional_email_enabled_for(recipient),
    )
    if not email_enabled:
        return notification

    delivery, delivery_created = EmailDelivery.objects.get_or_create(notification=notification)
    if delivery_created:
        transaction.on_commit(
            lambda delivery_id=str(delivery.pk): _safe_kick_email_delivery(delivery_id)
        )
    return notification


def list_my_notifications(
    *,
    actor: User,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> NotificationPage:
    if page < 1:
        raise InvalidNotificationInput("page must be at least 1")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise InvalidNotificationInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    offset = (page - 1) * page_size
    rows = list(
        Notification.objects.filter(recipient=actor).order_by("-created_at", "-id")[
            offset : offset + page_size + 1
        ]
    )
    return NotificationPage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def unread_count_for(*, actor: User) -> int:
    return Notification.objects.filter(recipient=actor, read_at__isnull=True).count()


def mark_my_notification_read(
    *,
    actor: User,
    notification_id: UUID,
) -> Notification:
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update()
            .filter(pk=notification_id, recipient=actor)
            .first()
        )
        if notification is None:
            raise NotificationNotFound("The requested Notification was not found.")
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return notification


def update_my_notification_preference(
    *,
    actor: User,
    optional_email_enabled: bool,
) -> bool:
    preference, _created = NotificationPreference.objects.update_or_create(
        user=actor,
        defaults={"optional_email_enabled": optional_email_enabled},
    )
    return bool(preference.optional_email_enabled)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "InvalidNotificationInput",
    "MAX_PAGE_SIZE",
    "NotificationError",
    "NotificationNotFound",
    "NotificationPage",
    "create_notification_for_event",
    "list_my_notifications",
    "mark_my_notification_read",
    "optional_email_enabled_for",
    "unread_count_for",
    "update_my_notification_preference",
]
