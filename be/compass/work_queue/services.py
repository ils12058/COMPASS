"""Bounded composition only. Each source owns authorization and its actionable predicate."""

from datetime import UTC, datetime

from django.utils import timezone

from compass.accounts.models import User
from compass.call_slips.work import due_call_slips
from compass.good_moral.work import issuance_requests, preparation_requests
from compass.guidance_messages.work import reply_needed_threads
from compass.routine_interviews.work import pending_evaluations

from .schemas import (
    MAX_PAGE,
    MAX_PAGE_SIZE,
    WorkItem,
    WorkKind,
    WorkPriority,
    WorkQueueResponse,
    WorkStudent,
)


class WorkQueueAccessDenied(PermissionError):
    pass


def _item(kind, record, *, waiting=None, due=None, conversation=None):
    return WorkItem(
        id=f"{kind.value.lower().replace('_', '-')}:{record.pk}",
        kind=kind,
        priority=WorkPriority.TIME_SENSITIVE if due else WorkPriority.ACTION_REQUIRED,
        source_id=record.pk,
        student=WorkStudent(id=record.student_id, display_name=record.student.get_full_name()),
        conversation_kind=conversation,
        due_at=due,
        waiting_since=waiting,
    )


def _rank(item):
    missing = datetime.max.replace(tzinfo=UTC)
    return (
        0 if item.priority == WorkPriority.TIME_SENSITIVE else 1,
        item.due_at or missing,
        item.waiting_since or missing,
        item.id,
    )


def list_work(*, actor, page=1, page_size=20):
    actor = (
        User.objects.select_related("role")
        .filter(pk=getattr(actor, "pk", None), is_active=True)
        .first()
    )
    if actor is None or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}:
        raise WorkQueueAccessDenied("An active Guidance staff account is required.")
    if not 1 <= page <= MAX_PAGE or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError("Work Queue pagination is outside its supported bounds.")
    now = timezone.now()
    end = page * page_size
    limit = end + 1
    # Never count/load whole sources. N+1 from each ordered source proves the global N+1 prefix.
    # Unexpected source failures propagate: an incomplete projection cannot claim 'caught up'.
    items = [
        *(
            _item(
                WorkKind.GUIDANCE_MESSAGE_REPLY,
                row,
                waiting=row.last_message_at,
                conversation=row.kind,
            )
            for row in reply_needed_threads(actor=actor, limit=limit)
        ),
        *(
            _item(WorkKind.ROUTINE_EVALUATION, row, waiting=row.intake_submitted_at)
            for row in pending_evaluations(actor=actor, limit=limit)
        ),
        *(
            _item(WorkKind.GOOD_MORAL_PREPARATION, row, waiting=row.created_at)
            for row in preparation_requests(actor=actor, limit=limit)
        ),
        *(
            _item(WorkKind.GOOD_MORAL_ISSUANCE, row, waiting=row.prepared_at)
            for row in issuance_requests(actor=actor, limit=limit)
        ),
        *(
            _item(WorkKind.CALL_SLIP_DUE, row, due=row.report_at)
            for row in due_call_slips(actor=actor, now=now, limit=limit)
        ),
    ]
    items.sort(key=_rank)
    return WorkQueueResponse(
        items=items[(page - 1) * page_size : end],
        page=page,
        page_size=page_size,
        has_next=len(items) > end,
        generated_at=now,
    )
