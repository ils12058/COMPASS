import html
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from django.core import mail
from django.db import close_old_connections, transaction
from django.utils import timezone
from django.utils.safestring import mark_safe

from compass.accounts.models import Capability, User, UserCapabilityOverride
from compass.appointments.email_presentation import (
    AppointmentEmailDetail,
    AppointmentEmailField,
    appointment_email_schedule,
)
from compass.appointments.models import (
    Appointment,
    AppointmentChangeEvent,
    AppointmentReminderOccurrence,
)
from compass.integrations.mail import Mailer
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from tests.test_appointments import (
    active_service,
    create_list_appointment,
    make_user,
    sync_policy,
)

EVENTS = tuple(event for event in NotificationEvent if event.value.startswith("appointment."))
POLICY = "operational_v1"


@pytest.fixture(autouse=True)
def no_external_transport(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


@pytest.fixture
def case(db):
    sync_policy()
    student = make_user("email-student@example.test", "STUDENT", first_name="PrivateStudentName")
    provider = make_user(
        "email-provider@example.test", "COUNSELOR", first_name="Synthetic Counselor"
    )
    previous = make_user(
        "email-previous@example.test", "COUNSELOR", first_name="Previous Counselor"
    )
    service = active_service(provider)
    item = create_list_appointment(
        reference_code="APT-SYNTHETIC-02",
        student=student,
        provider=provider,
        service=service,
        starts_at=datetime(2099, 10, 23, 1, tzinfo=UTC),
    )
    return student, provider, previous, item


def notice(case, event, *, recipient=None):
    student, provider, previous, item = case
    source_id, source_type = item.pk, "appointment"
    if event == NotificationEvent.APPOINTMENT_RESCHEDULED:
        source_type = "appointment_change_event"
        source = AppointmentChangeEvent.objects.create(
            appointment=item,
            event_type="RESCHEDULED",
            occurred_at=timezone.now(),
            previous_starts_at=item.starts_at - timedelta(hours=1),
            previous_ends_at=item.ends_at - timedelta(hours=1),
            new_starts_at=item.starts_at,
            new_ends_at=item.ends_at,
            reason="PRIVATE CHANGE REASON",
        )
        source_id = source.pk
        Appointment.objects.filter(pk=item.pk).update(
            reminder_revision=2,
            reminder_revision_started_at=source.occurred_at,
        )
    elif event == NotificationEvent.APPOINTMENT_REASSIGNED:
        source_type = "appointment_change_event"
        source = AppointmentChangeEvent.objects.create(
            appointment=item,
            event_type="REASSIGNED",
            occurred_at=timezone.now(),
            previous_provider=previous,
            new_provider=provider,
            reason="PRIVATE REASSIGNMENT REASON",
        )
        source_id = source.pk
        Appointment.objects.filter(pk=item.pk).update(
            reminder_revision=2,
            reminder_revision_started_at=source.occurred_at,
        )
    elif event == NotificationEvent.APPOINTMENT_CANCELLED:
        Appointment.objects.filter(pk=item.pk).update(
            status="CANCELLED", cancelled_at=timezone.now()
        )
    elif "reminder" in event.value:
        source_type = "appointment_reminder"
        kind = {
            NotificationEvent.APPOINTMENT_REMINDER_24H: "AUTO_24H",
            NotificationEvent.APPOINTMENT_REMINDER_3H: "AUTO_3H",
            NotificationEvent.APPOINTMENT_REMINDER_MANUAL: "MANUAL",
        }[event]
        source = AppointmentReminderOccurrence.objects.create(
            appointment=item,
            recipient=student,
            kind=kind,
            revision=1,
            starts_at=item.starts_at,
            issued_at=timezone.now(),
        )
        source_id = source.pk
    return create_notification_for_event(
        recipient=recipient or student,
        event=event,
        source_type=source_type,
        source_id=source_id,
        target_type="APPOINTMENT",
        target_id=item.pk,
    )


def resolve_render(notification):
    plan = resolve_notification_email_presentation(notification)
    return plan, render_notification_email(notification.event_code, presentation=plan)


@pytest.mark.parametrize("event", EVENTS)
def test_all_seven_events_keep_fixed_copy_without_approval(case, event):
    notification = notice(case, event)
    plan, message = resolve_render(notification)
    assert plan.appointment_facts is None
    assert "APT-SYNTHETIC-02" not in message.text_body + message.html_body
    if event != NotificationEvent.APPOINTMENT_SCHEDULED:
        assert message == render_notification_email(event)


@pytest.mark.parametrize("policy", ["", None, "true", "OPERATIONAL_V1", "unknown", [POLICY]])
def test_invalid_approval_policy_fails_to_minimal(case, settings, policy):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = policy
    plan, message = resolve_render(notice(case, NotificationEvent.APPOINTMENT_SCHEDULED))
    assert plan.appointment_facts is None
    assert "APT-SYNTHETIC-02" not in message.text_body
    assert "/portal/appointments/" in message.text_body


@pytest.mark.parametrize("event", EVENTS)
def test_approved_student_fields_and_links_for_every_event(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    plan, message = resolve_render(notice(case, event))
    assert plan.appointment_facts is not None
    assert "APT-SYNTHETIC-02" in message.text_body
    assert "Philippine Time" in message.text_body
    assert "9:00 AM" in message.text_body
    assert (
        "Synthetic Counselor" in message.text_body
        or event == NotificationEvent.APPOINTMENT_CANCELLED
    )
    assert f"https://portal.example/portal/appointments/{case[3].pk}" in message.text_body
    for private in ("PrivateStudentName", case[0].email, "PRIVATE", "Previous Counselor"):
        assert private not in message.text_body + message.html_body
    assert "APT-SYNTHETIC-02" not in repr(plan)
    assert "Synthetic Counselor" not in repr(plan.appointment_facts)
    for row in plan.appointment_facts.rows:
        assert row.value in message.text_body
    if event == NotificationEvent.APPOINTMENT_RESCHEDULED:
        assert "Previous date" in message.text_body and "Updated date" in message.text_body
        assert "8:00 AM" in message.text_body
    if event == NotificationEvent.APPOINTMENT_CANCELLED:
        assert "cancelled" in message.text_body.lower()
        assert "upcoming" not in message.text_body.lower()


@pytest.mark.parametrize(
    "event",
    [
        NotificationEvent.APPOINTMENT_SCHEDULED,
        NotificationEvent.APPOINTMENT_RESCHEDULED,
        NotificationEvent.APPOINTMENT_REASSIGNED,
        NotificationEvent.APPOINTMENT_CANCELLED,
    ],
)
def test_current_counselor_has_no_student_identity_or_provider_names(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    plan, message = resolve_render(notice(case, event, recipient=case[1]))
    assert plan.appointment_facts is not None
    assert "APT-SYNTHETIC-02" in message.text_body
    for private in (
        "PrivateStudentName",
        "Synthetic Counselor",
        "Previous Counselor",
        case[0].email,
    ):
        assert private not in message.text_body + message.html_body


def test_former_counselor_is_minimal_even_with_other_management_access(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_REASSIGNED, recipient=case[2])
    plan, message = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is None
    assert message == render_notification_email(notification.event_code)


@pytest.mark.parametrize("change", ["reschedule", "reassign"])
def test_initial_scheduled_event_never_borrows_changed_facts(case, settings, change):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_SCHEDULED)
    notice(
        case,
        NotificationEvent.APPOINTMENT_RESCHEDULED
        if change == "reschedule"
        else NotificationEvent.APPOINTMENT_REASSIGNED,
    )
    plan, message = resolve_render(notification)
    assert plan.appointment_facts is None
    assert "/portal/appointments/" in message.text_body
    assert "may have changed" in message.text_body


@pytest.mark.parametrize(
    "event", [NotificationEvent.APPOINTMENT_RESCHEDULED, NotificationEvent.APPOINTMENT_REASSIGNED]
)
def test_superseded_changes_are_suppressed_without_changing_event_identity(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, event)
    source_id = notification.source_id
    notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    plan = resolve_notification_email_presentation(notification)
    assert plan.suppress
    delivery = EmailDelivery.objects.get(notification=notification)
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.CANCELLED
    notification.refresh_from_db()
    assert notification.source_id == source_id
    assert not mail.outbox


@pytest.mark.parametrize(
    "start,end,date_part,time_part",
    [
        (
            datetime(2099, 10, 23, 1, tzinfo=UTC),
            datetime(2099, 10, 23, 2, tzinfo=UTC),
            "October 23",
            "9:00 AM–10:00 AM",
        ),
        (
            datetime(2099, 10, 22, 16, tzinfo=UTC),
            datetime(2099, 10, 22, 17, tzinfo=UTC),
            "October 23",
            "12:00 AM–1:00 AM",
        ),
        (
            datetime(2099, 10, 23, 15, 30, tzinfo=UTC),
            datetime(2099, 10, 23, 16, 30, tzinfo=UTC),
            "October 24",
            "11:30 PM–12:30 AM",
        ),
    ],
)
def test_institutional_date_time_and_cross_midnight(start, end, date_part, time_part):
    dates, times = appointment_email_schedule(start, end)
    assert date_part in dates and time_part in times and "Philippine Time" in times
    if start.hour == 15:
        assert "October 23" in dates and "October 24" in dates


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2099, 1, 1), datetime(2099, 1, 1, 1)),
        (datetime(2099, 1, 1, tzinfo=UTC), datetime(2099, 1, 1, tzinfo=UTC)),
        (datetime(2099, 1, 2, tzinfo=UTC), datetime(2099, 1, 1, tzinfo=UTC)),
    ],
)
def test_invalid_schedule_cannot_be_formatted(start, end):
    with pytest.raises(ValueError, match="invalid appointment email interval"):
        appointment_email_schedule(start, end)


@pytest.mark.parametrize(
    "value", [mark_safe("<b>unsafe</b>"), "https://evil.test", "x\ny", "x" * 601]
)
def test_unvalidated_detail_values_fail_with_content_free_error(value):
    with pytest.raises(ValueError, match="^invalid appointment email detail$"):
        AppointmentEmailDetail(AppointmentEmailField.SERVICE, value)


def test_html_escaping_and_plain_text_parity_use_snapshot_not_live_service(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    item = case[3]
    snapshot = 'Synthetic <Service> & "support"'
    Appointment.objects.filter(pk=item.pk).update(service_name_snapshot=snapshot)
    item.service.name = "LIVE NAME MUST NOT REPLACE SNAPSHOT"
    item.service.save()
    User.objects.filter(pk=case[1].pk).update(first_name='Synthetic <Counselor> & "A"')
    plan, message = resolve_render(notice(case, NotificationEvent.APPOINTMENT_SCHEDULED))
    for row in plan.appointment_facts.rows:
        assert row.value in message.text_body
        assert html.escape(row.value, quote=True).replace("&#x27;", "&#x27;") in message.html_body
    assert "<Service>" not in message.html_body and snapshot in message.text_body
    assert "LIVE NAME" not in message.text_body


def test_unsafe_optional_labels_are_omitted_not_rendered_as_links(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    Appointment.objects.filter(pk=case[3].pk).update(
        service_name_snapshot="https://evil.test/track"
    )
    User.objects.filter(pk=case[1].pk).update(first_name="https://evil.test/join?token=secret")
    plan, message = resolve_render(notice(case, NotificationEvent.APPOINTMENT_SCHEDULED))
    assert plan.appointment_facts is not None
    assert "evil.test" not in message.text_body + message.html_body
    assert "token=" not in message.text_body + message.html_body


@pytest.mark.parametrize("origin", ["", "http://evil.test", "https://user:secret@evil.test"])
def test_approved_details_still_require_trusted_link(case, settings, origin):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    settings.COMPASS_PORTAL_ORIGIN = origin
    plan, message = resolve_render(notice(case, NotificationEvent.APPOINTMENT_SCHEDULED))
    assert plan.appointment_facts is None
    assert "APT-SYNTHETIC-02" not in message.text_body
    assert "href=" not in message.html_body


@pytest.mark.parametrize("recipient", ["student", "counselor"])
def test_only_disclosed_name_changes_affect_final_comparison(
    case, settings, monkeypatch, recipient
):
    from compass.notifications import delivery as worker

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(
        case,
        NotificationEvent.APPOINTMENT_SCHEDULED,
        recipient=case[0] if recipient == "student" else case[1],
    )
    original = worker.render_notification_email

    def change_name(*args, **kwargs):
        result = original(*args, **kwargs)
        User.objects.filter(pk=case[1].pk).update(first_name="Changed display name")
        return result

    monkeypatch.setattr(worker, "render_notification_email", change_name)
    outcome = deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
    assert outcome == (
        EmailDeliveryStatus.CANCELLED if recipient == "student" else EmailDeliveryStatus.SENT
    )


@pytest.mark.parametrize("defect", ["kind", "parent", "recipient"])
def test_reminder_source_binding_prevents_wrong_event_data(case, settings, defect):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_REMINDER_24H)
    if defect == "kind":
        notification.event_code = NotificationEvent.APPOINTMENT_REMINDER_3H
    elif defect == "parent":
        notification.target_id = uuid4()
    else:
        notification.recipient = case[1]
    plan, _ = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is None


def test_retry_keeps_exact_event_facts_without_new_intents(case, settings, monkeypatch):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    delivery = EmailDelivery.objects.get(notification=notification)
    sends = []

    def send(self, **kwargs):
        sends.append(kwargs)
        return 0 if len(sends) == 1 else 1

    monkeypatch.setattr(Mailer, "send", send)
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    EmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
    assert sends[0] == sends[1]
    assert AppointmentChangeEvent.objects.count() == 1
    assert EmailDelivery.objects.count() == 1 and AppointmentReminderOccurrence.objects.count() == 0


def test_email_supersession_does_not_hide_in_app_or_change_push(case, settings):
    from compass.notifications.current import notification_is_current
    from compass.notifications.push_policy import push_body_for
    from compass.notifications.services import list_my_notifications

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    old = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    notice(case, NotificationEvent.APPOINTMENT_REASSIGNED)
    assert resolve_notification_email_presentation(old).suppress
    assert notification_is_current(old)
    assert old.pk in {row.pk for row in list_my_notifications(actor=case[0]).items}
    assert push_body_for(old.event_code) == "You have an appointment update."


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("change", ["schedule", "role", "reminder_revision"])
def test_committed_concurrent_changes_are_seen_after_render(case, settings, monkeypatch, change):
    from compass.notifications import delivery as worker

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    event = (
        NotificationEvent.APPOINTMENT_REMINDER_MANUAL
        if change == "reminder_revision"
        else NotificationEvent.APPOINTMENT_SCHEDULED
    )
    notification = notice(case, event)
    delivery = EmailDelivery.objects.get(notification=notification)
    rendered, release = threading.Event(), threading.Event()
    original = worker.render_notification_email
    sends = []

    def barrier(*args, **kwargs):
        result = original(*args, **kwargs)
        rendered.set()
        assert release.wait(timeout=15)
        return result

    def run():
        close_old_connections()
        try:
            return deliver_email_delivery(delivery.pk)
        finally:
            close_old_connections()

    monkeypatch.setattr(worker, "render_notification_email", barrier)
    monkeypatch.setattr(Mailer, "send", lambda *args, **kwargs: sends.append(kwargs) or 1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(run)
        try:
            assert rendered.wait(timeout=15)
            with transaction.atomic():
                item = Appointment.objects.select_for_update().get(pk=case[3].pk)
                if change == "schedule":
                    item.starts_at += timedelta(hours=2)
                    item.ends_at += timedelta(hours=2)
                    item.save(update_fields=["starts_at", "ends_at"])
                elif change == "role":
                    from compass.accounts.models import Role

                    User.objects.filter(pk=case[0].pk).update(
                        role=Role.objects.get(code="IT_ADMIN")
                    )
                else:
                    item.reminder_revision += 1
                    item.save(update_fields=["reminder_revision"])
        finally:
            release.set()
        assert task.result(timeout=15) == EmailDeliveryStatus.CANCELLED
    assert not sends


@pytest.mark.parametrize("defect", ["wrong_type", "wrong_parent", "missing_source"])
def test_incomplete_or_invalid_change_source_never_projects_facts(case, settings, defect):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    if defect == "wrong_type":
        notification.event_code = NotificationEvent.APPOINTMENT_REASSIGNED
    elif defect == "wrong_parent":
        notification.target_id = uuid4()
    else:
        notification.source_id = uuid4()
    notification.save()
    plan, message = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is None
    assert "APT-SYNTHETIC-02" not in message.text_body


@pytest.mark.parametrize("event", [event for event in EVENTS if "reminder" in event.value])
def test_reminder_projection_requires_exact_occurrence_revision_and_kind(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, event)
    Appointment.objects.filter(pk=case[3].pk).update(reminder_revision=2)
    assert resolve_notification_email_presentation(notification).suppress
    assert AppointmentReminderOccurrence.objects.count() == 1


@pytest.mark.parametrize(
    "change", ["approval", "capability", "schedule", "provider", "email", "origin"]
)
def test_post_render_safety_change_cancels_rich_transport(case, settings, monkeypatch, change):
    from compass.notifications import delivery as worker

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_SCHEDULED)
    original = worker.render_notification_email

    def render_then_change(*args, **kwargs):
        rendered = original(*args, **kwargs)
        if change == "approval":
            settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal"
        elif change == "origin":
            settings.COMPASS_PORTAL_ORIGIN = "https://changed-portal.example"
        elif change == "capability":
            UserCapabilityOverride.objects.create(
                user=case[0],
                capability=Capability.objects.get(code="appointments.view_self"),
                effect="REVOKE",
                reason="Synthetic revocation",
            )
        elif change == "email":
            User.objects.filter(pk=case[0].pk).update(email="changed@example.test")
        elif change == "provider":
            Appointment.objects.filter(pk=case[3].pk).update(provider=case[2])
        else:
            Appointment.objects.filter(pk=case[3].pk).update(
                starts_at=case[3].starts_at + timedelta(hours=2),
                ends_at=case[3].ends_at + timedelta(hours=2),
            )
        return rendered

    monkeypatch.setattr(worker, "render_notification_email", render_then_change)
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk) == (
        EmailDeliveryStatus.CANCELLED
    )
    assert not mail.outbox


def test_actual_settings_default_is_minimal():
    environment = dict(os.environ)
    environment.pop("COMPASS_EMAIL_DISCLOSURE_POLICY", None)
    environment.pop("COMPASS_EMAIL_DISCLOSURE_POLICY_FILE", None)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import tests.settings as s; assert s.COMPASS_EMAIL_DISCLOSURE_POLICY == 'minimal'",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.parametrize("state", ["CANCELLED", "COMPLETED", "NO_SHOW", "PAST"])
@pytest.mark.parametrize(
    "event",
    [
        NotificationEvent.APPOINTMENT_SCHEDULED,
        NotificationEvent.APPOINTMENT_RESCHEDULED,
        NotificationEvent.APPOINTMENT_REASSIGNED,
    ],
)
def test_approved_upcoming_events_suppress_terminal_or_started_source(case, settings, state, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, event)
    changes = {"status": state, f"{state.lower()}_at": timezone.now()}
    if state == "PAST":
        changes = {
            "starts_at": timezone.now() - timedelta(hours=2),
            "ends_at": timezone.now() - timedelta(hours=1),
        }
    Appointment.objects.filter(pk=case[3].pk).update(**changes)
    assert resolve_notification_email_presentation(notification).suppress


@pytest.mark.parametrize("event", EVENTS)
def test_unrelated_recipient_cannot_gain_details_from_intent(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    unrelated = make_user("unrelated-email@example.test", "COUNSELOR")
    notification = notice(case, event)
    notification.recipient = unrelated
    plan, message = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is None
    assert case[3].reference_code not in message.text_body


@pytest.mark.parametrize(
    "event",
    [
        NotificationEvent.APPOINTMENT_SCHEDULED,
        NotificationEvent.APPOINTMENT_CANCELLED,
        NotificationEvent.APPOINTMENT_RESCHEDULED,
    ],
)
def test_legacy_absent_sources_remain_deliverable_as_generic(case, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, event)
    notification.source_id = uuid4()
    if event != NotificationEvent.APPOINTMENT_RESCHEDULED:
        notification.target_id = notification.source_id
    notification.save()
    assert (
        deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
        == EmailDeliveryStatus.SENT
    )
    assert case[3].reference_code not in mail.outbox[0].body
    assert "https://" not in mail.outbox[0].body


def test_ambiguous_change_timestamps_suppress_both_events(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    first = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    second = notice(case, NotificationEvent.APPOINTMENT_REASSIGNED)
    timestamp = timezone.now()
    AppointmentChangeEvent.objects.update(occurred_at=timestamp)
    assert resolve_notification_email_presentation(first).suppress
    assert resolve_notification_email_presentation(second).suppress


def test_superseded_retry_does_not_reinterpret_later_schedule(case, settings, monkeypatch):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    first = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    delivery = EmailDelivery.objects.get(notification=first)
    sends = []
    monkeypatch.setattr(Mailer, "send", lambda self, **kwargs: sends.append(kwargs) or 0)
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    EmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.CANCELLED
    assert len(sends) == 1


def test_rich_resolution_failure_never_logs_private_rows(case, settings, monkeypatch, caplog):
    from compass.notifications import email_presentation

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification = notice(case, NotificationEvent.APPOINTMENT_SCHEDULED)

    def fail(**kwargs):
        raise RuntimeError("PrivateStudentName PRIVATE REASON synthetic@example.test")

    monkeypatch.setattr(email_presentation, "resolve_appointment_email_facts", fail)
    with caplog.at_level("INFO", logger="compass.notifications"):
        outcome = deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
    assert outcome == EmailDeliveryStatus.FAILED
    for private in (
        "PrivateStudentName",
        "PRIVATE REASON",
        "synthetic@example.test",
        case[3].reference_code,
    ):
        assert private not in repr([vars(record) for record in caplog.records])


def test_nine_to_ten_to_two_preserves_exact_change_identity(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    item = case[3]
    ten = datetime(2099, 10, 23, 2, tzinfo=UTC)
    two = datetime(2099, 10, 23, 6, tzinfo=UTC)
    Appointment.objects.filter(pk=item.pk).update(starts_at=ten, ends_at=ten + timedelta(hours=1))
    item.refresh_from_db()
    first = notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    source = AppointmentChangeEvent.objects.create(
        appointment=item,
        event_type="RESCHEDULED",
        occurred_at=timezone.now(),
        previous_starts_at=ten,
        previous_ends_at=ten + timedelta(hours=1),
        new_starts_at=two,
        new_ends_at=two + timedelta(hours=1),
        reason="PRIVATE LATER CHANGE",
    )
    Appointment.objects.filter(pk=item.pk).update(
        starts_at=two, ends_at=two + timedelta(hours=1), reminder_revision=3
    )
    second = create_notification_for_event(
        recipient=case[0],
        event=NotificationEvent.APPOINTMENT_RESCHEDULED,
        source_type="appointment_change_event",
        source_id=source.pk,
        target_type="APPOINTMENT",
        target_id=item.pk,
    )
    assert resolve_notification_email_presentation(first).suppress
    plan, message = resolve_render(second)
    assert plan.appointment_facts.source_id == source.pk
    assert "Previous time: 10:00 AM–11:00 AM" in message.text_body
    assert "Updated time: 2:00 PM–3:00 PM" in message.text_body
    assert "9:00 AM" not in message.text_body


def test_a_to_b_to_c_never_grants_former_provider_new_details(case, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    item = case[3]
    first = notice(case, NotificationEvent.APPOINTMENT_REASSIGNED)
    c = make_user("third-counselor@example.test", "COUNSELOR", first_name="Counselor C")
    source = AppointmentChangeEvent.objects.create(
        appointment=item,
        event_type="REASSIGNED",
        occurred_at=timezone.now(),
        previous_provider=case[1],
        new_provider=c,
    )
    Appointment.objects.filter(pk=item.pk).update(provider=c, reminder_revision=3)
    assert resolve_notification_email_presentation(first).suppress
    for recipient in (case[0], case[1], c):
        n = create_notification_for_event(
            recipient=recipient,
            event=NotificationEvent.APPOINTMENT_REASSIGNED,
            source_type="appointment_change_event",
            source_id=source.pk,
            target_type="APPOINTMENT",
            target_id=item.pk,
        )
        plan, message = resolve_render(n)
        if recipient == case[1]:
            assert plan.appointment_facts is None and plan.target is None
            assert "Counselor C" not in message.text_body
        else:
            assert plan.appointment_facts.source_id == source.pk
            assert ("Counselor C" in message.text_body) == (recipient == case[0])


def test_former_provider_with_independent_domain_scope_still_gets_minimal_email(case, settings):
    from compass.appointments.services import get_appointment_for_actor
    from tests.test_appointments import create_affiliation

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    create_affiliation(case[0], case[2])
    assert get_appointment_for_actor(appointment_id=case[3].pk, actor=case[2]).pk == case[3].pk
    plan, message = resolve_render(
        notice(case, NotificationEvent.APPOINTMENT_REASSIGNED, recipient=case[2])
    )
    assert plan.appointment_facts is None and plan.target is None
    assert "APT-SYNTHETIC-02" not in message.text_body


def test_gss_pilot_link_remains_scoped_and_never_rich(case, settings):
    from compass.organization.models import StaffSupervision
    from tests.test_appointments import create_affiliation

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    create_affiliation(case[0], case[1])
    staff = make_user("email-gss@example.test", "GUIDANCE_SERVICES_STAFF")
    supervision = StaffSupervision.objects.create(staff=staff, supervisor=case[1])
    notification = notice(case, NotificationEvent.APPOINTMENT_SCHEDULED, recipient=staff)
    plan, _ = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is not None
    supervision.delete()
    plan, _ = resolve_render(notification)
    assert plan.appointment_facts is None and plan.target is None


@pytest.mark.parametrize(
    "event",
    [
        NotificationEvent.SECURITY_PASSWORD_RESET,
        NotificationEvent.FOLLOWUP_ASSIGNED,
        NotificationEvent.STUDENT_SESSION_SUMMARY_PUBLISHED,
        NotificationEvent.ECOUNSELING_CONSENT_REQUESTED,
    ],
)
def test_operational_policy_keeps_confidential_and_security_events_generic(settings, event):
    from types import SimpleNamespace

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    plan, message = resolve_render(SimpleNamespace(event_code=event))
    assert plan.appointment_facts is None
    assert message == render_notification_email(event)


EXAMPLES = [
    ("scheduled-student", NotificationEvent.APPOINTMENT_SCHEDULED),
    ("scheduled-counselor", NotificationEvent.APPOINTMENT_SCHEDULED),
    ("rescheduled-student", NotificationEvent.APPOINTMENT_RESCHEDULED),
    ("reassigned-student", NotificationEvent.APPOINTMENT_REASSIGNED),
    ("reassigned-former-counselor", NotificationEvent.APPOINTMENT_REASSIGNED),
    ("cancelled-student", NotificationEvent.APPOINTMENT_CANCELLED),
    ("reminder-24h", NotificationEvent.APPOINTMENT_REMINDER_24H),
    ("reminder-3h", NotificationEvent.APPOINTMENT_REMINDER_3H),
    ("reminder-manual", NotificationEvent.APPOINTMENT_REMINDER_MANUAL),
    ("minimal-no-approval", NotificationEvent.APPOINTMENT_SCHEDULED),
    ("suppressed-superseded", NotificationEvent.APPOINTMENT_RESCHEDULED),
    ("long-labels", NotificationEvent.APPOINTMENT_SCHEDULED),
    ("missing-optionals", NotificationEvent.APPOINTMENT_SCHEDULED),
]


@pytest.mark.parametrize("name,event", EXAMPLES)
def test_synthetic_preview_examples(case, settings, tmp_path, name, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = (
        "minimal" if name == "minimal-no-approval" else POLICY
    )
    if name == "long-labels":
        User.objects.filter(pk=case[1].pk).update(
            first_name="S" * 150, middle_name="M" * 150, last_name="L" * 150
        )
        Appointment.objects.filter(pk=case[3].pk).update(
            service_name_snapshot="SyntheticService" * 10
        )
    elif name == "missing-optionals":
        User.objects.filter(pk=case[1].pk).update(first_name="", middle_name="", last_name="")
        Appointment.objects.filter(pk=case[3].pk).update(service_name_snapshot="")
    recipient = (
        case[1]
        if name == "scheduled-counselor"
        else case[2]
        if name == "reassigned-former-counselor"
        else case[0]
    )
    notification = notice(case, event, recipient=recipient)
    if name == "suppressed-superseded":
        notice(case, NotificationEvent.APPOINTMENT_RESCHEDULED)
    plan = resolve_notification_email_presentation(notification)
    output = Path(os.environ.get("COMPASS_EMAIL_PREVIEW_DIR", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    status = {
        "event": event.value,
        "reason": plan.reason.value,
        "suppressed": plan.suppress,
        "synthetic": True,
        "transport": "not_sent",
    }
    (output / f"{name}.json").write_text(json.dumps(status, indent=2) + "\n")
    if plan.suppress:
        assert name == "suppressed-superseded"
        return
    message = render_notification_email(event, presentation=plan)
    for extension, body in (("html", message.html_body), ("txt", message.text_body)):
        # Keep generated review fixtures whitespace-clean without changing rendering.
        normalized = "\n".join(line.rstrip() for line in body.splitlines()) + "\n"
        (output / f"{name}.{extension}").write_text(normalized)
    assert "PrivateStudentName" not in message.text_body
    assert "PRIVATE" not in message.text_body
