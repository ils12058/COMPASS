"""Institutional civil-time validation, also used when reading historical envelopes."""

from datetime import date, datetime, time, timedelta
from enum import StrEnum

from compass.common.institutional_time import institution_today, to_institution_time

from .confidential_content import validate_text
from .errors import InvalidReferralInput

MAX_WINDOWS = 5
MAX_NOTE_LENGTH = 500  # Provisional product default, not an institutional policy.
MAX_VALIDITY_DAYS = 180  # Provisional product default.


class ReferralTimingInformationType(StrEnum):
    STUDENT_AVAILABLE = "STUDENT_AVAILABLE"
    CLASS_RELEASE = "CLASS_RELEASE"


class ReferralTimingPattern(StrEnum):
    SPECIFIC_DATE = "SPECIFIC_DATE"
    RECURRING_WEEKDAY = "RECURRING_WEEKDAY"


class ReferralTimingWeekday(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"


class InvalidReferralTiming(InvalidReferralInput):
    def __init__(self, field, message):
        super().__init__("Check the timing information.")
        self.details = [
            {"loc": ["body", *map(str, field)], "message": message, "type": "referral_timing"}
        ]


def _invalid(field, message):
    raise InvalidReferralTiming(field, message)


def _date(value, field):
    try:
        parsed = value if type(value) is date else date.fromisoformat(value)
    except (TypeError, ValueError):
        _invalid(field, "Enter a valid date.")
    return parsed


def _time(value, field):
    try:
        parsed = value if isinstance(value, time) else time.fromisoformat(value)
    except (TypeError, ValueError):
        _invalid(field, "Enter a valid time in Philippine Time.")
    if parsed.tzinfo is not None:
        _invalid(field, "Use a local time in Philippine Time, without a timezone offset.")
    return parsed


def validate_timing_content(
    *, answer_kind, windows, note, verification=False, now=None, historical=False
):
    """Return an exact JSON payload. Historical reads retain expired windows."""
    none_kind = "NO_SUITABLE_TIME" if verification else "UNKNOWN"
    if answer_kind not in {"KNOWN", none_kind}:
        _invalid(["answer_kind"], "Choose known times or the unknown option.")
    if not isinstance(windows, list) or len(windows) > MAX_WINDOWS:
        _invalid(["windows"], "Provide at most five windows.")
    if answer_kind == "KNOWN" and not windows:
        _invalid(["windows"], "Add at least one window for known times.")
    if answer_kind == none_kind and windows:
        _invalid(["windows"], "Remove the windows when no time is known.")
    try:
        validate_text(note, label="Scheduling constraints note", max_length=MAX_NOTE_LENGTH)
    except InvalidReferralInput:
        _invalid(["note"], "Use plain text of at most 500 characters, without invalid characters.")
    if not verification and answer_kind == "UNKNOWN" and note:
        _invalid(["note"], "Add scheduling constraints only with known times.")
    today = institution_today(now)
    normalized = []
    seen = set()
    for index, window in enumerate(windows):
        field = ["windows", str(index)]
        required = {"information_type", "pattern", "start_time", "end_time"}
        if (
            not isinstance(window, dict)
            or not required.issubset(window)
            or set(window) - (required | {"date", "weekday", "valid_until"})
        ):
            _invalid(field, "Complete this timing window.")
        if window["information_type"] not in set(ReferralTimingInformationType):
            _invalid([*field, "information_type"], "Choose student availability or class release.")
        if window["pattern"] not in set(ReferralTimingPattern):
            _invalid([*field, "pattern"], "Choose a specific date or a recurring weekday.")
        start = _time(window["start_time"], [*field, "start_time"])
        end = _time(window["end_time"], [*field, "end_time"])
        if end <= start:
            _invalid([*field, "end_time"], "End time must be after start time.")
        value = {
            "information_type": str(window["information_type"]),
            "pattern": str(window["pattern"]),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "date": None,
            "weekday": None,
            "valid_until": None,
        }
        if window["pattern"] == "SPECIFIC_DATE":
            day = _date(window.get("date"), [*field, "date"])
            if not historical and day < today:
                _invalid([*field, "date"], "Date must be today or later in Philippine Time.")
            if window.get("weekday") is not None or window.get("valid_until") is not None:
                _invalid(
                    [*field, "pattern"],
                    "A specific date cannot also have a recurring weekday or validity date.",
                )
            value["date"] = day.isoformat()
        else:
            if window.get("weekday") not in set(ReferralTimingWeekday):
                _invalid([*field, "weekday"], "Choose Monday to Saturday.")
            until = _date(window.get("valid_until"), [*field, "valid_until"])
            if not historical and not today <= until <= today + timedelta(days=MAX_VALIDITY_DAYS):
                _invalid(
                    [*field, "valid_until"],
                    "Valid until must be today to 180 days ahead in Philippine Time.",
                )
            if window.get("date") is not None:
                _invalid([*field, "date"], "A recurring window cannot also have a specific date.")
            value.update(weekday=str(window["weekday"]), valid_until=until.isoformat())
        signature = tuple(value.values())
        if signature in seen:
            _invalid([*field, "start_time"], "This window duplicates another window.")
        seen.add(signature)
        normalized.append(value)
    return {"windows": normalized, "note": note}


def project_window(window, *, now):
    current = to_institution_time(now)
    expired = (
        datetime.combine(
            date.fromisoformat(window["date"]),
            time.fromisoformat(window["end_time"]),
            tzinfo=current.tzinfo,
        )
        <= current
        if window["pattern"] == "SPECIFIC_DATE"
        else date.fromisoformat(window["valid_until"]) < current.date()
    )
    return {**window, "expired": expired}
