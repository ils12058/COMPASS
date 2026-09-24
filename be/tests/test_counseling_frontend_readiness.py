from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.context import AuditContext
from compass.counseling.context_access import (
    CounselingContextNotFound,
    resolve_counseling_context,
)
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.service_catalog.services import create_service, set_service_active


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="User",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def make_counseling_service(admin: User):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        requires_current_inventory=False,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    return set_service_active(
        service_id=service.pk,
        is_active=True,
        context=context(admin),
    )


def make_appointment(
    *,
    student: User,
    counselor: User,
    service,
    starts_at,
    status: str,
) -> Appointment:
    terminal: dict[str, object] = {}
    if status == AppointmentStatus.COMPLETED:
        terminal = {
            "completed_at": starts_at + timedelta(hours=1),
            "completed_by": counselor,
        }
    elif status == AppointmentStatus.CANCELLED:
        terminal = {
            "cancelled_at": starts_at - timedelta(minutes=10),
            "cancelled_by": student,
        }
    elif status == AppointmentStatus.NO_SHOW:
        terminal = {
            "no_show_at": starts_at + timedelta(hours=1),
            "no_show_by": counselor,
        }
    return Appointment.objects.create(
        reference_code=f"APT-CTX-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **terminal,
    )


@pytest.fixture
def context_world(db):
    sync_policy()
    admin = make_user("frontend-context-admin@example.edu", "IT_ADMIN")
    student = make_user("frontend-context-student@example.edu", "STUDENT")
    counselor_a = make_user("frontend-context-a@example.edu", "COUNSELOR")
    counselor_b = make_user("frontend-context-b@example.edu", "COUNSELOR")
    service = make_counseling_service(admin)
    return {
        "student": student,
        "a": counselor_a,
        "b": counselor_b,
        "service": service,
    }


@pytest.mark.django_db
def test_completed_appointment_with_matching_encounter_keeps_post_encounter_context(context_world):
    appointment_start = timezone.now().replace(microsecond=0) - timedelta(hours=1)
    appointment = make_appointment(
        student=context_world["student"],
        counselor=context_world["b"],
        service=context_world["service"],
        starts_at=appointment_start,
        status=AppointmentStatus.COMPLETED,
    )
    encounter = CounselingEncounter.objects.create(
        student=context_world["student"],
        counselor=context_world["b"],
        service=context_world["service"],
        appointment=appointment,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        delivery_mode="IN_PERSON",
        started_at=appointment_start,
        ended_at=appointment_start + timedelta(minutes=50),
        created_by=context_world["b"],
    )

    access = resolve_counseling_context(
        actor=context_world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=encounter.ended_at + timedelta(days=6),
    )
    assert access.encounter_id == encounter.pk
    assert access.valid_until == encounter.ended_at + timedelta(days=7)

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=context_world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=encounter.ended_at + timedelta(days=8),
        )


@pytest.mark.django_db
def test_completed_appointment_without_encounter_uses_only_base_grace(context_world):
    appointment_start = timezone.now().replace(microsecond=0) - timedelta(hours=2)
    appointment = make_appointment(
        student=context_world["student"],
        counselor=context_world["b"],
        service=context_world["service"],
        starts_at=appointment_start,
        status=AppointmentStatus.COMPLETED,
    )

    access = resolve_counseling_context(
        actor=context_world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=appointment.ends_at + timedelta(hours=23),
    )
    assert access.encounter_id is None
    assert access.valid_until == appointment.ends_at + timedelta(hours=24)

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=context_world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=appointment.ends_at + timedelta(hours=25),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("status", [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
def test_cancelled_and_no_show_appointments_never_anchor_context(context_world, status):
    appointment_start = timezone.now().replace(microsecond=0) - timedelta(hours=2)
    appointment = make_appointment(
        student=context_world["student"],
        counselor=context_world["b"],
        service=context_world["service"],
        starts_at=appointment_start,
        status=status,
    )

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=context_world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=timezone.now(),
        )


@pytest.mark.django_db
def test_appointment_context_is_derived_from_current_provider_without_stale_access(context_world):
    now = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=context_world["student"],
        counselor=context_world["a"],
        service=context_world["service"],
        starts_at=now + timedelta(hours=2),
        status=AppointmentStatus.SCHEDULED,
    )

    assert (
        resolve_counseling_context(
            actor=context_world["a"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=now,
        ).counselor_id
        == context_world["a"].pk
    )

    appointment.provider = context_world["b"]
    appointment.save(update_fields=["provider", "updated_at"])

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=context_world["a"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=now,
        )
    assert (
        resolve_counseling_context(
            actor=context_world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=now,
        ).counselor_id
        == context_world["b"].pk
    )
