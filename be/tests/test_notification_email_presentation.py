import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from uuid import uuid4

import pytest
from django.core import mail
from django.db import close_old_connections
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.appointments.email_presentation import AppointmentEmailRecipient
from compass.appointments.models import Appointment
from compass.appointments.services import create_student_appointment
from compass.integrations.mail import Mailer
from compass.notifications import delivery as delivery_module
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_links import NotificationEmailTarget
from compass.notifications.email_presentation import (
    EmailPresentationReason,
    NotificationEmailPresentation,
    resolve_notification_email_presentation,
)
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.models import StaffSupervision, StudentAffiliation
from tests.test_appointments import (
    active_service,
    auth_client,
    configure_availability,
    context,
    create_affiliation,
    create_list_appointment,
    future_local_start,
    make_user,
    sync_policy,
)


@pytest.fixture(autouse=True)
def local_transport_only(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


@pytest.fixture
def case(db):
    sync_policy()
    student = make_user("notif-student@example.test", "STUDENT")
    counselor = make_user("notif-counselor@example.test", "COUNSELOR")
    service = active_service(counselor)
    item = create_list_appointment(
        reference_code="NOTIF-TEST",
        student=student,
        provider=counselor,
        service=service,
        starts_at=timezone.now() + timedelta(days=2),
    )
    return student, counselor, item


def notification_for(item, recipient, *, event=NotificationEvent.APPOINTMENT_SCHEDULED):
    return create_notification_for_event(
        recipient=recipient,
        event=event,
        source_type="appointment",
        source_id=item.pk,
        target_type="APPOINTMENT",
        target_id=item.pk,
    )


def rendered_for(notification):
    return render_notification_email(
        notification.event_code, presentation=resolve_notification_email_presentation(notification)
    )


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.destinations = []
        self.resources = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.destinations.extend(value for key, value in attrs if key == "href")
        elif tag in {"img", "link", "script", "iframe", "object", "embed"}:
            self.resources.append(tag)
        assert not any(key.startswith("on") or key == "src" for key, _ in attrs)


def deny_view(user):
    UserCapabilityOverride.objects.create(
        user=user,
        capability=Capability.objects.get(code="appointments.view_self"),
        effect="REVOKE",
        reason="Synthetic access removal",
    )


@pytest.mark.parametrize(
    "recipient_index,kind",
    [
        (0, AppointmentEmailRecipient.STUDENT),
        (1, AppointmentEmailRecipient.CURRENT_COUNSELOR),
    ],
)
def test_authorized_link_is_minimal_and_html_text_agree(case, recipient_index, kind):
    student, counselor, item = case
    notice = notification_for(item, (student, counselor)[recipient_index])
    plan = resolve_notification_email_presentation(notice)
    assert plan.recipient_class == kind
    rendered = rendered_for(notice)
    expected = f"https://portal.example/portal/appointments/{item.pk}"
    links = Links()
    links.feed(rendered.html_body)
    assert links.destinations == [expected] and not links.resources
    assert rendered.text_body.count(expected) == 1
    for body in (rendered.text_body, rendered.html_body):
        assert "View Appointment in COMPASS" in body
        assert "may have changed since this notice" in body
        for value in (
            student.email,
            student.get_full_name(),
            counselor.get_full_name(),
            item.service.name,
            item.reference_code,
            item.starts_at.isoformat(),
        ):
            assert value not in body
    assert str(item.pk) not in repr(plan)


def test_real_booking_delivers_one_link_per_recipient_without_duplicates(case):
    student, counselor, old_item = case
    service_id = old_item.service_id
    old_item.delete()
    configure_availability(counselor, counselor)
    item = create_student_appointment(
        student=student,
        provider_id=counselor.pk,
        service_id=service_id,
        delivery_mode="IN_PERSON",
        starts_at=future_local_start(),
        context=context(student),
    )
    notices = Notification.objects.filter(event_code=NotificationEvent.APPOINTMENT_SCHEDULED)
    assert notices.count() == 2
    assert set(notices.values_list("recipient_id", flat=True)) == {student.pk, counselor.pk}
    for notice in notices:
        delivery = EmailDelivery.objects.get(notification=notice)
        assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
        assert deliver_email_delivery(delivery.pk) == "skipped"
        delivery.refresh_from_db()
        assert delivery.attempt_count == 1 and delivery.claim_token is None
    assert len(mail.outbox) == 2
    assert all(f"/portal/appointments/{item.pk}" in message.body for message in mail.outbox)
    assert Notification.objects.count() == 2 and EmailDelivery.objects.count() == 2


@pytest.mark.parametrize(
    "change",
    [
        "former_counselor",
        "unrelated_counselor",
        "other_student",
        "removed_capability",
        "inactive",
        "role_changed",
    ],
)
def test_notification_ownership_never_grants_record_link(case, change):
    student, counselor, item = case
    recipient = counselor
    if change == "former_counselor":
        Appointment.objects.filter(pk=item.pk).update(
            provider=make_user("replacement@example.test", "COUNSELOR")
        )
    elif change == "unrelated_counselor":
        recipient = make_user("unrelated@example.test", "COUNSELOR")
    elif change == "other_student":
        recipient = make_user("other-student@example.test", "STUDENT")
    elif change == "removed_capability":
        recipient = student
        deny_view(student)
    elif change == "inactive":
        User.objects.filter(pk=recipient.pk).update(is_active=False)
    else:
        User.objects.filter(pk=recipient.pk).update(role=Role.objects.get(code="IT_ADMIN"))
    notice = notification_for(item, recipient)
    assert (
        resolve_notification_email_presentation(notice).reason
        == EmailPresentationReason.RECIPIENT_DENIED
    )
    rendered = rendered_for(notice)
    assert "https://" not in rendered.text_body + rendered.html_body
    assert str(item.pk) not in rendered.text_body + rendered.html_body


def test_staff_link_tracks_current_college_and_supervision(case):
    student, counselor, item = case
    create_affiliation(student, counselor)
    staff = make_user("staff@example.test", "GUIDANCE_SERVICES_STAFF")
    supervision = StaffSupervision.objects.create(staff=staff, supervisor=counselor)
    notice = notification_for(item, staff)
    assert (
        resolve_notification_email_presentation(notice).recipient_class
        == AppointmentEmailRecipient.AUTHORIZED_STAFF
    )
    supervision.delete()
    assert (
        resolve_notification_email_presentation(notice).reason
        == EmailPresentationReason.RECIPIENT_DENIED
    )
    StaffSupervision.objects.create(staff=staff, supervisor=counselor)
    StudentAffiliation.objects.filter(student=student).delete()
    assert resolve_notification_email_presentation(notice).target is None


@pytest.mark.parametrize(
    "kind",
    [
        "missing_source",
        "mismatched_source",
        "missing_target",
        "unsupported_target",
        "origin_missing",
        "origin_invalid",
    ],
)
def test_legacy_or_incomplete_notifications_send_generic_mail(case, kind, settings):
    student, _, item = case
    notice = notification_for(item, student)
    if kind == "missing_source":
        Appointment.objects.filter(pk=item.pk).delete()
    elif kind == "mismatched_source":
        notice.source_id = uuid4()
    elif kind == "missing_target":
        notice.target_id = None
    elif kind == "unsupported_target":
        notice.target_type = "UNKNOWN"
    elif kind == "origin_missing":
        settings.COMPASS_PORTAL_ORIGIN = ""
    else:
        settings.COMPASS_PORTAL_ORIGIN = "https://evil.test/@unsafe?token=secret"
    notice.save()
    assert (
        deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk)
        == EmailDeliveryStatus.SENT
    )
    assert "href=" not in mail.outbox[0].alternatives[0].content
    assert "https://" not in mail.outbox[0].body
    assert mail.outbox[0].body == render_notification_email(notice.event_code).text_body


@pytest.mark.parametrize("state", ["CANCELLED", "COMPLETED", "NO_SHOW", "PAST"])
def test_no_longer_upcoming_scheduled_notice_is_suppressed(case, state):
    student, _, item = case
    notice = notification_for(item, student)
    changes = {"status": state, f"{state.lower()}_at": timezone.now()}
    if state == "PAST":
        changes = {
            "starts_at": timezone.now() - timedelta(hours=2),
            "ends_at": timezone.now() - timedelta(hours=1),
        }
    Appointment.objects.filter(pk=item.pk).update(**changes)
    delivery = EmailDelivery.objects.get(notification=notice)
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.CANCELLED
    delivery.refresh_from_db()
    assert delivery.failure_code == "source_ineligible" and delivery.claim_token is None
    assert not mail.outbox


@pytest.mark.parametrize("change", ["email", "inactive", "capability", "reassignment", "cancelled"])
def test_final_check_blocks_changes_during_render(case, change, monkeypatch):
    student, counselor, item = case
    recipient = counselor if change == "reassignment" else student
    notice = notification_for(item, recipient)
    original = delivery_module.render_notification_email

    def render_then_change(*args, **kwargs):
        rendered = original(*args, **kwargs)
        if change == "email":
            User.objects.filter(pk=recipient.pk).update(email="changed@example.test")
        elif change == "inactive":
            User.objects.filter(pk=recipient.pk).update(is_active=False)
        elif change == "capability":
            deny_view(student)
        elif change == "reassignment":
            Appointment.objects.filter(pk=item.pk).update(
                provider=make_user("new@example.test", "COUNSELOR")
            )
        else:
            Appointment.objects.filter(pk=item.pk).update(
                status="CANCELLED", cancelled_at=timezone.now()
            )
        return rendered

    monkeypatch.setattr(delivery_module, "render_notification_email", render_then_change)
    assert (
        deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk)
        == EmailDeliveryStatus.CANCELLED
    )
    assert not mail.outbox


def test_retry_rechecks_access_and_current_email(case, monkeypatch):
    student, _, item = case
    notice = notification_for(item, student)
    delivery = EmailDelivery.objects.get(notification=notice)
    sends = []

    def send(self, **kwargs):
        sends.append(kwargs)
        return 0 if len(sends) == 1 else 1

    monkeypatch.setattr(Mailer, "send", send)
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    User.objects.filter(pk=student.pk).update(email="current@example.test")
    deny_view(student)
    EmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
    assert sends[1]["recipients"] == "current@example.test"
    assert "https://" in sends[0]["body"] and "https://" not in sends[1]["body"]
    assert Notification.objects.count() == 1 and EmailDelivery.objects.count() == 1


def test_private_source_and_hostile_labels_never_enter_context(case, monkeypatch):
    student, _, item = case
    hostile = '<img src="https://evil.test/track" onerror="alert(1)"> PRIVATE COUNSELING NARRATIVE'
    item.service.name = hostile
    item.service.description = "https://evil.test/private?session_token=secret"
    item.service.save()
    item.service_name_snapshot = hostile
    item.save()
    notice = notification_for(item, student)
    notice.title, notice.message = hostile, "assessment scores=99; MFA_SECRET; referral narrative"
    notice.save()
    from compass.common import email as email_module

    original, captured = email_module.render_to_string, []

    def capture(template, values, *args, **kwargs):
        captured.append(values)
        return original(template, values, *args, **kwargs)

    monkeypatch.setattr(email_module, "render_to_string", capture)
    rendered = rendered_for(notice)
    assert all(set(values) == {"subject", "action_url"} for values in captured)
    assert all(type(value) is str for values in captured for value in values.values())
    for forbidden in (hostile, "evil.test", "PRIVATE", "assessment", "MFA_SECRET", "session_token"):
        assert forbidden not in rendered.text_body + rendered.html_body


@pytest.mark.parametrize("stage", ["resolver", "renderer", "revalidation", "transport"])
def test_failure_logs_never_contain_context_or_exception(case, stage, monkeypatch, caplog):
    student, _, item = case
    notice = notification_for(item, student)
    private = f"PRIVATE {student.email} /portal/appointments/{item.pk} password=SECRET"

    def fail(*args, **kwargs):
        raise RuntimeError(private)

    if stage == "resolver":
        monkeypatch.setattr(delivery_module, "resolve_notification_email_presentation", fail)
    elif stage == "renderer":
        monkeypatch.setattr(delivery_module, "render_notification_email", fail)
    elif stage == "revalidation":
        monkeypatch.setattr(delivery_module, "_email_claim_is_current", fail)
    else:
        monkeypatch.setattr(Mailer, "send", fail)
    delivery = EmailDelivery.objects.get(notification=notice)
    with caplog.at_level("INFO", logger="compass.notifications"):
        outcome = deliver_email_delivery(delivery.pk)
    assert outcome == ("retry_or_failed" if stage == "transport" else EmailDeliveryStatus.FAILED)
    assert private not in caplog.text
    assert str(item.pk) not in repr([vars(record) for record in caplog.records])
    assert not mail.outbox
    delivery.refresh_from_db()
    assert delivery.failure_code == (
        "transport_error" if stage == "transport" else "template_error"
    )


def test_renderer_rejects_untyped_context_event_and_unapproved_target(case):
    student, _, item = case
    notice = notification_for(item, student)
    for plan in [
        {"action_url": "https://evil.test"},
        NotificationEmailPresentation(
            "security.password.reset", EmailPresentationReason.GENERIC_EVENT
        ),
        NotificationEmailPresentation(
            notice.event_code,
            EmailPresentationReason.LINK_AVAILABLE,
            target=NotificationEmailTarget("ACCOUNT_SECURITY", student.pk),
        ),
    ]:
        with pytest.raises(ValueError):
            render_notification_email(notice.event_code, presentation=plan)
    plan = NotificationEmailPresentation(
        notice.event_code,
        EmailPresentationReason.LINK_AVAILABLE,
        target=NotificationEmailTarget("APPOINTMENT", '//evil.test/" onclick="alert(1)'),
    )
    rendered = render_notification_email(notice.event_code, presentation=plan)
    assert "href=" not in rendered.html_body and "evil.test" not in rendered.text_body


@pytest.mark.parametrize(
    "event", [NotificationEvent.APPOINTMENT_REASSIGNED, NotificationEvent.SECURITY_PASSWORD_RESET]
)
def test_other_events_retain_fixed_copy(case, event):
    student, _, item = case
    notice = notification_for(item, student, event=event)
    assert (
        resolve_notification_email_presentation(notice).reason
        == EmailPresentationReason.GENERIC_EVENT
    )
    assert rendered_for(notice) == render_notification_email(event)


def test_record_url_requires_session_and_independent_authorization(case):
    student, counselor, item = case
    path = f"/api/v1/appointments/{item.pk}"
    assert Client().get(path).status_code == 401
    assert auth_client(student).get(path).status_code == 200
    assert auth_client(counselor).get(path).status_code == 200
    response = auth_client(make_user("other@example.test", "STUDENT")).get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "appointment_not_found"
    assert item.reference_code not in response.content.decode()


@pytest.mark.django_db(transaction=True)
def test_linked_delivery_keeps_concurrent_claim_protection(case, monkeypatch):
    student, _, item = case
    notice = notification_for(item, student)
    delivery = EmailDelivery.objects.get(notification=notice)
    entered, release = threading.Event(), threading.Event()
    sent = []

    def send(self, **kwargs):
        sent.append(kwargs)
        entered.set()
        assert release.wait(timeout=10)
        return 1

    def worker():
        close_old_connections()
        try:
            return deliver_email_delivery(delivery.pk)
        finally:
            close_old_connections()

    monkeypatch.setattr(Mailer, "send", send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        try:
            assert entered.wait(timeout=10)
            assert pool.submit(worker).result(timeout=10) == "skipped"
        finally:
            release.set()
        assert first.result(timeout=10) == EmailDeliveryStatus.SENT
    assert len(sent) == 1 and str(item.pk) in sent[0]["body"]


@pytest.mark.parametrize("change", ["supervision", "college"])
def test_final_check_requeries_staff_scope(case, change, monkeypatch):
    student, counselor, item = case
    create_affiliation(student, counselor)
    staff = make_user("scope-staff@example.test", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=staff, supervisor=counselor)
    notice = notification_for(item, staff)
    original = delivery_module.render_notification_email

    def render_then_revoke(*args, **kwargs):
        rendered = original(*args, **kwargs)
        if change == "supervision":
            StaffSupervision.objects.filter(staff=staff).delete()
        else:
            StudentAffiliation.objects.filter(student=student).delete()
        return rendered

    monkeypatch.setattr(delivery_module, "render_notification_email", render_then_revoke)
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == (
        EmailDeliveryStatus.CANCELLED
    )
    assert not mail.outbox


def test_cancelled_source_is_suppressed_even_after_access_is_lost(case):
    student, counselor, item = case
    notice = notification_for(item, counselor)
    Appointment.objects.filter(pk=item.pk).update(
        provider=make_user("replacement@example.test", "COUNSELOR"),
        status="CANCELLED",
        cancelled_at=timezone.now(),
    )
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == (
        EmailDeliveryStatus.CANCELLED
    )
    assert not mail.outbox
