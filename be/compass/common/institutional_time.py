"""Canonical helpers for UCN institutional civil-time semantics."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone


def institution_timezone_name() -> str:
    """Return the configured IANA timezone used for UCN civil/business time."""

    return str(settings.INSTITUTION_TIME_ZONE)


def institution_zone() -> ZoneInfo:
    """Resolve the configured institutional zone or fail explicitly."""

    name = institution_timezone_name()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ImproperlyConfigured(
            "INSTITUTION_TIME_ZONE must be a valid IANA timezone"
        ) from exc


def to_institution_time(value: datetime) -> datetime:
    """Convert an aware instant to institutional civil time."""

    if timezone.is_naive(value):
        raise ValueError("institutional time conversion requires a timezone-aware datetime")
    return value.astimezone(institution_zone())


def institution_today(value: datetime | None = None) -> date:
    """Return the institutional calendar date for an aware instant or for now."""

    current = value or timezone.now()
    return to_institution_time(current).date()
