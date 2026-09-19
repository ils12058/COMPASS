"""Celery boundary for security email delivery."""

from __future__ import annotations

import re

from celery import shared_task
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from compass.integrations.mail import Mailer
from compass.tasks import CorrelationTask

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
        pending = (
            EmailChangeRequest.objects.select_for_update()
            .filter(pk=request_id)
            .first()
        )
        if pending is None or pending.confirmed_at is None:
            return 0
        if pending.old_email_alert_sent_at is not None:
            return 0

        pending.old_email_alert_attempt_count += 1
        pending.save(update_fields=["old_email_alert_attempt_count"])

        sent = Mailer().send(
            subject="Your COMPASS sign-in email was changed",
            body=(
                "Your COMPASS sign-in email was changed. "
                "If you did not expect this change, contact the UCN Guidance and Counseling "
                "Office or your authorized COMPASS administrator immediately.\n\n"
                "No action is required if you expected this change."
            ),
            recipients=pending.current_email_snapshot,
        )
        if sent:
            pending.old_email_alert_sent_at = timezone.now()
            pending.save(update_fields=["old_email_alert_sent_at"])
        return sent


__all__ = ["deliver_email_change_security_alert", "deliver_email_otp"]
