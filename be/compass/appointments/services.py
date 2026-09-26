"""Transactional Appointment booking, cancellation, listing, and routing services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    APPOINTMENT_CANCELLED,
    APPOINTMENT_COMPLETED,
    APPOINTMENT_CREATED,
    APPOINTMENT_NO_SHOW,
    APPOINTMENT_REASSIGNED,
    APPOINTMENT_RESCHEDULED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.availability.services import AvailabilityError, compute_base_availability
from compass.inventory.services import (
    CurrentAcademicYearNotConfigured,
    InventoryStatus,
    get_current_inventory_status,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.services import resolve_default_counselor_for_student
from compass.service_catalog.models import AppointmentPolicy, DeliveryMode, Service
from compass.service_catalog.services import (
    ELIGIBLE_PROVIDER_ROLE_CODES,
    provider_role_eligible,
    service_allows_provider_role,
    service_supports_delivery_mode,
)

from .access import appointment_management_access_allowed, scope_managed_appointments
from .models import (
    Appointment,
    AppointmentChangeEvent,
    AppointmentChangeEventType,
    AppointmentReferenceCounter,
    AppointmentStatus,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_ELIGIBLE_COUNSELORS = 50
MAX_REFERENCE_SEQUENCE = 999_999
MAX_CHANGE_REASON_LENGTH = 1000
MAX_SEARCH_LENGTH = 160
PROVIDER_ROLE_CODES = ELIGIBLE_PROVIDER_ROLE_CODES


class AppointmentListOrdering(StrEnum):
    START_ASC = "START_ASC"
    START_DESC = "START_DESC"


class AppointmentActionBlocker(StrEnum):
    """Why an Appointment action is not currently available to the requesting actor."""

    NOT_PERMITTED = "NOT_PERMITTED"
    NOT_SCHEDULED = "NOT_SCHEDULED"
    ALREADY_STARTED = "ALREADY_STARTED"
    NOT_STARTED = "NOT_STARTED"
    NOT_ENDED = "NOT_ENDED"
    CUTOFF_PASSED = "CUTOFF_PASSED"
    CURRENT_STUDENT_REQUIRED = "CURRENT_STUDENT_REQUIRED"
    ECOUNSELING_ROOM_LINKED = "ECOUNSELING_ROOM_LINKED"
    ROUTINE_INTERVIEW_LINKED = "ROUTINE_INTERVIEW_LINKED"
    COUNSELING_ENCOUNTER_LINKED = "COUNSELING_ENCOUNTER_LINKED"


@dataclass(frozen=True, slots=True)
class AppointmentActionState:
    allowed: bool
    blocker: AppointmentActionBlocker | None


@dataclass(frozen=True, slots=True)
class AppointmentActions:
    cancel: AppointmentActionState
    reschedule: AppointmentActionState
    reassign: AppointmentActionState
    complete: AppointmentActionState
    mark_no_show: AppointmentActionState


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


class AppointmentCancellationCutoffPassed(AppointmentCancellationConflict):
    pass


class AppointmentLifecycleConflict(AppointmentError):
    pass


class AppointmentRoleTransitionConflict(AppointmentError):
    pass


class AppointmentReferenceConflict(AppointmentError):
    pass


class AppointmentCurrentInventoryRequired(AppointmentError):
    pass


class AppointmentCurrentStudentRequired(AppointmentError):
    pass


class AppointmentCurrentAcademicYearNotConfigured(AppointmentError):
    pass


@dataclass(frozen=True, slots=True)
class AppointmentPage:
    items: tuple[Appointment, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class AppointmentBookingServicePage:
    items: tuple[Service, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class EligibleCounselor:
    user: User
    is_default: bool


@dataclass(frozen=True, slots=True)
class BookableSlot:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class BookableSlotList:
    date: date
    timezone_name: str
    duration_minutes: int
    items: tuple[BookableSlot, ...]


@dataclass(frozen=True, slots=True)
class AppointmentReassignmentCandidate:
    user: User


@dataclass(frozen=True, slots=True)
class AppointmentHistoryEntry:
    event_type: str
    occurred_at: datetime
    actor: User | None
    reason: str
    previous_starts_at: datetime | None = None
    previous_ends_at: datetime | None = None
    new_starts_at: datetime | None = None
    new_ends_at: datetime | None = None
    previous_provider: User | None = None
    new_provider: User | None = None


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
        raise InvalidAppointmentInput("status must be SCHEDULED, CANCELLED, COMPLETED, or NO_SHOW")
    return str(normalized)


def _normalized_list_ordering(
    value: str | AppointmentListOrdering,
) -> AppointmentListOrdering:
    normalized = value.value if isinstance(value, AppointmentListOrdering) else value
    try:
        return AppointmentListOrdering(normalized)
    except (TypeError, ValueError) as exc:
        raise InvalidAppointmentInput("ordering must be START_ASC or START_DESC") from exc


def _ordering_fields(ordering: AppointmentListOrdering) -> tuple[str, str]:
    if ordering == AppointmentListOrdering.START_ASC:
        return "starts_at", "reference_code"
    return "-starts_at", "reference_code"


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
        "completed_by",
        "no_show_by",
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


def count_upcoming_self_appointments(
    *,
    actor: User,
    now: datetime | None = None,
) -> int | None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability("appointments.view_self")
    ):
        return None

    queryset = _apply_upcoming_filter(Appointment.objects.all(), upcoming=True, now=now)
    if actor.role.code == "STUDENT":
        return queryset.filter(student_id=actor.pk).count()
    if actor.role.code == "COUNSELOR":
        return queryset.filter(provider_id=actor.pk).count()
    return None


def count_upcoming_managed_appointments(
    *,
    actor: User,
    now: datetime | None = None,
) -> int | None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not actor.has_capability("appointments.manage")
    ):
        return None

    queryset = scope_managed_appointments(Appointment.objects.all(), actor)
    return _apply_upcoming_filter(queryset, upcoming=True, now=now).count()


def _apply_upcoming_filter(queryset, *, upcoming: bool, now: datetime | None):
    """Match the Overview upcoming population: SCHEDULED and not yet started (server time)."""

    if not upcoming:
        return queryset
    return queryset.filter(
        status=AppointmentStatus.SCHEDULED,
        starts_at__gte=now or timezone.now(),
    )


def list_my_appointments(
    *,
    actor: User,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    upcoming: bool = False,
    ordering: str | AppointmentListOrdering = AppointmentListOrdering.START_DESC,
    page: int = DEFAULT_PAGE_SIZE // DEFAULT_PAGE_SIZE,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> AppointmentPage:
    normalized_status = _normalized_status(status)
    normalized_ordering = _normalized_list_ordering(ordering)
    qs = _appointment_queryset()
    if actor.role.code == "STUDENT":
        qs = qs.filter(student_id=actor.pk)
    elif actor.role.code in PROVIDER_ROLE_CODES:
        qs = qs.filter(provider_id=actor.pk)
    else:
        qs = qs.none()
    if normalized_status is not None:
        qs = qs.filter(status=normalized_status)
    qs = _apply_upcoming_filter(qs, upcoming=upcoming, now=now)
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    return _page(
        qs.order_by(*_ordering_fields(normalized_ordering)),
        page=page,
        page_size=page_size,
    )


def list_managed_appointments(
    *,
    actor: User,
    status: str | None = None,
    student_id: UUID | None = None,
    provider_id: UUID | None = None,
    service_id: UUID | None = None,
    delivery_mode: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    upcoming: bool = False,
    ordering: str | AppointmentListOrdering = AppointmentListOrdering.START_DESC,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> AppointmentPage:
    normalized_status = _normalized_status(status)
    normalized_ordering = _normalized_list_ordering(ordering)
    normalized_mode = (
        _normalized_delivery_mode(delivery_mode) if delivery_mode is not None else None
    )
    qs = scope_managed_appointments(_appointment_queryset(), actor)
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
    qs = _apply_upcoming_filter(qs, upcoming=upcoming, now=now)
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    if search is not None:
        if not isinstance(search, str):
            raise InvalidAppointmentInput("search must be text")
        for token in search.strip()[:MAX_SEARCH_LENGTH].split():
            qs = qs.filter(
                Q(reference_code__icontains=token)
                | Q(student__institutional_id__icontains=token)
                | Q(student__first_name__icontains=token)
                | Q(student__middle_name__icontains=token)
                | Q(student__last_name__icontains=token)
            )
    return _page(
        qs.order_by(*_ordering_fields(normalized_ordering)),
        page=page,
        page_size=page_size,
    )


def list_booking_services(
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AppointmentBookingServicePage:
    page, page_size = _pagination(page, page_size)
    qs = (
        Service.objects.filter(
            is_active=True,
            appointment_policy__in=(AppointmentPolicy.OPTIONAL, AppointmentPolicy.REQUIRED),
            default_duration_minutes__isnull=False,
            provider_role_assignments__role__code__in=ELIGIBLE_PROVIDER_ROLE_CODES,
            delivery_mode_assignments__mode__in=DeliveryMode.values,
        )
        .prefetch_related("delivery_mode_assignments")
        .distinct()
        .order_by("code", "id")
    )
    if search is not None:
        if not isinstance(search, str):
            raise InvalidAppointmentInput("search must be text")
        term = search.strip()[:MAX_SEARCH_LENGTH]
        if term:
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))

    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return AppointmentBookingServicePage(
        tuple(rows[:page_size]),
        page,
        page_size,
        len(rows) > page_size,
    )


def get_appointment_for_actor(*, appointment_id: UUID, actor: User) -> Appointment:
    item = _appointment_queryset().filter(pk=appointment_id).first()
    if item is None:
        raise AppointmentNotFound("The requested Appointment was not found.")
    can_view_self = actor.has_capability("appointments.view_self")
    related = item.student_id == actor.pk or item.provider_id == actor.pk
    if can_view_self and related:
        return item
    if appointment_management_access_allowed(actor, item):
        return item
    raise AppointmentNotFound("The requested Appointment was not found.")


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


def _validate_inventory_prerequisite(service: Service, student: User) -> None:
    if not service.requires_current_inventory:
        return
    try:
        status = get_current_inventory_status(student)
    except CurrentAcademicYearNotConfigured as exc:
        raise AppointmentCurrentAcademicYearNotConfigured(
            "No current Academic Year is configured for Inventory prerequisites."
        ) from exc
    if status.status != InventoryStatus.SUBMITTED:
        raise AppointmentCurrentInventoryRequired(
            "A submitted Individual Inventory for the current Academic Year is required."
        )


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
        User.objects.select_for_update(of=("self",))
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


def _has_overlap(
    *,
    field: str,
    user_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> bool:
    filters = {
        field: user_id,
        "status": AppointmentStatus.SCHEDULED,
        "starts_at__lt": ends_at,
        "ends_at__gt": starts_at,
    }
    queryset = Appointment.objects.filter(**filters)
    if exclude_appointment_id is not None:
        queryset = queryset.exclude(pk=exclude_appointment_id)
    return queryset.exists()


def _candidate_slots(
    *,
    windows,
    duration: timedelta,
    provider_id: UUID,
    student_id: UUID,
    now: datetime,
    exclude_appointment_id: UUID | None = None,
) -> tuple[BookableSlot, ...]:
    if duration <= timedelta(0):
        raise AppointmentNotSchedulable("The Appointment duration must be positive.")
    if not windows:
        return ()
    first_start = min(window.starts_at for window in windows)
    last_end = max(window.ends_at for window in windows)
    reservations = Appointment.objects.filter(
        Q(provider_id=provider_id) | Q(student_id=student_id),
        status=AppointmentStatus.SCHEDULED,
        starts_at__lt=last_end,
        ends_at__gt=first_start,
    )
    if exclude_appointment_id is not None:
        reservations = reservations.exclude(pk=exclude_appointment_id)
    busy_intervals = tuple(reservations.values_list("starts_at", "ends_at"))
    items: list[BookableSlot] = []
    local_now = now.astimezone(_institution_zone())
    for window in windows:
        starts_at = window.starts_at
        while starts_at + duration <= window.ends_at:
            ends_at = starts_at + duration
            if starts_at > local_now and not any(
                busy_start < ends_at and busy_end > starts_at
                for busy_start, busy_end in busy_intervals
            ):
                items.append(
                    BookableSlot(
                        starts_at=starts_at,
                        ends_at=ends_at,
                    )
                )
            starts_at = ends_at
    return tuple(items)


def _base_slot_windows(
    *,
    provider_id: UUID,
    service_id: UUID,
    delivery_mode: str,
    target_date: date,
):
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise InvalidAppointmentInput("date must be a calendar date.")
    try:
        return compute_base_availability(
            provider_id=provider_id,
            service_id=service_id,
            delivery_mode=delivery_mode,
            start_date=target_date,
            end_date=target_date + timedelta(days=1),
        )
    except AvailabilityError as exc:
        raise AppointmentTimeUnavailable(
            "Current Availability could not provide bookable times for the requested date."
        ) from exc


def list_bookable_slots(
    *,
    student: User,
    service_id: UUID,
    provider_id: UUID,
    delivery_mode: str,
    target_date: date,
    now: datetime | None = None,
) -> BookableSlotList:
    if not is_current_student(student):
        raise AppointmentCurrentStudentRequired(
            "Current Student lifecycle is required to discover bookable Appointment times."
        )
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    normalized_mode = _normalized_delivery_mode(delivery_mode)
    provider = User.objects.select_related("role").filter(pk=provider_id).first()
    if provider is None:
        raise AppointmentNotSchedulable("The selected Counselor is not available for booking.")
    _validate_booking_users(student, provider)
    service = Service.objects.filter(pk=service_id).first()
    if service is None:
        raise AppointmentNotSchedulable("The selected Service was not found.")
    _validate_booking_service(service, provider, normalized_mode)
    _validate_inventory_prerequisite(service, student)
    assert service.default_duration_minutes is not None
    duration = timedelta(minutes=service.default_duration_minutes)
    base = _base_slot_windows(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode=normalized_mode,
        target_date=target_date,
    )
    return BookableSlotList(
        date=target_date,
        timezone_name=base.timezone_name,
        duration_minutes=service.default_duration_minutes,
        items=_candidate_slots(
            windows=base.windows,
            duration=duration,
            provider_id=provider.pk,
            student_id=student.pk,
            now=current,
        ),
    )


def _clean_change_reason(value: str | None, *, required: bool) -> str:
    if value is None:
        if required:
            raise InvalidAppointmentInput("reason is required.")
        return ""
    if not isinstance(value, str):
        raise InvalidAppointmentInput("reason must be text.")
    cleaned = value.strip()
    if required and not cleaned:
        raise InvalidAppointmentInput("reason is required.")
    if len(cleaned) > MAX_CHANGE_REASON_LENGTH:
        raise InvalidAppointmentInput(
            f"reason must be at most {MAX_CHANGE_REASON_LENGTH} characters."
        )
    return cleaned


def _require_scheduled_before_start(item: Appointment, *, now: datetime) -> None:
    if item.status != AppointmentStatus.SCHEDULED:
        raise AppointmentLifecycleConflict("Only a SCHEDULED Appointment may be changed.")
    if now >= item.starts_at:
        raise AppointmentLifecycleConflict(
            "The Appointment can no longer be changed after it has started."
        )


def _require_management_access(*, actor: User, item: Appointment) -> None:
    if not appointment_management_access_allowed(actor, item):
        raise AppointmentNotFound("The requested Appointment was not found.")


def _validate_existing_service(
    *,
    service: Service,
    provider: User,
    delivery_mode: str,
) -> None:
    if not service.is_active or service.appointment_policy == AppointmentPolicy.NONE:
        raise AppointmentNotSchedulable(
            "The Appointment Service is no longer operationally schedulable."
        )
    if not provider.is_active or provider.role.code != "COUNSELOR":
        raise AppointmentNotSchedulable("The assigned provider is no longer an active Counselor.")
    if not service_supports_delivery_mode(service, delivery_mode):
        raise AppointmentNotSchedulable(
            "The Service no longer supports the Appointment delivery mode."
        )
    if not provider_role_eligible(service, provider):
        raise AppointmentNotSchedulable(
            "The assigned Counselor is no longer eligible for this Service."
        )


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
    if not is_current_student(student):
        raise AppointmentCurrentStudentRequired(
            "Current Student lifecycle is required to create a new Appointment."
        )
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
        if not is_current_student(locked_student):
            raise AppointmentCurrentStudentRequired(
                "Current Student lifecycle is required to create a new Appointment."
            )
        if provider_id is None:
            _validate_default_provider_still_current(locked_student, locked_provider)

        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise AppointmentNotSchedulable("The selected Service was not found.")
        _validate_booking_service(service, locked_provider, normalized_mode)
        _validate_inventory_prerequisite(service, locked_student)

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
        for recipient in (locked_student, locked_provider):
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.APPOINTMENT_SCHEDULED,
                source_type="appointment",
                source_id=appointment.pk,
                target_type="APPOINTMENT",
                target_id=appointment.pk,
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
            if not appointment_management_access_allowed(actor, item):
                raise AppointmentNotFound("The requested Appointment was not found.")
        elif actor.pk != item.student_id or not actor.is_active or actor.role.code != "STUDENT":
            raise AppointmentNotFound("The requested Appointment was not found.")

        if item.status == AppointmentStatus.CANCELLED:
            return _appointment_queryset().get(pk=item.pk)
        if item.status != AppointmentStatus.SCHEDULED:
            raise AppointmentCancellationConflict("Only a SCHEDULED Appointment may be cancelled.")
        if current >= item.starts_at:
            raise AppointmentCancellationConflict(
                "An Appointment cannot be cancelled after it has started."
            )
        if not administrative and item.cancellation_cutoff_minutes is not None:
            boundary = item.starts_at - timedelta(minutes=item.cancellation_cutoff_minutes)
            if current > boundary:
                raise AppointmentCancellationCutoffPassed(
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
        for recipient in (item.student, item.provider):
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.APPOINTMENT_CANCELLED,
                source_type="appointment",
                source_id=item.pk,
                target_type="APPOINTMENT",
                target_id=item.pk,
            )
        return _appointment_queryset().get(pk=item.pk)


def list_reschedule_slots(
    *,
    appointment_id: UUID,
    actor: User,
    target_date: date,
    administrative: bool,
    now: datetime | None = None,
) -> BookableSlotList:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    item = _appointment_queryset().filter(pk=appointment_id).first()
    if item is None:
        raise AppointmentNotFound("The requested Appointment was not found.")

    if administrative:
        _require_management_access(actor=actor, item=item)
    else:
        if (
            not actor.is_active
            or actor.role.code != "STUDENT"
            or actor.pk != item.student_id
            or not actor.has_capability("appointments.manage_self")
        ):
            raise AppointmentNotFound("The requested Appointment was not found.")
        if not is_current_student(actor):
            raise AppointmentCurrentStudentRequired(
                "Current Student lifecycle is required to reschedule an Appointment."
            )

    _require_scheduled_before_start(item, now=current)
    if not administrative and item.cancellation_cutoff_minutes is not None:
        boundary = item.starts_at - timedelta(minutes=item.cancellation_cutoff_minutes)
        if current > boundary:
            raise AppointmentLifecycleConflict("The Appointment reschedule cutoff has passed.")

    from compass.ecounseling.models import ECounselingRoom

    if ECounselingRoom.objects.filter(appointment_id=item.pk).exists():
        raise AppointmentLifecycleConflict(
            "This Appointment already has an E-Counseling room binding and cannot be rescheduled."
        )

    _validate_existing_service(
        service=item.service,
        provider=item.provider,
        delivery_mode=item.delivery_mode,
    )
    duration = item.ends_at - item.starts_at
    duration_minutes = int(duration.total_seconds() // 60)
    if duration_minutes <= 0 or duration != timedelta(minutes=duration_minutes):
        raise AppointmentNotSchedulable("The saved Appointment duration is invalid.")
    base = _base_slot_windows(
        provider_id=item.provider_id,
        service_id=item.service_id,
        delivery_mode=item.delivery_mode,
        target_date=target_date,
    )
    return BookableSlotList(
        date=target_date,
        timezone_name=base.timezone_name,
        duration_minutes=duration_minutes,
        items=_candidate_slots(
            windows=base.windows,
            duration=duration,
            provider_id=item.provider_id,
            student_id=item.student_id,
            now=current,
            exclude_appointment_id=item.pk,
        ),
    )


def reschedule_appointment(
    *,
    appointment_id: UUID,
    actor: User,
    starts_at: datetime,
    reason: str | None,
    administrative: bool,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    normalized_start = _aware_start(starts_at)
    if normalized_start <= current.astimezone(_institution_zone()):
        raise AppointmentNotSchedulable("Appointments must start in the future.")
    cleaned_reason = _clean_change_reason(reason, required=False)

    with transaction.atomic():
        item = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("student__role", "provider__role", "service")
            .filter(pk=appointment_id)
            .first()
        )
        if item is None:
            raise AppointmentNotFound("The requested Appointment was not found.")

        if administrative:
            _require_management_access(actor=actor, item=item)
        else:
            if (
                not actor.is_active
                or actor.role.code != "STUDENT"
                or actor.pk != item.student_id
                or not actor.has_capability("appointments.manage_self")
            ):
                raise AppointmentNotFound("The requested Appointment was not found.")

        _require_scheduled_before_start(item, now=current)

        # Serialize on the same participant rows as booking before checking overlaps.
        # Lock only Appointment above so joined Role and Service rows are not locked
        # incidentally or in a database-dependent order.
        participants = _lock_users(item.student_id, item.provider_id)
        locked_student = participants[item.student_id]
        locked_provider = participants[item.provider_id]
        if not administrative and not is_current_student(locked_student):
            raise AppointmentCurrentStudentRequired(
                "Current Student lifecycle is required to reschedule an Appointment."
            )

        if not administrative and item.cancellation_cutoff_minutes is not None:
            boundary = item.starts_at - timedelta(minutes=item.cancellation_cutoff_minutes)
            if current > boundary:
                raise AppointmentLifecycleConflict("The Appointment reschedule cutoff has passed.")

        from compass.ecounseling.models import ECounselingRoom

        if ECounselingRoom.objects.filter(appointment_id=item.pk).exists():
            raise AppointmentLifecycleConflict(
                "This Appointment already has an E-Counseling room binding "
                "and cannot be rescheduled."
            )

        service = Service.objects.select_for_update().get(pk=item.service_id)
        _validate_existing_service(
            service=service,
            provider=locked_provider,
            delivery_mode=item.delivery_mode,
        )
        duration = item.ends_at - item.starts_at
        new_ends_at = normalized_start + duration
        if not _interval_is_available(
            provider_id=item.provider_id,
            service_id=item.service_id,
            delivery_mode=item.delivery_mode,
            starts_at=normalized_start,
            ends_at=new_ends_at,
        ):
            raise AppointmentTimeUnavailable(
                "The full rescheduled interval is not contained in current Availability."
            )
        if _has_overlap(
            field="provider_id",
            user_id=item.provider_id,
            starts_at=normalized_start,
            ends_at=new_ends_at,
            exclude_appointment_id=item.pk,
        ):
            raise AppointmentTimeConflict("The Counselor already has an overlapping Appointment.")
        if _has_overlap(
            field="student_id",
            user_id=item.student_id,
            starts_at=normalized_start,
            ends_at=new_ends_at,
            exclude_appointment_id=item.pk,
        ):
            raise AppointmentTimeConflict("The Student already has an overlapping Appointment.")

        previous_starts_at = item.starts_at
        previous_ends_at = item.ends_at
        event = AppointmentChangeEvent.objects.create(
            appointment=item,
            event_type=AppointmentChangeEventType.RESCHEDULED,
            changed_by=actor,
            occurred_at=current,
            reason=cleaned_reason,
            previous_starts_at=previous_starts_at,
            previous_ends_at=previous_ends_at,
            new_starts_at=normalized_start,
            new_ends_at=new_ends_at,
        )
        item.starts_at = normalized_start
        item.ends_at = new_ends_at
        item.save(update_fields=["starts_at", "ends_at", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_RESCHEDULED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "previous_starts_at": previous_starts_at.isoformat(),
                "previous_ends_at": previous_ends_at.isoformat(),
                "new_starts_at": normalized_start.isoformat(),
                "new_ends_at": new_ends_at.isoformat(),
                "administrative": administrative,
            },
        )
        for recipient in (item.student, item.provider):
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.APPOINTMENT_RESCHEDULED,
                source_type="appointment_change_event",
                source_id=event.pk,
                target_type="APPOINTMENT",
                target_id=item.pk,
            )
        return _appointment_queryset().get(pk=item.pk)


def _require_reassignment_relationships_clear(item: Appointment) -> None:
    from compass.counseling.models import CounselingEncounter
    from compass.ecounseling.models import ECounselingRoom
    from compass.routine_interviews.models import RoutineInterview

    if RoutineInterview.objects.filter(appointment_id=item.pk).exists():
        raise AppointmentLifecycleConflict(
            "An Appointment with a Routine Interview cannot be reassigned."
        )
    if CounselingEncounter.objects.filter(appointment_id=item.pk).exists():
        raise AppointmentLifecycleConflict(
            "An Appointment with a Counseling Encounter cannot be reassigned."
        )
    if ECounselingRoom.objects.filter(appointment_id=item.pk).exists():
        raise AppointmentLifecycleConflict(
            "An Appointment with an E-Counseling room cannot be reassigned."
        )


def reassign_appointment(
    *,
    appointment_id: UUID,
    actor: User,
    provider_id: UUID,
    reason: str,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    cleaned_reason = _clean_change_reason(reason, required=True)

    with transaction.atomic():
        item = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("student__role", "provider__role", "service")
            .filter(pk=appointment_id)
            .first()
        )
        if item is None:
            raise AppointmentNotFound("The requested Appointment was not found.")
        _require_management_access(actor=actor, item=item)
        _require_scheduled_before_start(item, now=current)

        if provider_id == item.provider_id:
            return _appointment_queryset().get(pk=item.pk)

        _require_reassignment_relationships_clear(item)

        new_provider = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=provider_id)
            .first()
        )
        if new_provider is None:
            raise AppointmentNotSchedulable("The selected Counselor was not found.")
        service = Service.objects.select_for_update().get(pk=item.service_id)
        _validate_existing_service(
            service=service,
            provider=new_provider,
            delivery_mode=item.delivery_mode,
        )
        if not _interval_is_available(
            provider_id=new_provider.pk,
            service_id=item.service_id,
            delivery_mode=item.delivery_mode,
            starts_at=item.starts_at,
            ends_at=item.ends_at,
        ):
            raise AppointmentTimeUnavailable(
                "The selected Counselor is not available for the Appointment interval."
            )
        if _has_overlap(
            field="provider_id",
            user_id=new_provider.pk,
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            exclude_appointment_id=item.pk,
        ):
            raise AppointmentTimeConflict(
                "The selected Counselor already has an overlapping Appointment."
            )

        previous_provider = item.provider
        event = AppointmentChangeEvent.objects.create(
            appointment=item,
            event_type=AppointmentChangeEventType.REASSIGNED,
            changed_by=actor,
            occurred_at=current,
            reason=cleaned_reason,
            previous_provider=previous_provider,
            new_provider=new_provider,
        )
        item.provider = new_provider
        item.save(update_fields=["provider", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_REASSIGNED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "previous_provider_id": str(previous_provider.pk),
                "new_provider_id": str(new_provider.pk),
            },
        )
        for recipient in (item.student, previous_provider, new_provider):
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.APPOINTMENT_REASSIGNED,
                source_type="appointment_change_event",
                source_id=event.pk,
                target_type="APPOINTMENT",
                target_id=item.pk,
            )
        return _appointment_queryset().get(pk=item.pk)


def list_reassignment_candidates(
    *,
    appointment_id: UUID,
    actor: User,
    now: datetime | None = None,
) -> tuple[AppointmentReassignmentCandidate, ...]:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    item = _appointment_queryset().filter(pk=appointment_id).first()
    if item is None:
        raise AppointmentNotFound("The requested Appointment was not found.")
    _require_management_access(actor=actor, item=item)
    _require_scheduled_before_start(item, now=current)
    _require_reassignment_relationships_clear(item)
    _validate_existing_service(
        service=item.service,
        provider=item.provider,
        delivery_mode=item.delivery_mode,
    )

    candidates: list[AppointmentReassignmentCandidate] = []
    providers = (
        User.objects.filter(is_active=True, role__code="COUNSELOR")
        .exclude(pk=item.provider_id)
        .select_related("role")
        .order_by("last_name", "first_name", "id")
    )
    for provider in providers:
        if not provider_role_eligible(item.service, provider):
            continue
        if not _interval_is_available(
            provider_id=provider.pk,
            service_id=item.service_id,
            delivery_mode=item.delivery_mode,
            starts_at=item.starts_at,
            ends_at=item.ends_at,
        ):
            continue
        if _has_overlap(
            field="provider_id",
            user_id=provider.pk,
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            exclude_appointment_id=item.pk,
        ):
            continue
        candidates.append(AppointmentReassignmentCandidate(user=provider))
        if len(candidates) >= MAX_ELIGIBLE_COUNSELORS:
            break
    return tuple(candidates)


def complete_appointment(
    *,
    appointment_id: UUID,
    actor: User,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    with transaction.atomic():
        item = Appointment.objects.select_for_update().filter(pk=appointment_id).first()
        if item is None:
            raise AppointmentNotFound("The requested Appointment was not found.")
        _require_management_access(actor=actor, item=item)
        if item.status == AppointmentStatus.COMPLETED:
            return _appointment_queryset().get(pk=item.pk)
        if item.status != AppointmentStatus.SCHEDULED:
            raise AppointmentLifecycleConflict("Only a SCHEDULED Appointment may be completed.")
        if current < item.starts_at:
            raise AppointmentLifecycleConflict(
                "An Appointment cannot be completed before it starts."
            )
        item.status = AppointmentStatus.COMPLETED
        item.completed_at = current
        item.completed_by = actor
        item.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "transition": "SCHEDULED -> COMPLETED",
            },
        )
        return _appointment_queryset().get(pk=item.pk)


def mark_appointment_no_show(
    *,
    appointment_id: UUID,
    actor: User,
    context: AuditContext,
    now: datetime | None = None,
) -> Appointment:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidAppointmentInput("The server time must be timezone-aware.")
    with transaction.atomic():
        item = Appointment.objects.select_for_update().filter(pk=appointment_id).first()
        if item is None:
            raise AppointmentNotFound("The requested Appointment was not found.")
        _require_management_access(actor=actor, item=item)
        if item.status == AppointmentStatus.NO_SHOW:
            return _appointment_queryset().get(pk=item.pk)
        if item.status != AppointmentStatus.SCHEDULED:
            raise AppointmentLifecycleConflict(
                "Only a SCHEDULED Appointment may be marked NO_SHOW."
            )
        if current < item.ends_at:
            raise AppointmentLifecycleConflict(
                "An Appointment cannot be marked NO_SHOW before it ends."
            )

        from compass.counseling.models import CounselingEncounter

        if CounselingEncounter.objects.filter(appointment_id=item.pk).exists():
            raise AppointmentLifecycleConflict(
                "An Appointment with a Counseling Encounter cannot be marked NO_SHOW."
            )
        item.status = AppointmentStatus.NO_SHOW
        item.no_show_at = current
        item.no_show_by = actor
        item.save(update_fields=["status", "no_show_at", "no_show_by", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_NO_SHOW,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.appointment",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "transition": "SCHEDULED -> NO_SHOW",
            },
        )
        return _appointment_queryset().get(pk=item.pk)


def get_appointment_history(
    *,
    appointment_id: UUID,
    actor: User,
) -> tuple[AppointmentHistoryEntry, ...]:
    item = get_appointment_for_actor(appointment_id=appointment_id, actor=actor)
    manager_view = appointment_management_access_allowed(actor, item)
    entries: list[AppointmentHistoryEntry] = [
        AppointmentHistoryEntry(
            event_type="CREATED",
            occurred_at=item.created_at,
            actor=item.created_by,
            reason="",
        )
    ]
    events = (
        AppointmentChangeEvent.objects.filter(appointment_id=item.pk)
        .select_related("changed_by", "previous_provider", "new_provider")
        .order_by("occurred_at", "id")
    )
    for event in events:
        entries.append(
            AppointmentHistoryEntry(
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                actor=event.changed_by,
                reason=event.reason if manager_view else "",
                previous_starts_at=event.previous_starts_at,
                previous_ends_at=event.previous_ends_at,
                new_starts_at=event.new_starts_at,
                new_ends_at=event.new_ends_at,
                previous_provider=event.previous_provider,
                new_provider=event.new_provider,
            )
        )
    if item.status == AppointmentStatus.CANCELLED and item.cancelled_at is not None:
        entries.append(
            AppointmentHistoryEntry(
                event_type="CANCELLED",
                occurred_at=item.cancelled_at,
                actor=item.cancelled_by,
                reason="",
            )
        )
    elif item.status == AppointmentStatus.COMPLETED and item.completed_at is not None:
        entries.append(
            AppointmentHistoryEntry(
                event_type="COMPLETED",
                occurred_at=item.completed_at,
                actor=item.completed_by,
                reason="",
            )
        )
    elif item.status == AppointmentStatus.NO_SHOW and item.no_show_at is not None:
        entries.append(
            AppointmentHistoryEntry(
                event_type="NO_SHOW",
                occurred_at=item.no_show_at,
                actor=item.no_show_by,
                reason="",
            )
        )
    return tuple(sorted(entries, key=lambda row: row.occurred_at))


def list_eligible_counselors(
    *, student: User, service_id: UUID, delivery_mode: str
) -> tuple[EligibleCounselor, ...]:
    normalized_mode = _normalized_delivery_mode(delivery_mode)
    if not is_current_student(student):
        raise AppointmentCurrentStudentRequired(
            "Current Student lifecycle is required to discover booking Counselors."
        )
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


_ALLOWED = AppointmentActionState(allowed=True, blocker=None)


def _blocked(blocker: AppointmentActionBlocker) -> AppointmentActionState:
    return AppointmentActionState(allowed=False, blocker=blocker)


def _first_blocker(*checks: AppointmentActionBlocker | None) -> AppointmentActionState:
    for blocker in checks:
        if blocker is not None:
            return _blocked(blocker)
    return _ALLOWED


def appointment_actions_for(
    *,
    actor: User,
    item: Appointment,
    now: datetime | None = None,
) -> AppointmentActions:
    """Project which lifecycle actions the requesting actor may attempt right now.

    This mirrors the mutation rules using server time and linked records so clients do not
    offer impossible actions. It is advisory: every mutation still revalidates under locks.
    """

    from compass.counseling.models import CounselingEncounter
    from compass.ecounseling.models import ECounselingRoom
    from compass.routine_interviews.models import RoutineInterview

    current = now or timezone.now()
    self_mode = (
        actor.is_active
        and actor.role.code == "STUDENT"
        and actor.pk == item.student_id
        and actor.has_capability("appointments.manage_self")
    )
    manager = not self_mode and appointment_management_access_allowed(actor, item)
    denied = _blocked(AppointmentActionBlocker.NOT_PERMITTED)
    if not self_mode and not manager:
        return AppointmentActions(
            cancel=denied,
            reschedule=denied,
            reassign=denied,
            complete=denied,
            mark_no_show=denied,
        )

    scheduled = item.status == AppointmentStatus.SCHEDULED
    not_scheduled = None if scheduled else AppointmentActionBlocker.NOT_SCHEDULED
    started = AppointmentActionBlocker.ALREADY_STARTED if current >= item.starts_at else None
    cutoff = None
    if self_mode and item.cancellation_cutoff_minutes is not None:
        boundary = item.starts_at - timedelta(minutes=item.cancellation_cutoff_minutes)
        if current > boundary:
            cutoff = AppointmentActionBlocker.CUTOFF_PASSED

    room_linked = encounter_linked = routine_linked = None
    if scheduled:
        if ECounselingRoom.objects.filter(appointment_id=item.pk).exists():
            room_linked = AppointmentActionBlocker.ECOUNSELING_ROOM_LINKED
        if manager and CounselingEncounter.objects.filter(appointment_id=item.pk).exists():
            encounter_linked = AppointmentActionBlocker.COUNSELING_ENCOUNTER_LINKED
        if manager and RoutineInterview.objects.filter(appointment_id=item.pk).exists():
            routine_linked = AppointmentActionBlocker.ROUTINE_INTERVIEW_LINKED

    cancel = _first_blocker(not_scheduled, started, cutoff)
    if self_mode:
        lifecycle = (
            None if is_current_student(actor) else AppointmentActionBlocker.CURRENT_STUDENT_REQUIRED
        )
        return AppointmentActions(
            cancel=cancel,
            reschedule=_first_blocker(not_scheduled, started, lifecycle, cutoff, room_linked),
            reassign=denied,
            complete=denied,
            mark_no_show=denied,
        )
    return AppointmentActions(
        cancel=cancel,
        reschedule=_first_blocker(not_scheduled, started, room_linked),
        reassign=_first_blocker(
            not_scheduled, started, routine_linked, encounter_linked, room_linked
        ),
        complete=_first_blocker(
            not_scheduled,
            AppointmentActionBlocker.NOT_STARTED if current < item.starts_at else None,
        ),
        mark_no_show=_first_blocker(
            not_scheduled,
            AppointmentActionBlocker.NOT_ENDED if current < item.ends_at else None,
            encounter_linked,
        ),
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
