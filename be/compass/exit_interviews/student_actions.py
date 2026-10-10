"""Exit opportunity and admitted owned drafts, including historical corrections."""

from django.db.models import Case, CharField, F, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce

from compass.accounts.services import is_current_student

from .models import ExitInterview, ExitInterviewReopenEvent, ExitInterviewStatus
from .opportunities import get_my_status
from .services import admitted_draft_filter


def start_opportunity(*, student):
    if not is_current_student(student) or not student.has_capability("exit_interviews.manage_self"):
        return None
    status = get_my_status(student, structural=True)
    return status["opportunity"] if status["can_start"] else None


def editable_drafts(*, student, limit):
    if not is_current_student(student) or not student.has_capability("exit_interviews.manage_self"):
        return ()
    reopened = (
        ExitInterviewReopenEvent.objects.filter(exit_interview_id=OuterRef("pk"))
        .order_by("-reopened_at", "-id")
        .values("reopened_at")[:1]
    )
    return tuple(
        ExitInterview.objects.filter(
            admitted_draft_filter(),
            student_id=student.pk,
            status=ExitInterviewStatus.DRAFT,
        )
        .annotate(
            action_waiting_since=Case(
                When(
                    first_submitted_at__isnull=False,
                    then=Coalesce(Subquery(reopened), F("created_at")),
                ),
                default=F("created_at"),
            ),
            action_kind=Case(
                When(first_submitted_at__isnull=False, then=Value("EXIT_INTERVIEW_CORRECTION")),
                default=Value("EXIT_INTERVIEW_CONTINUE"),
                output_field=CharField(),
            ),
        )
        .only("id")
        .order_by("action_waiting_since", "action_kind", "id")[:limit]
    )
