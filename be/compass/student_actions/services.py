"""Bounded sibling projection: sources own actionability; this module only composes."""

from datetime import UTC, datetime

from django.utils import timezone

from compass.accounts.models import User
from compass.call_slips.student_actions import live_instructions
from compass.ecounseling.student_actions import open_join_windows, pending_consents
from compass.exit_interviews.student_actions import editable_drafts, start_opportunity
from compass.graduate_tracer.student_actions import personal_draft
from compass.guidance_messages.student_actions import unread_threads
from compass.inventory.student_actions import current_action
from compass.routine_interviews.student_actions import pending_intakes

from .schemas import MAX_PAGE, MAX_PAGE_SIZE, StudentActionItem, StudentActionsResponse
from .schemas import StudentActionKind as Kind
from .schemas import StudentActionPriority as Priority


class StudentActionsAccessDenied(PermissionError):
    pass


def _item(
    kind,
    source_id,
    *,
    priority=Priority.ACTION_REQUIRED,
    due=None,
    waiting=None,
    conversation=None,
    count=None,
):
    return StudentActionItem(
        id=f"{kind.value.lower().replace('_', '-')}:{source_id}",
        kind=kind,
        priority=priority,
        source_id=source_id,
        due_at=due,
        waiting_since=waiting,
        conversation_kind=conversation,
        pending_count=count,
    )


def _rank(item):
    missing = datetime.max.replace(tzinfo=UTC)
    return (
        list(Priority).index(item.priority),
        item.due_at or missing,
        item.waiting_since or missing,
        item.id,
    )


def list_actions(*, actor, page=1, page_size=20):
    student = (
        User.objects.select_related("role")
        .only("id", "role", "is_active", "student_lifecycle_status")
        .filter(pk=getattr(actor, "pk", None), is_active=True)
        .first()
    )
    if student is None or student.role.code != "STUDENT":
        raise StudentActionsAccessDenied("An active Student account is required.")
    if (
        type(page) is not int
        or type(page_size) is not int
        or not 1 <= page <= MAX_PAGE
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise ValueError("Student Actions pagination is outside its supported bounds.")
    now = timezone.now()
    end = page * page_size
    limit = end + 1
    items = []
    inventory = current_action(student=student)
    if inventory is not None:
        draft = inventory.inventory
        items.append(
            _item(
                Kind.INVENTORY_CONTINUE if draft else Kind.INVENTORY_START,
                draft.pk if draft else inventory.academic_year.pk,
                priority=Priority.INCOMPLETE_SELF_SERVICE,
                waiting=draft.created_at if draft else None,
            )
        )
    opportunity = start_opportunity(student=student)
    if opportunity is not None:
        items.append(
            _item(Kind.EXIT_INTERVIEW_START, opportunity.pk, waiting=opportunity.opened_at)
        )
    for row in editable_drafts(student=student, limit=limit):
        items.append(_item(Kind(row.action_kind), row.pk, waiting=row.action_waiting_since))
    graduate = personal_draft(student=student)
    if graduate is not None:
        items.append(
            _item(
                Kind.GRADUATE_TRACER_CONTINUE,
                graduate.pk,
                priority=Priority.INCOMPLETE_SELF_SERVICE,
                waiting=graduate.created_at,
            )
        )
    items.extend(
        _item(Kind.ROUTINE_INTAKE, row.pk, waiting=row.created_at)
        for row in pending_intakes(student=student, limit=limit)
    )
    items.extend(
        _item(
            Kind.CALL_SLIP_ACTIVE,
            row.pk,
            due=row.report_at,
            waiting=row.created_at,
            priority=Priority.TIME_SENSITIVE if row.report_at <= now else Priority.ACTION_REQUIRED,
        )
        for row in live_instructions(student=student, now=now, limit=limit)
    )
    items.extend(
        _item(
            Kind.ECOUNSELING_CONSENT,
            row["room__appointment_id"],
            waiting=row["waiting_since"],
            count=row["pending_count"],
        )
        for row in pending_consents(student=student, limit=limit)
    )
    items.extend(
        _item(
            Kind.ECOUNSELING_JOIN,
            row.pk,
            priority=Priority.TIME_SENSITIVE,
            due=window.available_until,
            waiting=window.available_from,
        )
        for row, window in open_join_windows(student=student, now=now, limit=limit)
    )
    items.extend(
        _item(
            Kind.GUIDANCE_MESSAGE_UNREAD,
            row.pk,
            waiting=row.action_waiting_since,
            conversation=row.kind,
            count=row.own_unread_count,
        )
        for row in unread_threads(student=student, limit=limit)
    )
    # Unexpected failures propagate. Each correctly ordered N+1 prefix proves the global N+1.
    items.sort(key=_rank)
    return StudentActionsResponse(
        items=items[(page - 1) * page_size : end],
        page=page,
        page_size=page_size,
        has_next=len(items) > end,
        generated_at=now,
    )
