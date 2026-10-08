"""One source of demo time: a fixed academic calendar plus an anchor for recent activity.

Historical academic facts (Inventory periods, exit interviews, graduations) use fixed dates tied to
the dataset's Academic Year labels. Recent operational activity (appointments, referrals, call
slips) is placed on institutional business days before and after the anchor, which is the seed
run's institutional date. The only other time a run uses is its own start
(``SeedSession.started_at``), for records that genuinely happen during the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

HISTORICAL_ACADEMIC_YEARS = ("2024-2025", "2025-2026")
CURRENT_ACADEMIC_YEAR = "2026-2027"
DATASET_ACADEMIC_YEARS = (*HISTORICAL_ACADEMIC_YEARS, CURRENT_ACADEMIC_YEAR)

# Dataset version 2 describes the first semester of AY 2026-2027 onward. Before this window the
# current-year Inventory period would not yet be over; after it the graduating cast would already
# have graduated.
EARLIEST_ANCHOR = date(2026, 9, 21)
LATEST_ANCHOR = date(2027, 4, 30)

# Philippine non-working days that fall inside the anchor window. The demo only avoids them when
# placing activity; this is not an authoritative holiday calendar.
NON_WORKING_DAYS = frozenset(
    {
        date(2026, 11, 2),
        date(2026, 11, 30),
        date(2026, 12, 8),
        date(2026, 12, 24),
        date(2026, 12, 25),
        date(2026, 12, 30),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2027, 2, 25),
        date(2027, 3, 25),
        date(2027, 3, 26),
        date(2027, 4, 9),
    }
)


class DemoTimelineError(RuntimeError):
    """The requested anchor is outside the dataset's supported academic period."""


def institution_today() -> date:
    """The institutional date used as the default anchor; a narrow seam for tests."""

    return timezone.localdate()


def _is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in NON_WORKING_DAYS


def academic_semester(day: date) -> str:
    """The semester a dataset date falls in, worded the way a Student writes it on a request.

    The dataset's Academic Year runs August to May: August to December is the first semester and
    January to May the second. The anchor window never places activity in the midyear term.
    """

    if day.month >= 8:
        return "First"
    if day.month <= 5:
        return "Second"
    raise ValueError(f"{day.isoformat()} falls in the midyear term, outside the demo calendar")


@dataclass(frozen=True, slots=True)
class DemoTimeline:
    anchor: date
    zone: ZoneInfo

    def at(self, day: date, hour: int, minute: int = 0) -> datetime:
        return datetime.combine(day, time(hour, minute), tzinfo=self.zone)

    def on(self, year: int, month: int, day: int, hour: int = 9, minute: int = 0) -> datetime:
        """A fixed academic-calendar moment in the institutional timezone."""

        return self.at(date(year, month, day), hour, minute)

    def business_day(self, offset: int) -> date:
        """The ``offset``-th business day after (positive) or before (negative) the anchor."""

        if offset == 0:
            raise ValueError("demo activity never lands on the anchor day itself")
        step = timedelta(days=1 if offset > 0 else -1)
        remaining = abs(offset)
        day = self.anchor
        while remaining:
            day += step
            if _is_business_day(day):
                remaining -= 1
        return day

    def past(self, business_days: int, hour: int, minute: int = 0) -> datetime:
        return self.at(self.business_day(-business_days), hour, minute)

    def future(self, business_days: int, hour: int, minute: int = 0) -> datetime:
        return self.at(self.business_day(business_days), hour, minute)


def resolve_timeline(*, anchor: date | None = None) -> DemoTimeline:
    resolved = anchor or institution_today()
    if not EARLIEST_ANCHOR <= resolved <= LATEST_ANCHOR:
        raise DemoTimelineError(
            f"Demo dataset version 2 is anchored to Academic Year {CURRENT_ACADEMIC_YEAR}; seed it "
            f"between {EARLIEST_ANCHOR.isoformat()} and {LATEST_ANCHOR.isoformat()} "
            f"(institutional date is {resolved.isoformat()})."
        )
    return DemoTimeline(anchor=resolved, zone=ZoneInfo(settings.TIME_ZONE))


__all__ = [
    "CURRENT_ACADEMIC_YEAR",
    "DATASET_ACADEMIC_YEARS",
    "DemoTimeline",
    "DemoTimelineError",
    "EARLIEST_ANCHOR",
    "HISTORICAL_ACADEMIC_YEARS",
    "LATEST_ANCHOR",
    "academic_semester",
    "institution_today",
    "resolve_timeline",
]
