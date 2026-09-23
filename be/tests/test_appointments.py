from __future__ import annotations

import json
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.appointments.models import Appointment, AppointmentReferenceCounter
from compass.appointments.services import (
    AppointmentCancellationConflict,
    AppointmentCurrentStudentRequired,
    AppointmentDefaultProviderUnresolved,
    AppointmentListOrdering,
    AppointmentNotSchedulable,
    AppointmentTimeConflict,
    AppointmentTimeUnavailable,
    cancel_appointment,
    create_student_appointment,
    get_appointment_for_actor,
    list_eligible_counselors,
    list_managed_appointments,
    list_my_appointments,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StudentAffiliation,
)
from compass.service_catalog.models import Service, ServiceDeliveryMode
from compass.service_catalog.services import create_service, set_service_active, update_service


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str,
    *,
    active: bool = True,
    institutional_id: str | None = None,
    first_name: str | None = None,
    middle_name: str = "",
    last_name: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name or email.split("@")[0].title(),
        middle_name=middle_name,
        last_name=last_name or "User",
        institutional_id=institutional_id,
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def future_local_start(*, hour: int = 10, days: int = 7) -> datetime:
    zone = ZoneInfo("Asia/Manila")
    local_today = timezone.now().astimezone(zone).date()
    target = local_today + timedelta(days=days)
    while target.weekday() != 0:
        target += timedelta(days=1)
    return datetime.combine(target, time(hour), tzinfo=zone)


def weekly(start: time = time(8), end: time = time(17)) -> dict[str, object]:
    return {
        "weekday": "MONDAY",
        "start_time": start,
        "end_time": end,
        "mode_scope": "ALL",
    }


def active_service(
    actor: User,
    *,
    code: str = "APPOINTMENT_SERVICE",
    policy: str = "OPTIONAL",
    duration: int = 60,
    cutoff: int | None = 30,
    delivery_modes=None,
    provider_roles=None,
    requires_current_inventory: bool = False,
):
    service = create_service(
        code=code,
        name=code.replace("_", " ").title(),
        appointment_policy=policy,
        default_duration_minutes=duration,
        cancellation_cutoff_minutes=cutoff,
        requires_current_inventory=requires_current_inventory,
        delivery_modes=delivery_modes or ["IN_PERSON", "ONLINE"],
        provider_roles=provider_roles or ["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def configure_availability(actor: User, provider: User) -> None:
    replace_office_weekly(windows=[weekly()], context=context(actor))
    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly()],
        context=context(actor),
    )


def create_list_appointment(
    *,
    reference_code: str,
    student: User,
    provider: User,
    service: Service,
    starts_at: datetime,
    status: str = "SCHEDULED",
    delivery_mode: str = "IN_PERSON",
) -> Appointment:
    terminal = {}
    if status == "CANCELLED":
        terminal = {"cancelled_at": timezone.now(), "cancelled_by": student}
    elif status == "COMPLETED":
        terminal = {"completed_at": timezone.now(), "completed_by": provider}
    elif status == "NO_SHOW":
        terminal = {"no_show_at": timezone.now(), "no_show_by": provider}
    return Appointment.objects.create(
        reference_code=reference_code,
        student=student,
        provider=provider,
        service=service,
        delivery_mode=delivery_mode,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=60),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **terminal,
    )


def create_affiliation(student: User, counselor: User):
    campus = Campus.objects.create(code=f"C{Campus.objects.count() + 1}", name="Campus")
    college = College.objects.create(
        campus=campus,
        code=f"COL{College.objects.count() + 1}",
        name="College",
    )
    StudentAffiliation.objects.create(student=student, college=college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    return college


@pytest.mark.django_db
def test_appointment_capability_policy_preserves_business_authority_boundaries():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert not admin.has_capability("appointments.view_self")
    assert not admin.has_capability("appointments.manage_self")
    assert not admin.has_capability("appointments.manage")
    assert counselor.has_capability("appointments.view_self")
    assert not counselor.has_capability("appointments.manage_self")
    assert counselor.has_capability("appointments.manage")
    assert gss.has_capability("appointments.view_self")
    assert not gss.has_capability("appointments.manage_self")
    assert gss.has_capability("appointments.manage")
    assert student.has_capability("appointments.view_self")
    assert student.has_capability("appointments.manage_self")
    assert not student.has_capability("appointments.manage")
    assert head.has_capability("appointments.view_self")
    assert head.has_capability("appointments.manage")

    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="appointments.manage"),
        effect="REVOKE",
        reason="temporary separation",
    )
    assert not head.has_capability("appointments.manage")


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_creates_scheduled_reservation_with_snapshot_reference_and_audit():
    sync_policy()
    actor = make_user("catalog-admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, duration=60, cutoff=30)
    configure_availability(actor, provider)
    start = future_local_start()

    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )

    assert item.status == "SCHEDULED"
    assert item.reference_code.startswith(f"APT-{(start - timedelta(days=1)).year}-")
    assert item.student_id == student.pk
    assert item.provider_id == provider.pk
    assert item.service_id == service.pk
    assert item.starts_at.astimezone(ZoneInfo("Asia/Manila")) == start
    assert item.ends_at - item.starts_at == timedelta(minutes=60)
    assert item.cancellation_cutoff_minutes == 30
    assert item.created_by_id == student.pk
    scheduled = Notification.objects.filter(
        event_code="appointment.scheduled",
        source_type="appointment",
        source_id=item.pk,
    ).order_by("recipient_id")
    assert scheduled.count() == 2
    assert {row.recipient_id for row in scheduled} == {student.pk, provider.pk}
    assert {row.policy for row in scheduled} == {"MANDATORY_OPERATIONAL"}
    assert {row.target_type for row in scheduled} == {"APPOINTMENT"}
    assert {row.target_id for row in scheduled} == {item.pk}
    assert EmailDelivery.objects.filter(notification__in=scheduled).count() == 2
    event = AuditEvent.objects.get(action="appointment.created", target_id=str(item.pk))
    assert event.metadata == {
        "reference_code": item.reference_code,
        "service_id": str(service.pk),
        "provider_id": str(provider.pk),
        "delivery_mode": "IN_PERSON",
    }


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_service_policy_and_delivery_mode_gate_booking():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    configure_availability(actor, provider)
    start = future_local_start()

    none_service = create_service(
        code="NO_APPOINTMENT",
        name="No Appointment",
        appointment_policy="NONE",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    none_service = set_service_active(
        service_id=none_service.pk,
        is_active=True,
        context=context(actor),
    )
    with pytest.raises(AppointmentNotSchedulable, match="does not accept"):
        create_student_appointment(
            student=student,
            service_id=none_service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )

    service = active_service(
        actor,
        code="IN_PERSON_ONLY",
        delivery_modes=["IN_PERSON"],
    )
    with pytest.raises(AppointmentNotSchedulable, match="delivery mode"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="ONLINE",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )

    set_service_active(service_id=service.pk, is_active=False, context=context(actor))
    with pytest.raises(AppointmentNotSchedulable, match="inactive"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_default_counselor_uses_organization_resolver_and_unresolved_default_is_controlled():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    configure_availability(actor, provider)
    create_affiliation(student, provider)
    start = future_local_start()

    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=None,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    assert item.provider_id == provider.pk

    other_student = make_user("unrouted@example.edu", "STUDENT")
    with pytest.raises(AppointmentDefaultProviderUnresolved):
        create_student_appointment(
            student=other_student,
            service_id=service.pk,
            provider_id=None,
            delivery_mode="IN_PERSON",
            starts_at=start + timedelta(hours=2),
            context=context(other_student),
            now=start - timedelta(days=1),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_default_routing_does_not_silently_fallback_when_default_is_time_unavailable():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    default = make_user("default@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    service = active_service(actor)
    replace_office_weekly(windows=[weekly()], context=context(actor))
    replace_provider_weekly(
        provider_id=default.pk,
        windows=[weekly(start=time(8), end=time(9))],
        context=context(actor),
    )
    replace_provider_weekly(
        provider_id=head.pk,
        windows=[weekly()],
        context=context(actor),
    )
    create_affiliation(student, default)
    start = future_local_start(hour=10)

    with pytest.raises(AppointmentTimeUnavailable):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=None,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )
    assert not Appointment.objects.exists()


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_explicit_cross_scope_counselor_is_allowed_and_gss_is_not_student_selectable():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    default = make_user("default@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    service = active_service(
        actor,
        provider_roles=["COUNSELOR"],
    )
    replace_office_weekly(windows=[weekly()], context=context(actor))
    for provider in (default, other):
        replace_provider_weekly(
            provider_id=provider.pk,
            windows=[weekly()],
            context=context(actor),
        )
    create_affiliation(student, default)
    start = future_local_start()

    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=other.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    assert item.provider_id == other.pk

    with pytest.raises(AppointmentNotSchedulable, match="active Counselor"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=gss.pk,
            delivery_mode="IN_PERSON",
            starts_at=start + timedelta(hours=2),
            context=context(student),
            now=start - timedelta(days=1),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_rolls_back_domain_and_audit_when_mandatory_notification_persistence_fails(
    monkeypatch,
):
    sync_policy()
    actor = make_user("rollback-admin@example.edu", "IT_ADMIN")
    student = make_user("rollback-student@example.edu", "STUDENT")
    provider = make_user("rollback-provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    configure_availability(actor, provider)
    start = future_local_start()

    def fail_notification(**_kwargs):
        raise RuntimeError("synthetic notification persistence failure")

    monkeypatch.setattr(
        "compass.appointments.services.create_notification_for_event",
        fail_notification,
    )

    with pytest.raises(RuntimeError, match="synthetic notification persistence failure"):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )

    assert not Appointment.objects.filter(student=student, provider=provider).exists()
    assert not AuditEvent.objects.filter(
        action="appointment.created",
        actor_user=student,
    ).exists()
    assert not Notification.objects.filter(
        recipient__in=(student, provider),
        event_code="appointment.scheduled",
    ).exists()


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_full_interval_must_fit_base_availability():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, duration=60)
    replace_office_weekly(
        windows=[weekly(start=time(10), end=time(10, 30))],
        context=context(actor),
    )
    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly(start=time(10), end=time(10, 30))],
        context=context(actor),
    )
    start = future_local_start(hour=10)

    with pytest.raises(AppointmentTimeUnavailable):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
            now=start - timedelta(days=1),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_provider_and_student_overlaps_block_but_cancelled_rows_do_not():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student_a = make_user("a@example.edu", "STUDENT")
    student_b = make_user("b@example.edu", "STUDENT")
    provider_a = make_user("pa@example.edu", "COUNSELOR")
    provider_b = make_user("pb@example.edu", "COUNSELOR")
    service = active_service(actor)
    replace_office_weekly(windows=[weekly()], context=context(actor))
    for provider in (provider_a, provider_b):
        replace_provider_weekly(
            provider_id=provider.pk,
            windows=[weekly()],
            context=context(actor),
        )
    start = future_local_start()

    first = create_student_appointment(
        student=student_a,
        service_id=service.pk,
        provider_id=provider_a.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student_a),
        now=start - timedelta(days=1),
    )
    with pytest.raises(AppointmentTimeConflict, match="Counselor"):
        create_student_appointment(
            student=student_b,
            service_id=service.pk,
            provider_id=provider_a.pk,
            delivery_mode="IN_PERSON",
            starts_at=start + timedelta(minutes=30),
            context=context(student_b),
            now=start - timedelta(days=1),
        )
    with pytest.raises(AppointmentTimeConflict, match="Student"):
        create_student_appointment(
            student=student_a,
            service_id=service.pk,
            provider_id=provider_b.pk,
            delivery_mode="IN_PERSON",
            starts_at=start + timedelta(minutes=30),
            context=context(student_a),
            now=start - timedelta(days=1),
        )

    cancel_appointment(
        appointment_id=first.pk,
        actor=student_a,
        administrative=False,
        context=context(student_a),
        now=start - timedelta(hours=2),
    )
    replacement = create_student_appointment(
        student=student_b,
        service_id=service.pk,
        provider_id=provider_a.pk,
        delivery_mode="IN_PERSON",
        starts_at=start + timedelta(minutes=30),
        context=context(student_b),
        now=start - timedelta(days=1),
    )
    assert replacement.status == "SCHEDULED"


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_service_duration_and_cutoff_are_booking_time_snapshots():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student_a = make_user("a@example.edu", "STUDENT")
    student_b = make_user("b@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, duration=60, cutoff=30)
    configure_availability(actor, provider)
    start = future_local_start()

    first = create_student_appointment(
        student=student_a,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student_a),
        now=start - timedelta(days=1),
    )
    update_service(
        service_id=service.pk,
        changes={"default_duration_minutes": 45, "cancellation_cutoff_minutes": 60},
        context=context(actor),
    )
    second = create_student_appointment(
        student=student_b,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start + timedelta(hours=2),
        context=context(student_b),
        now=start - timedelta(days=1),
    )

    first.refresh_from_db()
    assert first.ends_at - first.starts_at == timedelta(minutes=60)
    assert first.cancellation_cutoff_minutes == 30
    assert second.ends_at - second.starts_at == timedelta(minutes=45)
    assert second.cancellation_cutoff_minutes == 60


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_cancellation_boundary_admin_bypass_and_repeat_are_safe():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    service = active_service(actor, cutoff=30)
    configure_availability(actor, provider)
    start = future_local_start()
    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )

    with pytest.raises(AppointmentCancellationConflict, match="cutoff"):
        cancel_appointment(
            appointment_id=item.pk,
            actor=student,
            administrative=False,
            context=context(student),
            now=start - timedelta(minutes=29),
        )
    cancelled = cancel_appointment(
        appointment_id=item.pk,
        actor=head,
        administrative=True,
        context=context(head),
        now=start - timedelta(minutes=1),
    )
    assert cancelled.status == "CANCELLED"
    cancelled_notifications = Notification.objects.filter(
        event_code="appointment.cancelled",
        source_type="appointment",
        source_id=item.pk,
    )
    assert cancelled_notifications.count() == 2
    assert {row.recipient_id for row in cancelled_notifications} == {student.pk, provider.pk}
    assert EmailDelivery.objects.filter(notification__in=cancelled_notifications).count() == 2
    event_count = AuditEvent.objects.filter(action="appointment.cancelled").count()
    notification_count = cancelled_notifications.count()
    repeated = cancel_appointment(
        appointment_id=item.pk,
        actor=head,
        administrative=True,
        context=context(head),
        now=start + timedelta(hours=1),
    )
    assert repeated.status == "CANCELLED"
    assert AuditEvent.objects.filter(action="appointment.cancelled").count() == event_count
    assert (
        Notification.objects.filter(
            event_code="appointment.cancelled",
            source_type="appointment",
            source_id=item.pk,
        ).count()
        == notification_count
    )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_exact_self_cancellation_cutoff_boundary_is_allowed():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, cutoff=30)
    configure_availability(actor, provider)
    start = future_local_start()
    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    cancelled = cancel_appointment(
        appointment_id=item.pk,
        actor=student,
        administrative=False,
        context=context(student),
        now=start - timedelta(minutes=30),
    )
    assert cancelled.status == "CANCELLED"
    self_cancel_notifications = Notification.objects.filter(
        event_code="appointment.cancelled",
        source_type="appointment",
        source_id=item.pk,
    )
    assert self_cancel_notifications.count() == 2
    assert {row.recipient_id for row in self_cancel_notifications} == {student.pk, provider.pk}


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_reference_counter_uses_local_booking_year_and_rolls_back_with_failed_transaction():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    configure_availability(actor, provider)

    booking_now = datetime(2026, 12, 31, 23, 30, tzinfo=ZoneInfo("Asia/Manila"))
    scheduled_start = datetime(2027, 1, 4, 10, 0, tzinfo=ZoneInfo("Asia/Manila"))
    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=scheduled_start,
        context=context(student),
        now=booking_now,
    )
    assert item.reference_code == "APT-2026-000001"
    assert AppointmentReferenceCounter.objects.get(year=2026).next_value == 2


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_eligible_counselors_are_cross_scope_bounded_and_default_is_marked():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    default = make_user("default@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    make_user("inactive@example.edu", "COUNSELOR", active=False)
    service = active_service(actor)
    create_affiliation(student, default)

    rows = list_eligible_counselors(
        student=student,
        service_id=service.pk,
        delivery_mode="IN_PERSON",
    )
    by_id = {row.user.pk: row for row in rows}
    assert default.pk in by_id
    assert other.pk in by_id
    assert by_id[default.pk].is_default
    assert not by_id[other.pk].is_default
    assert all(row.user.is_active and row.user.role.code == "COUNSELOR" for row in rows)


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_student_booking_api_requires_idempotency_and_replays_same_success():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    configure_availability(actor, provider)
    client = auth_client(student)
    start = future_local_start()
    payload = {
        "service_id": str(service.pk),
        "provider_id": str(provider.pk),
        "delivery_mode": "IN_PERSON",
        "starts_at": start.isoformat(),
    }
    headers = csrf(client)
    key = f"booking-{uuid.uuid4()}"

    missing = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload),
        content_type="application/json",
        **headers,
    )
    assert missing.status_code == 422

    first = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert first.status_code == 201
    replay = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert replay.status_code == 201
    assert replay.content == first.content
    assert Appointment.objects.count() == 1

    conflict_payload = {**payload, "starts_at": (start + timedelta(hours=2)).isoformat()}
    conflict = client.post(
        "/api/v1/appointments",
        data=json.dumps(conflict_payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_conflict"


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_api_failed_validation_releases_idempotency_key_for_retry():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    client = auth_client(student)
    start = future_local_start()
    payload = {
        "service_id": str(service.pk),
        "provider_id": str(provider.pk),
        "delivery_mode": "IN_PERSON",
        "starts_at": start.isoformat(),
    }
    headers = csrf(client)
    key = f"retry-{uuid.uuid4()}"

    failed = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "appointment_time_unavailable"

    configure_availability(actor, provider)
    retried = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert retried.status_code == 201


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_self_provider_manager_views_and_cancel_authorization_are_resource_scoped():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    outsider = make_user("outsider@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    service = active_service(actor)
    configure_availability(actor, provider)
    start = future_local_start()
    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )

    student_client = auth_client(student)
    provider_client = auth_client(provider)
    outsider_client = auth_client(outsider)
    head_client = auth_client(head, recent_mfa=True)
    assert student_client.get("/api/v1/appointments/me").status_code == 200
    assert provider_client.get("/api/v1/appointments/me").status_code == 200
    assert student_client.get(f"/api/v1/appointments/{item.pk}").status_code == 200
    assert provider_client.get(f"/api/v1/appointments/{item.pk}").status_code == 200
    assert outsider_client.get(f"/api/v1/appointments/{item.pk}").status_code == 404
    assert head_client.get("/api/v1/appointments").status_code == 200

    stale_head = auth_client(head, recent_mfa=False)
    denied = stale_head.post(
        f"/api/v1/appointments/{item.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(stale_head),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    cancelled = head_client.post(
        f"/api/v1/appointments/{item.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.django_db
def test_database_constraints_preserve_local_appointment_invariants():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = create_service(
        code="CONSTRAINT_SERVICE",
        name="Constraint Service",
        appointment_policy="NONE",
        context=context(student),
    )
    now = timezone.now()
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Appointment.objects.create(
                reference_code="APT-2099-999999",
                student=student,
                provider=provider,
                service=service,
                delivery_mode="IN_PERSON",
                starts_at=now,
                ends_at=now,
            )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
@pytest.mark.parametrize(
    "status",
    [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER],
)
def test_non_current_student_cannot_book_but_can_read_and_cancel_existing(status):
    sync_policy()
    admin = make_user(f"booking-admin-{status.lower()}@example.edu", "IT_ADMIN")
    student = make_user(f"booking-student-{status.lower()}@example.edu", "STUDENT")
    counselor = make_user(f"booking-counselor-{status.lower()}@example.edu", "COUNSELOR")
    service = active_service(admin)
    configure_availability(admin, counselor)
    start = future_local_start()

    existing = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    student.student_lifecycle_status = status
    student.save(update_fields=["student_lifecycle_status", "updated_at"])

    with pytest.raises(AppointmentCurrentStudentRequired):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=start + timedelta(hours=2),
            context=context(student),
            now=start - timedelta(days=1),
        )
    with pytest.raises(AppointmentCurrentStudentRequired):
        list_eligible_counselors(
            student=student,
            service_id=service.pk,
            delivery_mode="IN_PERSON",
        )

    assert existing.pk in {row.pk for row in list_my_appointments(actor=student).items}
    assert get_appointment_for_actor(appointment_id=existing.pk, actor=student).pk == existing.pk
    cancelled = cancel_appointment(
        appointment_id=existing.pk,
        actor=student,
        administrative=False,
        context=context(student),
    )
    assert cancelled.status == "CANCELLED"


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_appointment_responses_expose_narrow_student_projection_consistently():
    sync_policy()
    admin = make_user("projection-admin@example.edu", "IT_ADMIN")
    student = make_user(
        "reynan@example.edu",
        "STUDENT",
        institutional_id="2023-12345",
        first_name="Reynan",
        middle_name="Santos",
        last_name="Tolentino",
    )
    student_without_id = make_user(
        "no-id@example.edu",
        "STUDENT",
        first_name="No",
        last_name="Identifier",
    )
    provider = make_user("projection-provider@example.edu", "COUNSELOR")
    head = make_user("projection-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    service = active_service(admin, code="PROJECTION_SERVICE")
    configure_availability(admin, provider)
    start = future_local_start()

    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    second = create_student_appointment(
        student=student_without_id,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start + timedelta(hours=2),
        context=context(student_without_id),
        now=start - timedelta(days=1),
    )
    student.is_active = False
    student.save(update_fields=["is_active", "updated_at"])

    expected = {
        "id": str(student.pk),
        "institutional_id": "2023-12345",
        "display_name": "Reynan Santos Tolentino",
    }
    provider_rows = auth_client(provider).get("/api/v1/appointments/me").json()["items"]
    managed_rows = auth_client(head).get("/api/v1/appointments").json()["items"]
    detail = auth_client(head).get(f"/api/v1/appointments/{item.pk}").json()

    provider_row = next(row for row in provider_rows if row["id"] == str(item.pk))
    managed_row = next(row for row in managed_rows if row["id"] == str(item.pk))
    for row in (provider_row, managed_row, detail):
        assert row["student_id"] == str(student.pk)
        assert row["student"] == expected
        assert set(row["student"]) == {"id", "institutional_id", "display_name"}

    second_row = next(row for row in managed_rows if row["id"] == str(second.pk))
    assert second_row["student"]["institutional_id"] is None


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_managed_appointment_search_is_student_aware_composable_and_scope_preserving():
    sync_policy()
    admin = make_user("search-admin@example.edu", "IT_ADMIN")
    student = make_user(
        "search-target@example.edu",
        "STUDENT",
        institutional_id="2023-54321",
        first_name="Reynan",
        middle_name="Santos",
        last_name="Tolentino",
    )
    outside_student = make_user(
        "search-outside@example.edu",
        "STUDENT",
        institutional_id="2024-99999",
        first_name="Reynan",
        middle_name="Outside",
        last_name="Scope",
    )
    provider = make_user("search-provider@example.edu", "COUNSELOR")
    outside_provider = make_user("search-outside-provider@example.edu", "COUNSELOR")
    head = make_user("search-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    service = active_service(admin, code="SEARCH_SERVICE")
    configure_availability(admin, provider)
    configure_availability(admin, outside_provider)
    start = future_local_start()

    target = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(student),
        now=start - timedelta(days=1),
    )
    outside = create_student_appointment(
        student=outside_student,
        service_id=service.pk,
        provider_id=outside_provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=context(outside_student),
        now=start - timedelta(days=1),
    )

    head_client = auth_client(head)
    for search in (
        target.reference_code,
        "2023-54321",
        "Reynan",
        "Santos",
        "Tolentino",
        "Reynan Tolentino",
    ):
        rows = head_client.get("/api/v1/appointments", {"search": search}).json()["items"]
        assert str(target.pk) in {row["id"] for row in rows}

    unmatched = head_client.get("/api/v1/appointments", {"search": "No Such Student"})
    assert unmatched.status_code == 200
    assert unmatched.json()["items"] == []

    cancel_appointment(
        appointment_id=target.pk,
        actor=head,
        administrative=True,
        context=context(head),
    )
    composed = head_client.get(
        "/api/v1/appointments",
        {"search": "Tolentino", "status": "SCHEDULED"},
    )
    assert composed.status_code == 200
    assert composed.json()["items"] == []

    first_page = head_client.get(
        "/api/v1/appointments",
        {"search": "Reynan", "page": 1, "page_size": 1},
    ).json()
    assert len(first_page["items"]) == 1
    assert first_page["has_next"] is True

    provider_client = auth_client(provider)
    scoped = provider_client.get("/api/v1/appointments", {"search": "Outside Scope"})
    assert scoped.status_code == 200
    assert str(outside.pk) not in {row["id"] for row in scoped.json()["items"]}


@pytest.mark.django_db
def test_booking_service_discovery_is_appointment_owned_filtered_and_paginated():
    sync_policy()
    admin = make_user("booking-services-admin@example.edu", "IT_ADMIN")
    student = make_user("booking-services-student@example.edu", "STUDENT")
    counselor = make_user("booking-services-counselor@example.edu", "COUNSELOR")

    services_view = Capability.objects.filter(code="services.view").first()
    if services_view is not None:
        UserCapabilityOverride.objects.update_or_create(
            user=student,
            capability=services_view,
            defaults={"effect": "REVOKE", "reason": "Appointment discovery isolation test"},
        )
    assert not student.has_capability("services.view")
    assert not student.has_capability("accounts.manage")
    assert not student.has_capability("organization.manage")

    optional = active_service(
        admin,
        code="BOOK_OPTIONAL",
        policy="OPTIONAL",
        delivery_modes=["IN_PERSON"],
    )
    required = active_service(
        admin,
        code="BOOK_REQUIRED",
        policy="REQUIRED",
        delivery_modes=["ONLINE"],
        requires_current_inventory=True,
    )
    active_service(
        admin,
        code="BOOK_NONE",
        policy="NONE",
        cutoff=None,
        delivery_modes=["IN_PERSON"],
    )
    inactive = create_service(
        code="BOOK_INACTIVE",
        name="Book Inactive",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    invalid_provider = Service.objects.create(
        code="BOOK_NO_COUNSELOR",
        name="Book No Counselor",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        is_active=True,
    )
    ServiceDeliveryMode.objects.create(service=invalid_provider, mode="IN_PERSON")

    anonymous = Client().get("/api/v1/appointments/booking/services")
    assert anonymous.status_code == 401
    denied = auth_client(counselor).get("/api/v1/appointments/booking/services")
    assert denied.status_code == 403

    client = auth_client(student)
    response = client.get("/api/v1/appointments/booking/services")
    assert response.status_code == 200
    payload = response.json()
    by_code = {row["code"]: row for row in payload["items"]}
    assert set(by_code) == {"BOOK_OPTIONAL", "BOOK_REQUIRED"}
    assert optional.code in by_code
    assert required.code in by_code
    assert inactive.code not in by_code
    assert "BOOK_NONE" not in by_code
    assert invalid_provider.code not in by_code

    required_row = by_code["BOOK_REQUIRED"]
    assert required_row["requires_current_inventory"] is True
    assert set(required_row) == {
        "id",
        "code",
        "name",
        "description",
        "appointment_policy",
        "delivery_modes",
        "default_duration_minutes",
        "cancellation_cutoff_minutes",
        "requires_current_inventory",
    }

    searched = client.get(
        "/api/v1/appointments/booking/services",
        {"search": "required"},
    ).json()
    assert [row["code"] for row in searched["items"]] == ["BOOK_REQUIRED"]

    paged = client.get(
        "/api/v1/appointments/booking/services",
        {"page": 1, "page_size": 1},
    ).json()
    assert len(paged["items"]) == 1
    assert paged["page"] == 1
    assert paged["page_size"] == 1
    assert paged["has_next"] is True


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_self_appointment_list_ordering_defaults_filters_and_paginates_before_slicing():
    sync_policy()
    admin = make_user("ordering-admin@example.edu", "IT_ADMIN")
    student = make_user("ordering-student@example.edu", "STUDENT")
    provider = make_user("ordering-provider@example.edu", "COUNSELOR")
    service = active_service(admin, code="ORDERING_SELF_SERVICE")
    start = future_local_start(hour=8)

    appointments = [
        create_list_appointment(
            reference_code="APT-ORDER-003",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=3),
        ),
        create_list_appointment(
            reference_code="APT-ORDER-001",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=1),
        ),
        create_list_appointment(
            reference_code="APT-ORDER-004",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=4),
        ),
        create_list_appointment(
            reference_code="APT-ORDER-002",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=2),
        ),
    ]

    expected_asc = [str(item.pk) for item in sorted(appointments, key=lambda row: row.starts_at)]
    expected_desc = list(reversed(expected_asc))

    student_client = auth_client(student)
    default_rows = student_client.get("/api/v1/appointments/me").json()["items"]
    explicit_desc = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_DESC"},
    ).json()["items"]
    asc_rows = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_ASC"},
    ).json()["items"]
    assert [row["id"] for row in default_rows] == expected_desc
    assert [row["id"] for row in explicit_desc] == expected_desc
    assert [row["id"] for row in asc_rows] == expected_asc

    provider_rows = (
        auth_client(provider)
        .get(
            "/api/v1/appointments/me",
            {"ordering": "START_ASC"},
        )
        .json()["items"]
    )
    assert [row["id"] for row in provider_rows] == expected_asc

    first_page = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_ASC", "page": 1, "page_size": 2},
    ).json()
    second_page = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_ASC", "page": 2, "page_size": 2},
    ).json()
    assert [row["id"] for row in first_page["items"]] == expected_asc[:2]
    assert [row["id"] for row in second_page["items"]] == expected_asc[2:]
    assert first_page["has_next"] is True
    assert second_page["has_next"] is False

    desc_first = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_DESC", "page": 1, "page_size": 2},
    ).json()
    desc_second = student_client.get(
        "/api/v1/appointments/me",
        {"ordering": "START_DESC", "page": 2, "page_size": 2},
    ).json()
    assert [row["id"] for row in desc_first["items"]] == expected_desc[:2]
    assert [row["id"] for row in desc_second["items"]] == expected_desc[2:]

    filtered = student_client.get(
        "/api/v1/appointments/me",
        {
            "status": "SCHEDULED",
            "from_date": start.date().isoformat(),
            "to_date": start.date().isoformat(),
            "ordering": "START_ASC",
        },
    ).json()
    assert [row["id"] for row in filtered["items"]] == expected_asc

    invalid = student_client.get("/api/v1/appointments/me", {"ordering": "RANDOM"})
    assert invalid.status_code == 422


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_managed_appointment_ordering_composes_with_search_filters_and_scope():
    sync_policy()
    admin = make_user("ordering-managed-admin@example.edu", "IT_ADMIN")
    student = make_user(
        "ordering-managed-student@example.edu",
        "STUDENT",
        institutional_id="2026-ORDER",
        first_name="Queue",
        last_name="Student",
    )
    outside_student = make_user(
        "ordering-outside-student@example.edu",
        "STUDENT",
        first_name="Queue",
        last_name="Outside",
    )
    provider = make_user("ordering-managed-provider@example.edu", "COUNSELOR")
    outside_provider = make_user("ordering-outside-provider@example.edu", "COUNSELOR")
    service = active_service(admin, code="ORDERING_MANAGED_SERVICE")
    start = future_local_start(hour=8)

    visible = [
        create_list_appointment(
            reference_code="APT-MANAGED-003",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=3),
            delivery_mode="ONLINE",
        ),
        create_list_appointment(
            reference_code="APT-MANAGED-001",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=1),
            delivery_mode="ONLINE",
        ),
        create_list_appointment(
            reference_code="APT-MANAGED-004",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=4),
            delivery_mode="ONLINE",
        ),
        create_list_appointment(
            reference_code="APT-MANAGED-002",
            student=student,
            provider=provider,
            service=service,
            starts_at=start + timedelta(hours=2),
            delivery_mode="ONLINE",
        ),
    ]
    outside = create_list_appointment(
        reference_code="APT-MANAGED-OUTSIDE",
        student=outside_student,
        provider=outside_provider,
        service=service,
        starts_at=start + timedelta(minutes=30),
        delivery_mode="ONLINE",
    )

    expected_asc = [str(item.pk) for item in sorted(visible, key=lambda row: row.starts_at)]
    expected_desc = list(reversed(expected_asc))
    client = auth_client(provider)

    for ordering, expected in (
        ("START_ASC", expected_asc),
        ("START_DESC", expected_desc),
    ):
        page_one = client.get(
            "/api/v1/appointments",
            {
                "search": "Queue Student",
                "status": "SCHEDULED",
                "delivery_mode": "ONLINE",
                "from_date": start.date().isoformat(),
                "to_date": start.date().isoformat(),
                "ordering": ordering,
                "page": 1,
                "page_size": 2,
            },
        ).json()
        page_two = client.get(
            "/api/v1/appointments",
            {
                "search": "Queue Student",
                "status": "SCHEDULED",
                "delivery_mode": "ONLINE",
                "from_date": start.date().isoformat(),
                "to_date": start.date().isoformat(),
                "ordering": ordering,
                "page": 2,
                "page_size": 2,
            },
        ).json()
        rows = page_one["items"] + page_two["items"]
        assert [row["id"] for row in rows] == expected
        assert str(outside.pk) not in {row["id"] for row in rows}
        assert page_one["has_next"] is True
        assert page_two["has_next"] is False

    default_rows = client.get(
        "/api/v1/appointments",
        {"search": "Queue Student"},
    ).json()["items"]
    assert [row["id"] for row in default_rows] == expected_desc

    direct = list_managed_appointments(
        actor=provider,
        search="2026-ORDER",
        ordering=AppointmentListOrdering.START_ASC,
    )
    assert [row.pk for row in direct.items] == [
        item.pk for item in sorted(visible, key=lambda row: row.starts_at)
    ]

    invalid = client.get("/api/v1/appointments", {"ordering": "RANDOM"})
    assert invalid.status_code == 422
