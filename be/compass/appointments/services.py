"""Transactional Appointment booking, cancellation, listing, and routing services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import APPOINTMENT_CANCELLED, APPOINTMENT_CREATED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.availability.services import AvailabilityError, compute_base_availability
from compass.organization.services import resolve_default_counselor_for_student
from compass.service_catalog.models import AppointmentPolicy, DeliveryMode, Service
from compass.service_catalog.services import (
    provider_role_eligible,
    service_allows_provider_role,
    service_supports_delivery_mode,
)

from .models import Appointment, AppointmentReferenceCounter, AppointmentStatus

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_ELIGIBLE_COUNSELORS = 50
MAX_REFERENCE_SEQUENCE = 999_999
PROVIDER_ROLE_CODES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


class AppointmentError(RuntimeError):
    pass


class AppointmentNotFound(AppointmentError):
    pass


class InvalidAppointmentInput(AppointmentError):
    pass


class AppointmentNotSchedulable(AppointmentError):
    pass


class AppointmentTimeUnavailable(AppointmentError):
    pass


class AppointmentTimeConflict(AppointmentError):
    pass


class AppointmentDefaultProviderUnresolved(AppointmentError):
    pass


class AppointmentCancellationConflict(AppointmentError):
    pass


class AppointmentRoleTransitionConflict(AppointmentError):
    pass


class AppointmentReferenceConflict(AppointmentError):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentPage:
    items: tuple[Appointment, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class EligibleCounselor:
    user: User
    is_default: bool


def _institution_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise AppointmentNotSchedulable(
            "The configured institutional timezone is unavailable."
        ) from exc


def _normalized_delivery_mode(value: str | DeliveryMode) -> str:
    normalized = value.value if isinstance(value, DeliveryMode) else value
    if normalized not in DeliveryMode.values:
        raise InvalidAppointmentInput("delivery_mode must be IN_PERSON or ONLINE")
    return str(normalized)


def _normalized_status(value: str | AppointmentStatus | None) -> str | None:
    if value is None:
        return None
    normalized = value.value if isinstance(value, AppointmentStatus) else value
    if normalized not in AppointmentStatus.values:
        raise InvalidAppointmentInput("status must be SCHEDULED or CANCELLED")
    return str(normalized)


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidAppointmentInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidAppointmentInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _aware_start(value: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidAppointmentInput("starts_at must be a timezone-aware datetime")
    return value.astimezone(_institution_zone())


def _appointment_queryset():
    return Appointment.objects.select_related(
        "student",
        "student__role",
        "provider",
        "provider__role",
        "service",
        "created_by",
        "cancelled_by",
    )


def _date_bounds(
    from_date: date | None, to_date: date | None
) -> tuple[datetime | None, datetime | None]:
    if from_date is not None and not isinstance(from_date, date):
        raise InvalidAppointmentInput("from_date must be a date")
    if to_date is not None and not isinstance(to_date, date):
        raise InvalidAppointmentInput("to_date must be a date")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvalidAppointmentInput("from_date must not be after to_date")
    zone = _institution_zone()
    start = datetime.combine(from_date, time.min, tzinfo=zone) if from_date else None
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone) if to_date else None
    return start, end


def _apply_date_filters(queryset, *, from_date: date | None, to_date: date | None):
    start, end = _date_bounds(from_date, to_date)
    if start is not None:
        queryset = queryset.filter(starts_at__gte=start)
    if end is not None:
        queryset = queryset.filter(starts_at__lt=end)
    return queryset


def _page(queryset, *, page: int, page_size: int) -> AppointmentPage:
    page, page_size = _pagination(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return AppointmentPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def list_my_appointments(
    *,
    actor: User,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = DEFAULT_PAGE_SIZE // DEFAULT_PAGE_SIZE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AppointmentPage:
    normalized_status = _normalized_status(status)
    qs = _appointment_queryset()
    if actor.role.code == "STUDENT":
        qs = qs.filter(student_id=actor.pk)
    elif actor.role.code in PROVIDER_ROLE_CODES:
        qs = qs.filter(provider_id=actor.pk)
    else:
        qs = qs.none()
    if normalized_status is not None:
        qs = qs.filter(status=normalized_status)
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    return _page(qs.order_by("-starts_at", "reference_code"), page=page, page_size=page_size)


def list_managed_appointments(
    *,
    status: str | None = None,
    student_id: UUID | None = None,
    provider_id: UUID | None = None,
    service_id: UUID | None = None,
    delivery_mode: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AppointmentPage:
    normalized_status = _normalized_status(status)
    normalized_mode = (
        _normalized_delivery_mode(delivery_mode) if delivery_mode is not None else None
    )
    qs = _appointment_queryset()
    if normalized_status is not None:
        qs = qs.filter(status=normalized_status)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if provider_id is not None:
        qs = qs.filter(provider_id=provider_id)
    if service_id is not None:
        qs = qs.filter(service_id=service_id)
    if normalized_mode is not None:
        qs = qs.filter(delivery_mode=normalized_mode)
    if search and search.strip():
        qs = qs.filter(reference_code__icontains=search.strip()[:64])
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    return _page(qs.order_by("-starts_at", "reference_code"), page=page, page_size=page_size)


def get_appointment_for_actor(*, appointment_id: UUID, actor: User) -> Appointment:
    item = _appointment_queryset().filter(pk=appointment_id).first()
    if item is None:
        raise AppointmentNotFound("The requested Appointment was not found.")
    can_manage = actor.has_capability("appointments.manage")
    can_view_self = actor.has_capability("appointments.view_self")
    related = item.student_id == actor.pk or item.provider_id == actor.pk
    if not can_manage and not (can_view_self and related):
        raise AppointmentNotFound("The requested Appointment was not found.")
    return item


def _validate_booking_service(service: Service, provider: User, delivery_mode: str) -> None:
    if not service.is_active:
        raise AppointmentNotSchedulable("The selected Service is inactive.")
    if service.appointment_policy == AppointmentPolicy.NONE:
        raise AppointmentNotSchedulable("The selected Service does not accept Appointments.")
    if service.default_duration_minutes is None:
        raise AppointmentNotSchedulable("The selected Service has no schedulable duration.")
    if not service_supports_delivery_mode(service, delivery_mode):
        raise AppointmentNotSchedulable("The Service does not support the requested delivery mode.")
    if not provider_role_eligible(service, provider):
        raise AppointmentNotSchedulable("The selected Counselor is not eligible for this Service.")


def _resolve_booking_provider(student: User, provider_id: UUID | None) -> User:
    if provider_id is not None:
        provider = User.objects.select_related("role").filter(pk=provider_id).first()
        if provider is None:
            raise AppointmentNotSchedulable("The selected Counselor is not available for booking.")
        return provider
    resolution = resolve_default_counselor_for_student(student)
    if resolution.counselor is None:
        raise AppointmentDefaultProviderUnresolved(
            "A default Counselor could not be resolved for this Student."
        )
    return resolution.counselor


def _lock_users(*user_ids: UUID) -> dict[UUID, User]:
    unique_ids = sorted(set(user_ids), key=str)
    rows = list(
        User.objects.select_for_update()
        .select_related("role")
        .filter(pk__in=unique_ids)
        .order_by("pk")
    )
    by_id = {row.pk: row for row in rows}
    if len(by_id) != len(unique_ids):
        raise AppointmentNotSchedulable("A booking participant no longer exists.")
    return by_id


def _validate_booking_users(student: User, provider: User) -> None:
    if not student.is_active or student.role.code != "STUDENT":
        raise AppointmentNotSchedulable("Only an active Student can create this Appointment.")
    if not provider.is_active or provider.role.code != "COUNSELOR":
        raise AppointmentNotSchedulable("The selected provider must be an active Counselor.")


def _validate_default_provider_still_current(student: User, provider: User) -> None:
    resolution = resolve_default_counselor_for_student(student)
    if resolution.counselor is None or resolution.counselor.pk != provider.pk:
        raise AppointmentDefaultProviderUnresolved(
            "The default Counselor changed while the booking was being created; retry the booking."
        )


def _interval_is_available(
    *,
    provider_id: UUID,
    service_id: UUID,
    delivery_mode: str,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    query_end_date = ends_at.date() + timedelta(days=1)
    try:
        result = compute_base_availability(
            provider_id=provider_id,
            service_id=service_id,
            delivery_mode=delivery_mode,
            start_date=starts_at.date(),
            end_date=query_end_date,
        )
    except AvailabilityError as exc:
        raise AppointmentTimeUnavailable("The requested time is not available.") from exc
    return any(
        interval.starts_at <= starts_at and ends_at <= interval.ends_at
        for interval in result.windows
    )


def _has_overlap(*, field: str, user_id: UUID, starts_at: datetime, ends_at: datetime) -> bool:
    filters = {
        field: user_id,
        "status": AppointmentStatus.SCHEDULED,
        "starts_at__lt": ends_at,
        "ends_at__gt": starts_at,
    }
    return Appointment.objects.filter(**filters).exists()


def _reference_year(at: datetime) -> int:
    return at.astimezone(_institution_zone()).year


def _allocate_reference(*, at: datetime) -> str:
    year = _reference_year(at)
    counter = AppointmentReferenceCounter.objects.select_for_update().filter(year=year).first()
    if counter is None:
        try:
            with transaction.atomic():
                AppointmentReferenceCounter.objects.create(year=year, next_value=2)
            number = 1
        except IntegrityError:
            counter = AppointmentReferenceCounter.objects.select_for_update().get(year=year)
            number = counter.next_value
            if number > MAX_REFERENCE_SEQUENCE:
                raise AppointmentReferenceConflict(
                    "The Appointment reference sequence is exhausted for this year."
                ) from None
            counter.next_value = number + 1
            counter.save(update_fields=["next_value"])
    else:
        number = counter.next_value
        if number > MAX_REFERENCE_SEQUENCE:
            raise AppointmentReferenceConflict(
                "The Appointment reference sequence is exhausted for this year."
            )
        counter.next_value = number + 1
        counter.save(update_fields=["next_value"])
    return f"APT-{year:04d}-{number:06d}"


def create_student_appointment(
    *,
    student: User,
    service_id: UUID,
    provider_id: UUID | None,
    delivery_mode: str,
    starts_at: datetime,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    normalized_mode = _normalized_delivery_mode(delivery_mode)
    normalized_start = _aware_start(starts_at)
    current = now or timezone.now()
    if normalized_start <= current.astimezone(_institution_zone()):
        raise AppointmentNotSchedulable("Appointments must start in the future.")

    initially_resolved_provider = _resolve_booking_provider(student, provider_id)
    with transaction.atomic():
        locked = _lock_users(student.pk, initially_resolved_provider.pk)
        locked_student = locked[student.pk]
        locked_provider = locked[initially_resolved_provider.pk]
        _validate_booking_users(locked_student, locked_provider)
        if provider_id is None:
            _validate_default_provider_still_current(locked_student, locked_provider)

        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise AppointmentNotSchedulable("The selected Service was not found.")
        _validate_booking_service(service, locked_provider, normalized_mode)

        ends_at = normalized_start + timedelta(minutes=service.default_duration_minutes)
        if not _interval_is_available(
            provider_id=locked_provider.pk,
            service_id=service.pk,
            delivery_mode=normalized_mode,
            starts_at=normalized_start,
            ends_at=ends_at,
        ):
            raise AppointmentTimeUnavailable(
                "The full Appointment interval is not contained in current Availability."
            )
        if _has_overlap(
            field="provider_id",
            user_id=locked_provider.pk,
            starts_at=normalized_start,
            ends_at=ends_at,
        ):
            raise AppointmentTimeConflict("The Counselor already has an overlapping Appointment.")
        if _has_overlap(
            field="student_id",
            user_id=locked_student.pk,
            starts_at=normalized_start,
            ends_at=ends_at,
        ):
            raise AppointmentTimeConflict("The Student already has an overlapping Appointment.")

        reference_code = _allocate_reference(at=current)
        appointment = Appointment.objects.create(
            reference_code=reference_code,
            student=locked_student,
            service=service,
            provider=locked_provider,
            delivery_mode=normalized_mode,
            starts_at=normalized_start,
            ends_at=ends_at,
            cancellation_cutoff_minutes=service.cancellation_cutoff_minutes,
            created_by=locked_student,
        )
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
                "delivery_mode": normalized_mode,
            },
        )
    return _appointment_queryset().get(pk=appointment.pk)


def cancel_appointment(
    *,
    appointment_id: UUID,
    actor: User,
    administrative: bool,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    current = now or timezone.now()
    with transaction.atomic():
        item = Appointment.objects.select_for_update().filter(pk=appointment_id).first()
        if item is None:
            raise AppointmentNotFound("The requested Appointment was not found.")
        if administrative:
            pass
        elif actor.pk != item.student_id or not actor.is_active or actor.role.code != "STUDENT":
            raise AppointmentNotFound("The requested Appointment was not found.")

        if item.status == AppointmentStatus.CANCELLED:
            return item
        if current >= item.starts_at:
            raise AppointmentCancellationConflict(
                "An Appointment cannot be cancelled after it has started."
            )
        if not administrative and item.cancellation_cutoff_minutes is not None:
            boundary = item.starts_at - timedelta(minutes=item.cancellation_cutoff_minutes)
            if current > boundary:
                raise AppointmentCancellationConflict(
                    "The Appointment cancellation cutoff has passed."
                )

        item.status = AppointmentStatus.CANCELLED
        item.cancelled_at = current
        item.cancelled_by = actor
        item.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_CANCELLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "administrative": administrative,
            },
        )
        return _appointment_queryset().get(pk=item.pk)


def list_eligible_counselors(
    *, student: User, service_id: UUID, delivery_mode: str
) -> tuple[EligibleCounselor, ...]:
    normalized_mode = _normalized_delivery_mode(delivery_mode)
    if not student.is_active or student.role.code != "STUDENT":
        raise AppointmentNotSchedulable("Only an active Student can discover booking Counselors.")
    service = Service.objects.filter(pk=service_id).first()
    if service is None or not service.is_active:
        raise AppointmentNotSchedulable("The selected Service is not bookable.")
    if service.appointment_policy == AppointmentPolicy.NONE:
        raise AppointmentNotSchedulable("The selected Service does not accept Appointments.")
    if not service_supports_delivery_mode(service, normalized_mode):
        raise AppointmentNotSchedulable("The Service does not support the requested delivery mode.")
    if not service_allows_provider_role(service, "COUNSELOR"):
        return ()

    default_resolution = resolve_default_counselor_for_student(student)
    default_id = default_resolution.counselor.pk if default_resolution.counselor else None
    counselors = list(
        User.objects.filter(is_active=True, role__code="COUNSELOR")
        .select_related("role")
        .order_by("last_name", "first_name", "id")[:MAX_ELIGIBLE_COUNSELORS]
    )
    return tuple(
        EligibleCounselor(user=item, is_default=item.pk == default_id) for item in counselors
    )


def validate_role_transition(
    *, user: User, new_role_code: str, now: datetime | None = None
) -> None:
    if user.role.code == new_role_code:
        return
    current = now or timezone.now()
    future_scheduled = Q(status=AppointmentStatus.SCHEDULED, ends_at__gt=current)
    if user.role.code in PROVIDER_ROLE_CODES and new_role_code not in PROVIDER_ROLE_CODES:
        if Appointment.objects.filter(future_scheduled, provider_id=user.pk).exists():
            raise AppointmentRoleTransitionConflict(
                "Resolve the provider's active or future Appointments before changing role."
            )
    if user.role.code == "STUDENT" and new_role_code != "STUDENT":
        if Appointment.objects.filter(future_scheduled, student_id=user.pk).exists():
            raise AppointmentRoleTransitionConflict(
                "Resolve the Student's active or future Appointments before changing role."
            )
