"""Managed Reminders overview: scope, windows, decision states, and activity filters."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from compass.appointments.models import (
    Appointment,
    AppointmentReminderKind,
    AppointmentReminderOccurrence,
)
from compass.appointments.reminders import issue_manual_reminder
from compass.audit.context import AuditContext
from compass.common.institutional_time import institution_zone
from compass.organization.models import CounselorResponsibility, StaffSupervision
from tests.test_appointment_management_scope import (
    affiliate,
    auth_client,
    make_college,
    make_service,
    make_user,
    sync_policy,
)

UPCOMING = "/api/v1/appointments/reminders/upcoming"
ACTIVITY = "/api/v1/appointments/reminders/activity"

UPCOMING_FIELDS = {
    "appointment_id",
    "reference_code",
    "student_name",
    "counselor",
    "service_name",
    "starts_at",
    "next_automatic",
    "last_reminder_kind",
    "last_reminder_at",
    "manual_available",
    "manual_reason",
}
HISTORY_FIELDS = {
    "id",
    "kind",
    "issued_at",
    "scheduled_start",
    "issued_by",
    "is_current",
    "in_app",
    "email",
    "push",
}
ACTIVITY_FIELDS = {
    *HISTORY_FIELDS,
    "appointment_id",
    "reference_code",
    "student_name",
}


@pytest.fixture(autouse=True)
def no_outbound_queue(monkeypatch):
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


@pytest.fixture
def overview():
    sync_policy()
    admin = make_user("ov-admin@example.edu", "IT_ADMIN")
    supervisor = make_user("ov-supervisor@example.edu", "COUNSELOR")
    provider = make_user("ov-provider@example.edu", "COUNSELOR")
    other_provider = make_user("ov-other-provider@example.edu", "COUNSELOR")
    goa = make_user("ov-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    student = make_user("ov-student@example.edu", "STUDENT")
    outside_student = make_user("ov-outside-student@example.edu", "STUDENT")
    in_college = make_college("OVIN")
    out_college = make_college("OVOUT")
    affiliate(student, in_college)
    affiliate(outside_student, out_college)
    CounselorResponsibility.objects.create(college=in_college, counselor=supervisor)
    CounselorResponsibility.objects.create(college=out_college, counselor=other_provider)
    StaffSupervision.objects.create(staff=goa, supervisor=supervisor)
    service = make_service(admin)
    now = timezone.now()

    def make(
        reference: str,
        *,
        student=student,
        provider=provider,
        starts_at=None,
        service=service,
    ):
        start = starts_at or now + timedelta(days=2)
        return Appointment.objects.create(
            reference_code=reference,
            student=student,
            provider=provider,
            service=service,
            delivery_mode="IN_PERSON",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            created_by=student,
        )

    def occurrence(item, *, kind, issued_at, revision=None):
        return AppointmentReminderOccurrence.objects.create(
            appointment=item,
            recipient=item.student,
            kind=kind,
            revision=revision or item.reminder_revision,
            starts_at=item.starts_at,
            issued_at=issued_at,
        )

    return SimpleNamespace(
        admin=admin,
        supervisor=supervisor,
        provider=provider,
        other_provider=other_provider,
        goa=goa,
        student=student,
        outside_student=outside_student,
        service=service,
        now=now,
        make=make,
        occurrence=occurrence,
    )


def rows_by_reference(response):
    return {row["reference_code"]: row for row in response.json()["items"]}


@pytest.mark.django_db
def test_upcoming_and_activity_never_reveal_appointments_outside_the_managed_scope(overview):
    inside = overview.make("APT-OV-IN")
    outside = overview.make(
        "APT-OV-OUT",
        student=overview.outside_student,
        provider=overview.other_provider,
    )
    overview.occurrence(inside, kind=AppointmentReminderKind.MANUAL, issued_at=overview.now)
    overview.occurrence(outside, kind=AppointmentReminderKind.MANUAL, issued_at=overview.now)

    client = auth_client(overview.goa)
    upcoming = client.get(UPCOMING)
    assert upcoming.status_code == 200
    assert [row["appointment_id"] for row in upcoming.json()["items"]] == [str(inside.pk)]

    activity = client.get(ACTIVITY)
    assert activity.status_code == 200
    assert [row["appointment_id"] for row in activity.json()["items"]] == [str(inside.pk)]

    filtered = client.get(f"{ACTIVITY}?page_size=50")
    assert "OV-OUT" not in filtered.content.decode()


@pytest.mark.django_db
def test_non_managers_are_denied_both_overview_lists(overview):
    overview.make("APT-OV-IN")
    student_client = auth_client(overview.student)
    assert student_client.get(UPCOMING).status_code == 403
    assert student_client.get(ACTIVITY).status_code == 403


@pytest.mark.django_db
def test_upcoming_window_defaults_to_seven_days_and_caps_at_thirty(overview):
    inside = overview.make("APT-OV-INSIDE", starts_at=overview.now + timedelta(days=2))
    far = overview.make("APT-OV-FAR", starts_at=overview.now + timedelta(days=10))
    today = overview.now.astimezone(institution_zone()).date()

    client = auth_client(overview.goa)
    default = client.get(UPCOMING)
    assert default.status_code == 200
    assert [row["appointment_id"] for row in default.json()["items"]] == [str(inside.pk)]

    widened = client.get(f"{UPCOMING}?to_date={today + timedelta(days=29)}")
    assert widened.status_code == 200
    assert [row["appointment_id"] for row in widened.json()["items"]] == [
        str(inside.pk),
        str(far.pk),
    ]

    too_wide = client.get(f"{UPCOMING}?to_date={today + timedelta(days=30)}")
    assert too_wide.status_code == 422
    assert too_wide.json()["error"]["code"] == "invalid_reminder_request"

    reversed_window = client.get(
        f"{UPCOMING}?from_date={today + timedelta(days=3)}&to_date={today + timedelta(days=2)}"
    )
    assert reversed_window.status_code == 422


@pytest.mark.django_db
def test_upcoming_reports_next_automatic_reminder_and_manual_availability(overview):
    first = overview.make("APT-OV-24H", starts_at=overview.now + timedelta(hours=30))
    overview.make("APT-OV-3H", starts_at=overview.now + timedelta(hours=20))
    neither = overview.make("APT-OV-NONE", starts_at=overview.now + timedelta(hours=2))
    cooling = overview.make("APT-OV-COOLDOWN", starts_at=overview.now + timedelta(days=2))
    overview.make("APT-OV-SOON", starts_at=overview.now + timedelta(minutes=10))
    overview.occurrence(
        cooling,
        kind=AppointmentReminderKind.MANUAL,
        issued_at=overview.now - timedelta(hours=1),
    )
    # The current revision already received its 24-hour reminder: only 3-hour remains.
    overview.occurrence(
        first,
        kind=AppointmentReminderKind.AUTO_24H,
        issued_at=overview.now - timedelta(hours=1),
    )

    client = auth_client(overview.goa)
    response = client.get(UPCOMING)
    assert response.status_code == 200
    rows = rows_by_reference(response)

    assert rows["APT-OV-24H"]["next_automatic"] == "AUTO_3H"
    assert rows["APT-OV-3H"]["next_automatic"] == "AUTO_3H"
    assert rows["APT-OV-NONE"]["next_automatic"] is None
    assert rows["APT-OV-NONE"]["manual_available"] is True
    assert rows["APT-OV-NONE"]["manual_reason"] == "ELIGIBLE"
    assert rows["APT-OV-24H"]["last_reminder_kind"] == "AUTO_24H"
    assert rows["APT-OV-24H"]["last_reminder_at"] is not None

    assert rows["APT-OV-COOLDOWN"]["manual_available"] is False
    assert rows["APT-OV-COOLDOWN"]["manual_reason"] == "COOLDOWN"
    assert rows["APT-OV-SOON"]["manual_available"] is False
    assert rows["APT-OV-SOON"]["manual_reason"] == "TOO_SOON"

    sendable = client.get(f"{UPCOMING}?manual_available=true")
    assert sendable.status_code == 200
    assert set(rows_by_reference(sendable)) == {"APT-OV-24H", "APT-OV-3H", "APT-OV-NONE"}
    blocked = client.get(f"{UPCOMING}?manual_available=false")
    assert set(rows_by_reference(blocked)) == {"APT-OV-COOLDOWN", "APT-OV-SOON"}

    for row in response.json()["items"]:
        assert set(row) == UPCOMING_FIELDS
    assert neither.pk


@pytest.mark.django_db
def test_activity_filters_paginate_and_never_include_transport_diagnostics(overview):
    item = overview.make("APT-OV-ACTIVITY", starts_at=overview.now + timedelta(days=2))
    zone = institution_zone()
    today = overview.now.astimezone(zone).date()
    older = datetime.combine(today - timedelta(days=2), time(hour=9), tzinfo=zone)
    newer = datetime.combine(today - timedelta(days=1), time(hour=9), tzinfo=zone)
    overview.occurrence(item, kind=AppointmentReminderKind.AUTO_24H, issued_at=older)
    overview.occurrence(item, kind=AppointmentReminderKind.MANUAL, issued_at=newer)
    issued = issue_manual_reminder(
        actor=overview.goa,
        appointment_id=item.pk,
        request_key=uuid4(),
        context=AuditContext.user(overview.goa),
        now=overview.now,
    )
    assert issued["accepted"] is True

    client = auth_client(overview.goa)
    response = client.get(f"{ACTIVITY}?page_size=2")
    assert response.status_code == 200
    page = response.json()
    assert page["has_next"] is True
    assert [row["kind"] for row in page["items"]] == ["MANUAL", "MANUAL"]
    assert page["items"][0]["issued_by"]["id"] == str(overview.goa.pk)
    for row in page["items"]:
        assert set(row) == ACTIVITY_FIELDS
        assert row["appointment_id"] == str(item.pk)
        assert row["reference_code"] == "APT-OV-ACTIVITY"
        assert row["student_name"] == overview.student.get_full_name()
    assert "failure_code" not in response.content.decode()
    assert "claim_token" not in response.content.decode()
    assert overview.student.email not in response.content.decode()

    second = client.get(f"{ACTIVITY}?page_size=2&page=2").json()
    assert second["has_next"] is False
    assert [row["kind"] for row in second["items"]] == ["AUTO_24H"]

    manual = client.get(f"{ACTIVITY}?kind=MANUAL").json()
    assert {row["kind"] for row in manual["items"]} == {"MANUAL"}

    windowed = client.get(
        f"{ACTIVITY}?from_date={today - timedelta(days=1)}&to_date={today - timedelta(days=1)}"
    ).json()
    assert [row["kind"] for row in windowed["items"]] == ["MANUAL"]

    pending = client.get(f"{ACTIVITY}?delivery=PENDING").json()
    assert len(pending["items"]) == 1
    assert pending["items"][0]["kind"] == "MANUAL"
    assert pending["items"][0]["email"] == "PENDING"

    not_requested = client.get(f"{ACTIVITY}?delivery=NOT_REQUESTED").json()
    assert {row["kind"] for row in not_requested["items"]} == {"AUTO_24H", "MANUAL"}

    assert client.get(f"{ACTIVITY}?delivery=SENT").json()["items"] == []
    assert client.get(f"{ACTIVITY}?page_size=0").status_code == 422


@pytest.mark.django_db
def test_per_appointment_history_response_is_unchanged(overview):
    item = overview.make("APT-OV-HISTORY", starts_at=overview.now + timedelta(days=2))
    issue_manual_reminder(
        actor=overview.goa,
        appointment_id=item.pk,
        request_key=uuid4(),
        context=AuditContext.user(overview.goa),
        now=overview.now,
    )

    response = auth_client(overview.goa).get(f"/api/v1/appointments/{item.pk}/reminders")
    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert set(entry) == HISTORY_FIELDS
    assert entry["kind"] == "MANUAL"
    assert entry["issued_by"]["id"] == str(overview.goa.pk)
