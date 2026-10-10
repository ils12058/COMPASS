"""Office-wide preparation and Counselor-only issuance remain separate authorities."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Min

from .models import GoodMoralRequest, GoodMoralStatus
from .services import GoodMoralNotPermitted, _validate_counselor, _validate_operational


@dataclass(frozen=True, slots=True)
class RequestWorkSummary:
    count: int
    oldest_waiting_since: datetime | None


def _prefix(rows, *, waiting_field, limit):
    return tuple(
        rows.select_related("student")
        .only(
            "id",
            waiting_field,
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by(waiting_field, "id")[:limit]
    )


def _preparation_queryset(actor):
    try:
        _validate_operational(actor, "good_moral.prepare")
    except GoodMoralNotPermitted:
        return None
    return GoodMoralRequest.objects.filter(status=GoodMoralStatus.REQUESTED)


def _issuance_queryset(actor):
    try:
        _validate_counselor(actor, "good_moral.issue")
    except GoodMoralNotPermitted:
        return None
    return GoodMoralRequest.objects.filter(status=GoodMoralStatus.READY_FOR_ISSUANCE)


def preparation_requests(*, actor, limit):
    rows = _preparation_queryset(actor)
    return () if rows is None else _prefix(rows, waiting_field="created_at", limit=limit)


def issuance_requests(*, actor, limit):
    rows = _issuance_queryset(actor)
    return () if rows is None else _prefix(rows, waiting_field="prepared_at", limit=limit)


def preparation_summary(*, actor) -> RequestWorkSummary | None:
    rows = _preparation_queryset(actor)
    if rows is None:
        return None
    return RequestWorkSummary(
        **rows.aggregate(count=Count("pk"), oldest_waiting_since=Min("created_at"))
    )


def issuance_summary(*, actor) -> RequestWorkSummary | None:
    rows = _issuance_queryset(actor)
    if rows is None:
        return None
    return RequestWorkSummary(
        **rows.aggregate(count=Count("pk"), oldest_waiting_since=Min("prepared_at"))
    )
