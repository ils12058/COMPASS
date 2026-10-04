"""Branded transactional email: shared shell, template contract, privacy, and security email."""

from __future__ import annotations

import html
import io
import logging
import re
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.template.loader import get_template
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.models import AuditEvent
from compass.authentication.email_otp import issue_email_otp
from compass.authentication.models import EmailChangeRequest, EmailOTPChallenge
from compass.authentication.security_email import (
    EMAIL_CHANGED_SUBJECT,
    SECURITY_CODE_SUBJECT,
    render_email_changed_alert,
    render_security_code_email,
)
from compass.authentication.tasks import (
    deliver_email_change_security_alert,
    deliver_email_otp,
)
from compass.common.rate_limit import RateLimitResult
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification
from compass.notifications.policy import (
    _EVENT_CATALOG,
    NotificationChannel,
    NotificationEvent,
    NotificationPolicy,
)
from compass.platform_ops.management.commands.render_email_previews import preview_messages

LOCMEM = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
NOTIFICATION_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[1]
    / "compass"
    / "notifications"
    / "templates"
    / "notifications"
    / "email"
)
FOOTER_LINES = (
    "This is an automated COMPASS message.",
    "University of Camarines Norte",
    "Guidance and Counseling Office",
)
EMAIL_EVENTS = tuple(
    event
    for event in NotificationEvent
    if NotificationChannel.EMAIL in _EVENT_CATALOG[event].channels
)
ALL_MESSAGES = tuple(preview_messages())


class _VisibleText(HTMLParser):
    """Collect rendered text, skipping <head> content such as <title> and <style>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._head_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self._head_depth += 1

    def handle_endtag(self, tag):
        if tag == "head":
            self._head_depth -= 1

    def handle_data(self, data):
        if not self._head_depth:
            self.parts.append(data)


def visible_text(markup: str) -> str:
    parser = _VisibleText()
    parser.feed(markup)
    return " ".join(" ".join(parser.parts).split())


def message_ids():
    return [name for name, _message in ALL_MESSAGES]


# --- Template contract -------------------------------------------------------------------------


def test_every_email_event_has_a_renderable_template_pair():
    for event in NotificationEvent:
        definition = _EVENT_CATALOG[event]
        if NotificationChannel.EMAIL not in definition.channels:
            assert definition.email_subject == ""
            assert definition.email_template == ""
            continue

        assert definition.email_subject.strip()
        assert definition.email_template.strip()
        get_template(f"notifications/email/{definition.email_template}.txt")
        get_template(f"notifications/email/{definition.email_template}.html")
        rendered = render_notification_email(event)
        assert rendered.subject == definition.email_subject
        assert rendered.text_body.strip()
        assert rendered.html_body.strip()


def test_notification_template_directory_matches_the_event_catalog():
    expected = {_EVENT_CATALOG[event].email_template for event in EMAIL_EVENTS}
    text_templates = {path.stem for path in NOTIFICATION_TEMPLATE_DIR.glob("*.txt")}
    html_templates = {path.stem for path in NOTIFICATION_TEMPLATE_DIR.glob("*.html")}

    assert text_templates == expected
    assert html_templates == expected
    assert {path.suffix for path in NOTIFICATION_TEMPLATE_DIR.iterdir()} == {".txt", ".html"}


# --- Shared shell --------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "message"), ALL_MESSAGES, ids=message_ids())
def test_every_message_uses_the_branded_shell(name, message):
    text = visible_text(message.html_body)

    assert message.html_body.lstrip().startswith("<!doctype html>")
    assert '<html lang="en">' in message.html_body
    assert 'name="viewport"' in message.html_body
    assert f"<title>{html.escape(message.subject)}</title>" in message.html_body
    heading = re.search(r"<h1 [^>]*>([^<]+)</h1>", message.html_body)
    assert heading
    # Reading order: institutional header, then the message, then the footer.
    header_at = text.index("COMPASS University of Camarines Norte Guidance and Counseling Office")
    heading_at = text.index(heading.group(1))
    footer_at = text.index("This is an automated COMPASS message.")
    assert header_at < heading_at < footer_at
    for line in FOOTER_LINES:
        assert line in text[footer_at:]
    assert message.text_body.rstrip().endswith("\n".join(FOOTER_LINES))


@pytest.mark.parametrize(("name", "message"), ALL_MESSAGES, ids=message_ids())
def test_messages_load_nothing_remote_and_run_nothing(name, message):
    combined = "\n".join((message.subject, message.text_body, message.html_body)).lower()
    for forbidden in (
        "<script",
        "javascript:",
        "<img",
        "<link",
        "<iframe",
        "<form",
        "<object",
        "<embed",
        "@import",
        "url(",
        " src=",
        " href=",
        "http://",
        "https://",
        "{{",
        "{%",
    ):
        assert forbidden not in combined
    assert "<" not in message.text_body


@pytest.mark.parametrize(("name", "message"), ALL_MESSAGES, ids=message_ids())
def test_html_and_plain_text_carry_the_same_wording(name, message):
    text = visible_text(message.html_body)
    for line in message.text_body.splitlines():
        if line.strip():
            assert " ".join(line.split()) in text


def test_security_messages_use_the_security_notice_variant():
    for event in EMAIL_EVENTS:
        rendered = render_notification_email(event)
        security = _EVENT_CATALOG[event].policy == NotificationPolicy.MANDATORY_SECURITY
        assert ("Security notice" in rendered.text_body) is security
        assert ("Security notice" in visible_text(rendered.html_body)) is security

    alert = render_email_changed_alert()
    assert alert.text_body.startswith("Security notice\n\n")
    assert "Security notice" in visible_text(alert.html_body)
    assert "Security notice" not in render_security_code_email("482193").text_body


def test_previews_command_writes_every_message_without_sending(tmp_path):
    with override_settings(MAILERS=LOCMEM):
        call_command("render_email_previews", output_dir=tmp_path, stdout=io.StringIO())
        assert mail.outbox == []

    written = {path.name for path in tmp_path.iterdir()}
    for name, _message in ALL_MESSAGES:
        assert {f"{name}.html", f"{name}.txt"} <= written
    assert len(ALL_MESSAGES) == len(EMAIL_EVENTS) + 2


# --- Notification privacy ---------------------------------------------------------------------


def test_notification_templates_receive_no_record_or_domain_context():
    from compass.common import email as email_module

    captured: list[dict] = []
    original = email_module.render_to_string

    def capture(template_name, context=None, *args, **kwargs):
        captured.append(dict(context or {}))
        return original(template_name, context, *args, **kwargs)

    with patch.object(email_module, "render_to_string", side_effect=capture):
        for event in EMAIL_EVENTS:
            captured.clear()
            render_notification_email(event)
            assert captured == [{"subject": _EVENT_CATALOG[event].email_subject}] * 2


@pytest.mark.parametrize(
    ("event", "protected_terms"),
    [
        (NotificationEvent.CALL_SLIP_ISSUED, ("referral", "remarks", "course", "destination")),
        (NotificationEvent.CALL_SLIP_VOIDED, ("referral", "remarks", "reason", "destination")),
        (NotificationEvent.APPOINTMENT_SCHEDULED, ("purpose", "concern", "counselor", "online")),
        (NotificationEvent.APPOINTMENT_REASSIGNED, ("purpose", "concern", "counselor")),
        (
            NotificationEvent.COUNSELING_SHARED_SUMMARY_PUBLISHED,
            ("concern", "notes", "session", "diagnos", "summary:"),
        ),
        (
            NotificationEvent.ECOUNSELING_CONSENT_REQUESTED,
            ("recording", "camera", "microphone", "declined", "granted", "room", "meeting"),
        ),
        (NotificationEvent.INVENTORY_REOPENED, ("answer", "family", "health", "reason")),
        (NotificationEvent.EXIT_INTERVIEW_REOPENED, ("answer", "reason", "remarks")),
        (NotificationEvent.GOOD_MORAL_ISSUED, ("purpose", "receipt", "disciplinary", "control")),
    ],
)
def test_sensitive_domain_email_keeps_protected_detail_inside_compass(event, protected_terms):
    rendered = render_notification_email(event)
    combined = "\n".join(
        (rendered.subject, rendered.text_body, visible_text(rendered.html_body))
    ).lower()
    assert "sign in" in combined or "in compass" in combined
    for term in protected_terms:
        assert term not in combined


@override_settings(
    SMTP_HOST="smtp-host-sentinel.example.test",
    SMTP_USERNAME="smtp-user-sentinel",
    SMTP_PASSWORD="smtp-password-sentinel",
    DEFAULT_FROM_EMAIL="sender-sentinel@example.test",
)
def test_rendered_messages_carry_no_transport_configuration():
    for _name, message in preview_messages():
        combined = "\n".join((message.subject, message.text_body, message.html_body))
        for sentinel in ("smtp-host-sentinel", "smtp-user-sentinel", "smtp-password-sentinel"):
            assert sentinel not in combined
        assert "sender-sentinel" not in combined


def test_rendered_email_repr_omits_bodies():
    rendered = render_security_code_email("482193")
    assert "482193" not in repr(rendered)


# --- Email OTP -------------------------------------------------------------------------------


class AllowLimiter:
    def consume_with_failure_policy(self, policy, subject):
        return RateLimitResult(
            allowed=True,
            count=1,
            limit=policy.limit,
            remaining=policy.limit - 1,
            retry_after_seconds=1,
        )


def make_user(email: str) -> User:
    role, _created = Role.objects.get_or_create(code="STUDENT", defaults={"name": "Student"})
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=role,
        first_name="Synthetic",
        last_name="Recipient",
    )


@pytest.fixture
def security_logs(caplog):
    """Capture COMPASS and Celery records; those loggers do not propagate to the root handler."""

    names = ("compass", "celery", "django")
    caplog.set_level(logging.DEBUG)
    for name in names:
        caplog.set_level(logging.DEBUG, logger=name)
    loggers = [logging.getLogger(name) for name in names]
    for logger in loggers:
        logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        for logger in loggers:
            logger.removeHandler(caplog.handler)


def issue_challenge(
    user: User,
    code: str = "482193",
    *,
    purpose: str = "security_challenge",
    now=None,
):
    with patch("compass.authentication.email_otp._new_code", return_value=code):
        return issue_email_otp(
            email=user.email,
            purpose=purpose,
            user=user,
            limiter=AllowLimiter(),
            dispatch=False,
            now=now,
        ).challenge


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_otp_is_sent_as_plain_text_and_branded_html():
    user = make_user("otp-multipart@example.edu")
    challenge = issue_challenge(user)
    mail.outbox.clear()

    assert deliver_email_otp.run(str(challenge.pk), "482193") == 1

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == SECURITY_CODE_SUBJECT
    assert message.to == ["otp-multipart@example.edu"]
    assert "\n482193\n" in message.body
    assert "This code expires shortly and can be used once." in message.body
    assert len(message.alternatives) == 1
    html_body, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    # One selectable text node holds the exact six digits; spacing is CSS only.
    assert re.search(r">482193</td>", html_body)
    assert "Your COMPASS security code" in visible_text(html_body)


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
@pytest.mark.parametrize("code", ["000000", "48219", "4821930", "48219a", "482 193", "", 482193])
def test_email_otp_with_wrong_or_malformed_code_sends_nothing(code):
    user = make_user("otp-invalid@example.edu")
    challenge = issue_challenge(user)
    mail.outbox.clear()

    assert deliver_email_otp.run(str(challenge.pk), code) == 0
    assert mail.outbox == []


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_otp_for_missing_expired_or_consumed_challenge_sends_nothing():
    user = make_user("otp-unusable@example.edu")
    mail.outbox.clear()
    assert deliver_email_otp.run("", "482193") == 0
    assert deliver_email_otp.run("00000000-0000-0000-0000-000000000000", "482193") == 0

    issued_long_ago = timezone.now() - timedelta(seconds=settings.AUTH_EMAIL_OTP_TTL_SECONDS + 60)
    expired = issue_challenge(user, now=issued_long_ago)
    assert deliver_email_otp.run(str(expired.pk), "482193") == 0

    consumed = issue_challenge(user, "135790")
    EmailOTPChallenge.objects.filter(pk=consumed.pk).update(consumed_at=timezone.now())
    assert deliver_email_otp.run(str(consumed.pk), "135790") == 0
    assert mail.outbox == []


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_otp_delivery_does_not_persist_or_log_the_code(security_logs):
    user = make_user("otp-transient@example.edu")
    challenge = issue_challenge(user)
    audit_before = AuditEvent.objects.count()
    security_logs.clear()

    result = deliver_email_otp.run(str(challenge.pk), "482193")

    assert result == 1
    assert "482193" not in security_logs.text
    stored = EmailOTPChallenge.objects.filter(pk=challenge.pk).values().get()
    assert all("482193" not in str(value) for value in stored.values())
    assert Notification.objects.count() == 0
    assert EmailDelivery.objects.count() == 0
    assert AuditEvent.objects.count() == audit_before
    assert all("482193" not in str(event) for event in AuditEvent.objects.values())


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_otp_render_failure_sends_nothing_and_keeps_the_code_out_of_logs(security_logs):
    user = make_user("otp-render-failure@example.edu")
    challenge = issue_challenge(user)
    mail.outbox.clear()
    security_logs.clear()

    with patch(
        "compass.authentication.tasks.render_security_code_email",
        side_effect=RuntimeError("template failed for 482193"),
    ):
        assert deliver_email_otp.run(str(challenge.pk), "482193") == 0

    assert mail.outbox == []
    assert "email_otp_render_failed" in [getattr(r, "event", "") for r in security_logs.records]
    assert "482193" not in security_logs.text


# --- Email-change security alert ---------------------------------------------------------------


def confirmed_email_change(old: str, new: str) -> EmailChangeRequest:
    user = make_user(new)
    administrator = make_user("alert-actor@example.edu")
    challenge = issue_challenge(user, "246802", purpose="email_change")
    now = timezone.now()
    return EmailChangeRequest.objects.create(
        user=user,
        requested_by=administrator,
        current_email_snapshot=old,
        new_email=new,
        email_otp_challenge=challenge,
        expires_at=now + timedelta(hours=1),
        current_email_authorized_at=now,
        confirmed_at=now,
    )


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_change_alert_is_multipart_and_names_neither_address_nor_actor():
    pending = confirmed_email_change("alert-before@example.edu", "alert-after@example.edu")
    mail.outbox.clear()

    assert deliver_email_change_security_alert.run(str(pending.pk)) == 1

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == EMAIL_CHANGED_SUBJECT
    assert message.to == ["alert-before@example.edu"]
    assert "Your COMPASS sign-in email was changed." in message.body
    assert "No action is required if you expected this change." in message.body
    assert len(message.alternatives) == 1
    html_body, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert "contact the UCN Guidance and Counseling Office" in visible_text(html_body)
    for content in (message.subject, message.body, html_body):
        for withheld in (
            "alert-before@example.edu",
            "alert-after@example.edu",
            "alert-actor@example.edu",
            "Synthetic",
            "Recipient",
            "246802",
            str(pending.pk),
        ):
            assert withheld not in content


@override_settings(MAILERS=LOCMEM)
@pytest.mark.django_db
def test_email_change_alert_stays_single_send_and_recoverable():
    pending = confirmed_email_change("retry-before@example.edu", "retry-after@example.edu")
    mail.outbox.clear()

    with (
        patch("compass.authentication.tasks.Mailer.send", return_value=0),
        pytest.raises(RuntimeError),
    ):
        deliver_email_change_security_alert.run(str(pending.pk))
    pending.refresh_from_db()
    assert pending.old_email_alert_sent_at is None
    assert pending.old_email_alert_attempt_count == 1

    assert deliver_email_change_security_alert.run(str(pending.pk)) == 1
    assert deliver_email_change_security_alert.run(str(pending.pk)) == 0
    assert len(mail.outbox) == 1
    pending.refresh_from_db()
    assert pending.old_email_alert_sent_at is not None
    assert pending.old_email_alert_attempt_count == 2
