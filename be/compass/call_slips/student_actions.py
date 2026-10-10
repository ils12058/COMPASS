"""Only known LIVE Student instructions contribute, under canonical self authority."""

from django.db.models import Case, Value, When

from .models import CallSlip, CallSlipIssuanceMode
from .services import CallSlipNotPermitted, _validate_student_actor


def live_instructions(*, student, now, limit):
    try:
        _validate_student_actor(student)
    except CallSlipNotPermitted:
        return ()
    if not student.has_capability("call_slips.view_self"):
        return ()
    return tuple(
        CallSlip.objects.filter(
            student_id=student.pk,
            issuance_mode=CallSlipIssuanceMode.LIVE,
            interview_ended_at__isnull=True,
            voided_at__isnull=True,
        )
        .annotate(
            action_priority=Case(
                When(report_at__lte=now, then=Value(0)),
                default=Value(1),
            )
        )
        .only("id", "report_at", "created_at")
        .order_by(
            "action_priority",
            "report_at",
            "created_at",
            "id",
        )[:limit]
    )
