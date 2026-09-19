"""Application-facing email adapter using Django's normal SMTP backend."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives


class Mailer:
    def send(
        self,
        subject: str,
        body: str,
        recipients: Sequence[str] | str,
        *,
        from_email: str | None = None,
        attachments: Iterable[object] = (),
        html_body: str | None = None,
    ) -> int:
        to = [recipients] if isinstance(recipients, str) else list(recipients)
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=to,
        )
        if html_body is not None:
            message.attach_alternative(html_body, "text/html")
        for attachment in attachments:
            message.attach(*attachment)
        return mail.mailers["default"].send_messages([message])
