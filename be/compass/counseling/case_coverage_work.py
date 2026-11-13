"""The Head and receiver act from My work; recovery exposes no confidential task text."""

from django.db.models import F, Q

from compass.work_queue.schemas import WorkItem, WorkKind, WorkPriority, WorkStudent

from .case_continuity_rules import receiver_eligible
from .case_coverage_services import coverages
from .case_coverage_tasks import reconcile_returns
from .continuity_rules import is_head


def pending_coverage_work(*, actor, limit, now):
    if not actor.has_capability("counseling.continuity.view", at=now):
        return ()
    reconcile_returns(actor=actor)
    query = coverages().filter(case__status="ACTIVE")
    current = Q(case__primary_counselor_id=F("primary_counselor_id"))
    wanted = Q(pk__in=[])
    if receiver_eligible(actor, now) and actor.has_capability(
        "counseling.continuity.read_selected", at=now
    ):
        wanted |= current & Q(
            state="AUTHORIZED",
            receiving_counselor=actor,
            review_expires_at__gt=now,
            authorized_version=F("version"),
        )
        wanted |= current & Q(state="ACCEPTED", receiving_counselor=actor, expires_at__gt=now)
    if is_head(actor) and actor.has_capability("counseling.continuity.approve", at=now):
        wanted |= (
            current
            & Q(state="PREPARED", submitted_at__isnull=False, expires_at__gt=now)
            & ~Q(prepared_by=actor)
            & ~Q(receiving_counselor=actor)
        )
        if actor.has_capability("counseling.continuity.request", at=now):
            wanted |= Q(task_plans__recovery_required=True)
    rows = (
        query.filter(wanted).distinct().order_by("review_expires_at", "submitted_at", "pk")[:limit]
    )
    return tuple(
        WorkItem(
            id=f"case-coverage:{row.pk}",
            source_id=row.pk,
            kind=WorkKind.CASE_COVERAGE_RECOVERY
            if row.task_plans.filter(recovery_required=True).exists()
            else WorkKind.CASE_COVERAGE_AUTHORIZATION
            if row.state == "PREPARED"
            else WorkKind.CASE_COVERAGE_ACCEPTANCE
            if row.state == "AUTHORIZED"
            else WorkKind.CASE_COVERAGE_WORK,
            priority=WorkPriority.ACTION_REQUIRED
            if row.state == "PREPARED"
            else WorkPriority.TIME_SENSITIVE,
            student=WorkStudent(
                id=row.case.student_id, display_name=row.case.student.get_full_name()
            ),
            conversation_kind=None,
            due_at=row.review_expires_at
            if row.state == "AUTHORIZED"
            else row.starts_at
            if row.state == "ACCEPTED" and row.starts_at > now
            else row.expires_at,
            waiting_since=row.submitted_at,
            case_reference_code=row.case.reference_code,
        )
        for row in rows
    )
