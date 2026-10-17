"""Cross-pathway commitments and Service transition guarantees for CORR-1B."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connections
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.appointments.services import (
    AppointmentNotSchedulable,
    AppointmentTimeConflict,
    create_student_appointment,
    list_bookable_slots,
    reschedule_appointment,
)
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.common.institutional_time import institution_zone
from compass.group_sessions.models import (
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.group_sessions.services import (
    create_group_session,
    publish_group_session,
    register_student,
    update_group_session,
)
from compass.organization.models import StaffSupervision
from compass.service_catalog.fixed_slots_services import (
    SlotConflictError,
    create_fixed_slot,
    update_fixed_slot,
)
from compass.service_catalog.models import BookingPathwayCode, ServiceAppointmentSlot
from compass.service_catalog.services import (
    ServiceSchedulingConsequenceReviewRequired,
    create_service,
    set_service_active,
    update_service,
)


def _user(email: str, role_code: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-15chars",
        role=Role.objects.get(code=role_code),
        first_name=email.split("@")[0].title(),
        last_name="User",
        institutional_id=f"ID-{email.split('@')[0]}",
        is_active=True,
    )


def _future_monday(*, hour: int = 10, days: int = 7) -> datetime:
    zone = institution_zone()
    target = timezone.now().astimezone(zone).date() + timedelta(days=days)
    while target.weekday() != 0:
        target += timedelta(days=1)
    return datetime.combine(target, time(hour), tzinfo=zone)


def _weekly_window() -> dict[str, object]:
    return {
        "weekday": "MONDAY",
        "start_time": time(8),
        "end_time": time(17),
        "mode_scope": "ALL",
    }


@pytest.fixture
def schedule_env(db):
    call_command("sync_identity_policy", verbosity=0)
    admin = _user("corr1b-admin@example.test", "IT_ADMIN")
    counselor = _user("corr1b-counselor@example.test", "COUNSELOR")
    counselor_b = _user("corr1b-counselor-b@example.test", "COUNSELOR")
    student = _user("corr1b-student@example.test", "STUDENT")
    student_b = _user("corr1b-student-b@example.test", "STUDENT")
    context = AuditContext.user(admin)
    replace_office_weekly(windows=[_weekly_window()], context=context)
    for provider in (counselor, counselor_b):
        replace_provider_weekly(
            provider_id=provider.pk,
            windows=[_weekly_window()],
            context=context,
        )
    service = create_service(
        code="CORR1B_CROSS_PATH",
        name="Cross-pathway Consultation and Workshops",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON", "ONLINE"],
        booking_pathways=[
            BookingPathwayCode.FLEXIBLE_APPOINTMENT,
            BookingPathwayCode.FIXED_DATE_SLOT,
            BookingPathwayCode.GROUP_SESSION,
        ],
        context=context,
    )
    service = set_service_active(service_id=service.pk, is_active=True, context=context)
    return {
        "admin": admin,
        "counselor": counselor,
        "counselor_b": counselor_b,
        "student": student,
        "student_b": student_b,
        "service": service,
    }


def _appointment(env, *, student: User, provider: User, starts_at: datetime) -> Appointment:
    return create_student_appointment(
        student=student,
        service_id=env["service"].pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        context=AuditContext.user(student),
        now=starts_at - timedelta(days=1),
    )


def _external_session(env, *, title: str, starts_at: datetime):
    session = create_group_session(
        service_id=env["service"].pk,
        organizer=env["counselor"],
        title=title,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        capacity=20,
        facilitators=[
            {
                "kind": "EXTERNAL",
                "internal_user_id": None,
                "external_display_name": "Guest Speaker",
                "is_lead": True,
            }
        ],
    )
    return publish_group_session(session_id=session.pk, actor=env["counselor"])


@pytest.mark.django_db
def test_published_fixed_slot_cannot_overlap_a_counselor_appointment(schedule_env):
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    _appointment(schedule_env, student=schedule_env["student"], provider=counselor, starts_at=start)

    with pytest.raises(SlotConflictError, match="overlapping.*Appointment"):
        create_fixed_slot(
            service_id=schedule_env["service"].pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            actor=counselor,
            context=AuditContext.user(counselor),
        )


@pytest.mark.django_db
def test_unpublished_fixed_slot_does_not_block_flexible_booking(schedule_env):
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    create_fixed_slot(
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        is_published=False,
        actor=counselor,
        context=AuditContext.user(counselor),
    )

    appointment = _appointment(
        schedule_env,
        student=schedule_env["student"],
        provider=counselor,
        starts_at=start,
    )
    assert appointment.status == AppointmentStatus.SCHEDULED


@pytest.mark.django_db
def test_flexible_availability_omits_published_slots_and_group_facilitation(schedule_env):
    counselor = schedule_env["counselor"]
    student = schedule_env["student"]
    start = _future_monday(hour=10)
    create_fixed_slot(
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    group_session = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Provider availability commitment",
        starts_at=start + timedelta(hours=3),
        ends_at=start + timedelta(hours=4),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    publish_group_session(session_id=group_session.pk, actor=counselor)

    slots = list_bookable_slots(
        student=student,
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        target_date=start.date(),
        now=start - timedelta(days=1),
    )
    starts = {item.starts_at for item in slots.items}
    assert start not in starts
    assert start + timedelta(hours=3) not in starts


@pytest.mark.django_db
def test_terminal_fixed_slot_appointment_does_not_block_flexible_availability(schedule_env):
    counselor = schedule_env["counselor"]
    student = schedule_env["student"]
    start = _future_monday(hour=10)
    slot = create_fixed_slot(
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        is_published=False,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    appointment = _appointment(
        schedule_env,
        student=student,
        provider=counselor,
        starts_at=start,
    )
    Appointment.objects.filter(pk=appointment.pk).update(
        status=AppointmentStatus.COMPLETED,
        completed_at=timezone.now(),
    )
    ServiceAppointmentSlot.objects.filter(pk=slot.pk).update(
        current_appointment=appointment,
        is_published=True,
    )

    bookable = list_bookable_slots(
        student=student,
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        target_date=start.date(),
        now=start - timedelta(days=1),
    )

    assert any(item.starts_at == start for item in bookable.items)


@pytest.mark.django_db
def test_internal_facilitators_cannot_accept_overlapping_appointments_or_group_sessions(
    schedule_env,
):
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    _appointment(schedule_env, student=schedule_env["student"], provider=counselor, starts_at=start)
    appointment_conflict = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Overlapping with an Appointment",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    with pytest.raises(ValidationError, match="overlapping Appointment"):
        publish_group_session(session_id=appointment_conflict.pk, actor=counselor)

    first = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="First facilitator commitment",
        starts_at=start + timedelta(hours=2),
        ends_at=start + timedelta(hours=3),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    publish_group_session(session_id=first.pk, actor=counselor)
    with pytest.raises(AppointmentTimeConflict, match="published Group Session"):
        _appointment(
            schedule_env,
            student=schedule_env["student_b"],
            provider=counselor,
            starts_at=start + timedelta(hours=2),
        )
    second = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Overlapping facilitator commitment",
        starts_at=start + timedelta(hours=2, minutes=30),
        ends_at=start + timedelta(hours=3, minutes=30),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    with pytest.raises(ValidationError, match="overlapping.*Group Session"):
        publish_group_session(session_id=second.pk, actor=counselor)

    slot_start = start + timedelta(hours=4)
    create_fixed_slot(
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=slot_start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    slot_conflict = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Overlapping with a published slot",
        starts_at=slot_start,
        ends_at=slot_start + timedelta(hours=1),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    with pytest.raises(ValidationError, match="published Fixed Slot"):
        publish_group_session(session_id=slot_conflict.pk, actor=counselor)


@pytest.mark.django_db
def test_student_appointments_registrations_and_reschedules_share_one_overlap_policy(schedule_env):
    student = schedule_env["student"]
    counselor = schedule_env["counselor"]
    counselor_b = schedule_env["counselor_b"]
    start = _future_monday(hour=10)

    first = _external_session(schedule_env, title="First student event", starts_at=start)
    register_student(session_id=first.pk, student=student)
    with pytest.raises(AppointmentTimeConflict, match="overlapping"):
        _appointment(schedule_env, student=student, provider=counselor, starts_at=start)

    second_start = start + timedelta(hours=3)
    second = _external_session(schedule_env, title="Second student event", starts_at=second_start)
    _appointment(
        schedule_env,
        student=schedule_env["student_b"],
        provider=counselor,
        starts_at=second_start,
    )
    with pytest.raises(ValidationError, match="overlapping Appointment"):
        register_student(session_id=second.pk, student=schedule_env["student_b"])

    third_start = start + timedelta(hours=5)
    third = _external_session(schedule_env, title="Registered student event", starts_at=third_start)
    register_student(session_id=third.pk, student=student)
    _appointment(
        schedule_env,
        student=student,
        provider=counselor_b,
        starts_at=third_start + timedelta(hours=1),
    )
    with pytest.raises(ValidationError, match="overlaps an Appointment"):
        update_group_session(
            session_id=third.pk,
            actor=counselor,
            starts_at=third_start + timedelta(hours=1),
            ends_at=third_start + timedelta(hours=2),
        )
    third.refresh_from_db()
    assert third.starts_at == third_start

    appointment_to_reschedule = _appointment(
        schedule_env,
        student=student,
        provider=counselor_b,
        starts_at=start + timedelta(hours=4),
    )
    with pytest.raises(AppointmentTimeConflict, match="registered.*Group Session"):
        reschedule_appointment(
            appointment_id=appointment_to_reschedule.pk,
            actor=counselor_b,
            starts_at=start,
            reason="Student schedule conflict regression",
            administrative=True,
            context=AuditContext.user(counselor_b),
            now=start - timedelta(days=1),
        )

    overlapping = _external_session(
        schedule_env,
        title="Another event at the same time",
        starts_at=start,
    )
    with pytest.raises(ValidationError, match="overlapping.*Group Session"):
        register_student(session_id=overlapping.pk, student=student)


@pytest.mark.django_db
def test_group_registration_stays_separate_and_internal_gss_is_not_an_appointment_provider(
    schedule_env,
):
    from compass.counseling.models import CounselingEncounter

    counselor = schedule_env["counselor"]
    student = schedule_env["student"]
    gss = _user("corr1b-direct-facilitator@example.test", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    start = _future_monday(hour=10)
    session = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Internal facilitator role separation",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        capacity=10,
        facilitator_ids=[gss.pk],
    )
    publish_group_session(session_id=session.pk, actor=counselor)
    appointments_before = Appointment.objects.count()
    encounters_before = CounselingEncounter.objects.count()

    registration = register_student(session_id=session.pk, student=student)

    assert registration.status == RegistrationStatus.REGISTERED
    assert Appointment.objects.count() == appointments_before
    assert CounselingEncounter.objects.count() == encounters_before
    with pytest.raises(AppointmentNotSchedulable, match="active Counselor"):
        _appointment(schedule_env, student=student, provider=gss, starts_at=start)


@pytest.mark.django_db(transaction=True)
def test_concurrent_appointment_and_group_registration_have_one_student_commitment(schedule_env):
    from compass.group_sessions.services import register_student

    student = schedule_env["student"]
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    session = _external_session(schedule_env, title="Concurrent registration", starts_at=start)
    barrier = Barrier(2)

    def attempt_appointment() -> str:
        try:
            barrier.wait()
            _appointment(schedule_env, student=student, provider=counselor, starts_at=start)
            return "appointment"
        except AppointmentTimeConflict:
            return "conflict"
        finally:
            connections.close_all()

    def attempt_registration() -> str:
        try:
            barrier.wait()
            register_student(session_id=session.pk, student=student)
            return "registration"
        except ValidationError as exc:
            if "overlapping Appointment or registered Group Session" not in str(exc):
                raise
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt_appointment), pool.submit(attempt_registration)]
        results = sorted(future.result() for future in futures)

    assert results in (["appointment", "conflict"], ["conflict", "registration"])
    assert (
        Appointment.objects.filter(student=student, status=AppointmentStatus.SCHEDULED).count()
        + GroupSessionRegistration.objects.filter(
            student=student, status=RegistrationStatus.REGISTERED
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_appointment_and_group_session_publication_have_one_provider_commitment(
    schedule_env,
):
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    session = create_group_session(
        service_id=schedule_env["service"].pk,
        organizer=counselor,
        title="Concurrent publication",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    barrier = Barrier(2)

    def attempt_appointment() -> str:
        try:
            barrier.wait()
            _appointment(
                schedule_env,
                student=schedule_env["student"],
                provider=counselor,
                starts_at=start,
            )
            return "appointment"
        except AppointmentTimeConflict:
            return "conflict"
        finally:
            connections.close_all()

    def attempt_publish() -> str:
        try:
            barrier.wait()
            publish_group_session(session_id=session.pk, actor=counselor)
            return "publication"
        except ValidationError as exc:
            if "overlapping Appointment" not in str(exc):
                raise
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(
            future.result()
            for future in (
                pool.submit(attempt_appointment),
                pool.submit(attempt_publish),
            )
        )

    assert results in (["appointment", "conflict"], ["conflict", "publication"])
    session.refresh_from_db()
    assert (
        Appointment.objects.filter(provider=counselor, starts_at=start).count()
        + int(session.status == GroupSessionStatus.PUBLISHED)
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_appointment_and_fixed_slot_publication_have_one_provider_commitment(
    schedule_env,
):
    counselor = schedule_env["counselor"]
    start = _future_monday(hour=10)
    slot = create_fixed_slot(
        service_id=schedule_env["service"].pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        is_published=False,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    barrier = Barrier(2)

    def attempt_appointment() -> str:
        try:
            barrier.wait()
            _appointment(
                schedule_env,
                student=schedule_env["student"],
                provider=counselor,
                starts_at=start,
            )
            return "appointment"
        except AppointmentTimeConflict:
            return "conflict"
        finally:
            connections.close_all()

    def attempt_publish() -> str:
        try:
            barrier.wait()
            update_fixed_slot(
                slot_id=slot.pk,
                actor=counselor,
                context=AuditContext.user(counselor),
                is_published=True,
            )
            return "publication"
        except SlotConflictError:
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(
            future.result()
            for future in (
                pool.submit(attempt_appointment),
                pool.submit(attempt_publish),
            )
        )

    assert results in (["appointment", "conflict"], ["conflict", "publication"])
    slot.refresh_from_db()
    assert (
        Appointment.objects.filter(provider=counselor, starts_at=start).count()
        + int(slot.is_published)
        == 1
    )


@pytest.mark.django_db
def test_disabling_service_reviews_and_preserves_slots_sessions_and_registrations(schedule_env):
    from compass.group_sessions.models import GroupSession

    counselor = schedule_env["counselor"]
    student = schedule_env["student"]
    service = schedule_env["service"]
    start = _future_monday(hour=10)
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    session = _external_session(
        schedule_env,
        title="Service deactivation history",
        starts_at=start + timedelta(days=7),
    )
    registration = register_student(session_id=session.pk, student=student)
    appointment = _appointment(
        schedule_env,
        student=schedule_env["student_b"],
        provider=schedule_env["counselor_b"],
        starts_at=start + timedelta(days=7, hours=3),
    )

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired) as caught:
        set_service_active(
            service_id=service.pk,
            is_active=False,
            context=AuditContext.user(schedule_env["admin"]),
        )
    assert caught.value.existing_fixed_slot_dependency_detected
    assert caught.value.existing_group_session_dependency_detected
    assert caught.value.existing_appointment_dependency_detected
    assert ServiceAppointmentSlot.objects.filter(pk=slot.pk, is_published=True).exists()
    assert GroupSessionRegistration.objects.filter(pk=registration.pk, status="REGISTERED").exists()

    inactive = set_service_active(
        service_id=service.pk,
        is_active=False,
        context=AuditContext.user(schedule_env["admin"]),
        acknowledge_scheduling_consequences=True,
    )
    assert not inactive.is_active
    assert ServiceAppointmentSlot.objects.filter(pk=slot.pk, is_published=True).exists()
    assert GroupSession.objects.get(pk=session.pk).status == GroupSessionStatus.PUBLISHED
    assert (
        GroupSessionRegistration.objects.get(pk=registration.pk).status
        == RegistrationStatus.REGISTERED
    )
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED

    with pytest.raises(ValidationError, match="not currently accepting"):
        register_student(session_id=session.pk, student=schedule_env["student_b"])

    now = timezone.now()
    issued = create_auth_session(student, now=now)
    client = Client()
    client.cookies["compass_session"] = issued.token
    assert client.get("/api/v1/group-sessions/me/registrations").status_code == 200
    historical_detail = client.get(f"/api/v1/group-sessions/{session.pk}")
    assert historical_detail.status_code == 200
    assert historical_detail.json()["status"] == GroupSessionStatus.PUBLISHED


@pytest.mark.django_db
def test_service_transition_reviews_an_open_slot_until_its_end(schedule_env):
    counselor = schedule_env["counselor"]
    service = schedule_env["service"]
    start = _future_monday(hour=10)
    create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired) as caught:
        set_service_active(
            service_id=service.pk,
            is_active=False,
            context=AuditContext.user(schedule_env["admin"]),
            now=start + timedelta(minutes=30),
        )

    assert caught.value.existing_fixed_slot_dependency_detected


@pytest.mark.django_db
def test_removing_pathways_keeps_published_offerings_and_active_registrations(schedule_env):
    counselor = schedule_env["counselor"]
    student = schedule_env["student"]
    service = schedule_env["service"]
    start = _future_monday(hour=10)
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    session = _external_session(
        schedule_env,
        title="Preserved registration after pathway change",
        starts_at=start + timedelta(days=7),
    )
    registration = register_student(session_id=session.pk, student=student)
    appointment = _appointment(
        schedule_env,
        student=schedule_env["student_b"],
        provider=schedule_env["counselor_b"],
        starts_at=start + timedelta(days=7, hours=3),
    )

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired) as caught:
        update_service(
            service_id=service.pk,
            changes={"booking_pathways": [BookingPathwayCode.FLEXIBLE_APPOINTMENT]},
            context=AuditContext.user(schedule_env["admin"]),
        )
    assert caught.value.existing_fixed_slot_dependency_detected
    assert caught.value.existing_group_session_dependency_detected
    assert not caught.value.existing_appointment_dependency_detected

    updated = update_service(
        service_id=service.pk,
        changes={"booking_pathways": [BookingPathwayCode.FLEXIBLE_APPOINTMENT]},
        context=AuditContext.user(schedule_env["admin"]),
        acknowledge_scheduling_consequences=True,
    )
    assert updated.is_active
    assert ServiceAppointmentSlot.objects.filter(pk=slot.pk, is_published=True).exists()
    assert GroupSessionRegistration.objects.filter(
        pk=registration.pk,
        status=RegistrationStatus.REGISTERED,
    ).exists()
    assert session.__class__.objects.get(pk=session.pk).status == GroupSessionStatus.PUBLISHED
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED

    with pytest.raises(ValidationError, match="not currently accepting"):
        register_student(session_id=session.pk, student=schedule_env["student_b"])
