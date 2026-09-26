"""Appointment detail projects server-owned action availability and upcoming discovery."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from compass.appointments.services import (
    AppointmentActionBlocker,
    appointment_actions_for,
    list_managed_appointments,
    list_my_appointments,
)
from compass.counseling.models import CounselingEncounter
from compass.ecounseling.models import ECounselingRoom
from tests.test_appointments import (
    active_service,
    auth_client,
    create_affiliation,
    create_list_appointment,
    csrf,
    make_user,
    sync_policy,
)


def states(actions) -> dict[str, str | None]:
    return {
        name: None if state.allowed else state.blocker.value
        for name, state in (
            ("cancel", actions.cancel),
            ("reschedule", actions.reschedule),
            ("reassign", actions.reassign),
            ("complete", actions.complete),
            ("mark_no_show", actions.mark_no_show),
        )
    }


def setup_participants(prefix: str):
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    student.student_lifecycle_status = "CURRENT"
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    manager = make_user(f"{prefix}-manager@example.edu", "COUNSELOR")
    service = active_service(admin, code=f"{prefix.upper()}_SERVICE")
    create_affiliation(student, manager)
    return student, manager, service


@pytest.mark.django_db
def test_manager_actions_follow_server_time_and_linked_records():
    sync_policy()
    student, manager, service = setup_participants("mgr")
    now = timezone.now()
    future = create_list_appointment(
        reference_code="APT-2099-900001",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(days=2),
    )
    assert states(appointment_actions_for(actor=manager, item=future, now=now)) == {
        "cancel": None,
        "reschedule": None,
        "reassign": None,
        "complete": "NOT_STARTED",
        "mark_no_show": "NOT_ENDED",
    }

    ECounselingRoom.objects.create(appointment=future, daily_room_name=f"room-{future.pk}")
    linked = states(appointment_actions_for(actor=manager, item=future, now=now))
    assert linked["reschedule"] == "ECOUNSELING_ROOM_LINKED"
    assert linked["reassign"] == "ECOUNSELING_ROOM_LINKED"
    assert linked["cancel"] is None

    past = create_list_appointment(
        reference_code="APT-2099-900002",
        student=student,
        provider=manager,
        service=service,
        starts_at=now - timedelta(hours=3),
    )
    assert states(appointment_actions_for(actor=manager, item=past, now=now)) == {
        "cancel": "ALREADY_STARTED",
        "reschedule": "ALREADY_STARTED",
        "reassign": "ALREADY_STARTED",
        "complete": None,
        "mark_no_show": None,
    }
    CounselingEncounter.objects.create(
        student=student,
        counselor=manager,
        service=service,
        appointment=past,
        entry_mode="APPOINTMENT",
        delivery_mode="IN_PERSON",
        started_at=past.starts_at,
        ended_at=past.ends_at,
        created_by=manager,
    )
    assert (
        appointment_actions_for(actor=manager, item=past, now=now).mark_no_show.blocker
        == AppointmentActionBlocker.COUNSELING_ENCOUNTER_LINKED
    )

    cancelled = create_list_appointment(
        reference_code="APT-2099-900003",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(days=3),
        status="CANCELLED",
    )
    assert set(
        states(appointment_actions_for(actor=manager, item=cancelled, now=now)).values()
    ) == {"NOT_SCHEDULED"}


@pytest.mark.django_db
def test_student_self_actions_apply_saved_cutoff_and_lifecycle():
    sync_policy()
    student, manager, service = setup_participants("self")
    now = timezone.now()
    open_item = create_list_appointment(
        reference_code="APT-2099-900011",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(days=1),
    )
    assert states(appointment_actions_for(actor=student, item=open_item, now=now)) == {
        "cancel": None,
        "reschedule": None,
        "reassign": "NOT_PERMITTED",
        "complete": "NOT_PERMITTED",
        "mark_no_show": "NOT_PERMITTED",
    }

    within_cutoff = create_list_appointment(
        reference_code="APT-2099-900012",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(minutes=10),
    )
    self_states = states(appointment_actions_for(actor=student, item=within_cutoff, now=now))
    assert self_states["cancel"] == "CUTOFF_PASSED"
    assert self_states["reschedule"] == "CUTOFF_PASSED"
    manager_states = states(appointment_actions_for(actor=manager, item=within_cutoff, now=now))
    assert manager_states["cancel"] is None

    student.student_lifecycle_status = "GRADUATED"
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    graduated = states(appointment_actions_for(actor=student, item=open_item, now=now))
    assert graduated["cancel"] is None
    assert graduated["reschedule"] == "CURRENT_STUDENT_REQUIRED"


@pytest.mark.django_db
def test_detail_api_returns_actions_for_the_requesting_actor_only():
    sync_policy()
    student, manager, service = setup_participants("api")
    item = create_list_appointment(
        reference_code="APT-2099-900021",
        student=student,
        provider=manager,
        service=service,
        starts_at=timezone.now() + timedelta(days=2),
    )

    as_student = auth_client(student).get(f"/api/v1/appointments/{item.pk}")
    assert as_student.status_code == 200
    assert as_student.json()["actions"]["cancel"] == {"allowed": True, "blocker": None}
    assert as_student.json()["actions"]["complete"] == {
        "allowed": False,
        "blocker": "NOT_PERMITTED",
    }

    as_manager = auth_client(manager).get(f"/api/v1/appointments/{item.pk}")
    assert as_manager.json()["actions"]["reassign"] == {"allowed": True, "blocker": None}
    assert as_manager.json()["actions"]["complete"]["blocker"] == "NOT_STARTED"

    listed = auth_client(manager).get("/api/v1/appointments").json()["items"][0]
    assert "actions" not in listed


@pytest.mark.django_db
def test_upcoming_filter_matches_overview_population():
    sync_policy()
    student, manager, service = setup_participants("upcoming")
    now = timezone.now()
    upcoming = create_list_appointment(
        reference_code="APT-2099-900031",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(days=1),
    )
    create_list_appointment(
        reference_code="APT-2099-900032",
        student=student,
        provider=manager,
        service=service,
        starts_at=now - timedelta(days=1),
    )
    create_list_appointment(
        reference_code="APT-2099-900033",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(days=2),
        status="CANCELLED",
    )

    mine = list_my_appointments(actor=student, upcoming=True, now=now)
    assert [item.pk for item in mine.items] == [upcoming.pk]
    managed = list_managed_appointments(actor=manager, upcoming=True, now=now)
    assert [item.pk for item in managed.items] == [upcoming.pk]
    assert len(list_my_appointments(actor=student, status="SCHEDULED").items) == 2

    api = auth_client(student).get("/api/v1/appointments/me?upcoming=true").json()["items"]
    assert [item["id"] for item in api] == [str(upcoming.pk)]
    overview = auth_client(student).get("/api/v1/overview").json()["student"]
    assert overview["upcoming_appointments_count"] == len(api)


@pytest.mark.django_db
def test_cancellation_error_codes_come_from_exception_types_not_message_text():
    sync_policy()
    student, manager, service = setup_participants("cancelcode")
    now = timezone.now()
    within_cutoff = create_list_appointment(
        reference_code="APT-2099-900041",
        student=student,
        provider=manager,
        service=service,
        starts_at=now + timedelta(minutes=10),
    )
    started = create_list_appointment(
        reference_code="APT-2099-900042",
        student=student,
        provider=manager,
        service=service,
        starts_at=now - timedelta(minutes=10),
    )
    client = auth_client(student)
    headers = csrf(client)

    cutoff = client.post(f"/api/v1/appointments/{within_cutoff.pk}/cancel", **headers)
    assert cutoff.status_code == 409
    assert cutoff.json()["error"]["code"] == "appointment_cancellation_cutoff_passed"

    lifecycle = client.post(f"/api/v1/appointments/{started.pk}/cancel", **headers)
    assert lifecycle.status_code == 409
    assert lifecycle.json()["error"]["code"] == "appointment_cancellation_conflict"
