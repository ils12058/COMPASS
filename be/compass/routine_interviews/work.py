"""The assigned Counselor's actionable evaluation prefix, without confidential content."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Min

from .services import _pending_evaluation_queryset


@dataclass(frozen=True, slots=True)
class PendingEvaluationSummary:
    count: int
    oldest_waiting_since: datetime | None


def pending_evaluation_summary(*, actor) -> PendingEvaluationSummary | None:
    rows = _pending_evaluation_queryset(actor)
    if rows is None:
        return None
    return PendingEvaluationSummary(
        **rows.aggregate(count=Count("pk"), oldest_waiting_since=Min("intake_submitted_at"))
    )


def pending_evaluations(*, actor, limit):
    rows = _pending_evaluation_queryset(actor)
    if rows is None:
        return ()
    return tuple(
        rows.select_related("student")
        .only(
            "id",
            "intake_submitted_at",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by("intake_submitted_at", "id")[:limit]
    )
