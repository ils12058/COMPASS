"""Durable completion notices; task arguments contain only the record ID."""

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from compass.authentication.models import AccountRecoveryLink
from compass.authentication.security_email import (
    render_email_changed_alert,
    render_recovery_completion_email,
)
from compass.integrations.mail import Mailer
from compass.tasks import CorrelationTask


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.authentication.recovery_link.completion",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def deliver_recovery_completion(self, link_id: str) -> int:
    """Follow the old-address alert's locked send/stamp pattern for both notices."""
    sent_count = 0
    # Separate transactions preserve the old-alert stamp if sending the confirmation fails.
    for field in ("old_email_alert_sent_at", "confirmation_sent_at"):
        with transaction.atomic():
            link = AccountRecoveryLink.objects.select_for_update().filter(pk=link_id).first()
            if link is None or link.consumed_at is None:
                return sent_count
            if getattr(link, field) is not None or (
                field == "old_email_alert_sent_at" and not link.email_change
            ):
                continue
            old_alert = field == "old_email_alert_sent_at"
            message = (
                render_email_changed_alert() if old_alert else render_recovery_completion_email()
            )
            sent = Mailer().send(
                subject=message.subject,
                body=message.text_body,
                recipients=link.current_email_snapshot if old_alert else link.destination_email,
                html_body=message.html_body,
            )
            if sent != 1:
                raise RuntimeError(
                    "COMPASS account completion notice was not accepted for delivery"
                )
            setattr(link, field, timezone.now())
            link.save(update_fields=[field])
            sent_count += sent
    return sent_count


@shared_task(
    bind=True, base=CorrelationTask, name="compass.authentication.recovery_link.recover_notices"
)
def recover_recovery_completion_notices(self, batch_size: int = 100) -> int:
    from django.db.models import Q

    from compass.authentication.recovery_links import _enqueue_receipts

    bounded = batch_size if type(batch_size) is int and 1 <= batch_size <= 500 else 100
    ids = (
        AccountRecoveryLink.objects.filter(consumed_at__isnull=False)
        .filter(
            Q(confirmation_sent_at__isnull=True)
            | Q(email_change=True, old_email_alert_sent_at__isnull=True)
        )
        .order_by("consumed_at", "id")
        .values_list("id", flat=True)[:bounded]
    )
    for link_id in ids:
        _enqueue_receipts(str(link_id))
    return len(ids)
