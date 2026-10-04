"""Bookable slot lists subtract scheduled Appointments; base Availability stays reservation-neutral.

These cover the times a picker is offered. The transactional overlap checks at booking and
reschedule time are covered in ``test_appointments`` and ``test_final_api_ergonomics``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import override_settings

from compass.appointments.services import (
    cancel_appointment,
    create_student_appointment,
    list_bookable_slots,
    list_reschedule_slots,
)
from compass.availability.services import compute_base_availability
from tests.test_appointments import (
    active_service,
    configure_availability,
    context,
    future_local_start,
    make_user,
    sync_policy,
)


def offered(student, service, provider, start):
    result = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=start.date(),
        now=start - timedelta(days=1),
    )
    return [slot.starts_at for slot in result.items]


def book(student, service, provider, starts_at):
    return create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        context=context(student),
        now=starts_at - timedelta(days=1),
    )


@pytest.fixture
def scheduling():
    sync_policy()
    admin = make_user("slots-admin@example.edu", "IT_ADMIN")
    provider = make_user("slots-provider@example.edu", "COUNSELOR")
    other_provider = make_user("slots-other-provider@example.edu", "COUNSELOR")
    student_a = make_user("slots-a@example.edu", "STUDENT")
    student_b = make_user("slots-b@example.edu", "STUDENT")
    service = active_service(admin, duration=60)
    configure_availability(admin, provider)
    configure_availability(admin, other_provider)
    start = future_local_start(hour=10)
    return {
        "admin": admin,
        "provider": provider,
        "other_provider": other_provider,
        "student_a": student_a,
        "student_b": student_b,
        "service": service,
        "start": start,
    }


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_scheduled_counselor_appointment_removes_overlapping_slot_for_other_students(scheduling):
    s = scheduling
    book(s["student_a"], s["service"], s["provider"], s["start"])

    times = offered(s["student_b"], s["service"], s["provider"], s["start"])

    assert s["start"] not in times
    assert s["start"] - timedelta(hours=1) in times
    assert s["start"] + timedelta(hours=1) in times


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_scheduled_student_appointment_removes_overlapping_slot_with_any_counselor(scheduling):
    s = scheduling
    book(s["student_a"], s["service"], s["provider"], s["start"])

    # The same Student cannot be offered the time with another Counselor...
    assert s["start"] not in offered(s["student_a"], s["service"], s["other_provider"], s["start"])
    # ...but another Student still can.
    assert s["start"] in offered(s["student_b"], s["service"], s["other_provider"], s["start"])


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_cancelled_appointment_releases_its_interval(scheduling):
    s = scheduling
    appointment = book(s["student_a"], s["service"], s["provider"], s["start"])
    assert s["start"] not in offered(s["student_b"], s["service"], s["provider"], s["start"])

    cancel_appointment(
        appointment_id=appointment.pk,
        actor=s["student_a"],
        administrative=False,
        context=context(s["student_a"]),
        now=s["start"] - timedelta(days=1),
    )

    assert s["start"] in offered(s["student_b"], s["service"], s["provider"], s["start"])


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_reschedule_slots_exclude_the_appointment_being_rescheduled(scheduling):
    s = scheduling
    own = book(s["student_a"], s["service"], s["provider"], s["start"])
    book(s["student_b"], s["service"], s["provider"], s["start"] + timedelta(hours=2))

    result = list_reschedule_slots(
        appointment_id=own.pk,
        actor=s["student_a"],
        target_date=s["start"].date(),
        administrative=False,
        now=s["start"] - timedelta(days=1),
    )
    times = [slot.starts_at for slot in result.items]

    # Its own interval does not block it; another Student's reservation with the Counselor does.
    assert s["start"] in times
    assert s["start"] + timedelta(hours=2) not in times


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_longer_reservation_removes_every_candidate_it_intersects(scheduling):
    s = scheduling
    long_service = active_service(s["admin"], code="LONG_SERVICE", duration=90)
    # 10:00-11:30 intersects the 10:00 and 11:00 one-hour slots; it only touches 9:00 and 12:00.
    book(s["student_a"], long_service, s["provider"], s["start"])

    times = offered(s["student_b"], s["service"], s["provider"], s["start"])

    assert s["start"] not in times
    assert s["start"] + timedelta(hours=1) not in times
    assert s["start"] - timedelta(hours=1) in times
    assert s["start"] + timedelta(hours=2) in times


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_base_availability_still_ignores_reservations(scheduling):
    s = scheduling
    before = compute_base_availability(
        provider_id=s["provider"].pk,
        service_id=s["service"].pk,
        delivery_mode="IN_PERSON",
        start_date=s["start"].date(),
        end_date=s["start"].date() + timedelta(days=1),
    )
    book(s["student_a"], s["service"], s["provider"], s["start"])
    after = compute_base_availability(
        provider_id=s["provider"].pk,
        service_id=s["service"].pk,
        delivery_mode="IN_PERSON",
        start_date=s["start"].date(),
        end_date=s["start"].date() + timedelta(days=1),
    )

    assert after.windows == before.windows
