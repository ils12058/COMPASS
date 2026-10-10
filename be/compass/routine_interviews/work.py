"""The assigned Counselor's actionable evaluation prefix, without confidential content."""

from compass.appointments.models import AppointmentStatus

from .models import RoutineInterview
from .services import RoutineInterviewNotPermitted, _validate_counselor


def pending_evaluations(*, actor, limit):
    try:
        _validate_counselor(actor)
    except RoutineInterviewNotPermitted:
        return ()
    if not all(
        actor.has_capability(code)
        for code in ("routine_interviews.view_assigned", "routine_interviews.manage_assigned")
    ):
        return ()
    return tuple(
        RoutineInterview.objects.filter(
            counselor_id=actor.pk,
            intake_submitted_at__isnull=False,
            evaluation_finalized_at__isnull=True,
        )
        .exclude(appointment__status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
        .select_related("student")
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
