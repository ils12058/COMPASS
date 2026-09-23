"""Transactional Availability use cases and pure interval calculation utilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    AVAILABILITY_OFFICE_EXCEPTION_CREATED,
    AVAILABILITY_OFFICE_EXCEPTION_REMOVED,
    AVAILABILITY_OFFICE_SCHEDULE_UPDATED,
    AVAILABILITY_PROVIDER_EXCEPTION_CREATED,
    AVAILABILITY_PROVIDER_EXCEPTION_REMOVED,
    AVAILABILITY_PROVIDER_SCHEDULE_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.models import DeliveryMode, Service
from compass.service_catalog.services import (
    ELIGIBLE_PROVIDER_ROLE_CODES,
    provider_role_eligible,
    service_supports_delivery_mode,
)

from .models import (
    AvailabilityModeScope,
    OfficeAvailabilityWindow,
    OfficeUnavailability,
    ProviderAvailabilityWindow,
    ProviderUnavailability,
    Weekday,
)

MAX_EFFECTIVE_QUERY_DAYS = 31
MAX_EXCEPTION_REASON_LENGTH = 255
DEFAULT_PROVIDER_PAGE_SIZE = 20
MAX_PROVIDER_PAGE_SIZE = 50
OFFICE_ADVISORY_LOCK_KEY = 1_127_914_579

WEEKDAY_TO_INDEX = {
    Weekday.MONDAY: 0,
    Weekday.TUESDAY: 1,
    Weekday.WEDNESDAY: 2,
    Weekday.THURSDAY: 3,
    Weekday.FRIDAY: 4,
    Weekday.SATURDAY: 5,
    Weekday.SUNDAY: 6,
}
INDEX_TO_WEEKDAY = {value: key for key, value in WEEKDAY_TO_INDEX.items()}


class AvailabilityError(RuntimeError):
    pass


class AvailabilityNotFound(AvailabilityError):
    pass


class InvalidAvailabilityInput(AvailabilityError):
    pass


class AvailabilityConflict(AvailabilityError):
    pass


class AvailabilityNotApplicable(AvailabilityError):
    pass


class AvailabilityRoleTransitionConflict(AvailabilityError):
    pass


@dataclass(frozen=True, slots=True, order=True)
class Interval:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedWeeklyWindow:
    weekday: str
    start_time: time
    end_time: time
    mode_scope: str


@dataclass(frozen=True, slots=True)
class BaseAvailabilityResult:
    provider_id: UUID
    service_id: UUID
    delivery_mode: str
    timezone_name: str
    start_date: date
    end_date: date
    windows: tuple[Interval, ...]


@dataclass(frozen=True, slots=True)
class AvailabilityProviderPage:
    items: tuple[User, ...]
    page: int
    page_size: int
    has_next: bool


def _mode_value(value: object) -> str:
    normalized = getattr(value, "value", value)
    if normalized not in AvailabilityModeScope.values:
        raise InvalidAvailabilityInput("mode_scope must be ALL, IN_PERSON, or ONLINE")
    return str(normalized)


def _delivery_mode_value(value: object) -> str:
    normalized = getattr(value, "value", value)
    if normalized not in DeliveryMode.values:
        raise InvalidAvailabilityInput("delivery_mode must be IN_PERSON or ONLINE")
    return str(normalized)


def _weekday_value(value: object) -> str:
    normalized = getattr(value, "value", value)
    if normalized not in Weekday.values:
        raise InvalidAvailabilityInput("weekday must be a canonical weekday name")
    return str(normalized)


def _local_wall_time(value: object, *, field_name: str) -> time:
    if not isinstance(value, time):
        raise InvalidAvailabilityInput(f"{field_name} must be a local wall-clock time")
    if value.tzinfo is not None and value.utcoffset() is not None:
        raise InvalidAvailabilityInput(f"{field_name} must not contain a timezone offset")
    return value.replace(tzinfo=None)


def _reason(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidAvailabilityInput("reason must be a string")
    cleaned = value.strip()
    if len(cleaned) > MAX_EXCEPTION_REASON_LENGTH:
        raise InvalidAvailabilityInput(
            f"reason must be at most {MAX_EXCEPTION_REASON_LENGTH} characters"
        )
    return cleaned


def _aware_range(starts_at: object, ends_at: object) -> tuple[datetime, datetime]:
    if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime):
        raise InvalidAvailabilityInput("starts_at and ends_at must be datetimes")
    if timezone.is_naive(starts_at) or timezone.is_naive(ends_at):
        raise InvalidAvailabilityInput("starts_at and ends_at must be timezone-aware")
    if starts_at >= ends_at:
        raise InvalidAvailabilityInput("starts_at must be earlier than ends_at")
    return starts_at, ends_at


def _scope_overlaps(left: str, right: str) -> bool:
    return left == AvailabilityModeScope.ALL or right == AvailabilityModeScope.ALL or left == right


def _scope_applies(scope: str, requested_mode: str) -> bool:
    return scope == AvailabilityModeScope.ALL or scope == requested_mode


def normalize_weekly_windows(
    values: Sequence[Mapping[str, object]],
) -> tuple[NormalizedWeeklyWindow, ...]:
    normalized: list[NormalizedWeeklyWindow] = []
    seen: set[NormalizedWeeklyWindow] = set()
    for value in values:
        if not isinstance(value, Mapping):
            raise InvalidAvailabilityInput("each weekly window must be an object")
        weekday = _weekday_value(value.get("weekday"))
        start_time = _local_wall_time(value.get("start_time"), field_name="start_time")
        end_time = _local_wall_time(value.get("end_time"), field_name="end_time")
        mode_scope = _mode_value(value.get("mode_scope"))
        if start_time >= end_time:
            raise InvalidAvailabilityInput("weekly start_time must be earlier than end_time")
        window = NormalizedWeeklyWindow(weekday, start_time, end_time, mode_scope)
        if window in seen:
            raise InvalidAvailabilityInput("weekly windows must not contain exact duplicates")
        for existing in normalized:
            if existing.weekday != weekday or not _scope_overlaps(existing.mode_scope, mode_scope):
                continue
            if existing.start_time < end_time and start_time < existing.end_time:
                raise InvalidAvailabilityInput(
                    "weekly windows must not overlap for the same delivery-mode context"
                )
        normalized.append(window)
        seen.add(window)
    normalized.sort(
        key=lambda item: (
            WEEKDAY_TO_INDEX[Weekday(item.weekday)],
            item.start_time,
            item.end_time,
            item.mode_scope,
        )
    )
    return tuple(normalized)


def _stored_weekly_windows(rows) -> tuple[NormalizedWeeklyWindow, ...]:
    values = [
        NormalizedWeeklyWindow(row.weekday, row.start_time, row.end_time, row.mode_scope)
        for row in rows
    ]
    values.sort(
        key=lambda item: (
            WEEKDAY_TO_INDEX[Weekday(item.weekday)],
            item.start_time,
            item.end_time,
            item.mode_scope,
        )
    )
    return tuple(values)


def _get_provider(provider_id: UUID, *, for_update: bool = False) -> User:
    queryset = User.objects.select_related("role")
    if for_update:
        queryset = queryset.select_for_update()
    provider = queryset.filter(pk=provider_id).first()
    if provider is None:
        raise AvailabilityNotFound("The requested provider was not found.")
    return provider


def _validate_provider_for_new_configuration(provider: User) -> None:
    if not provider.is_active:
        raise AvailabilityNotApplicable("An inactive provider cannot receive new Availability.")
    if provider.role.code not in ELIGIBLE_PROVIDER_ROLE_CODES:
        raise AvailabilityNotApplicable(
            "Availability may only be configured for Counselor providers."
        )


def list_availability_providers(
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PROVIDER_PAGE_SIZE,
) -> AvailabilityProviderPage:
    if type(page) is not int or page < 1:
        raise InvalidAvailabilityInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PROVIDER_PAGE_SIZE:
        raise InvalidAvailabilityInput(f"page_size must be between 1 and {MAX_PROVIDER_PAGE_SIZE}")

    term = ""
    if search is not None:
        if not isinstance(search, str):
            raise InvalidAvailabilityInput("search must be text")
        term = search.strip()[:254]

    legacy_gss = Q(role__code="GUIDANCE_SERVICES_STAFF") & (
        Q(availability_windows__isnull=False) | Q(unavailability_exceptions__isnull=False)
    )
    queryset = (
        User.objects.select_related("role")
        .filter(Q(role__code="COUNSELOR") | legacy_gss)
        .distinct()
        .order_by("last_name", "first_name", "id")
    )
    if term:
        queryset = queryset.filter(
            Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(email__icontains=term)
        )

    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return AvailabilityProviderPage(
        tuple(rows[:page_size]),
        page,
        page_size,
        len(rows) > page_size,
    )


def list_office_weekly() -> tuple[OfficeAvailabilityWindow, ...]:
    return tuple(
        OfficeAvailabilityWindow.objects.all().order_by(
            "weekday", "start_time", "end_time", "mode_scope", "id"
        )
    )


def list_provider_weekly(provider_id: UUID) -> tuple[ProviderAvailabilityWindow, ...]:
    _get_provider(provider_id)
    return tuple(
        ProviderAvailabilityWindow.objects.filter(provider_id=provider_id).order_by(
            "weekday", "start_time", "end_time", "mode_scope", "id"
        )
    )


def _lock_office_configuration() -> None:
    if connection.vendor != "postgresql":
        raise AvailabilityConflict("Office Availability mutation requires PostgreSQL.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [OFFICE_ADVISORY_LOCK_KEY])


def _actor_user(context: AuditContext) -> User | None:
    actor = context.actor_user
    return actor if isinstance(actor, User) else None


def replace_office_weekly(
    *,
    windows: Sequence[Mapping[str, object]],
    context: AuditContext,
) -> tuple[OfficeAvailabilityWindow, ...]:
    normalized = normalize_weekly_windows(windows)
    with transaction.atomic():
        _lock_office_configuration()
        existing_rows = tuple(OfficeAvailabilityWindow.objects.select_for_update().all())
        if _stored_weekly_windows(existing_rows) == normalized:
            return list_office_weekly()
        OfficeAvailabilityWindow.objects.all().delete()
        OfficeAvailabilityWindow.objects.bulk_create(
            [
                OfficeAvailabilityWindow(
                    weekday=item.weekday,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    mode_scope=item.mode_scope,
                )
                for item in normalized
            ]
        )
        record_event(
            context=context,
            action=AVAILABILITY_OFFICE_SCHEDULE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="availability.office",
            target_id="gco",
            metadata={"window_count": len(normalized)},
        )
    return list_office_weekly()


def replace_provider_weekly(
    *,
    provider_id: UUID,
    windows: Sequence[Mapping[str, object]],
    context: AuditContext,
) -> tuple[ProviderAvailabilityWindow, ...]:
    normalized = normalize_weekly_windows(windows)
    with transaction.atomic():
        provider = _get_provider(provider_id, for_update=True)
        if normalized:
            _validate_provider_for_new_configuration(provider)
        existing_rows = tuple(
            ProviderAvailabilityWindow.objects.select_for_update().filter(provider_id=provider.pk)
        )
        if _stored_weekly_windows(existing_rows) == normalized:
            return list_provider_weekly(provider.pk)
        ProviderAvailabilityWindow.objects.filter(provider_id=provider.pk).delete()
        ProviderAvailabilityWindow.objects.bulk_create(
            [
                ProviderAvailabilityWindow(
                    provider=provider,
                    weekday=item.weekday,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    mode_scope=item.mode_scope,
                )
                for item in normalized
            ]
        )
        record_event(
            context=context,
            action=AVAILABILITY_PROVIDER_SCHEDULE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=provider.pk,
            metadata={"provider_id": str(provider.pk), "window_count": len(normalized)},
        )
    return list_provider_weekly(provider.pk)


def list_office_exceptions() -> tuple[OfficeUnavailability, ...]:
    return tuple(
        OfficeUnavailability.objects.select_related("created_by").order_by(
            "starts_at", "ends_at", "id"
        )
    )


def create_office_exception(
    *,
    starts_at: datetime,
    ends_at: datetime,
    mode_scope: str,
    reason: str = "",
    context: AuditContext,
) -> OfficeUnavailability:
    starts_at, ends_at = _aware_range(starts_at, ends_at)
    normalized_scope = _mode_value(mode_scope)
    cleaned_reason = _reason(reason)
    with transaction.atomic():
        _lock_office_configuration()
        item = OfficeUnavailability.objects.create(
            starts_at=starts_at,
            ends_at=ends_at,
            mode_scope=normalized_scope,
            reason=cleaned_reason,
            created_by=_actor_user(context),
        )
        record_event(
            context=context,
            action=AVAILABILITY_OFFICE_EXCEPTION_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="availability.officeexception",
            target_id=item.pk,
            metadata={"mode_scope": normalized_scope},
        )
    return item


def remove_office_exception(*, exception_id: UUID, context: AuditContext) -> bool:
    with transaction.atomic():
        _lock_office_configuration()
        item = OfficeUnavailability.objects.select_for_update().filter(pk=exception_id).first()
        if item is None:
            return False
        mode_scope = item.mode_scope
        item.delete()
        record_event(
            context=context,
            action=AVAILABILITY_OFFICE_EXCEPTION_REMOVED,
            outcome=AuditOutcome.SUCCESS,
            target_type="availability.officeexception",
            target_id=exception_id,
            metadata={"mode_scope": mode_scope},
        )
    return True


def list_provider_exceptions(provider_id: UUID) -> tuple[ProviderUnavailability, ...]:
    _get_provider(provider_id)
    return tuple(
        ProviderUnavailability.objects.filter(provider_id=provider_id)
        .select_related("created_by")
        .order_by("starts_at", "ends_at", "id")
    )


def create_provider_exception(
    *,
    provider_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    mode_scope: str,
    reason: str = "",
    context: AuditContext,
) -> ProviderUnavailability:
    starts_at, ends_at = _aware_range(starts_at, ends_at)
    normalized_scope = _mode_value(mode_scope)
    cleaned_reason = _reason(reason)
    with transaction.atomic():
        provider = _get_provider(provider_id, for_update=True)
        _validate_provider_for_new_configuration(provider)
        item = ProviderUnavailability.objects.create(
            provider=provider,
            starts_at=starts_at,
            ends_at=ends_at,
            mode_scope=normalized_scope,
            reason=cleaned_reason,
            created_by=_actor_user(context),
        )
        record_event(
            context=context,
            action=AVAILABILITY_PROVIDER_EXCEPTION_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="availability.providerexception",
            target_id=item.pk,
            metadata={"provider_id": str(provider.pk), "mode_scope": normalized_scope},
        )
    return item


def remove_provider_exception(
    *,
    exception_id: UUID,
    context: AuditContext,
    provider_id: UUID | None = None,
) -> bool:
    candidate = ProviderUnavailability.objects.filter(pk=exception_id).values("provider_id").first()
    if candidate is None:
        return False
    actual_provider_id = candidate["provider_id"]
    if provider_id is not None and actual_provider_id != provider_id:
        return False
    with transaction.atomic():
        _get_provider(actual_provider_id, for_update=True)
        item = ProviderUnavailability.objects.select_for_update().filter(pk=exception_id).first()
        if item is None or (provider_id is not None and item.provider_id != provider_id):
            return False
        target_provider_id = item.provider_id
        mode_scope = item.mode_scope
        item.delete()
        record_event(
            context=context,
            action=AVAILABILITY_PROVIDER_EXCEPTION_REMOVED,
            outcome=AuditOutcome.SUCCESS,
            target_type="availability.providerexception",
            target_id=exception_id,
            metadata={"provider_id": str(target_provider_id), "mode_scope": mode_scope},
        )
    return True


def normalize_intervals(intervals: Sequence[Interval]) -> tuple[Interval, ...]:
    ordered = sorted(intervals, key=lambda item: (item.starts_at, item.ends_at))
    merged: list[Interval] = []
    for interval in ordered:
        if interval.starts_at >= interval.ends_at:
            continue
        if not merged or interval.starts_at > merged[-1].ends_at:
            merged.append(interval)
            continue
        if interval.ends_at > merged[-1].ends_at:
            merged[-1] = Interval(merged[-1].starts_at, interval.ends_at)
    return tuple(merged)


def intersect_intervals(
    left: Sequence[Interval], right: Sequence[Interval]
) -> tuple[Interval, ...]:
    left_items = normalize_intervals(left)
    right_items = normalize_intervals(right)
    result: list[Interval] = []
    i = 0
    j = 0
    while i < len(left_items) and j < len(right_items):
        start = max(left_items[i].starts_at, right_items[j].starts_at)
        end = min(left_items[i].ends_at, right_items[j].ends_at)
        if start < end:
            result.append(Interval(start, end))
        if left_items[i].ends_at <= right_items[j].ends_at:
            i += 1
        else:
            j += 1
    return tuple(result)


def subtract_intervals(
    base: Sequence[Interval], exclusions: Sequence[Interval]
) -> tuple[Interval, ...]:
    current = list(normalize_intervals(base))
    for exclusion in normalize_intervals(exclusions):
        next_items: list[Interval] = []
        for interval in current:
            if exclusion.ends_at <= interval.starts_at or exclusion.starts_at >= interval.ends_at:
                next_items.append(interval)
                continue
            if interval.starts_at < exclusion.starts_at:
                next_items.append(Interval(interval.starts_at, exclusion.starts_at))
            if exclusion.ends_at < interval.ends_at:
                next_items.append(Interval(exclusion.ends_at, interval.ends_at))
        current = next_items
    return tuple(current)


def _institution_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise AvailabilityConflict("The configured institutional timezone is unavailable.") from exc


def expand_weekly_windows(
    windows: Sequence[NormalizedWeeklyWindow],
    *,
    start_date: date,
    end_date: date,
    timezone_name: str | None = None,
) -> tuple[Interval, ...]:
    try:
        zone = ZoneInfo(timezone_name or settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise AvailabilityConflict("The configured institutional timezone is unavailable.") from exc
    result: list[Interval] = []
    day = start_date
    by_weekday: dict[str, list[NormalizedWeeklyWindow]] = {}
    for window in windows:
        by_weekday.setdefault(window.weekday, []).append(window)
    while day < end_date:
        weekday = INDEX_TO_WEEKDAY[day.weekday()].value
        for window in by_weekday.get(weekday, []):
            result.append(
                Interval(
                    datetime.combine(day, window.start_time, tzinfo=zone),
                    datetime.combine(day, window.end_time, tzinfo=zone),
                )
            )
        day += timedelta(days=1)
    return normalize_intervals(result)


def _validate_query_range(start_date: date, end_date: date) -> None:
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise InvalidAvailabilityInput("start_date and end_date are required")
    if start_date >= end_date:
        raise InvalidAvailabilityInput("start_date must be earlier than end_date")
    if (end_date - start_date).days > MAX_EFFECTIVE_QUERY_DAYS:
        raise InvalidAvailabilityInput(
            f"Availability queries may cover at most {MAX_EFFECTIVE_QUERY_DAYS} days"
        )


def _mode_windows(rows, requested_mode: str) -> tuple[NormalizedWeeklyWindow, ...]:
    return _stored_weekly_windows(
        [row for row in rows if _scope_applies(row.mode_scope, requested_mode)]
    )


def _exception_intervals(queryset, requested_mode: str) -> tuple[Interval, ...]:
    return normalize_intervals(
        [
            Interval(item.starts_at, item.ends_at)
            for item in queryset
            if _scope_applies(item.mode_scope, requested_mode)
        ]
    )


def compute_base_availability(
    *,
    provider_id: UUID,
    service_id: UUID,
    delivery_mode: str,
    start_date: date,
    end_date: date,
) -> BaseAvailabilityResult:
    _validate_query_range(start_date, end_date)
    requested_mode = _delivery_mode_value(delivery_mode)
    provider = _get_provider(provider_id)
    service = Service.objects.filter(pk=service_id).first()
    if service is None:
        raise AvailabilityNotFound("The requested Service was not found.")
    if not provider.is_active or provider.role.code not in ELIGIBLE_PROVIDER_ROLE_CODES:
        raise AvailabilityNotApplicable("The requested provider is not operationally available.")
    if not service.is_active:
        raise AvailabilityNotApplicable("The requested Service is inactive.")
    if not service_supports_delivery_mode(service, requested_mode):
        raise AvailabilityNotApplicable("The Service does not support the requested delivery mode.")
    if not provider_role_eligible(service, provider):
        raise AvailabilityNotApplicable("The provider role is not eligible for this Service.")

    zone = _institution_zone()
    range_start = datetime.combine(start_date, time.min, tzinfo=zone)
    range_end = datetime.combine(end_date, time.min, tzinfo=zone)

    provider_rows = list(ProviderAvailabilityWindow.objects.filter(provider_id=provider.pk))
    office_rows = list(OfficeAvailabilityWindow.objects.all())
    provider_intervals = expand_weekly_windows(
        _mode_windows(provider_rows, requested_mode),
        start_date=start_date,
        end_date=end_date,
        timezone_name=settings.TIME_ZONE,
    )
    office_intervals = expand_weekly_windows(
        _mode_windows(office_rows, requested_mode),
        start_date=start_date,
        end_date=end_date,
        timezone_name=settings.TIME_ZONE,
    )
    available = intersect_intervals(provider_intervals, office_intervals)

    office_exceptions = OfficeUnavailability.objects.filter(
        starts_at__lt=range_end,
        ends_at__gt=range_start,
    ).filter(Q(mode_scope=AvailabilityModeScope.ALL) | Q(mode_scope=requested_mode))
    provider_exceptions = ProviderUnavailability.objects.filter(
        provider_id=provider.pk,
        starts_at__lt=range_end,
        ends_at__gt=range_start,
    ).filter(Q(mode_scope=AvailabilityModeScope.ALL) | Q(mode_scope=requested_mode))
    available = subtract_intervals(
        available,
        _exception_intervals(tuple(office_exceptions), requested_mode),
    )
    available = subtract_intervals(
        available,
        _exception_intervals(tuple(provider_exceptions), requested_mode),
    )

    clipped: list[Interval] = []
    for interval in available:
        starts_at = max(interval.starts_at, range_start)
        ends_at = min(interval.ends_at, range_end)
        if starts_at < ends_at:
            clipped.append(Interval(starts_at, ends_at))
    available = tuple(
        Interval(
            interval.starts_at.astimezone(zone),
            interval.ends_at.astimezone(zone),
        )
        for interval in normalize_intervals(clipped)
    )

    if service.default_duration_minutes is not None:
        minimum = timedelta(minutes=service.default_duration_minutes)
        available = tuple(
            interval for interval in available if interval.ends_at - interval.starts_at >= minimum
        )

    return BaseAvailabilityResult(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode=requested_mode,
        timezone_name=settings.TIME_ZONE,
        start_date=start_date,
        end_date=end_date,
        windows=tuple(available),
    )


def validate_role_transition(*, user: User, new_role_code: str) -> None:
    if user.role.code == new_role_code:
        return
    if user.role.code not in ELIGIBLE_PROVIDER_ROLE_CODES:
        return
    if new_role_code in ELIGIBLE_PROVIDER_ROLE_CODES:
        return
    if ProviderAvailabilityWindow.objects.filter(provider_id=user.pk).exists():
        raise AvailabilityRoleTransitionConflict(
            "Remove the provider's recurring Availability before changing to a non-provider role."
        )
    if ProviderUnavailability.objects.filter(provider_id=user.pk).exists():
        raise AvailabilityRoleTransitionConflict(
            "Remove the provider's unavailability exceptions before changing "
            "to a non-provider role."
        )
