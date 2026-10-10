"""Due active permits under this domain's existing operational/Head scope."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Min

from .services import _active_operational_queryset


@dataclass(frozen=True, slots=True)
class DueCallSlipSummary:
    count: int
    oldest_due_at: datetime | None


def _due_queryset(*, actor, now):
    rows = _active_operational_queryset(actor)
    return None if rows is None else rows.filter(report_at__lte=now)


def due_call_slip_summary(*, actor, now) -> DueCallSlipSummary | None:
    rows = _due_queryset(actor=actor, now=now)
    if rows is None:
        return None
    return DueCallSlipSummary(**rows.aggregate(count=Count("pk"), oldest_due_at=Min("report_at")))


def due_call_slips(*, actor, now, limit):
    rows = _due_queryset(actor=actor, now=now)
    if rows is None:
        return ()
    return tuple(
        rows.select_related("student")
        .only(
            "id",
            "report_at",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by("report_at", "id")[:limit]
    )
