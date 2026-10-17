"""Transactional Fixed-Date Appointment Slot management and Student booking services (SVC-2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.appointments.models import Appointment, AppointmentStatus
from compass.appointments.services import (
    AppointmentCurrentStudentRequired,
    AppointmentTimeConflict,
    AppointmentTimeUnavailable,
    _allocate_reference,
    _aware_start,
    _has_overlap,
    _interval_is_available,
    _lock_users,
    _normalized_delivery_mode,
    _validate_booking_users,
    _validate_inventory_prerequisite,
)
from compass.audit.actions import (
    APPOINTMENT_CREATED,
    SERVICE_SLOT_CREATED,
    SERVICE_SLOT_DELETED,
    SERVICE_SLOT_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_zone
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.service_catalog.models import (
    BookingPathwayCode,
    Service,
    ServiceAppointmentSlot,
)
from compass.service_catalog.services import (
    service_counselor_eligible,
    service_supports_delivery_mode,
)


class FixedSlotError(RuntimeError):
    """Base error for fixed-date slot operations."""


class ServiceNotEligibleForFixedSlots(FixedSlotError):
    """The Service is inactive or does not have the FIXED_DATE_SLOT pathway enabled."""


class CounselorNotQualifiedForService(FixedSlotError):
    """The selected Counselor is not qualified to provide this Service."""


class DeliveryModeNotSupported(FixedSlotError):
    """The requested delivery mode is not supported by the Service."""


class SlotTimeInvalid(FixedSlotError):
    """The slot start/end times are invalid (e.g. in the past, or start >= end)."""


class SlotConflictError(FixedSlotError):
    """The slot collides with an existing appointment or another published slot."""


class SlotAlreadyBookedError(FixedSlotError):
    """The slot is already booked by another student."""


class SlotCannotBeModifiedError(FixedSlotError):
    """An already booked slot cannot have its schedule, provider, or delivery mode changed."""


class SlotCannotBeDeletedError(FixedSlotError):
    """An already booked slot cannot be deleted while an active Appointment is linked."""


class SlotUnavailableError(FixedSlotError):
    """The slot is not published, has expired, or is currently unavailable."""


def is_slot_booked(slot: ServiceAppointmentSlot) -> bool:
    """Return True if the slot has an active, scheduled canonical Appointment."""
    if not slot.current_appointment_id:
        return False
    appt = slot.current_appointment
    return appt.status == AppointmentStatus.SCHEDULED and appt.starts_at == slot.starts_at


def _validate_service_and_counselor(
    *,
    service: Service,
    provider: User,
    delivery_mode: str,
    starts_at: datetime,
    ends_at: datetime,
    exclude_slot_id: UUID | None = None,
) -> None:
    """Validate that the service, provider, delivery mode, and time window are eligible."""
    if not service.is_active:
        raise ServiceNotEligibleForFixedSlots("Service is inactive.")

    has_fixed_pathway = service.booking_pathways.filter(
        code=BookingPathwayCode.FIXED_DATE_SLOT
    ).exists()
    if not has_fixed_pathway:
        raise ServiceNotEligibleForFixedSlots(
            "Service does not have fixed-date slot booking pathway enabled."
        )

    if not provider.is_active:
        raise CounselorNotQualifiedForService("The provider account is inactive.")

    if not service_counselor_eligible(service, provider):
        raise CounselorNotQualifiedForService(
            "The provider is not qualified for this Service under current provider coverage."
        )

    if not service_supports_delivery_mode(service, delivery_mode):
        raise DeliveryModeNotSupported(
            f"Delivery mode '{delivery_mode}' is not supported by this Service."
        )

    now = timezone.now().astimezone(institution_zone())
    if starts_at <= now:
        raise SlotTimeInvalid("Fixed slots must be scheduled in the future.")

    if ends_at <= starts_at:
        raise SlotTimeInvalid("Slot start time must be before end time.")

    # Check counselor availability
    if not _interval_is_available(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode=delivery_mode,
        starts_at=starts_at,
        ends_at=ends_at,
    ):
        raise SlotConflictError(
            "The Counselor's availability schedule does not cover this slot time window."
        )

    # Check for overlapping scheduled Appointments for this provider
    has_appt_overlap = Appointment.objects.filter(
        provider=provider,
        status=AppointmentStatus.SCHEDULED,
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    ).exists()
    if has_appt_overlap:
        raise SlotConflictError("The Counselor already has an overlapping scheduled Appointment.")

    # Check for overlapping fixed slots for this provider
    existing_slots = ServiceAppointmentSlot.objects.filter(
        provider=provider,
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    )
    if exclude_slot_id:
        existing_slots = existing_slots.exclude(pk=exclude_slot_id)

    if existing_slots.exists():
        raise SlotConflictError(
            "The Counselor already has another fixed slot scheduled at this time."
        )


def create_fixed_slot(
    *,
    service_id: UUID,
    provider_id: UUID,
    delivery_mode: str,
    starts_at: datetime,
    ends_at: datetime | None = None,
    is_published: bool = True,
    actor: User,
    context: AuditContext,
) -> ServiceAppointmentSlot:
    """Publish a new fixed-date individual appointment slot for an eligible Service."""
    normalized_mode = _normalized_delivery_mode(delivery_mode)
    aware_starts_at = _aware_start(starts_at)

    with transaction.atomic():
        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise ServiceNotEligibleForFixedSlots("Service not found.")

        provider = User.objects.filter(pk=provider_id).first()
        if provider is None:
            raise CounselorNotQualifiedForService("Provider not found.")

        if ends_at is None:
            duration = service.default_appointment_duration_minutes or 60
            calculated_ends_at = aware_starts_at + timedelta(minutes=duration)
        else:
            calculated_ends_at = _aware_start(ends_at)

        _validate_service_and_counselor(
            service=service,
            provider=provider,
            delivery_mode=normalized_mode,
            starts_at=aware_starts_at,
            ends_at=calculated_ends_at,
        )

        slot = ServiceAppointmentSlot.objects.create(
            service=service,
            provider=provider,
            delivery_mode=normalized_mode,
            starts_at=aware_starts_at,
            ends_at=calculated_ends_at,
            is_published=is_published,
            created_by=actor,
        )

        record_event(
            context=context,
            action=SERVICE_SLOT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.slot",
            target_id=slot.pk,
            metadata={
                "service_id": str(service.pk),
                "provider_id": str(provider.pk),
                "delivery_mode": normalized_mode,
                "starts_at": aware_starts_at.isoformat(),
                "ends_at": calculated_ends_at.isoformat(),
                "is_published": is_published,
            },
        )
        return slot


def update_fixed_slot(
    *,
    slot_id: UUID,
    actor: User,
    context: AuditContext,
    delivery_mode: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    is_published: bool | None = None,
    provider_id: UUID | None = None,
) -> ServiceAppointmentSlot:
    """Update a future fixed-date slot. Booked slots cannot have time or provider changed."""
    with transaction.atomic():
        slot = (
            ServiceAppointmentSlot.objects.select_for_update()
            .select_related("service", "provider")
            .filter(pk=slot_id)
            .first()
        )
        if slot is None:
            raise FixedSlotError("Slot not found.")

        booked = is_slot_booked(slot)
        time_or_provider_changed = (
            starts_at is not None
            or ends_at is not None
            or provider_id is not None
            or delivery_mode is not None
        )

        if booked and time_or_provider_changed:
            raise SlotCannotBeModifiedError(
                "Cannot modify the schedule, provider, or delivery mode of an already booked slot."
            )

        new_provider = slot.provider
        if provider_id is not None:
            new_provider = User.objects.filter(pk=provider_id).first()
            if new_provider is None:
                raise CounselorNotQualifiedForService("Provider not found.")

        new_mode = _normalized_delivery_mode(delivery_mode) if delivery_mode else slot.delivery_mode
        new_starts = _aware_start(starts_at) if starts_at else slot.starts_at
        new_ends = _aware_start(ends_at) if ends_at else slot.ends_at

        if time_or_provider_changed:
            _validate_service_and_counselor(
                service=slot.service,
                provider=new_provider,
                delivery_mode=new_mode,
                starts_at=new_starts,
                ends_at=new_ends,
                exclude_slot_id=slot.pk,
            )
            slot.provider = new_provider
            slot.delivery_mode = new_mode
            slot.starts_at = new_starts
            slot.ends_at = new_ends

        if is_published is not None:
            slot.is_published = is_published

        slot.save()

        record_event(
            context=context,
            action=SERVICE_SLOT_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.slot",
            target_id=slot.pk,
            metadata={
                "service_id": str(slot.service_id),
                "provider_id": str(slot.provider_id),
                "is_published": slot.is_published,
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
            },
        )
        return slot


def delete_fixed_slot(
    *,
    slot_id: UUID,
    actor: User,
    context: AuditContext,
) -> None:
    """Delete an unbooked fixed-date slot."""
    with transaction.atomic():
        slot = ServiceAppointmentSlot.objects.select_for_update().filter(pk=slot_id).first()
        if slot is None:
            raise FixedSlotError("Slot not found.")

        if is_slot_booked(slot):
            raise SlotCannotBeDeletedError(
                "Cannot delete an already booked slot. The student appointment must be cancelled"
                " first."
            )

        target_id = slot.pk
        service_id = slot.service_id
        slot.delete()

        record_event(
            context=context,
            action=SERVICE_SLOT_DELETED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.slot",
            target_id=target_id,
            metadata={"service_id": str(service_id)},
        )


def list_staff_fixed_slots(
    *,
    service_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    provider_id: UUID | None = None,
) -> list[ServiceAppointmentSlot]:
    """List fixed-date slots for staff management."""
    qs = (
        ServiceAppointmentSlot.objects.filter(service_id=service_id)
        .select_related(
            "service", "provider", "current_appointment", "current_appointment__student"
        )
        .order_by("starts_at")
    )
    if from_date:
        qs = qs.filter(starts_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(starts_at__date__lte=to_date)
    if provider_id:
        qs = qs.filter(provider_id=provider_id)
    return list(qs)


def list_student_bookable_slots(
    *,
    service_id: UUID,
    student: User,
    from_date: date | None = None,
    to_date: date | None = None,
    delivery_mode: str | None = None,
    provider_id: UUID | None = None,
) -> list[ServiceAppointmentSlot]:
    """List published, unbooked, and available fixed-date slots for a Student."""
    if not is_current_student(student):
        return []

    service = Service.objects.filter(pk=service_id, is_active=True).first()
    if not service:
        return []

    has_fixed_pathway = service.booking_pathways.filter(
        code=BookingPathwayCode.FIXED_DATE_SLOT
    ).exists()
    if not has_fixed_pathway:
        return []

    now = timezone.now()
    qs = (
        ServiceAppointmentSlot.objects.filter(
            service=service,
            is_published=True,
            starts_at__gt=now,
        )
        .filter(
            Q(current_appointment__isnull=True)
            | Q(current_appointment__status=AppointmentStatus.CANCELLED)
        )
        .select_related("service", "provider")
        .order_by("starts_at")
    )

    if from_date:
        qs = qs.filter(starts_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(starts_at__date__lte=to_date)
    if delivery_mode:
        qs = qs.filter(delivery_mode=_normalized_delivery_mode(delivery_mode))
    if provider_id:
        qs = qs.filter(provider_id=provider_id)

    # Runtime availability and qualification verification
    candidates = list(qs)
    available: list[ServiceAppointmentSlot] = []
    for slot in candidates:
        if not slot.provider.is_active:
            continue
        if not service_counselor_eligible(service, slot.provider):
            continue
        # Verify counselor has no conflicting scheduled appointment
        has_conflict = Appointment.objects.filter(
            provider=slot.provider,
            status=AppointmentStatus.SCHEDULED,
            starts_at__lt=slot.ends_at,
            ends_at__gt=slot.starts_at,
        ).exists()
        if has_conflict:
            continue
        # Verify counselor availability window still covers the slot
        if not _interval_is_available(
            provider_id=slot.provider.pk,
            service_id=service.pk,
            delivery_mode=slot.delivery_mode,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        ):
            continue
        available.append(slot)

    return available


def book_fixed_slot(
    *,
    slot_id: UUID,
    student: User,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    """Book a published fixed-date appointment slot, creating a canonical COMPASS Appointment."""
    if not is_current_student(student):
        raise AppointmentCurrentStudentRequired(
            "Current Student lifecycle is required to book an Appointment."
        )

    current_time = now or timezone.now()

    with transaction.atomic():
        slot = (
            ServiceAppointmentSlot.objects.select_for_update()
            .select_related("service", "provider")
            .filter(pk=slot_id)
            .first()
        )
        if slot is None:
            raise SlotUnavailableError("The selected slot was not found.")

        if not slot.is_published:
            raise SlotUnavailableError("This slot is not currently published for booking.")

        if is_slot_booked(slot):
            raise SlotAlreadyBookedError("This slot has already been booked by another student.")

        if slot.starts_at <= current_time:
            raise SlotUnavailableError("This slot is in the past and can no longer be booked.")

        service = slot.service
        if not service.is_active:
            raise ServiceNotEligibleForFixedSlots("This Service is currently disabled.")

        has_fixed = service.booking_pathways.filter(
            code=BookingPathwayCode.FIXED_DATE_SLOT
        ).exists()
        if not has_fixed:
            raise ServiceNotEligibleForFixedSlots(
                "Fixed-date slot booking is not enabled for this Service."
            )

        locked = _lock_users(student.pk, slot.provider.pk)
        locked_student = locked[student.pk]
        locked_provider = locked[slot.provider.pk]
        _validate_booking_users(locked_student, locked_provider)

        if not service_counselor_eligible(service, locked_provider):
            raise CounselorNotQualifiedForService(
                "The assigned Counselor is not qualified to provide this Service."
            )

        _validate_inventory_prerequisite(service, locked_student)

        # Check for provider availability
        if not _interval_is_available(
            provider_id=locked_provider.pk,
            service_id=service.pk,
            delivery_mode=slot.delivery_mode,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        ):
            raise AppointmentTimeUnavailable(
                "The Counselor's availability does not cover this slot time window."
            )

        # Check for provider appointment collision
        if _has_overlap(
            field="provider_id",
            user_id=locked_provider.pk,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        ):
            raise AppointmentTimeConflict("The Counselor already has an overlapping Appointment.")

        # Check for student appointment collision
        if _has_overlap(
            field="student_id",
            user_id=locked_student.pk,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        ):
            raise AppointmentTimeConflict("You already have an overlapping scheduled Appointment.")

        # Allocate canonical reference code
        reference_code = _allocate_reference(at=current_time)

        # Create canonical Appointment
        appointment = Appointment.objects.create(
            reference_code=reference_code,
            student=locked_student,
            service=service,
            service_name_snapshot=service.name,
            provider=locked_provider,
            delivery_mode=slot.delivery_mode,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            cancellation_cutoff_minutes=service.cancellation_cutoff_minutes,
            created_by=locked_student,
        )

        # Link slot to canonical appointment
        slot.current_appointment = appointment
        slot.save(update_fields=["current_appointment", "updated_at"])

        # Audit event
        record_event(
            context=context,
            action=APPOINTMENT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=appointment.pk,
            metadata={
                "reference_code": appointment.reference_code,
                "service_id": str(service.pk),
                "provider_id": str(locked_provider.pk),
                "delivery_mode": slot.delivery_mode,
                "fixed_slot_id": str(slot.pk),
            },
        )

        # In-app notifications
        for recipient in (locked_student, locked_provider):
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.APPOINTMENT_SCHEDULED,
                source_type="appointment",
                source_id=appointment.pk,
                target_type="APPOINTMENT",
                target_id=appointment.pk,
            )

        return appointment
