"""Write every COMPASS transactional email to local files for review; nothing is sent."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from django.core.management.base import BaseCommand

from compass.authentication.security_email import (
    render_email_changed_alert,
    render_security_code_email,
)
from compass.common.email import RenderedEmail
from compass.notifications.delivery import render_notification_email
from compass.notifications.policy import (
    NotificationChannel,
    NotificationEvent,
    get_event_definition,
)

# Placeholder only. Real codes exist solely inside the Email OTP delivery task.
SAMPLE_SECURITY_CODE = "123456"


def preview_messages() -> Iterator[tuple[str, RenderedEmail]]:
    for event in NotificationEvent:
        definition = get_event_definition(event)
        if NotificationChannel.EMAIL in definition.channels:
            yield f"notification-{definition.email_template}", render_notification_email(event)
    yield "authentication-security_code", render_security_code_email(SAMPLE_SECURITY_CODE)
    yield "authentication-email_changed", render_email_changed_alert()


class Command(BaseCommand):
    help = (
        "Render every COMPASS transactional email to .html and .txt files for visual review. "
        "Sends nothing and reads no database records."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True, type=Path)

    def handle(self, *args, output_dir: Path, **options):
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for name, message in preview_messages():
            (output_dir / f"{name}.html").write_text(message.html_body, encoding="utf-8")
            (output_dir / f"{name}.txt").write_text(
                f"Subject: {message.subject}\n\n{message.text_body}", encoding="utf-8"
            )
            count += 1
        self.stdout.write(f"Wrote {count} email previews to {output_dir}")
