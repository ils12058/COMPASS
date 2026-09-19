"""Celery tasks for durable Notification email delivery and recovery."""

from __future__ import annotations

import logging
from uuid import UUID

from celery import shared_task

from compass.common.correlation import get_current_request_id
from compass.tasks import CorrelationTask

from .delivery import deliver_email_delivery, due_email_delivery_ids

logger = logging.getLogger("compass.notifications")


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.notifications.email.deliver",
)
def deliver_notification_email(self, email_delivery_id: str) -> str:
    try:
        delivery_id = UUID(email_delivery_id)
    except (TypeError, ValueError):
        return "skipped"
    return deliver_email_delivery(delivery_id)


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.notifications.email.dispatch_due",
)
def dispatch_due_notification_emails(self) -> int:
    queued = 0
    for delivery_id in due_email_delivery_ids():
        try:
            deliver_notification_email.delay(str(delivery_id))
        except Exception:
            logger.warning(
                "notification email recovery enqueue failed",
                extra={
                    "event": "notification_email_recovery_enqueue_failed",
                    "email_delivery_id": str(delivery_id),
                    "request_id": get_current_request_id(),
                },
            )
            continue
        queued += 1
    return queued


__all__ = ["deliver_notification_email", "dispatch_due_notification_emails"]
