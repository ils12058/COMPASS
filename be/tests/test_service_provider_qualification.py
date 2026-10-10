"""ADR-089: Counselor provider coverage, booking capability, and Appointment provenance."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Role
from compass.appointments.models import Appointment, AppointmentStatus
from compass.appointments.services import (
    AppointmentDefaultProviderNotQualified,
    AppointmentNotSchedulable,
    create_student_appointment,
    list_bookable_slots,
    list_booking_services,
    list_eligible_counselors,
    list_reassignment_candidates,
    list_reschedule_slots,
    reassign_appointment,
)
from compass.availability.services import AvailabilityNotApplicable, compute_base_availability
from compass.counseling.services import (
    CounselingNotPermitted,
    create_encounter,
    list_appointment_candidates,
)
from compass.ecounseling.services import get_counselor_workspace, get_student_workspace
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StudentAffiliation,
)
from compass.routine_interviews.services import (
    RoutineInterviewAppointmentInvalid,
    create_direct,
    ensure_for_appointment,
    get_direct_creation_options,
    list_my_appointment_candidates,
)
from compass.service_catalog.bootstrap import sync_canonical_services
from compass.service_catalog.models import Service
from compass.service_catalog.services import create_service, set_service_active, update_service
from tests.test_appointments import (
    configure_availability,
    context,
    future_local_start,
    make_user,
    sync_policy,
)


def counseling(*, online: bool = True, coverage: dict | None = None) -> Service:
    service = Service.objects.get(pk=sync_canonical_services().service_id)
    changes: dict[str, object] = {}
    if online:
        changes["delivery_modes"] = ["IN_PERSON", "ONLINE"]
    changes.update(coverage or {})
    if changes:
        service = update_service(
            service_id=service.pk,
            changes=changes,
            context=context(make_user(f"sync-{uuid4().hex[:6]}@example.edu", "IT_ADMIN")),
            acknowledge_scheduling_consequences=True,
        )
    return service


def saved_appointment(*, student, counselor, service, mode="ONLINE", minutes_from_now=-5):
    starts_at = timezone.now() + timedelta(minutes=minutes_from_now)
    return Appointment.objects.create(
        reference_code=f"APT-Q-{uuid4().hex[:12].upper()}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode=mode,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=AppointmentStatus.SCHEDULED,
        cancellation_cutoff_minutes=30,
        created_by=student,
    )


def record_appointment_encounter(counselor, appointment):
    ended_at = timezone.now() - timedelta(minutes=1)
    return create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=appointment.pk,
        started_at=ended_at - timedelta(minutes=3),
        ended_at=ended_at,
        context=context(counselor),
    )


def record_direct(counselor, student, mode="IN_PERSON"):
    ended_at = timezone.now() - timedelta(minutes=10)
    return create_encounter(
        counselor=counselor,
        entry_mode="WALK_IN",
        student_id=student.pk,
        delivery_mode=mode,
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        context=context(counselor),
    )


def college(code: str, counselor) -> College:
    campus = Campus.objects.create(code=f"CAMP-{code}", name=f"Campus {code}")
    item = College.objects.create(campus=campus, code=code, name=f"College {code}")
    CounselorResponsibility.objects.create(college=item, counselor=counselor)
    return item


# Appointment discovery and booking -------------------------------------------------------------


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_discovery_respects_coverage_default_and_cross_college_choice():
    sync_policy()
    admin = make_user("discovery-admin@example.edu", "IT_ADMIN")
    tester = make_user("discovery-tester@example.edu", "COUNSELOR")
    home = make_user("discovery-home@example.edu", "COUNSELOR")
    student = make_user("discovery-student@example.edu", "STUDENT")
    StudentAffiliation.objects.create(student=student, college=college("HOME", home))
    college("AWAY", tester)

    testing = create_service(
        code="PSYCH_TESTING",
        name="Psychological Testing",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_coverage="SELECTED_COUNSELORS",
        selected_counselor_ids=[tester.pk],
        context=context(admin),
    )
    testing = set_service_active(service_id=testing.pk, is_active=True, context=context(admin))
    for counselor in (tester, home):
        configure_availability(admin, counselor)

    # Only the selected Counselor is a candidate; the College default is not forced in.
    eligible = list_eligible_counselors(
        student=student, service_id=testing.pk, delivery_mode="IN_PERSON"
    )
    assert [(item.user, item.is_default) for item in eligible] == [(tester, False)]
    general = counseling(online=False)
    defaults = {
        item.user.pk: item.is_default
        for item in list_eligible_counselors(
            student=student, service_id=general.pk, delivery_mode="IN_PERSON"
        )
    }
    assert defaults[home.pk] is True and defaults[tester.pk] is False

    # The default Counselor does not provide this Service: fail, never substitute.
    starts_at = future_local_start()
    with pytest.raises(AppointmentDefaultProviderNotQualified):
        create_student_appointment(
            student=student,
            service_id=testing.pk,
            provider_id=None,
            delivery_mode="IN_PERSON",
            starts_at=starts_at,
            context=context(student),
        )
    with pytest.raises(AppointmentNotSchedulable, match="does not provide"):
        create_student_appointment(
            student=student,
            service_id=testing.pk,
            provider_id=home.pk,
            delivery_mode="IN_PERSON",
            starts_at=starts_at,
            context=context(student),
        )
    # A qualified Counselor from another College may be chosen explicitly.
    booked = create_student_appointment(
        student=student,
        service_id=testing.pk,
        provider_id=tester.pk,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        context=context(student),
    )
    assert booked.provider_id == tester.pk
    assert booked.ends_at - booked.starts_at == timedelta(minutes=60)
    assert booked.cancellation_cutoff_minutes == 30

    # Availability for an unqualified Counselor is unavailable even with free time.
    with pytest.raises(AvailabilityNotApplicable):
        compute_base_availability(
            provider_id=home.pk,
            service_id=testing.pk,
            delivery_mode="IN_PERSON",
            start_date=starts_at.date(),
            end_date=starts_at.date() + timedelta(days=1),
        )
    assert compute_base_availability(
        provider_id=tester.pk,
        service_id=testing.pk,
        delivery_mode="IN_PERSON",
        start_date=starts_at.date(),
        end_date=starts_at.date() + timedelta(days=1),
    ).windows

    # New durations apply to new Appointments only.
    update_service(
        service_id=testing.pk,
        changes={"default_appointment_duration_minutes": 90, "cancellation_cutoff_minutes": 10},
        context=context(admin),
    )
    booked.refresh_from_db()
    assert booked.ends_at - booked.starts_at == timedelta(minutes=60)
    assert booked.cancellation_cutoff_minutes == 30
    slots = list_bookable_slots(
        student=student,
        service_id=testing.pk,
        provider_id=tester.pk,
        delivery_mode="IN_PERSON",
        target_date=(starts_at + timedelta(days=7)).date(),
    )
    assert slots.duration_minutes == 90


@pytest.mark.django_db
def test_booking_disabled_services_are_not_bookable_or_duration_shaped():
    sync_policy()
    admin = make_user("disabled-admin@example.edu", "IT_ADMIN")
    counselor = make_user("disabled-counselor@example.edu", "COUNSELOR")
    student = make_user("disabled-student@example.edu", "STUDENT")
    configure_availability(admin, counselor)
    walk_in = create_service(
        code="WALK_IN_ONLY",
        name="Walk-in only",
        delivery_modes=["IN_PERSON"],
        context=context(admin),
    )
    walk_in = set_service_active(service_id=walk_in.pk, is_active=True, context=context(admin))
    bookable = counseling(online=False)

    codes = {item.code for item in list_booking_services().items}
    assert codes == {bookable.code}
    with pytest.raises(AppointmentNotSchedulable, match="does not accept Appointments"):
        list_eligible_counselors(student=student, service_id=walk_in.pk, delivery_mode="IN_PERSON")

    # Availability for a non-bookable Service is not filtered by any Appointment duration.
    day = future_local_start().date()
    windows = compute_base_availability(
        provider_id=counselor.pk,
        service_id=walk_in.pk,
        delivery_mode="IN_PERSON",
        start_date=day,
        end_date=day + timedelta(days=1),
    ).windows
    assert windows


# Direct Counseling and Routine -----------------------------------------------------------------


@pytest.mark.django_db
def test_new_direct_counseling_and_routine_follow_current_qualification_and_modes():
    sync_policy()
    selected = make_user("direct-selected@example.edu", "COUNSELOR")
    unselected = make_user("direct-unselected@example.edu", "COUNSELOR")
    student = make_user("direct-student@example.edu", "STUDENT")
    college("ELSEWHERE", selected)  # College responsibility is irrelevant to qualification.

    counseling(online=False)
    assert record_direct(unselected, student).counselor_id == unselected.pk  # ALL coverage
    with pytest.raises(CounselingNotPermitted, match="delivery mode"):
        record_direct(selected, student, mode="ONLINE")

    counseling(
        online=False,
        coverage={
            "provider_coverage": "SELECTED_COUNSELORS",
            "selected_counselor_ids": [selected.pk],
        },
    )
    assert record_direct(selected, student).counselor_id == selected.pk
    with pytest.raises(CounselingNotPermitted, match="does not permit"):
        record_direct(unselected, student)

    assert get_direct_creation_options(selected).delivery_modes == ("IN_PERSON",)
    with pytest.raises(RoutineInterviewAppointmentInvalid):
        get_direct_creation_options(unselected)
    with pytest.raises(RoutineInterviewAppointmentInvalid):
        create_direct(
            counselor=unselected,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            idempotency_key="unselected",
            request_fingerprint="a" * 64,
            context=context(unselected),
        )
    routine = create_direct(
        counselor=selected,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="selected",
        request_fingerprint="b" * 64,
        context=context(selected),
    )
    assert routine.inventory_id is None  # ADR-088: Inventory stays optional.


# Existing Appointment resilience ---------------------------------------------------------------


@pytest.mark.django_db
@override_settings(DAILY_ENABLED=False, TIME_ZONE="Asia/Manila")
def test_removing_online_keeps_existing_online_counseling_fulfillable():
    sync_policy()
    counselor = make_user("online-counselor@example.edu", "COUNSELOR")
    student = make_user("online-student@example.edu", "STUDENT")
    admin = make_user("online-admin@example.edu", "IT_ADMIN")
    service = counseling(online=True)
    appointment = saved_appointment(student=student, counselor=counselor, service=service)

    update_service(
        service_id=service.pk,
        changes={"delivery_modes": ["IN_PERSON"]},
        context=context(admin),
        acknowledge_scheduling_consequences=True,
    )
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert appointment.delivery_mode == "ONLINE"

    # E-Counseling, Routine ensure, and the Encounter all trust the saved Appointment. With Daily
    # disabled the video session is unavailable, but the Appointment itself stays valid.
    student_workspace = get_student_workspace(student=student, appointment_id=appointment.pk)
    assert student_workspace["provider_readiness"]["join_state"] == "PROVIDER_DISABLED"
    assert get_counselor_workspace(counselor=counselor, appointment_id=appointment.pk)
    assert [item.pk for item in list_my_appointment_candidates(student)] == [appointment.pk]
    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    assert [item.pk for item in list_appointment_candidates(counselor=counselor).items] == [
        appointment.pk
    ]
    encounter = record_appointment_encounter(counselor, appointment)
    assert encounter.delivery_mode == "ONLINE"
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == encounter.pk  # ADR-087 linking intact.

    # No new ONLINE work can start: direct Counseling, direct Routine Interviews, or booking.
    with pytest.raises(CounselingNotPermitted, match="delivery mode"):
        record_direct(counselor, student, mode="ONLINE")
    with pytest.raises(RoutineInterviewAppointmentInvalid, match="delivery mode"):
        create_direct(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="ONLINE",
            idempotency_key="online-after-removal",
            request_fingerprint="c" * 64,
            context=context(counselor),
        )
    configure_availability(admin, counselor)
    with pytest.raises(AppointmentNotSchedulable, match="delivery mode"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="ONLINE",
            starts_at=future_local_start(),
            context=context(student),
        )


@pytest.mark.django_db
@override_settings(DAILY_ENABLED=False, TIME_ZONE="Asia/Manila")
def test_removed_provider_keeps_existing_appointment_but_gets_no_new_work():
    sync_policy()
    admin = make_user("removed-admin@example.edu", "IT_ADMIN")
    removed = make_user("removed-counselor@example.edu", "COUNSELOR")
    kept = make_user("removed-kept@example.edu", "COUNSELOR")
    student = make_user("removed-student@example.edu", "STUDENT")
    service = counseling(online=False)
    for counselor in (removed, kept):
        configure_availability(admin, counselor)
    current = saved_appointment(
        student=student, counselor=removed, service=service, mode="IN_PERSON"
    )
    upcoming = saved_appointment(
        student=student,
        counselor=removed,
        service=service,
        mode="IN_PERSON",
        minutes_from_now=int((future_local_start() - timezone.now()).total_seconds() // 60),
    )

    update_service(
        service_id=service.pk,
        changes={"provider_coverage": "SELECTED_COUNSELORS", "selected_counselor_ids": [kept.pk]},
        context=context(admin),
        acknowledge_scheduling_consequences=True,
    )
    for item in (current, upcoming):
        item.refresh_from_db()
        assert (item.status, item.provider_id) == (AppointmentStatus.SCHEDULED, removed.pk)

    # No new work for the removed Counselor.
    assert [
        item.user
        for item in list_eligible_counselors(
            student=student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    ] == [kept]
    with pytest.raises(CounselingNotPermitted):
        record_direct(removed, student)

    # The existing Appointment can still be fulfilled as booked.
    routine = ensure_for_appointment(
        student=student, appointment_id=current.pk, context=context(student)
    )
    encounter = record_appointment_encounter(removed, current)
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == encounter.pk

    # Changing the reservation follows current rules: it cannot be rescheduled with the removed
    # Counselor, but it can be reassigned to a qualified one (Counseling Appointments are
    # managed by their provider).
    with pytest.raises(AppointmentNotSchedulable, match="no longer eligible"):
        list_reschedule_slots(
            appointment_id=upcoming.pk,
            actor=removed,
            target_date=(future_local_start() + timedelta(days=7)).date(),
            administrative=True,
        )
    candidates = list_reassignment_candidates(appointment_id=upcoming.pk, actor=removed)
    assert [item.user for item in candidates] == [kept]
    reassigned = reassign_appointment(
        appointment_id=upcoming.pk,
        actor=removed,
        provider_id=kept.pk,
        reason="Provider no longer offers this Service.",
        context=context(removed),
    )
    assert reassigned.provider_id == kept.pk


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_disabling_booking_keeps_existing_appointments_fulfillable():
    sync_policy()
    admin = make_user("booking-admin@example.edu", "IT_ADMIN")
    counselor = make_user("booking-counselor@example.edu", "COUNSELOR")
    student = make_user("booking-student@example.edu", "STUDENT")
    service = counseling(online=False)
    configure_availability(admin, counselor)
    appointment = saved_appointment(
        student=student, counselor=counselor, service=service, mode="IN_PERSON"
    )

    update_service(
        service_id=service.pk,
        changes={"appointment_booking_enabled": False},
        context=context(admin),
        acknowledge_scheduling_consequences=True,
    )
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert appointment.cancellation_cutoff_minutes == 30

    with pytest.raises(AppointmentNotSchedulable, match="does not accept Appointments"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=future_local_start(),
            context=context(student),
        )
    assert record_appointment_encounter(counselor, appointment).appointment_id == appointment.pk


# Migration -------------------------------------------------------------------------------------

BEFORE = [("service_catalog", "0003_service_requires_current_inventory")]
LATEST = [("service_catalog", "0004_booking_capability_and_counselor_coverage")]


@pytest.mark.django_db(transaction=True)
def test_migration_maps_policy_normalizes_settings_and_keeps_legacy_roles():
    sync_policy()
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        apps = executor.loader.project_state(BEFORE).apps
        Legacy = apps.get_model("service_catalog", "Service")
        LegacyRole = apps.get_model("service_catalog", "ServiceProviderRole")
        HistoricalRole = apps.get_model("accounts", "Role")
        rows = {
            "NONE": Legacy.objects.create(
                code="MIG_NONE",
                name="None",
                appointment_policy="NONE",
                default_duration_minutes=45,
                cancellation_cutoff_minutes=20,
                requires_current_inventory=True,
            ),
            "OPTIONAL": Legacy.objects.create(
                code="MIG_OPTIONAL",
                name="Optional",
                appointment_policy="OPTIONAL",
                default_duration_minutes=50,
                cancellation_cutoff_minutes=25,
                requires_current_inventory=True,
            ),
            "REQUIRED": Legacy.objects.create(
                code="MIG_REQUIRED",
                name="Required",
                appointment_policy="REQUIRED",
                default_duration_minutes=55,
            ),
        }
        LegacyRole.objects.create(
            service=rows["REQUIRED"],
            role=HistoricalRole.objects.get(code="GUIDANCE_SERVICES_STAFF"),
        )

        MigrationExecutor(connection).migrate(LATEST)
        none = Service.objects.get(code="MIG_NONE")
        optional = Service.objects.get(code="MIG_OPTIONAL")
        required = Service.objects.get(code="MIG_REQUIRED")
        assert none.appointment_booking_enabled is False
        assert (
            none.default_appointment_duration_minutes,
            none.cancellation_cutoff_minutes,
            none.requires_current_inventory,
        ) == (None, None, False)
        assert optional.appointment_booking_enabled is True
        assert (
            optional.default_appointment_duration_minutes,
            optional.cancellation_cutoff_minutes,
            optional.requires_current_inventory,
        ) == (50, 25, True)
        assert required.appointment_booking_enabled is True
        assert required.default_appointment_duration_minutes == 55
        assert {none.provider_coverage, optional.provider_coverage, required.provider_coverage} == {
            "ALL_COUNSELORS"
        }
        assert required.provider_role_assignments.filter(
            role=Role.objects.get(code="GUIDANCE_SERVICES_STAFF")
        ).exists()
    finally:
        Service.objects.filter(code__startswith="MIG_").delete()
        MigrationExecutor(connection).migrate(LATEST)
