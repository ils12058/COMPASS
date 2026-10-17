"""Comprehensive unit, authorization, conflict, and concurrency tests for Fixed Slots (SVC-2)."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta

import pytest
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.appointments.models import AppointmentStatus
from compass.audit.actions import (
    SERVICE_SLOT_CREATED,
    SERVICE_SLOT_UPDATED,
    SERVICE_SLOT_WITHDRAWN,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.common.institutional_time import institution_zone
from compass.notifications.models import Notification
from compass.service_catalog.fixed_slots_services import (
    CounselorNotQualifiedForService,
    DeliveryModeNotSupported,
    SlotAlreadyBookedError,
    SlotCannotBeModifiedError,
    SlotConflictError,
    SlotTimeInvalid,
    book_fixed_slot,
    create_fixed_slot,
    withdraw_fixed_slot,
    is_slot_booked,
    list_student_bookable_slots,
    update_fixed_slot,
)
from compass.service_catalog.models import (
    BookingPathwayCode,
    ServiceAppointmentSlot,
    ServiceAppointmentSlotBooking,
)
from compass.service_catalog.services import (
    create_service,
    set_service_active,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str,
    *,
    active: bool = True,
    institutional_id: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-15chars",
        role=Role.objects.get(code=role),
        first_name=first_name or email.split("@")[0].title(),
        last_name=last_name or "User",
        institutional_id=institutional_id or f"ID-{email.split('@')[0]}",
        is_active=active,
    )


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
    zone = institution_zone()
    local_today = timezone.now().astimezone(zone).date()
    target = local_today + timedelta(days=days)
    while target.weekday() != 0:  # Monday
        target += timedelta(days=1)
    return datetime.combine(target, time(hour), tzinfo=zone)


def weekly_schedule(start: time = time(8), end: time = time(17)) -> dict[str, object]:
    return {
        "weekday": "MONDAY",
        "start_time": start,
        "end_time": end,
        "mode_scope": "ALL",
    }


def configure_availability(actor: User, provider: User) -> None:
    ctx = AuditContext.user(actor)
    replace_office_weekly(windows=[weekly_schedule()], context=ctx)
    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly_schedule()],
        context=ctx,
    )


@pytest.fixture
def env():
    sync_policy()
    admin = make_user("admin-slots@example.edu", "IT_ADMIN")
    counselor = make_user("counselor-slots@example.edu", "COUNSELOR")
    counselor_b = make_user("counselor-b-slots@example.edu", "COUNSELOR")
    gss = make_user("gss-slots@example.edu", "GUIDANCE_SERVICES_STAFF")
    student_1 = make_user("student1-slots@example.edu", "STUDENT")
    student_2 = make_user("student2-slots@example.edu", "STUDENT")

    configure_availability(admin, counselor)
    configure_availability(admin, counselor_b)

    service = create_service(
        code="FIXED_CAREER_SVC",
        name="Career Guidance Consultation",
        appointment_booking_enabled=True,
        booking_pathways=[
            BookingPathwayCode.FLEXIBLE_APPOINTMENT,
            BookingPathwayCode.FIXED_DATE_SLOT,
        ],
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON", "ONLINE"],
        context=AuditContext.user(admin),
    )
    service = set_service_active(
        service_id=service.pk, is_active=True, context=AuditContext.user(admin)
    )

    return {
        "admin": admin,
        "counselor": counselor,
        "counselor_b": counselor_b,
        "gss": gss,
        "student_1": student_1,
        "student_2": student_2,
        "service": service,
    }


@pytest.mark.django_db
def test_create_fixed_slot_validation_and_audit(env):
    counselor = env["counselor"]
    service = env["service"]
    ctx = AuditContext.user(counselor)

    start_time = future_local_start(hour=9)
    end_time = start_time + timedelta(minutes=60)

    # Valid creation
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start_time,
        ends_at=end_time,
        is_published=True,
        actor=counselor,
        context=ctx,
    )

    assert slot.service_id == service.pk
    assert slot.provider_id == counselor.pk
    assert slot.delivery_mode == "IN_PERSON"
    assert slot.starts_at == start_time
    assert slot.ends_at == end_time
    assert slot.is_published is True
    assert not is_slot_booked(slot)

    # Verify audit event
    assert AuditEvent.objects.filter(
        action=SERVICE_SLOT_CREATED,
        target_id=slot.pk,
    ).exists()

    # Past time validation
    past_time = timezone.now() - timedelta(hours=1)
    with pytest.raises(SlotTimeInvalid):
        create_fixed_slot(
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=past_time,
            ends_at=past_time + timedelta(minutes=60),
            actor=counselor,
            context=ctx,
        )

    # Overlapping slot for same counselor
    with pytest.raises(SlotConflictError, match="another fixed slot scheduled"):
        create_fixed_slot(
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=start_time,
            ends_at=end_time,
            actor=counselor,
            context=ctx,
        )


@pytest.mark.django_db
def test_create_fixed_slot_unqualified_counselor_and_unsupported_mode(env):
    admin = env["admin"]
    counselor = env["counselor"]
    counselor_b = env["counselor_b"]
    ctx = AuditContext.user(admin)

    # Create service with SELECTED_COUNSELORS where only counselor is selected
    service_sel = create_service(
        code="SELECTED_COUNSELOR_SVC",
        name="Specialized Consultation",
        appointment_booking_enabled=True,
        booking_pathways=[
            BookingPathwayCode.FLEXIBLE_APPOINTMENT,
            BookingPathwayCode.FIXED_DATE_SLOT,
        ],
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON"],
        provider_coverage="SELECTED_COUNSELORS",
        selected_counselor_ids=[counselor.pk],
        context=ctx,
    )
    service_sel = set_service_active(service_id=service_sel.pk, is_active=True, context=ctx)

    start = future_local_start(hour=14)

    # Counselor B is not qualified for this service
    with pytest.raises(CounselorNotQualifiedForService):
        create_fixed_slot(
            service_id=service_sel.pk,
            provider_id=counselor_b.pk,
            delivery_mode="IN_PERSON",
            starts_at=start,
            ends_at=start + timedelta(minutes=60),
            actor=counselor_b,
            context=AuditContext.user(counselor_b),
        )

    # Delivery mode ONLINE is not supported by service_sel
    with pytest.raises(DeliveryModeNotSupported):
        create_fixed_slot(
            service_id=service_sel.pk,
            provider_id=counselor.pk,
            delivery_mode="ONLINE",
            starts_at=start,
            ends_at=start + timedelta(minutes=60),
            actor=counselor,
            context=AuditContext.user(counselor),
        )


@pytest.mark.django_db
def test_update_and_withdraw_slot_protection(env):
    counselor = env["counselor"]
    service = env["service"]
    student = env["student_1"]
    ctx = AuditContext.user(counselor)

    start = future_local_start(hour=11)
    end = start + timedelta(minutes=60)

    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        ends_at=end,
        is_published=True,
        actor=counselor,
        context=ctx,
    )

    # Update unbooked slot publication status and delivery mode
    updated = update_fixed_slot(
        slot_id=slot.pk,
        actor=counselor,
        context=ctx,
        delivery_mode="ONLINE",
        is_published=False,
    )
    assert updated.delivery_mode == "ONLINE"
    assert updated.is_published is False
    assert AuditEvent.objects.filter(action=SERVICE_SLOT_UPDATED, target_id=slot.pk).exists()

    # Re-publish and book slot
    update_fixed_slot(slot_id=slot.pk, actor=counselor, context=ctx, is_published=True)
    appt = book_fixed_slot(slot_id=slot.pk, student=student, context=AuditContext.user(student))
    assert appt.status == AppointmentStatus.SCHEDULED

    # Verify slot is booked
    slot.refresh_from_db()
    assert is_slot_booked(slot)

    # Attempt to change schedule or provider on booked slot must fail
    with pytest.raises(SlotCannotBeModifiedError):
        update_fixed_slot(
            slot_id=slot.pk,
            actor=counselor,
            context=ctx,
            starts_at=future_local_start(hour=13),
        )

    # Withdrawal removes the slot from booking while retaining its Appointment link.
    withdrawn = withdraw_fixed_slot(slot_id=slot.pk, actor=counselor, context=ctx)
    assert withdrawn.pk == slot.pk
    assert withdrawn.withdrawn_at is not None
    assert withdrawn.current_appointment_id == appt.pk
    assert ServiceAppointmentSlotBooking.objects.filter(
        slot=slot, appointment=appt
    ).exists()

    # Unbooked slots are withdrawn in place and repeated requests do not duplicate audits.
    other_start = future_local_start(hour=15)
    unbooked_slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=other_start,
        ends_at=other_start + timedelta(minutes=60),
        actor=counselor,
        context=ctx,
    )
    withdraw_fixed_slot(slot_id=unbooked_slot.pk, actor=counselor, context=ctx)
    withdraw_fixed_slot(slot_id=unbooked_slot.pk, actor=counselor, context=ctx)
    assert ServiceAppointmentSlot.objects.filter(pk=unbooked_slot.pk).exists()
    assert ServiceAppointmentSlot.objects.get(pk=unbooked_slot.pk).withdrawn_at is not None
    assert AuditEvent.objects.filter(
        action=SERVICE_SLOT_WITHDRAWN, target_id=unbooked_slot.pk
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_fixed_slot_concurrent_withdrawal_records_one_transition(env):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    counselor = env["counselor"]
    service = env["service"]
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=future_local_start(hour=16),
        actor=counselor,
        context=AuditContext.user(counselor),
    )

    def withdraw() -> datetime:
        try:
            result = withdraw_fixed_slot(
                slot_id=slot.pk,
                actor=counselor,
                context=AuditContext.user(counselor),
            )
            return result.withdrawn_at
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        transition_times = list(pool.map(lambda _: withdraw(), range(2)))

    assert transition_times[0] == transition_times[1]
    assert AuditEvent.objects.filter(
        action=SERVICE_SLOT_WITHDRAWN,
        target_id=slot.pk,
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_prevents_physical_deletion_of_unbooked_fixed_slot(env):
    from django.db import DatabaseError, connection, transaction

    if connection.vendor != "postgresql":
        pytest.skip("The direct-delete guard is PostgreSQL-specific.")

    counselor = env["counselor"]
    service = env["service"]
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=future_local_start(hour=15),
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    table = connection.ops.quote_name(ServiceAppointmentSlot._meta.db_table)
    primary_key = connection.ops.quote_name(ServiceAppointmentSlot._meta.pk.column)

    with pytest.raises(DatabaseError, match="operational records and cannot be deleted"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE {primary_key} = %s", [slot.pk])

    assert ServiceAppointmentSlot.objects.filter(pk=slot.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_postgresql_records_legacy_slot_pointer_changes_in_booking_history(env):
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("The rolling-deployment compatibility trigger is PostgreSQL-specific.")

    counselor = env["counselor"]
    service = env["service"]
    target_slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=future_local_start(hour=9),
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    source_slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=future_local_start(hour=11),
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    appointment = book_fixed_slot(
        slot_id=source_slot.pk,
        student=env["student_1"],
        context=AuditContext.user(env["student_1"]),
    )

    # Simulate a still-running prior application writing only current_appointment.
    ServiceAppointmentSlot.objects.filter(pk=target_slot.pk).update(
        current_appointment_id=appointment.pk
    )

    assert ServiceAppointmentSlotBooking.objects.filter(
        slot=target_slot,
        appointment=appointment,
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW],
)
def test_fixed_slot_preserves_booking_provenance_after_appointment_lifecycle(env, status):
    counselor = env["counselor"]
    student = env["student_1"]
    service = env["service"]
    ctx = AuditContext.user(counselor)
    starts_at = future_local_start(hour=12)
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        actor=counselor,
        context=ctx,
    )
    appointment = book_fixed_slot(
        slot_id=slot.pk,
        student=student,
        context=AuditContext.user(student),
    )
    appointment.status = status
    appointment.save(update_fields=["status", "updated_at"])

    slot.refresh_from_db()
    assert slot.current_appointment_id == appointment.pk
    assert ServiceAppointmentSlotBooking.objects.filter(
        slot=slot, appointment=appointment
    ).exists()
    with pytest.raises(SlotCannotBeModifiedError):
        update_fixed_slot(
            slot_id=slot.pk,
            actor=counselor,
            context=ctx,
            starts_at=starts_at + timedelta(hours=2),
        )
    with pytest.raises(ProtectedError):
        slot.delete()
    with pytest.raises(ProtectedError):
        appointment.delete()


@pytest.mark.django_db
def test_student_bookable_slots_discovery(env):
    counselor = env["counselor"]
    service = env["service"]
    student = env["student_1"]
    ctx = AuditContext.user(counselor)

    start_1 = future_local_start(hour=9)
    start_2 = future_local_start(hour=10)
    start_3 = future_local_start(hour=11)

    slot_1 = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start_1,
        actor=counselor,
        context=ctx,
    )
    slot_2 = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="ONLINE",
        starts_at=start_2,
        is_published=False,  # Unpublished
        actor=counselor,
        context=ctx,
    )
    slot_3 = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start_3,
        actor=counselor,
        context=ctx,
    )

    # Student lists available slots
    available = list_student_bookable_slots(
        service_id=service.pk,
        student=student,
    )
    # Only slot_1 and slot_3 should be listed (slot_2 is unpublished)
    slot_ids = [s.pk for s in available]
    assert slot_1.pk in slot_ids
    assert slot_3.pk in slot_ids
    assert slot_2.pk not in slot_ids

    # Book slot_1
    book_fixed_slot(slot_id=slot_1.pk, student=student, context=AuditContext.user(student))

    # After booking, slot_1 must not be listed
    available_after = list_student_bookable_slots(
        service_id=service.pk,
        student=student,
    )
    slot_ids_after = [s.pk for s in available_after]
    assert slot_1.pk not in slot_ids_after
    assert slot_3.pk in slot_ids_after


@pytest.mark.django_db
def test_student_booking_concurrency_and_notifications(env):
    counselor = env["counselor"]
    service = env["service"]
    student_1 = env["student_1"]
    student_2 = env["student_2"]
    ctx = AuditContext.user(counselor)

    start = future_local_start(hour=10)
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=ctx,
    )

    # Student 1 books the slot
    appt = book_fixed_slot(
        slot_id=slot.pk,
        student=student_1,
        context=AuditContext.user(student_1),
    )
    assert appt.reference_code.startswith("APT-")
    assert appt.student_id == student_1.pk
    assert appt.provider_id == counselor.pk
    assert appt.starts_at == start
    assert appt.status == AppointmentStatus.SCHEDULED

    # Verify notifications created for both student and counselor
    assert Notification.objects.filter(
        recipient=student_1,
        source_id=appt.pk,
    ).exists()
    assert Notification.objects.filter(
        recipient=counselor,
        source_id=appt.pk,
    ).exists()

    # Second student attempting to book the same slot must fail with SlotAlreadyBookedError
    with pytest.raises(SlotAlreadyBookedError):
        book_fixed_slot(
            slot_id=slot.pk,
            student=student_2,
            context=AuditContext.user(student_2),
        )


@pytest.mark.django_db
def test_api_staff_fixed_slot_crud_and_student_booking(env):
    counselor = env["counselor"]
    service = env["service"]
    student = env["student_1"]

    staff_client = auth_client(counselor, recent_mfa=True)
    student_client = auth_client(student, recent_mfa=False)

    start = future_local_start(hour=14)
    end = start + timedelta(minutes=60)

    # 1. Staff creates slot
    create_payload = {
        "provider_id": str(counselor.pk),
        "delivery_mode": "IN_PERSON",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "is_published": True,
    }
    res = staff_client.post(
        f"/api/v1/services/{service.pk}/slots",
        data=json.dumps(create_payload),
        content_type="application/json",
        **csrf(staff_client),
    )
    assert res.status_code == 200, res.content
    slot_data = res.json()
    slot_id = slot_data["id"]
    assert slot_data["is_published"] is True
    assert slot_data["is_booked"] is False

    # 2. Staff lists slots
    list_res = staff_client.get(f"/api/v1/services/{service.pk}/slots")
    assert list_res.status_code == 200
    assert any(s["id"] == slot_id for s in list_res.json())

    # 3. Student lists bookable slots
    bookable_res = student_client.get(f"/api/v1/services/{service.pk}/slots/bookable")
    assert bookable_res.status_code == 200
    assert any(s["id"] == slot_id for s in bookable_res.json())

    # 4. Student books slot
    book_res = student_client.post(
        f"/api/v1/services/{service.pk}/slots/{slot_id}/book",
        **csrf(student_client),
    )
    assert book_res.status_code == 200, book_res.content
    booking_data = book_res.json()
    assert booking_data["reference_code"].startswith("APT-")
    assert booking_data["provider_id"] == str(counselor.pk)

    # 5. Staff inspects slot -> now marked is_booked = True
    list_after = staff_client.get(f"/api/v1/services/{service.pk}/slots")
    booked_slot = next(s for s in list_after.json() if s["id"] == slot_id)
    assert booked_slot["is_booked"] is True
    assert booked_slot["appointment_reference_code"] == booking_data["reference_code"]

    # 6. The former destructive DELETE route no longer exists.
    del_res = staff_client.delete(
        f"/api/v1/services/{service.pk}/slots/{slot_id}",
        **csrf(staff_client),
    )
    assert del_res.status_code in (404, 405)
    assert ServiceAppointmentSlot.objects.filter(pk=slot_id).exists()


@pytest.mark.django_db
def test_api_fixed_slot_authorization_scope_redaction_and_cross_service_isolation(env):
    from compass.accounts.models import Designation
    from compass.organization.models import StaffSupervision

    admin = env["admin"]
    counselor = env["counselor"]
    counselor_b = env["counselor_b"]
    gss = env["gss"]
    service = env["service"]
    student = env["student_1"]

    admin_client = auth_client(admin, recent_mfa=True)
    no_mfa_counselor = auth_client(counselor, recent_mfa=False)
    counselor_client = auth_client(counselor, recent_mfa=True)
    counselor_b_client = auth_client(counselor_b, recent_mfa=True)
    gss_client = auth_client(gss, recent_mfa=True)
    student_client = auth_client(student, recent_mfa=False)

    start = future_local_start(hour=15)
    end = start + timedelta(minutes=60)
    create_payload = {
        "provider_id": str(counselor.pk),
        "delivery_mode": "IN_PERSON",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "is_published": True,
    }

    # 1. IT_ADMIN (services.manage without COUNSELOR/GSS + appointments.manage) rejected with 403
    assert admin_client.get(f"/api/v1/services/{service.pk}/slots").status_code == 403
    assert (
        admin_client.post(
            f"/api/v1/services/{service.pk}/slots",
            data=json.dumps(create_payload),
            content_type="application/json",
            **csrf(admin_client),
        ).status_code
        == 403
    )

    # 2. Counselor without recent MFA rejected with 403 on mutation
    no_mfa_res = no_mfa_counselor.post(
        f"/api/v1/services/{service.pk}/slots",
        data=json.dumps(create_payload),
        content_type="application/json",
        **csrf(no_mfa_counselor),
    )
    assert no_mfa_res.status_code == 403
    assert no_mfa_res.json()["error"]["code"] in ("mfa_setup_required", "mfa_step_up_required")

    # 3. Counselor creates slot and student books it
    create_res = counselor_client.post(
        f"/api/v1/services/{service.pk}/slots",
        data=json.dumps(create_payload),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert create_res.status_code == 200
    slot_id = create_res.json()["id"]

    book_res = student_client.post(
        f"/api/v1/services/{service.pk}/slots/{slot_id}/book",
        **csrf(student_client),
    )
    assert book_res.status_code == 200

    # 4. Owning counselor sees student details; out-of-scope counselor_b sees redacted details
    owner_slots = counselor_client.get(f"/api/v1/services/{service.pk}/slots").json()
    owner_slot = next(s for s in owner_slots if s["id"] == slot_id)
    assert owner_slot["is_booked"] is True
    assert owner_slot["student_name"] is not None
    assert owner_slot["appointment_id"] is not None
    assert owner_slot["appointment_reference_code"] is not None

    other_slots = counselor_b_client.get(f"/api/v1/services/{service.pk}/slots").json()
    other_slot = next(s for s in other_slots if s["id"] == slot_id)
    assert other_slot["is_booked"] is True
    assert other_slot["student_name"] is None
    assert other_slot["appointment_id"] is None
    assert other_slot["appointment_reference_code"] is None

    # A GSS may manage only the directly supervised Counselor's slots, and does not
    # inherit that Counselor's Appointment participant-data access.
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    gss_slots = gss_client.get(f"/api/v1/services/{service.pk}/slots")
    assert gss_slots.status_code == 200
    gss_slot = next(s for s in gss_slots.json() if s["id"] == slot_id)
    assert gss_slot["has_booking_history"] is True
    assert gss_slot["student_name"] is None
    assert gss_slot["appointment_id"] is None

    unrelated_mutation = counselor_b_client.patch(
        f"/api/v1/services/{service.pk}/slots/{slot_id}",
        data=json.dumps({"is_published": False}),
        content_type="application/json",
        **csrf(counselor_b_client),
    )
    assert unrelated_mutation.status_code == 404
    counselor_b.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    head_mutation = counselor_b_client.patch(
        f"/api/v1/services/{service.pk}/slots/{slot_id}",
        data=json.dumps({"is_published": False}),
        content_type="application/json",
        **csrf(counselor_b_client),
    )
    assert head_mutation.status_code == 404

    gss_mutation = gss_client.patch(
        f"/api/v1/services/{service.pk}/slots/{slot_id}",
        data=json.dumps({"is_published": False}),
        content_type="application/json",
        **csrf(gss_client),
    )
    assert gss_mutation.status_code == 200

    withdraw_res = counselor_client.post(
        f"/api/v1/services/{service.pk}/slots/{slot_id}/withdraw",
        **csrf(counselor_client),
    )
    assert withdraw_res.status_code == 200, withdraw_res.content
    assert withdraw_res.json()["withdrawn_at"] is not None
    slot = ServiceAppointmentSlot.objects.get(pk=slot_id)
    assert slot.current_appointment_id == book_res.json()["appointment_id"]
    assert slot.current_appointment.status == AppointmentStatus.SCHEDULED

    # 5. Cross-service slot_id isolation returns 404 slot_not_found
    other_service = create_service(
        code="OTHER_FIXED_SVC",
        name="Other Fixed Slot Service",
        appointment_booking_enabled=True,
        booking_pathways=[
            BookingPathwayCode.FLEXIBLE_APPOINTMENT,
            BookingPathwayCode.FIXED_DATE_SLOT,
        ],
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON"],
        context=AuditContext.user(admin),
    )
    other_service = set_service_active(
        service_id=other_service.pk, is_active=True, context=AuditContext.user(admin)
    )

    patch_wrong_svc = counselor_client.patch(
        f"/api/v1/services/{other_service.pk}/slots/{slot_id}",
        data=json.dumps({"is_published": False}),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert patch_wrong_svc.status_code == 404
    assert patch_wrong_svc.json()["error"]["code"] == "slot_not_found"

    del_wrong_svc = counselor_client.delete(
        f"/api/v1/services/{other_service.pk}/slots/{slot_id}",
        **csrf(counselor_client),
    )
    assert del_wrong_svc.status_code in (404, 405)
    assert ServiceAppointmentSlot.objects.filter(pk=slot_id).exists()

    book_wrong_svc = student_client.post(
        f"/api/v1/services/{other_service.pk}/slots/{slot_id}/book",
        **csrf(student_client),
    )
    assert book_wrong_svc.status_code == 404
    assert book_wrong_svc.json()["error"]["code"] == "slot_not_found"


@pytest.mark.django_db
def test_fixed_slot_management_rechecks_capability_and_active_identity(env):
    from compass.accounts.models import UserCapabilityOverride
    from compass.accounts.services import set_user_capability_override
    from compass.organization.models import StaffSupervision

    counselor = env["counselor"]
    counselor_b = env["counselor_b"]
    service = env["service"]
    start = future_local_start(hour=16)
    slot = create_fixed_slot(
        service_id=service.pk,
        provider_id=counselor.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=counselor,
        context=AuditContext.user(counselor),
    )
    gss = make_user("supervised-gss-slots@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    gss_client = auth_client(gss, recent_mfa=True)
    assert gss_client.get(f"/api/v1/services/{service.pk}/slots").status_code == 200

    set_user_capability_override(
        user=counselor,
        capability="appointments.manage",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Regression test capability revocation",
    )
    revoked_client = auth_client(counselor, recent_mfa=True)
    assert revoked_client.get(f"/api/v1/services/{service.pk}/slots").status_code == 403
    assert revoked_client.patch(
        f"/api/v1/services/{service.pk}/slots/{slot.pk}",
        data=json.dumps({"is_published": False}),
        content_type="application/json",
        **csrf(revoked_client),
    ).status_code == 403
    assert gss_client.get(f"/api/v1/services/{service.pk}/slots").status_code == 403

    counselor_b.is_active = False
    counselor_b.save(update_fields=["is_active", "updated_at"])
    inactive_client = auth_client(counselor_b, recent_mfa=True)
    assert inactive_client.get(f"/api/v1/services/{service.pk}/slots").status_code == 403
