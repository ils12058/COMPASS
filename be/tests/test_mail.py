from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import override_settings

from compass.integrations.mail import Mailer


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_mailer_uses_django_mailer_boundary():
    count = Mailer().send("Subject", "Body", ["recipient@example.test"])

    assert count == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Subject"


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_mailer_can_add_html_alternative_without_losing_plain_text():
    count = Mailer().send(
        "HTML Subject",
        "Plain fallback",
        "recipient@example.test",
        html_body="<p>HTML body</p>",
    )

    assert count == 1
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == "HTML Subject"
    assert message.body == "Plain fallback"
    assert message.to == ["recipient@example.test"]
    assert len(message.alternatives) == 1
    assert message.alternatives[0].content == "<p>HTML body</p>"
    assert message.alternatives[0].mimetype == "text/html"



def test_mailer_connection_probe_opens_and_closes_without_sending():
    backend = MagicMock()
    with patch("compass.integrations.mail.mail.mailers", {"default": backend}):
        Mailer().probe_connection()

    backend.open.assert_called_once_with()
    backend.close.assert_called_once_with()
    backend.send_messages.assert_not_called()
