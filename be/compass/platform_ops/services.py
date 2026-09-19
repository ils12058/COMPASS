"""Transactional Maintenance Mode services and effective-state derivation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from compass.audit.actions import (
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import (
    MAINTENANCE_MESSAGE_MAX_LENGTH,
    MAINTENANCE_SINGLETON_ID,
    MaintenanceConfiguration,
)

MAINTENANCE_TARGET_TYPE = "platform.maintenance"


class MaintenanceState(StrEnum):
    NORMAL = "NORMAL"
    SCHEDULED = "SCHEDULED"
    MAINTENANCE = "MAINTENANCE"


class MaintenanceSource(StrEnum):
    NONE = "NONE"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


@dataclass(frozen=True, slots=True)
class MaintenanceSnapshot:
    state: MaintenanceState
    source: MaintenanceSource
    message: str
    manual_expected_end_at: datetime | None
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    schedule_upcoming: bool
    schedule_active: bool


class MaintenanceError(RuntimeError):
    """Base class for expected Maintenance Mode failures."""


class MaintenanceAlreadyEnabled(MaintenanceError):
    """Manual Maintenance Mode is already enabled."""


class MaintenanceNotEnabled(MaintenanceError):
    """Manual Maintenance Mode is not enabled."""


class MaintenanceScheduleConflict(MaintenanceError):
    """The requested manual/scheduled state conflicts with current state."""


class MaintenanceScheduleNotFound(MaintenanceError):
    """No configured schedule exists to cancel."""


class InvalidMaintenanceWindow(MaintenanceError):
    """The requested maintenance message/window is invalid."""


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _clean_message(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidMaintenanceWindow("maintenance message must be a string")
    message = value.strip()
    if not message:
        raise InvalidMaintenanceWindow("maintenance message is required")
    if len(message) > MAINTENANCE_MESSAGE_MAX_LENGTH:
        raise InvalidMaintenanceWindow(
            f"maintenance message must be at most {MAINTENANCE_MESSAGE_MAX_LENGTH} characters"
        )
    return message


def _get_or_create_configuration() -> MaintenanceConfiguration:
    item, _created = MaintenanceConfiguration.objects.get_or_create(
        pk=MAINTENANCE_SINGLETON_ID
    )
    return item


def get_maintenance_configuration() -> MaintenanceConfiguration:
    return _get_or_create_configuration()


def derive_maintenance_snapshot(
    item: MaintenanceConfiguration,
    *,
    now: datetime | None = None,
) -> MaintenanceSnapshot:
    current = _normalize_datetime(now) or timezone.now()

    if item.manual_enabled:
        return MaintenanceSnapshot(
            state=MaintenanceState.MAINTENANCE,
            source=MaintenanceSource.MANUAL,
            message=item.manual_message,
            manual_expected_end_at=item.manual_expected_end_at,
            scheduled_start_at=item.scheduled_start_at,
            scheduled_end_at=item.scheduled_end_at,
            schedule_upcoming=False,
            schedule_active=False,
        )

    start = item.scheduled_start_at
    end = item.scheduled_end_at
    if start is not None and end is not None:
        if current < start:
            return MaintenanceSnapshot(
                state=MaintenanceState.SCHEDULED,
                source=MaintenanceSource.SCHEDULED,
                message=item.scheduled_message,
                manual_expected_end_at=None,
                scheduled_start_at=start,
                scheduled_end_at=end,
                schedule_upcoming=True,
                schedule_active=False,
            )
        if start <= current < end:
            return MaintenanceSnapshot(
                state=MaintenanceState.MAINTENANCE,
                source=MaintenanceSource.SCHEDULED,
                message=item.scheduled_message,
                manual_expected_end_at=None,
                scheduled_start_at=start,
                scheduled_end_at=end,
                schedule_upcoming=False,
                schedule_active=True,
            )

    return MaintenanceSnapshot(
        state=MaintenanceState.NORMAL,
        source=MaintenanceSource.NONE,
        message="",
        manual_expected_end_at=None,
        scheduled_start_at=None,
        scheduled_end_at=None,
        schedule_upcoming=False,
        schedule_active=False,
    )


def get_maintenance_snapshot(*, now: datetime | None = None) -> MaintenanceSnapshot:
    return derive_maintenance_snapshot(get_maintenance_configuration(), now=now)


def _locked_configuration() -> MaintenanceConfiguration:
    _get_or_create_configuration()
    return MaintenanceConfiguration.objects.select_for_update().get(
        pk=MAINTENANCE_SINGLETON_ID
    )


def _validate_model(item: MaintenanceConfiguration) -> None:
    try:
        item.full_clean(validate_unique=False)
    except ValidationError as exc:
        raise InvalidMaintenanceWindow("maintenance configuration is invalid") from exc


def enable_manual_maintenance(
    *,
    message: str,
    expected_end_at: datetime | None,
    context: AuditContext,
    now: datetime | None = None,
) -> MaintenanceSnapshot:
    current = _normalize_datetime(now) or timezone.now()
    cleaned_message = _clean_message(message)
    expected_end = _normalize_datetime(expected_end_at)

    with transaction.atomic():
        item = _locked_configuration()
        if item.manual_enabled:
            raise MaintenanceAlreadyEnabled("manual Maintenance Mode is already enabled")
        if item.scheduled_end_at is not None and item.scheduled_end_at > current:
            raise MaintenanceScheduleConflict(
                "cancel the current or upcoming maintenance schedule before enabling manual mode"
            )

        item.manual_enabled = True
        item.manual_message = cleaned_message
        item.manual_expected_end_at = expected_end
        _validate_model(item)
        item.save(
            update_fields=[
                "manual_enabled",
                "manual_message",
                "manual_expected_end_at",
                "updated_at",
            ]
        )
        metadata: dict[str, object] = {}
        if expected_end is not None:
            metadata["expected_end_at"] = expected_end.isoformat()
        record_event(
            context=context,
            action=PLATFORM_MAINTENANCE_ENABLED,
            outcome=AuditOutcome.SUCCESS,
            target_type=MAINTENANCE_TARGET_TYPE,
            target_id=MAINTENANCE_SINGLETON_ID,
            metadata=metadata,
        )
        return derive_maintenance_snapshot(item, now=current)


def disable_manual_maintenance(
    *,
    context: AuditContext,
    now: datetime | None = None,
) -> MaintenanceSnapshot:
    current = _normalize_datetime(now) or timezone.now()

    with transaction.atomic():
        item = _locked_configuration()
        if not item.manual_enabled:
            raise MaintenanceNotEnabled("manual Maintenance Mode is not enabled")

        item.manual_enabled = False
        item.manual_message = ""
        item.manual_expected_end_at = None
        _validate_model(item)
        item.save(
            update_fields=[
                "manual_enabled",
                "manual_message",
                "manual_expected_end_at",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=PLATFORM_MAINTENANCE_DISABLED,
            outcome=AuditOutcome.SUCCESS,
            target_type=MAINTENANCE_TARGET_TYPE,
            target_id=MAINTENANCE_SINGLETON_ID,
            metadata={},
        )
        return derive_maintenance_snapshot(item, now=current)


def schedule_maintenance(
    *,
    message: str,
    starts_at: datetime,
    ends_at: datetime,
    context: AuditContext,
    now: datetime | None = None,
) -> MaintenanceSnapshot:
    current = _normalize_datetime(now) or timezone.now()
    start = _normalize_datetime(starts_at)
    end = _normalize_datetime(ends_at)
    if start is None or end is None:
        raise InvalidMaintenanceWindow("scheduled start and end are required")
    cleaned_message = _clean_message(message)
    if end <= start:
        raise InvalidMaintenanceWindow("scheduled end must be after scheduled start")
    if start <= current:
        raise InvalidMaintenanceWindow("scheduled start must be in the future")

    with transaction.atomic():
        item = _locked_configuration()
        if item.manual_enabled:
            raise MaintenanceScheduleConflict(
                "disable manual Maintenance Mode before configuring a schedule"
            )
        existing = derive_maintenance_snapshot(item, now=current)
        if existing.schedule_active:
            raise MaintenanceScheduleConflict(
                "cancel the currently active maintenance schedule before replacing it"
            )

        item.scheduled_start_at = start
        item.scheduled_end_at = end
        item.scheduled_message = cleaned_message
        _validate_model(item)
        item.save(
            update_fields=[
                "scheduled_start_at",
                "scheduled_end_at",
                "scheduled_message",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=PLATFORM_MAINTENANCE_SCHEDULED,
            outcome=AuditOutcome.SUCCESS,
            target_type=MAINTENANCE_TARGET_TYPE,
            target_id=MAINTENANCE_SINGLETON_ID,
            metadata={
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
        )
        return derive_maintenance_snapshot(item, now=current)


def cancel_maintenance_schedule(
    *,
    context: AuditContext,
    now: datetime | None = None,
) -> MaintenanceSnapshot:
    current = _normalize_datetime(now) or timezone.now()

    with transaction.atomic():
        item = _locked_configuration()
        if item.scheduled_start_at is None or item.scheduled_end_at is None:
            raise MaintenanceScheduleNotFound("no maintenance schedule is configured")

        start = item.scheduled_start_at
        end = item.scheduled_end_at
        item.scheduled_start_at = None
        item.scheduled_end_at = None
        item.scheduled_message = ""
        _validate_model(item)
        item.save(
            update_fields=[
                "scheduled_start_at",
                "scheduled_end_at",
                "scheduled_message",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
            outcome=AuditOutcome.SUCCESS,
            target_type=MAINTENANCE_TARGET_TYPE,
            target_id=MAINTENANCE_SINGLETON_ID,
            metadata={
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
        )
        return derive_maintenance_snapshot(item, now=current)


__all__ = [
    "InvalidMaintenanceWindow",
    "MAINTENANCE_TARGET_TYPE",
    "MaintenanceAlreadyEnabled",
    "MaintenanceError",
    "MaintenanceNotEnabled",
    "MaintenanceScheduleConflict",
    "MaintenanceScheduleNotFound",
    "MaintenanceSnapshot",
    "MaintenanceSource",
    "MaintenanceState",
    "cancel_maintenance_schedule",
    "derive_maintenance_snapshot",
    "disable_manual_maintenance",
    "enable_manual_maintenance",
    "get_maintenance_configuration",
    "get_maintenance_snapshot",
    "schedule_maintenance",
]
