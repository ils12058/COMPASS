"""Due active permits under this domain's existing operational/Head scope."""

from .models import CallSlip
from .services import CallSlipNotPermitted, _scope_queryset, _validate_operational_actor


def due_call_slips(*, actor, now, limit):
    try:
        _validate_operational_actor(actor)
    except CallSlipNotPermitted:
        return ()
    if not actor.has_capability("call_slips.view"):
        return ()
    return tuple(
        _scope_queryset(CallSlip.objects.all(), actor)
        .filter(voided_at__isnull=True, interview_ended_at__isnull=True, report_at__lte=now)
        .select_related("student")
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
