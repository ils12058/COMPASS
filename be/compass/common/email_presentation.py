"""Small display-only primitives; domain field vocabularies remain source-owned."""

import re
from datetime import datetime
from enum import StrEnum

from django.utils import timezone

from .institutional_time import institution_timezone_name, to_institution_time


class EmailSourceEligibility(StrEnum):
    ALLOWED = "allowed"
    SOURCE_MISSING = "source_missing"
    SOURCE_STALE = "source_stale"
    SOURCE_SUPERSEDED = "source_superseded"
    RECIPIENT_DENIED = "recipient_denied"
    INVALID_SOURCE = "invalid_source"
    PROVENANCE_UNAVAILABLE = "provenance_unavailable"


_UNSAFE_DISPLAY = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://|\b(?:javascript|data|file|mailto):|www\.|@)", re.I
)


def safe_email_display_text(value: object) -> str | None:
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > 600
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or _UNSAFE_DISPLAY.search(value)
    ):
        return None
    return value.strip()


def valid_email_interval(start, end) -> bool:
    return bool(
        isinstance(start, datetime)
        and isinstance(end, datetime)
        and timezone.is_aware(start)
        and timezone.is_aware(end)
        and start < end
    )


def email_date(value: datetime) -> str:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise ValueError("invalid email date")
    local = to_institution_time(value)
    return f"{local:%A, %B} {local.day}, {local:%Y}"


def email_schedule(start: datetime, end: datetime) -> tuple[str, str]:
    if not valid_email_interval(start, end):
        raise ValueError("invalid appointment email interval")
    first, last = to_institution_time(start), to_institution_time(end)

    def clock(value):
        return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"

    zone = (
        "Philippine Time" if institution_timezone_name() == "Asia/Manila" else str(first.tzname())
    )
    dates = email_date(start)
    if first.date() != last.date():
        dates += f" – {email_date(end)}"
    return dates, f"{clock(first)}–{clock(last)} ({zone})"
