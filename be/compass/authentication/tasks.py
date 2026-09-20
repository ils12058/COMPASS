"""Celery boundary for security email delivery."""

from __future__ import annotations

import logging
import re

from celery import shared_task
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from compass.integrations.mail import Mailer
from compass.tasks import CorrelationTask

logger = logging.getLogger("compass.authentication")
_EMAIL_OTP_CODE_RE = re.compile(r"^\d{6}$", re.ASCII)


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.authentication.email_otp.deliver",
)
def deliver_email_otp(self, challenge_id: str, code: str) -> int:
    """Deliver a transient plaintext code; it is never logged or stored by this task."""

    if not isinstance(challenge_id, str) or not challenge_id:
        return 0
    if not isinstance(code, str) or not _EMAIL_OTP_CODE_RE.fullmatch(code):
        return 0
    from compass.authentication.models import EmailOTPChallenge

    challenge = EmailOTPChallenge.objects.filter(pk=challenge_id).first()
    if (
        challenge is None
        or challenge.consumed_at is not None
        or challenge.expires_at <= timezone.now()
        or not check_password(code, challenge.code_hash)
    ):
        return 0
    return Mailer().send(
        subject="Your COMPASS security code",
        body=(
            "Use this COMPASS security code to continue: "
            f"{code}\n\nThis code expires shortly and can be used once."
        ),
        recipients=challenge.email,
    )


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.authentication.email_change.security_alert",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def deliver_email_change_security_alert(self, request_id: str) -> int:
    """Send the mandatory alert to the previous sign-in address.

    The destination comes from the immutable request snapshot, never from User.email after
    the identity transition. No old/new address is written to logs or audit metadata.
    """

    if not isinstance(request_id, str) or not request_id:
        return 0

    from django.db import transaction

    from compass.authentication.models import EmailChangeRequest

    with transaction.atomic():
        pending = EmailChangeRequest.objects.select_for_update().filter(pk=request_id).first()
        if pending is None or pending.confirmed_at is None:
            return 0
        if pending.old_email_alert_sent_at is not None:
            return 0

        pending.old_email_alert_attempt_count += 1
        pending.save(update_fields=["old_email_alert_attempt_count"])
        destination = pending.current_email_snapshot

        # Keep the row lock through the transport call. Recovery may publish the same durable row
        # more than once, but only one task may send before old_email_alert_sent_at is stamped.
        sent = Mailer().send(
            subject="Your COMPASS sign-in email was changed",
            body=(
                "Your COMPASS sign-in email was changed. "
                "If you did not expect this change, contact the UCN Guidance and Counseling "
                "Office or your authorized COMPASS administrator immediately.\n\n"
                "No action is required if you expected this change."
            ),
            recipients=destination,
        )
        if sent == 1:
            pending.old_email_alert_sent_at = timezone.now()
            pending.save(update_fields=["old_email_alert_sent_at"])

    if sent != 1:
        raise RuntimeError("COMPASS email-change security alert was not accepted for delivery")
    return sent


@shared_task(
    bind=True,
    base=CorrelationTask,
    name="compass.authentication.email_change.recover_unsent_alerts",
)
def recover_unsent_email_change_security_alerts(self, batch_size: int = 100) -> int:
    """Re-publish durable confirmed email-change alerts whose initial enqueue was lost."""

    from compass.authentication.models import EmailChangeRequest

    bounded = batch_size if type(batch_size) is int and 1 <= batch_size <= 500 else 100
    request_ids = list(
        EmailChangeRequest.objects.filter(
            confirmed_at__isnull=False,
            old_email_alert_sent_at__isnull=True,
        )
        .order_by("confirmed_at", "id")
        .values_list("id", flat=True)[:bounded]
    )
    queued = 0
    for request_id in request_ids:
        try:
            deliver_email_change_security_alert.delay(str(request_id))
        except Exception:
            logger.warning(
                "email change security alert recovery enqueue failed",
                extra={
                    "event": "email_change_security_alert_recovery_enqueue_failed",
                    "email_change_request_id": str(request_id),
                },
            )
            continue
        queued += 1
    return queued


__all__ = [
    "deliver_email_change_security_alert",
    "deliver_email_otp",
    "recover_unsent_email_change_security_alerts",
]
