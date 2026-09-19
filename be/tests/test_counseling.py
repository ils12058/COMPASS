from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import (
    CounselingAppointmentAlreadyUsed,
    CounselingAppointmentInvalid,
    CounselingConfigurationConflict,
    CounselingInvalidTime,
    CounselingNotFound,
    CounselingNotPermitted,
    create_encounter,
    update_encounter,
)
from compass.notifications.models import EmailDelivery, Notification
from compass.service_catalog.services import create_service, set_service_active


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def create_counseling_service(
    actor: User,
    *,
    active: bool = True,
    delivery_modes: list[str] | None = None,
    provider_roles: list[str] | None = None,
):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=delivery_modes or ["IN_PERSON", "ONLINE"],
        provider_roles=provider_roles or ["COUNSELOR"],
        context=context(actor),
    )
    if active:
        service = set_service_active(
            service_id=service.pk,
            is_active=True,
            context=context(actor),
        )
    return service


def actual_times(*, minutes: int = 48):
    end = timezone.now() - timedelta(minutes=5)
    return end - timedelta(minutes=minutes), end


def make_appointment(
    *,
    student: User,
    provider: User,
    service,
    delivery_mode: str = "IN_PERSON",
    status: str = "SCHEDULED",
):
    start = timezone.now() - timedelta(hours=2)
    kwargs = {}
    if status == "CANCELLED":
        kwargs = {"cancelled_at": timezone.now() - timedelta(hours=3), "cancelled_by": student}
    return Appointment.objects.create(
        reference_code=f"APT-2026-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=provider,
        service=service,
        delivery_mode=delivery_mode,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **kwargs,
    )


@pytest.mark.django_db
def test_counseling_capabilities_are_counselor_only_and_revoke_still_wins():
    sync_policy()
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert counselor.has_capability("counseling.view_assigned")
    assert counselor.has_capability("counseling.manage_assigned")
    assert head.has_capability("counseling.view_assigned")
    assert head.has_capability("counseling.manage_assigned")
    assert not gss.has_capability("counseling.view_assigned")
    assert not student.has_capability("counseling.view_assigned")
    assert not admin.has_capability("counseling.view_assigned")

    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code="counseling.view_assigned"),
        effect="REVOKE",
        reason="temporary separation",
    )
    assert not counselor.has_capability("counseling.view_assigned")


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
@pytest.mark.parametrize("entry_mode", ["WALK_IN", "CALLED_IN", "REFERRED"])
def test_direct_encounter_records_actual_completed_time_without_fake_appointment(entry_mode):
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    started_at, ended_at = actual_times(minutes=75)

    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        appointment_id=None,
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )

    assert item.student_id == student.pk
    assert item.counselor_id == counselor.pk
    assert item.service.code == "COUNSELING"
    assert item.appointment_id is None
    assert item.entry_mode == entry_mode
    assert item.ended_at - item.started_at == timedelta(minutes=75)
    assert AuditEvent.objects.filter(action="counseling.encounter.created").count() == 1
    invitation = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_type="counseling_encounter",
        source_id=item.pk,
    )
    assert invitation.policy == "OPTIONAL_INFORMATIONAL"
    assert invitation.target_type == "FEEDBACK"
    assert invitation.target_id is None
    assert EmailDelivery.objects.filter(notification=invitation).exists()


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_appointment_origin_derives_identity_service_and_mode_but_keeps_actual_time():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    appointment = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="ONLINE",
    )
    started_at = appointment.starts_at + timedelta(minutes=4)
    ended_at = appointment.ends_at - timedelta(minutes=8)

    item = create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=appointment.pk,
        student_id=None,
        delivery_mode=None,
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )

    assert item.student_id == appointment.student_id
    assert item.counselor_id == appointment.provider_id
    assert item.service_id == appointment.service_id
    assert item.delivery_mode == "ONLINE"
    assert item.started_at == started_at
    assert item.ended_at == ended_at
    appointment.refresh_from_db()
    assert appointment.status == "SCHEDULED"
    invitation = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_type="counseling_encounter",
        source_id=item.pk,
    )
    assert invitation.policy == "OPTIONAL_INFORMATIONAL"
    assert EmailDelivery.objects.filter(notification=invitation).exists()


@pytest.mark.django_db
def test_appointment_link_validation_rejects_missing_cancelled_wrong_provider_and_duplicate():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    started_at, ended_at = actual_times()

    with pytest.raises(CounselingAppointmentInvalid, match="requires"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    cancelled = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status="CANCELLED",
    )
    with pytest.raises(CounselingAppointmentInvalid, match="SCHEDULED"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            appointment_id=cancelled.pk,
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    wrong_provider = make_appointment(
        student=student,
        provider=other,
        service=service,
    )
    with pytest.raises(CounselingAppointmentInvalid, match="different Counselor"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            appointment_id=wrong_provider.pk,
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    usable = make_appointment(student=student, provider=counselor, service=service)
    create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=usable.pk,
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )
    with pytest.raises(CounselingAppointmentAlreadyUsed):
        create_encounter(
            counselor=counselor,
            entry_mode="CALLED_IN",
            appointment_id=usable.pk,
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_linked_create_rejects_wrong_service_and_smuggled_student_or_mode():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    other_student = make_user("other-student@example.edu", "STUDENT")
    counseling = create_counseling_service(admin)
    other_service = create_service(
        code="GOOD_MORAL",
        name="Good Moral",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    other_service = set_service_active(
        service_id=other_service.pk,
        is_active=True,
        context=context(admin),
    )
    started_at, ended_at = actual_times()
    wrong_service = make_appointment(
        student=student,
        provider=counselor,
        service=other_service,
    )
    with pytest.raises(CounselingAppointmentInvalid, match="COUNSELING"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            appointment_id=wrong_service.pk,
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    usable = make_appointment(student=student, provider=counselor, service=counseling)
    with pytest.raises(CounselingAppointmentInvalid, match="student_id"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            appointment_id=usable.pk,
            student_id=other_student.pk,
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )
    with pytest.raises(CounselingAppointmentInvalid, match="delivery_mode"):
        create_encounter(
            counselor=counselor,
            entry_mode="APPOINTMENT",
            appointment_id=usable.pk,
            delivery_mode="ONLINE",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_missing_inactive_or_misconfigured_counseling_service_rejects_new_encounter():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    started_at, ended_at = actual_times()

    with pytest.raises(CounselingConfigurationConflict, match="not been configured"):
        create_encounter(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    service = create_counseling_service(admin, active=False)
    with pytest.raises(CounselingConfigurationConflict, match="inactive"):
        create_encounter(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )

    set_service_active(service_id=service.pk, is_active=True, context=context(admin))
    service.delivery_mode_assignments.filter(mode="ONLINE").delete()
    with pytest.raises(CounselingNotPermitted, match="delivery mode"):
        create_encounter(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="ONLINE",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_actual_time_validation_requires_aware_ordered_completed_interval_without_maximum():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    now = timezone.now()

    for start, end in ((now, now), (now, now - timedelta(minutes=1))):
        with pytest.raises(CounselingInvalidTime):
            create_encounter(
                counselor=counselor,
                student_id=student.pk,
                entry_mode="WALK_IN",
                delivery_mode="IN_PERSON",
                started_at=start,
                ended_at=end,
                context=context(counselor),
            )

    with pytest.raises(CounselingInvalidTime, match="future"):
        create_encounter(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=now,
            ended_at=now + timedelta(minutes=1),
            context=context(counselor),
        )

    long_start = now - timedelta(hours=4)
    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=long_start,
        ended_at=now - timedelta(minutes=1),
        context=context(counselor),
    )
    assert item.ended_at - item.started_at > timedelta(hours=3)


@pytest.mark.django_db
def test_student_and_gss_cannot_be_used_as_counseling_provider_or_selected_student():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    started_at, ended_at = actual_times()

    with pytest.raises(CounselingNotPermitted, match="active Counselor"):
        create_encounter(
            counselor=gss,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=started_at,
            ended_at=ended_at,
            context=context(gss),
        )
    with pytest.raises(CounselingNotPermitted, match="active Student"):
        create_encounter(
            counselor=counselor,
            student_id=gss.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=started_at,
            ended_at=ended_at,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_update_is_assigned_only_immutable_identity_and_noop_has_no_fake_audit():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    started_at, ended_at = actual_times()
    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )
    created_events = AuditEvent.objects.count()

    unchanged = update_encounter(
        encounter_id=item.pk,
        counselor=counselor,
        changes={},
        context=context(counselor),
    )
    assert unchanged.pk == item.pk
    assert AuditEvent.objects.count() == created_events

    with pytest.raises(CounselingNotFound):
        update_encounter(
            encounter_id=item.pk,
            counselor=other,
            changes={"entry_mode": "CALLED_IN"},
            context=context(other),
        )

    changed = update_encounter(
        encounter_id=item.pk,
        counselor=counselor,
        changes={"entry_mode": "CALLED_IN", "started_at": started_at - timedelta(minutes=2)},
        context=context(counselor),
    )
    assert changed.entry_mode == "CALLED_IN"
    event = AuditEvent.objects.get(action="counseling.encounter.updated")
    assert set(event.metadata["changed_fields"]) == {"entry_mode", "started_at"}
    assert "student" not in event.metadata


@pytest.mark.django_db
def test_historical_correction_survives_service_deactivation():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    started_at, ended_at = actual_times()
    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )
    set_service_active(service_id=service.pk, is_active=False, context=context(admin))

    corrected = update_encounter(
        encounter_id=item.pk,
        counselor=counselor,
        changes={"ended_at": ended_at - timedelta(minutes=1)},
        context=context(counselor),
    )
    assert corrected.service_id == service.pk


@pytest.mark.django_db
def test_entry_mode_is_not_link_type_and_relink_validates_immutable_identity():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, provider=counselor, service=service)
    started_at, ended_at = actual_times()
    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="REFERRED",
        delivery_mode="IN_PERSON",
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )

    linked = update_encounter(
        encounter_id=item.pk,
        counselor=counselor,
        changes={"appointment_id": appointment.pk},
        context=context(counselor),
    )
    assert linked.entry_mode == "REFERRED"
    assert linked.appointment_id == appointment.pk

    retained = update_encounter(
        encounter_id=item.pk,
        counselor=counselor,
        changes={"entry_mode": "CALLED_IN"},
        context=context(counselor),
    )
    assert retained.appointment_id == appointment.pk


@pytest.mark.django_db
def test_database_constraints_enforce_time_order_and_appointment_mode_link():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    now = timezone.now()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CounselingEncounter.objects.create(
                student=student,
                counselor=counselor,
                service=service,
                entry_mode="WALK_IN",
                delivery_mode="IN_PERSON",
                started_at=now,
                ended_at=now,
                created_by=counselor,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CounselingEncounter.objects.create(
                student=student,
                counselor=counselor,
                service=service,
                entry_mode="APPOINTMENT",
                delivery_mode="IN_PERSON",
                started_at=now - timedelta(minutes=30),
                ended_at=now - timedelta(minutes=1),
                created_by=counselor,
            )


@pytest.mark.django_db
def test_api_assignment_privacy_student_lookup_and_no_idempotency_requirement():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    make_user("inactive@example.edu", "STUDENT", active=False)
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    create_counseling_service(admin)
    started_at, ended_at = actual_times()
    payload = {
        "student_id": str(student.pk),
        "entry_mode": "WALK_IN",
        "delivery_mode": "IN_PERSON",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
    }
    client = auth_client(counselor)
    created = client.post(
        "/api/v1/counseling/encounters",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert created.status_code == 201
    encounter_id = created.json()["id"]

    assert client.get("/api/v1/counseling/me/encounters").status_code == 200
    assert client.get(f"/api/v1/counseling/encounters/{encounter_id}").status_code == 200
    students = client.get("/api/v1/counseling/students?search=student")
    assert students.status_code == 200
    assert students.json()["items"] == [
        {"id": str(student.pk), "display_name": student.get_full_name()}
    ]
    assert "email" not in students.content.decode().lower()

    assert (
        auth_client(other).get(f"/api/v1/counseling/encounters/{encounter_id}").status_code == 404
    )
    assert (
        auth_client(student).get(f"/api/v1/counseling/encounters/{encounter_id}").status_code == 403
    )
    assert auth_client(gss).get(f"/api/v1/counseling/encounters/{encounter_id}").status_code == 403
    assert (
        auth_client(admin).get(f"/api/v1/counseling/encounters/{encounter_id}").status_code == 403
    )


@pytest.mark.django_db
def test_head_designation_has_no_blanket_read_and_patch_cannot_change_identity():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    create_counseling_service(admin)
    started_at, ended_at = actual_times()
    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=started_at,
        ended_at=ended_at,
        context=context(counselor),
    )

    head_client = auth_client(head)
    assert head_client.get(f"/api/v1/counseling/encounters/{item.pk}").status_code == 404

    counselor_client = auth_client(counselor)
    response = counselor_client.patch(
        f"/api/v1/counseling/encounters/{item.pk}",
        data=json.dumps({"student_id": str(uuid4())}),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert response.status_code == 422
