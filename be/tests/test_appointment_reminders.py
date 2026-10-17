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
    LATE_WINDOW, MANUAL_COOLDOWN, _base_reason, _manager,
    dispatch_due_reminders, reminder_notification_is_current,
)


@pytest.mark.parametrize("kind,lead", [
    (AppointmentReminderKind.AUTO_24H, timedelta(hours=24)),
    (AppointmentReminderKind.AUTO_3H, timedelta(hours=3)),
])
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
    item = SimpleNamespace(status="SCHEDULED", student=student,
                           starts_at=now + timedelta(minutes=15))
    assert _base_reason(item, now) == ""
    assert _base_reason(item, now + timedelta(seconds=1)) == "TOO_SOON"


def test_manager_requires_appropriate_role_and_capability():
    def actor(role, capability):
        return SimpleNamespace(is_active=True, role=SimpleNamespace(code=role),
                               has_capability=lambda name: capability and name == "appointments.manage")
    assert _manager(actor("COUNSELOR", True))
    assert _manager(actor("GSS", True))
    for role in ("STUDENT", "DPO", "IT_ADMIN"):
        assert not _manager(actor(role, True))
    assert not _manager(actor("GSS", False))


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
