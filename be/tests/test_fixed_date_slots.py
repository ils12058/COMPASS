"""Comprehensive unit, authorization, conflict, and concurrency tests for Fixed Slots (SVC-2)."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.appointments.models import AppointmentStatus
from compass.audit.actions import (
    SERVICE_SLOT_CREATED,
    SERVICE_SLOT_DELETED,
    SERVICE_SLOT_UPDATED,
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
    SlotCannotBeDeletedError,
    SlotCannotBeModifiedError,
    SlotConflictError,
    SlotTimeInvalid,
    book_fixed_slot,
    create_fixed_slot,
    delete_fixed_slot,
    is_slot_booked,
    list_student_bookable_slots,
    update_fixed_slot,
)
from compass.service_catalog.models import (
    BookingPathwayCode,
    ServiceAppointmentSlot,
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
            actor=admin,
            context=ctx,
        )

    # Delivery mode ONLINE is not supported by service_sel
    with pytest.raises(DeliveryModeNotSupported):
        create_fixed_slot(
            service_id=service_sel.pk,
            provider_id=counselor.pk,
            delivery_mode="ONLINE",
            starts_at=start,
            ends_at=start + timedelta(minutes=60),
            actor=admin,
            context=ctx,
        )


@pytest.mark.django_db
def test_update_and_delete_slot_protection(env):
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

    # Attempt to delete booked slot must fail
    with pytest.raises(SlotCannotBeDeletedError):
        delete_fixed_slot(slot_id=slot.pk, actor=counselor, context=ctx)

    # Deleting unbooked slot succeeds
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
    delete_fixed_slot(slot_id=unbooked_slot.pk, actor=counselor, context=ctx)
    assert not ServiceAppointmentSlot.objects.filter(pk=unbooked_slot.pk).exists()
    assert AuditEvent.objects.filter(
        action=SERVICE_SLOT_DELETED, target_id=unbooked_slot.pk
    ).exists()


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

    # 6. Staff cannot delete booked slot
    del_res = staff_client.delete(
        f"/api/v1/services/{service.pk}/slots/{slot_id}",
        **csrf(staff_client),
    )
    assert del_res.status_code == 409
    assert del_res.json()["error"]["code"] == "slot_cannot_be_deleted"
