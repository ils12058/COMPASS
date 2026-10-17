"""Deterministic reminder boundaries and authorization safeguards."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test import override_settings
from django.utils import timezone

from compass.appointments.models import AppointmentReminderKind, AppointmentReminderOccurrence
from compass.appointments.reminders import (
    LATE_WINDOW,
    MANUAL_COOLDOWN,
    _base_reason,
    _manager,
    dispatch_due_reminders,
    reminder_notification_is_current,
)


@pytest.mark.parametrize(
    "kind,lead",
    [
        (AppointmentReminderKind.AUTO_24H, timedelta(hours=24)),
        (AppointmentReminderKind.AUTO_3H, timedelta(hours=3)),
    ],
)
def test_due_window_starts_at_correct_offset(kind, lead):
    now = timezone.now()
    start = now + lead
    due = start - lead
    assert due == now
    assert due <= now < due + LATE_WINDOW
    assert not (due <= now + LATE_WINDOW < due + LATE_WINDOW)


def test_short_notice_bookings_skip_past_windows():
    now = timezone.now()
    starts = now + timedelta(hours=2)
    assert starts - timedelta(hours=24) < now
    assert starts - timedelta(hours=3) < now


@pytest.mark.parametrize("status", ["CANCELLED", "COMPLETED", "NO_SHOW"])
def test_manual_rejects_non_scheduled(status):
    now = timezone.now()
    item = SimpleNamespace(status=status, starts_at=now + timedelta(hours=7))
    assert _base_reason(item, now) == "NOT_SCHEDULED"


def test_manual_lead_time_is_inclusive():
    now = timezone.now()
    student = SimpleNamespace(is_active=True, role=SimpleNamespace(code="STUDENT"))
    item = SimpleNamespace(
        status="SCHEDULED", student=student, starts_at=now + timedelta(minutes=15)
    )
    assert _base_reason(item, now) == ""
    assert _base_reason(item, now + timedelta(seconds=1)) == "TOO_SOON"


def test_manager_requires_appropriate_role_and_capability():
    def actor(role, capability):
        return SimpleNamespace(
            is_active=True,
            role=SimpleNamespace(code=role),
            has_capability=lambda name: capability and name == "appointments.manage",
        )

    assert _manager(actor("COUNSELOR", True))
    assert _manager(actor("GUIDANCE_SERVICES_STAFF", True))
    for role in ("STUDENT", "DPO", "IT_ADMIN"):
        assert not _manager(actor(role, True))
    assert not _manager(actor("GUIDANCE_SERVICES_STAFF", False))


@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=False)
def test_automatic_dispatch_is_off_by_default():
    with patch("compass.appointments.reminders.Appointment.objects") as objects:
        assert dispatch_due_reminders() == 0
        objects.filter.assert_not_called()


@pytest.mark.django_db
def test_external_delivery_rejects_absent_occurrence():
    notification = SimpleNamespace(source_type="appointment_reminder", source_id=uuid4())
    assert not reminder_notification_is_current(notification)


def test_manual_cooldown_is_three_hours():
    assert MANUAL_COOLDOWN == timedelta(hours=3)


@pytest.fixture(autouse=True)
def no_outbound_queue(monkeypatch):
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


@pytest.fixture
def reminder_case():
    from django.core.management import call_command

    from compass.appointments.models import Appointment
    from tests.test_appointment_management_scope import make_service, make_user

    call_command("sync_identity_policy", verbosity=0)
    staff = make_user("rem-counselor@example.test", "COUNSELOR")
    student = make_user("rem-student@example.test", "STUDENT")
    service = make_service(staff)
    now = timezone.now()
    item = Appointment.objects.create(
        reference_code="REM-TEST",
        student=student,
        provider=staff,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=now + timedelta(hours=24),
        ends_at=now + timedelta(hours=25),
        created_by=student,
    )
    Appointment.objects.filter(pk=item.pk).update(created_at=now - timedelta(days=2))
    return staff, student, item, now


def send_case(case, *, key=None, now=None):
    from compass.appointments.reminders import issue_manual_reminder
    from compass.audit.context import AuditContext

    actor, _, item, at = case
    return issue_manual_reminder(
        actor=actor,
        appointment_id=item.pk,
        request_key=key or uuid4(),
        context=AuditContext.user(actor),
        now=now or at,
    )


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
@pytest.mark.parametrize("lead", [3, 24])
def test_automatic_dispatch_is_durable_student_only_and_repeat_safe(reminder_case, lead):
    from compass.appointments.models import Appointment
    from compass.notifications.models import EmailDelivery, Notification

    actor, student, item, now = reminder_case
    Appointment.objects.filter(pk=item.pk).update(starts_at=now + timedelta(hours=lead))
    assert dispatch_due_reminders(now=now) == 1
    assert dispatch_due_reminders(now=now) == 0
    notice = Notification.objects.get()
    assert notice.recipient_id == student.pk
    assert notice.source_id == AppointmentReminderOccurrence.objects.get().pk
    assert notice.target_id == item.pk
    assert not Notification.objects.filter(recipient=actor).exists()
    assert EmailDelivery.objects.filter(notification=notice).exists()
    assert student.email not in notice.message
    assert item.reference_code not in notice.message


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
def test_bounded_discovery_advances_past_issued_candidates(reminder_case):
    from compass.appointments.models import Appointment

    _, student, item, now = reminder_case
    Appointment.objects.create(
        reference_code="REM-SECOND",
        student=student,
        provider=item.provider,
        service=item.service,
        delivery_mode="IN_PERSON",
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        reminder_revision_started_at=now - timedelta(days=2),
    )
    with patch("compass.appointments.reminders.SCAN_BATCH", 1):
        assert dispatch_due_reminders(now=now) == 1
        assert dispatch_due_reminders(now=now) == 1
        assert dispatch_due_reminders(now=now) == 0


@pytest.mark.django_db
def test_manual_replay_survives_cooldown_and_contains_no_stored_names(reminder_case):
    from compass.appointments.models import AppointmentReminderBatch

    key = uuid4()
    first = send_case(reminder_case, key=key)
    assert first["accepted"]
    assert send_case(reminder_case, key=key, now=reminder_case[3] + timedelta(hours=4)) == first
    assert AppointmentReminderOccurrence.objects.count() == 1
    assert "student_name" not in str(AppointmentReminderBatch.objects.get().result)
    assert not send_case(reminder_case)["accepted"]


@pytest.mark.django_db
def test_replay_rechecks_resource_authority(reminder_case):
    from compass.appointments.models import Appointment
    from tests.test_appointment_management_scope import make_user

    key = uuid4()
    assert send_case(reminder_case, key=key)["accepted"]
    other = make_user("rem-other@example.test", "COUNSELOR")
    Appointment.objects.filter(pk=reminder_case[2].pk).update(provider=other)
    replay = send_case(reminder_case, key=key)
    assert replay["reason"] == "NOT_AVAILABLE"
    assert replay["student_name"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change", ["cancel", "complete", "no_show", "reschedule", "reassign", "inactive"]
)
def test_stale_reminders_disappear_and_email_never_hands_off(reminder_case, change):
    from compass.accounts.models import User
    from compass.appointments.models import Appointment
    from compass.notifications.delivery import deliver_email_delivery
    from compass.notifications.models import EmailDelivery, Notification
    from compass.notifications.services import list_my_notifications, unread_count_for

    _, student, item, _ = reminder_case
    assert send_case(reminder_case)["accepted"]
    notice = Notification.objects.get()
    assert reminder_notification_is_current(notice)
    if change == "inactive":
        User.objects.filter(pk=student.pk).update(is_active=False)
    elif change in {"reschedule", "reassign"}:
        Appointment.objects.filter(pk=item.pk).update(reminder_revision=2)
    else:
        Appointment.objects.filter(pk=item.pk).update(
            status={"cancel": "CANCELLED", "complete": "COMPLETED", "no_show": "NO_SHOW"}[change],
            **{
                {"cancel": "cancelled_at", "complete": "completed_at", "no_show": "no_show_at"}[
                    change
                ]: timezone.now()
            },
        )
    assert not reminder_notification_is_current(notice)
    assert not list_my_notifications(actor=student).items
    assert unread_count_for(actor=student) == 0
    with patch("compass.notifications.delivery.Mailer") as mailer:
        assert deliver_email_delivery(EmailDelivery.objects.get().pk) == "skipped"
        mailer.assert_not_called()
    assert EmailDelivery.objects.get().status == "CANCELLED"


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
def test_new_revision_can_issue_new_logical_occurrence(reminder_case):
    from compass.appointments.models import Appointment
    from compass.notifications.models import Notification

    _, _, item, now = reminder_case
    assert dispatch_due_reminders(now=now) == 1
    Appointment.objects.filter(pk=item.pk).update(
        reminder_revision=2,
        reminder_revision_started_at=now + timedelta(hours=1),
        starts_at=now + timedelta(hours=48),
        ends_at=now + timedelta(hours=49),
    )
    assert dispatch_due_reminders(now=now + timedelta(hours=24)) == 1
    assert Notification.objects.values("source_id").distinct().count() == 2


@pytest.mark.django_db(transaction=True)
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
@pytest.mark.parametrize("race", ["scheduler", "manual_bulk", "auto_manual"])
def test_postgresql_concurrent_issuers_produce_one_occurrence(reminder_case, race):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection, connections

    from compass.accounts.models import User
    from compass.appointments.reminders import issue_bulk_reminders
    from compass.audit.context import AuditContext

    assert connection.vendor == "postgresql"
    actor, _, item, now = reminder_case
    barrier = Barrier(2)

    def run(index):
        close_old_connections()
        try:
            staff = User.objects.select_related("role").get(pk=actor.pk)
            barrier.wait(timeout=10)
            if race == "scheduler" or (race == "auto_manual" and index == 0):
                return dispatch_due_reminders(now=now)
            return issue_bulk_reminders(
                actor=staff,
                appointment_ids=[item.pk],
                request_key=uuid4(),
                context=AuditContext.user(staff),
                now=now,
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, range(2)))
    if race == "auto_manual":
        auto_count = AppointmentReminderOccurrence.objects.filter(
            kind=AppointmentReminderKind.AUTO_24H
        ).count()
        manual_count = AppointmentReminderOccurrence.objects.filter(
            kind=AppointmentReminderKind.MANUAL
        ).count()
        assert auto_count == 1
        assert manual_count == 1
    else:
        assert AppointmentReminderOccurrence.objects.count() == 1


@pytest.mark.django_db
def test_manual_http_uses_canonical_role_and_durable_request_id(reminder_case):
    import json

    from tests.test_appointment_management_scope import auth_client, csrf

    staff, _, item, _ = reminder_case
    client = auth_client(staff, recent_mfa=True)
    key = str(uuid4())
    path = f"/api/v1/appointments/{item.pk}/reminder"
    for _ in range(2):
        response = client.post(
            path,
            data=json.dumps({"request_key": key}),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 200, response.content
    assert AppointmentReminderOccurrence.objects.count() == 1


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
def test_bounded_scheduler_does_not_starve_behind_short_notice_rows(reminder_case):
    from compass.appointments.models import Appointment

    _, student, item, now = reminder_case
    Appointment.objects.filter(pk=item.pk).update(
        created_at=now + timedelta(seconds=1),
        starts_at=now + timedelta(hours=24) - timedelta(seconds=1),
    )
    valid = Appointment.objects.create(
        reference_code="REM-VALID-BEHIND-LATE",
        student=student,
        provider=item.provider,
        service=item.service,
        delivery_mode="IN_PERSON",
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        reminder_revision_started_at=now - timedelta(days=2),
    )
    with patch("compass.appointments.reminders.SCAN_BATCH", 1):
        assert dispatch_due_reminders(now=now) == 1
    assert AppointmentReminderOccurrence.objects.get().appointment_id == valid.pk


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
def test_manual_reminder_does_not_block_later_automatic_reminder(reminder_case):
    from compass.appointments.models import Appointment

    _, _, item, now = reminder_case
    # Appointment starts at now + 24 hours.
    # Send a manual reminder at now.
    send_case(reminder_case, now=now)
    manual_count = AppointmentReminderOccurrence.objects.filter(
        kind=AppointmentReminderKind.MANUAL
    ).count()
    assert manual_count == 1

    # Advance to now + 21 hours (appointment starts at 3 hours from this point).
    at_3h_window = now + timedelta(hours=21)
    Appointment.objects.filter(pk=item.pk).update(starts_at=at_3h_window + timedelta(hours=3))
    # Automatic 3h window is due. The prior manual reminder must not block the auto reminder.
    dispatched = dispatch_due_reminders(now=at_3h_window)
    assert dispatched == 1
    auto_3h_count = AppointmentReminderOccurrence.objects.filter(
        kind=AppointmentReminderKind.AUTO_3H
    ).count()
    assert auto_3h_count == 1


@pytest.mark.django_db
@override_settings(APPOINTMENT_AUTO_REMINDERS_ENABLED=True)
def test_prior_automatic_reminder_does_not_block_manual_reminder(reminder_case):
    _, _, item, now = reminder_case
    # Dispatch automatic 24h reminder
    assert dispatch_due_reminders(now=now) == 1
    auto_24h_count = AppointmentReminderOccurrence.objects.filter(
        kind=AppointmentReminderKind.AUTO_24H
    ).count()
    assert auto_24h_count == 1

    # 10 minutes later, counselor sends a manual reminder.
    # It must not be blocked by the automatic reminder cooldown.
    result = send_case(reminder_case, now=now + timedelta(minutes=10))
    assert result["accepted"] is True
    manual_count = AppointmentReminderOccurrence.objects.filter(
        kind=AppointmentReminderKind.MANUAL
    ).count()
    assert manual_count == 1


@pytest.mark.django_db
def test_manual_to_manual_reminder_enforces_three_hour_cooldown(reminder_case):
    _, _, item, now = reminder_case
    # First manual reminder accepted
    first = send_case(reminder_case, now=now)
    assert first["accepted"] is True

    # Second manual reminder 1 hour later rejected due to COOLDOWN
    second = send_case(reminder_case, now=now + timedelta(hours=1))
    assert second["accepted"] is False
    assert second["reason"] == "COOLDOWN"

    # Third manual reminder after 3 hours and 1 minute is accepted
    third = send_case(reminder_case, now=now + timedelta(hours=3, minutes=1))
    assert third["accepted"] is True


@pytest.mark.django_db
def test_reminder_send_endpoints_require_recent_mfa(reminder_case):
    import json

    from tests.test_appointment_management_scope import auth_client, csrf

    staff, _, item, _ = reminder_case
    stale_client = auth_client(staff, recent_mfa=False)
    single_path = f"/api/v1/appointments/{item.pk}/reminder"
    bulk_path = "/api/v1/appointments/reminders/send"
    preview_path = "/api/v1/appointments/reminders/preview"

    # Single-send without recent MFA returns 403 mfa_setup_required / recent_mfa_required
    resp = stale_client.post(
        single_path,
        data=json.dumps({"request_key": str(uuid4())}),
        content_type="application/json",
        **csrf(stale_client),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] in ("mfa_setup_required", "recent_mfa_required")

    # Bulk-send without recent MFA returns 403
    resp = stale_client.post(
        bulk_path,
        data=json.dumps({"appointment_ids": [str(item.pk)], "request_key": str(uuid4())}),
        content_type="application/json",
        **csrf(stale_client),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] in ("mfa_setup_required", "recent_mfa_required")

    # Preview is read-only and does not require recent MFA
    resp = stale_client.post(
        preview_path,
        data=json.dumps({"appointment_ids": [str(item.pk)]}),
        content_type="application/json",
        **csrf(stale_client),
    )
    assert resp.status_code == 200

    # With recent MFA, send succeeds
    fresh_client = auth_client(staff, recent_mfa=True)
    resp = fresh_client.post(
        single_path,
        data=json.dumps({"request_key": str(uuid4())}),
        content_type="application/json",
        **csrf(fresh_client),
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


@pytest.mark.django_db
def test_reminder_history_visibility_and_boundary(reminder_case):
    from compass.appointments.models import Appointment
    from tests.test_appointment_management_scope import auth_client, make_user

    staff, student, item, now = reminder_case
    # Issue a manual reminder
    send_case(reminder_case, now=now)

    client = auth_client(staff)
    history_path = f"/api/v1/appointments/{item.pk}/reminders"
    resp = client.get(history_path)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    entry = data["items"][0]
    assert entry["kind"] == "MANUAL"
    assert entry["is_current"] is True
    assert entry["issued_by"]["id"] == str(staff.pk)
    assert entry["in_app"] == "CREATED"
    assert entry["email"] in ("PENDING", "SENT", "NOT_REQUESTED")
    # Verify no leaked transports, secrets, tokens, or recipient email in payload
    assert "token" not in str(data)
    assert "ciphertext" not in str(data)
    assert student.email not in str(data)

    # Reschedule changes revision and marks historical reminder not current
    Appointment.objects.filter(pk=item.pk).update(reminder_revision=2)
    resp = client.get(history_path)
    assert resp.status_code == 200
    assert resp.json()["items"][0]["is_current"] is False

    # Student cannot view staff reminder history (forbidden or concealed)
    student_client = auth_client(student)
    assert student_client.get(history_path).status_code in (403, 404)

    # Unrelated counselor cannot view appointment reminders (404 concealment)
    other = make_user("rem-unrelated@example.test", "COUNSELOR")
    other_client = auth_client(other)
    assert other_client.get(history_path).status_code == 404
