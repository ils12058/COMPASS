"""REM-4 timing, bounded discovery, concurrent issuance and read-only oversight."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.core import mail
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from compass.accounts.models import StudentLifecycleStatus
from compass.audit.context import AuditContext
from compass.common.institutional_time import institution_day_start
from compass.graduate_tracer import reminders
from compass.graduate_tracer.models import GraduateTracerReminderOccurrence, GraduateTracerStatus
from compass.graduate_tracer.services import (
    ensure_my_response,
    replace_my_draft,
    submit_my_response,
)
from compass.notifications.current import notification_is_current
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_links import NotificationEmailTarget, notification_email_route
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import (
    EmailDelivery,
    EmailDeliveryStatus,
    Notification,
    NotificationPreference,
)
from compass.notifications.policy import NotificationEvent
from compass.student_academics.models import StudentGraduationRecord
from tests.test_graduate_tracer import (
    auth_client,
    default_academic_classification,
    make_head,
    make_user,
    sync_policy,
    valid_unemployed_payload,
)


@pytest.fixture(autouse=True)
def no_outbound_queue(monkeypatch):
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)
    monkeypatch.setattr(
        "compass.notifications.services.publish_to_user_on_commit", lambda *args: None
    )


@pytest.fixture
def graduate(db):
    sync_policy()
    return make_graduate()


def make_graduate(day=date(2026, 5, 8)):
    student = make_user(f"tracer-{uuid4()}@example.test")
    college, _, _ = default_academic_classification()
    record = StudentGraduationRecord.objects.create(
        student=student,
        graduated_college=college,
        graduation_date=day,
        verification_source="Registrar",
        verified_at=institution_day_start(day),
    )
    return student, record


def submit(student, *, at=None):
    ensure_my_response(student=student, context=AuditContext.user(student))
    values = valid_unemployed_payload()
    values["birth_date"] = date.fromisoformat(values["birth_date"])
    for name in (
        "name",
        "permanent_address",
        "email",
        "telephone_contact_numbers",
        "mobile_number",
    ):
        values[name + "_snapshot"] = values.pop(name)
    replace_my_draft(student=student, values=values)
    return submit_my_response(student=student, context=AuditContext.user(student), now=at)


@pytest.mark.parametrize(
    "graduated,due",
    [
        (date(2026, 5, 8), date(2026, 11, 8)),
        (date(2026, 8, 31), date(2027, 2, 28)),
        (date(2023, 8, 31), date(2024, 2, 29)),
        (date(2024, 2, 29), date(2024, 8, 29)),
    ],
)
def test_calendar_month_anniversary(graduate, graduated, due):
    _, record = graduate
    assert reminders.six_month_due_date(graduated) == due
    record.graduation_date = graduated
    record.save(update_fields=["graduation_date"])
    assert (
        reminders.dispatch_due_reminders(now=institution_day_start(due) - timedelta(microseconds=1))
        == 0
    )
    assert reminders.dispatch_due_reminders(now=institution_day_start(due)) == 1


def test_institutional_midnight_and_two_send_lifetime_limit(graduate):
    student, record = graduate
    # 16:00 UTC is the start of the anniversary in Philippine Time.
    before = datetime(2026, 11, 7, 15, 59, 59, tzinfo=UTC)
    at = before + timedelta(seconds=1)
    assert reminders.dispatch_due_reminders(now=before) == 0
    assert reminders.dispatch_due_reminders(now=at) == 1
    assert reminders.dispatch_due_reminders(now=at) == 0
    assert (
        reminders.dispatch_due_reminders(now=at + timedelta(days=30) - timedelta(microseconds=1))
        == 0
    )
    assert reminders.dispatch_due_reminders(now=at + timedelta(days=30)) == 1
    assert reminders.dispatch_due_reminders(now=at + timedelta(days=500)) == 0
    assert record.tracer_reminder_occurrences.count() == 2
    assert Notification.objects.filter(recipient=student).count() == 2


def test_late_initial_notice_keeps_thirty_day_gap(graduate):
    _, record = graduate
    at = institution_day_start(date(2027, 1, 10))
    assert reminders.dispatch_due_reminders(now=at) == 1
    assert reminders.dispatch_due_reminders(now=at) == 0
    row = reminders.list_reminders()["items"][0]
    assert row["reminders"][1]["due_date"] == date(2027, 2, 9)
    assert reminders.dispatch_due_reminders(now=at + timedelta(days=30)) == 1
    assert record.tracer_reminder_occurrences.count() == 2


@pytest.mark.parametrize("change", ["inactive", "current", "former", "staff"])
def test_only_active_graduate_student_accounts_are_eligible(graduate, change):
    student, _ = graduate
    if change == "inactive":
        student.is_active = False
    elif change == "staff":
        student.role = make_head().role
        student.student_lifecycle_status = None
    else:
        student.student_lifecycle_status = (
            StudentLifecycleStatus.CURRENT if change == "current" else StudentLifecycleStatus.FORMER
        )
    student.save()
    assert reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8))) == 0
    assert not Notification.objects.exists()


@pytest.mark.parametrize("already_sent", [False, True])
def test_submission_stops_all_remaining_notices(graduate, already_sent):
    student, _ = graduate
    at = institution_day_start(date(2026, 11, 8))
    if already_sent:
        assert reminders.dispatch_due_reminders(now=at) == 1
    response = submit(student, at=at + timedelta(hours=1))
    assert response.status == GraduateTracerStatus.SUBMITTED
    assert reminders.dispatch_due_reminders(now=at + timedelta(days=30)) == 0
    row = reminders.list_reminders()["items"][0]
    assert {notice["state"] for notice in row["reminders"]} == {"ANSWERED"}


def test_draft_remains_eligible(graduate):
    student, _ = graduate
    response = ensure_my_response(student=student, context=AuditContext.user(student))
    assert response.status == GraduateTracerStatus.DRAFT
    assert reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8))) == 1


def test_bounded_scan_advances_without_future_or_completed_starvation(graduate, monkeypatch):
    make_graduate(date(2026, 5, 7))
    future, _ = make_graduate(date(2026, 12, 1))
    monkeypatch.setattr(reminders, "SCAN_BATCH", 1)
    at = institution_day_start(date(2026, 11, 8))
    assert reminders.dispatch_due_reminders(now=at) == 1
    assert reminders.dispatch_due_reminders(now=at) == 1
    assert reminders.dispatch_due_reminders(now=at) == 0
    assert not Notification.objects.filter(recipient=future).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("follow_up", [False, True])
def test_two_concurrent_dispatches_issue_one_occurrence(monkeypatch, follow_up):
    sync_policy()
    _, record = make_graduate()
    at = institution_day_start(date(2026, 11, 8))
    if follow_up:
        assert reminders.dispatch_due_reminders(now=at) == 1
        at += timedelta(days=30)
    barrier = Barrier(2)
    issue = reminders._issue

    def synchronized_issue(record_id, *, at):
        barrier.wait(timeout=10)
        return issue(record_id, at=at)

    def worker():
        close_old_connections()
        try:
            return reminders.dispatch_due_reminders(now=at)
        finally:
            close_old_connections()

    monkeypatch.setattr(reminders, "_issue", synchronized_issue)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        assert sorted(future.result(timeout=20) for future in futures) == [0, 1]
    count = 2 if follow_up else 1
    assert record.tracer_reminder_occurrences.count() == count
    assert Notification.objects.count() == count
    assert EmailDelivery.objects.count() == count


def test_issuance_and_notification_roll_back_together(graduate, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("simulated occurrence write failure")

    monkeypatch.setattr(GraduateTracerReminderOccurrence.objects, "create", fail)
    with pytest.raises(RuntimeError):
        reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8)))
    assert not Notification.objects.exists()
    assert not EmailDelivery.objects.exists()


def test_uniqueness_rejects_duplicate_kind(graduate):
    reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8)))
    occurrence = GraduateTracerReminderOccurrence.objects.get()
    original = occurrence.notification
    another = Notification.objects.create(
        recipient=original.recipient,
        event_code=original.event_code,
        policy=original.policy,
        title=original.title,
        message=original.message,
        source_type=original.source_type,
        source_id=uuid4(),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        GraduateTracerReminderOccurrence.objects.create(
            graduation_record=occurrence.graduation_record,
            kind=occurrence.kind,
            issued_at=occurrence.issued_at,
            notification=another,
        )


@pytest.mark.parametrize("enabled", [True, False, None])
def test_optional_email_preference_keeps_in_app_notice(graduate, enabled):
    student, record = graduate
    if enabled is not None:
        NotificationPreference.objects.create(user=student, optional_email_enabled=enabled)
    assert reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8))) == 1
    occurrence = record.tracer_reminder_occurrences.get()
    assert occurrence.notification.recipient_id == student.pk
    assert EmailDelivery.objects.filter(notification=occurrence.notification).exists() == (
        enabled is not False
    )
    assert not occurrence.notification.pushdelivery_set.exists()


@override_settings(
    COMPASS_PORTAL_ORIGIN="https://compass.example.edu",
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
)
def test_generic_email_and_in_app_link_are_live(graduate):
    student, record = graduate
    reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8)))
    notification = record.tracer_reminder_occurrences.get().notification
    plan = resolve_notification_email_presentation(notification)
    rendered = render_notification_email(
        NotificationEvent.GRADUATE_TRACER_REMINDER, presentation=plan
    )
    url = "https://compass.example.edu/portal/graduate-tracer"
    assert url in rendered.text_body
    assert f'href="{url}"' in rendered.html_body
    assert "Please" not in rendered.text_body
    assert student.email not in rendered.text_body
    assert (
        notification_email_route(NotificationEmailTarget("GRADUATE_TRACER", student.pk))
        == "/portal/graduate-tracer"
    )
    assert deliver_email_delivery(notification.email_delivery.pk) == EmailDeliveryStatus.SENT
    assert len(mail.outbox) == 1
    assert url in mail.outbox[0].body
    row = auth_client(student).get("/api/v1/notifications").json()["items"][0]
    assert row["target_type"] == "GRADUATE_TRACER"
    assert row["target_id"] == str(student.pk)


@pytest.mark.parametrize("change", ["submitted", "inactive", "current", "preference"])
@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_queued_email_rechecks_current_participation(graduate, change):
    student, record = graduate
    reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8)))
    notification = record.tracer_reminder_occurrences.get().notification
    assert notification_is_current(notification)
    if change == "preference":
        NotificationPreference.objects.create(user=student, optional_email_enabled=False)
    elif change == "submitted":
        submit(student)
    else:
        if change == "inactive":
            student.is_active = False
        else:
            student.student_lifecycle_status = StudentLifecycleStatus.CURRENT
        student.save()
    assert notification_is_current(notification) == (change == "preference")
    delivery = notification.email_delivery
    assert deliver_email_delivery(delivery.pk) in {EmailDeliveryStatus.CANCELLED, "skipped"}
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.CANCELLED
    assert mail.outbox == []


def test_endpoint_uses_existing_review_authority_and_never_sends(graduate):
    student, _ = graduate
    path = "/api/v1/graduate-tracer/reminders"
    assert Client().get(path).status_code == 401
    for outsider in [
        student,
        make_user("other-rem@example.test", role="COUNSELOR", lifecycle=None),
        make_user("it-rem@example.test", role="IT_ADMIN", lifecycle=None),
    ]:
        assert auth_client(outsider).get(path).status_code == 403
    response = auth_client(make_head()).get(path)
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert set(row) == {"graduation_record_id", "graduate_name", "graduation_date", "reminders"}
    assert len(row["reminders"]) == 2
    assert set(row["reminders"][0]) == {"kind", "due_date", "issued_at", "state"}
    assert not Notification.objects.exists()


def test_overview_pagination_ordering_and_no_n_plus_one(graduate):
    _, first = graduate
    _, earlier = make_graduate(date(2026, 4, 1))
    make_graduate(date(2026, 12, 1))
    with CaptureQueriesContext(connection) as queries:
        page = reminders.list_reminders(page=1, page_size=1)
    assert len(queries) <= 2
    assert page["items"][0]["graduation_record_id"] == earlier.pk
    assert page["has_next"] is True
    page = reminders.list_reminders(page=2, page_size=1)
    assert page["items"][0]["graduation_record_id"] == first.pk
    assert reminders.list_reminders(page=4, page_size=1)["items"] == []
    latest = reminders.list_reminders(ordering="LATEST_GRADUATION")
    assert latest["items"][0]["graduation_date"] == date(2026, 12, 1)
    for params in [{"page": 0}, {"page_size": 0}, {"page_size": 51}, {"ordering": "unknown"}]:
        assert (
            auth_client(make_head(f"head-{uuid4()}@example.test"))
            .get("/api/v1/graduate-tracer/reminders", params)
            .status_code
            == 422
        )


def test_currentness_rejects_another_recipient_target(graduate):
    reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8)))
    notice = Notification.objects.get()
    notice.target_id = uuid4()
    assert not notification_is_current(notice)


@pytest.mark.parametrize("change", ["inactive", "submitted"])
def test_current_participation_is_rechecked_after_discovery(graduate, monkeypatch, change):
    student, _ = graduate
    issue = reminders._issue

    def changed_before_lock(record_id, *, at):
        if change == "submitted":
            submit(student, at=at)
        else:
            student.is_active = False
            student.save(update_fields=["is_active"])
        return issue(record_id, at=at)

    monkeypatch.setattr(reminders, "_issue", changed_before_lock)
    assert reminders.dispatch_due_reminders(now=institution_day_start(date(2026, 11, 8))) == 0
    assert not Notification.objects.exists()


def test_daily_beat_task_is_registered_and_delegates(monkeypatch):
    from django.conf import settings

    from compass.graduate_tracer.tasks import dispatch_due_graduate_tracer_reminders
    from config.celery import app

    schedule = settings.CELERY_BEAT_SCHEDULE["graduate-tracer-reminders-dispatch-due"]
    assert schedule == {"task": "compass.graduate_tracer.reminders.dispatch_due", "schedule": 86400}
    app.autodiscover_tasks(force=True)
    assert schedule["task"] in app.tasks
    monkeypatch.setattr("compass.graduate_tracer.tasks.dispatch_due_reminders", lambda: 7)
    assert dispatch_due_graduate_tracer_reminders.run() == 7
