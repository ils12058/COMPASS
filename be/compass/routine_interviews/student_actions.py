"""Student intake prefixes use the same parent actionability as Routine mutations."""

from compass.accounts.services import is_current_student

from .models import RoutineInterview
from .services import actionable_parent_filter


def pending_intakes(*, student, limit):
    if not is_current_student(student) or not student.has_capability(
        "routine_interviews.manage_self"
    ):
        return ()
    return tuple(
        RoutineInterview.objects.filter(
            actionable_parent_filter(),
            student_id=student.pk,
            intake_submitted_at__isnull=True,
        )
        .only("id", "created_at")
        .order_by("created_at", "id")[:limit]
    )
