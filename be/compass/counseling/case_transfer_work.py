"""Bounded personal Head/receiver queues over the live arrangement, never task content."""

from django.db.models import F, Q

from compass.counseling.continuity_rules import is_head
from compass.work_queue.schemas import WorkItem, WorkKind, WorkPriority, WorkStudent

from .case_continuity_rules import receiver_eligible
from .case_transfer_models import CounselingCaseTransfer


def pending_transfer_work(*, actor, limit, now):
    if not actor.has_capability("counseling.continuity.view", at=now):
        return ()
    query = CounselingCaseTransfer.objects.filter(
        case__status="ACTIVE", case__primary_counselor_id=F("outgoing_counselor_id")
    ).select_related(
        "case__student",
        "case__primary_counselor",
        "prepared_by__role",
        "receiving_counselor__role",
        "case_handoff",
        "handoff_exception__recorded_by__role",
    )
    wanted = Q(pk__in=[])
    if receiver_eligible(actor, now) and actor.has_capability(
        "counseling.continuity.read_selected", at=now
    ):
        wanted |= Q(
            state="AUTHORIZED",
            receiving_counselor=actor,
            review_expires_at__gt=now,
            authorized_version=F("version"),
        )
    if is_head(actor) and actor.has_capability("counseling.continuity.approve", at=now):
        wanted |= (
            (
                Q(state="PREPARED", submitted_at__isnull=False)
                | Q(
                    state="PREPARED",
                    submitted_at__isnull=True,
                    case_handoff__isnull=True,
                    handoff_exception__isnull=True,
                    office_preparation_reason__in=["OWNER_UNAVAILABLE", "IMPARTIALITY_CONCERN"],
                )
            )
            & ~Q(prepared_by=actor)
            & ~Q(receiving_counselor=actor)
        )
    from .case_handoff_services import may_record_exception

    rows = query.filter(wanted).order_by("review_expires_at", "submitted_at", "pk")[:limit]
    rows = [row for row in rows if row.submitted_at or may_record_exception(actor, row, now)]
    return tuple(
        WorkItem(
            id=f"case-transfer:{row.pk}",
            kind=WorkKind.CASE_TRANSFER_ACCEPTANCE
            if row.state == "AUTHORIZED"
            else WorkKind.CASE_TRANSFER_AUTHORIZATION
            if row.submitted_at
            else WorkKind.CASE_HANDOFF_EXCEPTION,
            priority=WorkPriority.TIME_SENSITIVE
            if row.review_expires_at
            else WorkPriority.ACTION_REQUIRED,
            source_id=row.pk,
            student=WorkStudent(
                id=row.case.student_id, display_name=row.case.student.get_full_name()
            ),
            conversation_kind=None,
            due_at=row.review_expires_at,
            waiting_since=row.submitted_at,
            case_reference_code=row.case.reference_code,
        )
        for row in rows
    )
