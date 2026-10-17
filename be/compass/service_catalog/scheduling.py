"""Cross-pathway commitments for the Service Catalog's three booking paths.

The functions here are deliberately limited to the records that reserve an
individual Counselor or Student time: scheduled Appointments, open published
Fixed Slots, and registered/published Group Sessions. They are not a general
scheduler. Callers must lock every affected User with ``lock_schedule_users``
before locking a Service, slot, or Group Session.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from django.db.models import Q

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.group_sessions.models import (
    GroupSession,
    GroupSessionFacilitator,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.service_catalog.models import ServiceAppointmentSlot


def lock_schedule_users(*user_ids: UUID | None) -> dict[UUID, User]:
    """Lock participating Users in one deterministic order across booking paths."""

    identifiers = sorted({value for value in user_ids if value is not None}, key=str)
    if not identifiers:
        return {}
    rows = list(
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk__in=identifiers)
        .order_by("pk")
    )
    by_id = {row.pk: row for row in rows}
    if len(by_id) != len(identifiers):
        raise ValueError("A scheduling participant no longer exists; retry the operation.")
    return by_id


def _overlapping(start: datetime, end: datetime):
    """Return the common half-open interval predicate: start < other_end and end > other_start."""

    return {"starts_at__lt": end, "ends_at__gt": start}


def provider_schedule_conflict(
    *,
    provider_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
    exclude_slot_id: UUID | None = None,
    exclude_group_session_id: UUID | None = None,
) -> str | None:
    """Return the first active Counselor commitment overlapping this interval."""

    appointments = Appointment.objects.filter(
        provider_id=provider_id,
        status=AppointmentStatus.SCHEDULED,
        **_overlapping(starts_at, ends_at),
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    if appointments.exists():
        return "appointment"

    # A currently scheduled canonical Appointment is the commitment for a booked
    # slot. Count the slot as a hold only when it is available for a new booking.
    slots = ServiceAppointmentSlot.objects.filter(
        provider_id=provider_id,
        is_published=True,
        withdrawn_at__isnull=True,
        **_overlapping(starts_at, ends_at),
    ).filter(
        Q(current_appointment__isnull=True)
        | Q(current_appointment__status=AppointmentStatus.CANCELLED)
    )
    if exclude_slot_id:
        slots = slots.exclude(pk=exclude_slot_id)
    if slots.exists():
        return "fixed_slot"

    sessions = GroupSession.objects.filter(
        status=GroupSessionStatus.PUBLISHED,
        facilitators__internal_user_id=provider_id,
        facilitators__removed_at__isnull=True,
        **_overlapping(starts_at, ends_at),
    )
    if exclude_group_session_id:
        sessions = sessions.exclude(pk=exclude_group_session_id)
    if sessions.exists():
        return "group_session"
    return None


def student_schedule_conflict(
    *,
    student_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
    exclude_group_session_id: UUID | None = None,
) -> str | None:
    """Return the first active Student commitment overlapping this interval."""

    appointments = Appointment.objects.filter(
        student_id=student_id,
        status=AppointmentStatus.SCHEDULED,
        **_overlapping(starts_at, ends_at),
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    if appointments.exists():
        return "appointment"

    registrations = GroupSessionRegistration.objects.filter(
        student_id=student_id,
        status=RegistrationStatus.REGISTERED,
        group_session__status=GroupSessionStatus.PUBLISHED,
        group_session__starts_at__lt=ends_at,
        group_session__ends_at__gt=starts_at,
    )
    if exclude_group_session_id:
        registrations = registrations.exclude(group_session_id=exclude_group_session_id)
    if registrations.exists():
        return "group_session"
    return None


def providers_with_schedule_conflicts(
    *,
    provider_ids: Iterable[UUID],
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
    exclude_slot_id: UUID | None = None,
    exclude_group_session_id: UUID | None = None,
) -> set[UUID]:
    """Batch form used when a published Group Session affects several facilitators."""

    identifiers = set(provider_ids)
    if not identifiers:
        return set()
    overlap = _overlapping(starts_at, ends_at)
    appointments = Appointment.objects.filter(
        provider_id__in=identifiers,
        status=AppointmentStatus.SCHEDULED,
        **overlap,
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    conflicts = set(appointments.values_list("provider_id", flat=True))

    slots = ServiceAppointmentSlot.objects.filter(
        provider_id__in=identifiers,
        is_published=True,
        withdrawn_at__isnull=True,
        **overlap,
    ).filter(
        Q(current_appointment__isnull=True)
        | Q(current_appointment__status=AppointmentStatus.CANCELLED)
    )
    if exclude_slot_id:
        slots = slots.exclude(pk=exclude_slot_id)
    conflicts.update(slots.values_list("provider_id", flat=True))

    sessions = GroupSessionFacilitator.objects.filter(
        internal_user_id__in=identifiers,
        removed_at__isnull=True,
        group_session__status=GroupSessionStatus.PUBLISHED,
        group_session__starts_at__lt=ends_at,
        group_session__ends_at__gt=starts_at,
    )
    if exclude_group_session_id:
        sessions = sessions.exclude(group_session_id=exclude_group_session_id)
    conflicts.update(sessions.values_list("internal_user_id", flat=True))
    return conflicts


def students_with_schedule_conflicts(
    *,
    student_ids: Iterable[UUID],
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
    exclude_group_session_id: UUID | None = None,
) -> set[UUID]:
    """Batch form used when a published Group Session affects registered Students."""

    identifiers = set(student_ids)
    if not identifiers:
        return set()
    overlap = _overlapping(starts_at, ends_at)
    appointments = Appointment.objects.filter(
        student_id__in=identifiers,
        status=AppointmentStatus.SCHEDULED,
        **overlap,
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    conflicts = set(appointments.values_list("student_id", flat=True))

    registrations = GroupSessionRegistration.objects.filter(
        student_id__in=identifiers,
        status=RegistrationStatus.REGISTERED,
        group_session__status=GroupSessionStatus.PUBLISHED,
        group_session__starts_at__lt=ends_at,
        group_session__ends_at__gt=starts_at,
    )
    if exclude_group_session_id:
        registrations = registrations.exclude(group_session_id=exclude_group_session_id)
    conflicts.update(registrations.values_list("student_id", flat=True))
    return conflicts


def schedule_busy_intervals(
    *,
    provider_id: UUID,
    student_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> tuple[tuple[datetime, datetime], ...]:
    """Intervals used to render flexible Appointment availability without competing offers."""

    overlap = _overlapping(starts_at, ends_at)
    appointments = Appointment.objects.filter(
        Q(provider_id=provider_id) | Q(student_id=student_id),
        status=AppointmentStatus.SCHEDULED,
        **overlap,
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    intervals = set(appointments.values_list("starts_at", "ends_at"))

    intervals.update(
        ServiceAppointmentSlot.objects.filter(
            provider_id=provider_id,
            is_published=True,
            withdrawn_at__isnull=True,
            **overlap,
        )
        .filter(
            Q(current_appointment__isnull=True)
            | Q(current_appointment__status=AppointmentStatus.CANCELLED)
        )
        .values_list("starts_at", "ends_at")
    )
    intervals.update(
        GroupSession.objects.filter(
            status=GroupSessionStatus.PUBLISHED,
            facilitators__internal_user_id=provider_id,
            facilitators__removed_at__isnull=True,
            **overlap,
        ).values_list("starts_at", "ends_at")
    )
    intervals.update(
        GroupSessionRegistration.objects.filter(
            student_id=student_id,
            status=RegistrationStatus.REGISTERED,
            group_session__status=GroupSessionStatus.PUBLISHED,
            group_session__starts_at__lt=ends_at,
            group_session__ends_at__gt=starts_at,
        ).values_list("group_session__starts_at", "group_session__ends_at")
    )
    return tuple(intervals)
