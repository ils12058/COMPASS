"""Metadata review packages; historical sources never gain another Counselor audience."""

from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.counseling.continuity_rules import is_head, is_office_requester, office_college_ids
from compass.guidance_followups import policy as task_policy
from compass.guidance_followups.content import decrypt_text

from . import case_continuity_rules as rules
from .case_models import CounselingCase
from .case_transfer_models import CounselingCaseTransferEvent
from .case_transfer_plans import case_tasks, disposition_allowed, upcoming_links
from .case_transfer_services import can_authorize, transfers


def person(row):
    return {"id": row.pk, "display_name": row.get_full_name()}


def case_identity(case):
    return {
        "id": case.pk,
        "reference_code": case.reference_code,
        "student": person(case.student),
        "primary_counselor": person(case.primary_counselor),
        "status": case.status,
        "version": case.version,
    }


def appointment_record_accessible(actor, appointment):
    from compass.appointments.services import AppointmentError, get_appointment_for_actor

    try:
        get_appointment_for_actor(actor=actor, appointment_id=appointment.pk)
    except AppointmentError:
        return False
    return True


def appointment_context(link, actor):
    appointment = link.appointment
    return {
        "link_id": link.pk,
        "appointment_id": appointment.pk,
        "reference_code": appointment.reference_code,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "status": appointment.status,
        "provider": person(appointment.provider),
        "record_accessible": appointment_record_accessible(actor, appointment),
    }


def transfer_context(*, actor, case_id, reason="SERVICE_RESPONSIBILITY_CHANGE"):
    actor = rules.current_actor(actor, "request")
    case = (
        CounselingCase.objects.select_related("student", "primary_counselor")
        .filter(pk=case_id)
        .first()
    )
    if case is None or not rules.may_prepare(actor, case):
        rules.fail("case_not_found", "The case is not available for this arrangement.", 404)
    if case.status != "ACTIVE":
        rules.fail("case_not_active", "Only an Active case can be transferred.")
    office = actor.pk != case.primary_counselor_id
    now = timezone.now()
    options = []
    for receiver in (
        User.objects.select_related("role")
        .filter(is_active=True, role__code="COUNSELOR")
        .exclude(pk=case.primary_counselor_id)
        .order_by("last_name", "first_name", "pk")
    ):
        if not rules.receiver_eligible(receiver, now):
            continue
        route, blocked = None, None
        try:
            route = rules.authorization_route(
                requester=actor, receiver=receiver, case=case, now=now
            )
        except rules.CaseContinuityError as exc:
            blocked = exc.message
        options.append(
            {"person": person(receiver), "authorization_route": route, "blocked_reason": blocked}
        )
    tasks = []
    for task in case_tasks(case).filter(status="PENDING").order_by("due_at", "pk"):
        readable = not office and task_policy.authorized(actor, task)
        tasks.append(
            {
                "task_id": task.pk,
                "version": task.version,
                "category": task.category,
                "source_kind": task.source_kind,
                "due_at": task.due_at,
                "assignee": person(task.assigned_to),
                "title": decrypt_text(task.pk, "title", task.title_ciphertext)
                if readable and task.title_ciphertext
                else None,
                "allowed_dispositions": list(
                    disposition_allowed(task, office=office, reason=reason, actor=actor)
                ),
                "record_accessible": readable,
            }
        )
    return {
        "case": case_identity(case),
        "office_prepared": office,
        "receiver_options": options,
        "tasks": tasks,
        "appointments": [
            appointment_context(link, actor)
            for link in upcoming_links(case, now).order_by("appointment__starts_at", "pk")
        ],
    }


def lookup_cases(*, actor, search=None, page=1, page_size=20):
    actor = rules.current_actor(actor, "request")
    if not is_office_requester(actor):
        rules.fail(
            "office_access_required",
            "This lookup is for authorized Guidance office preparation.",
            403,
        )
    if (
        not 1 <= page <= 1000
        or not 1 <= page_size <= 50
        or (search is not None and len(search) > 120)
    ):
        rules.fail("lookup_invalid", "Choose a valid search and page.", 422)
    query = CounselingCase.objects.filter(status="ACTIVE").select_related(
        "student", "primary_counselor"
    )
    if not is_head(actor):
        query = query.filter(
            student__student_academic_profile__current_college_id__in=office_college_ids(actor)
        )
    if search:
        query = query.filter(
            Q(reference_code__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )
    offset = (page - 1) * page_size
    rows = list(query.order_by("reference_code", "pk")[offset : offset + page_size + 1])
    return {
        "items": [case_identity(case) for case in rows[:page_size]],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }


def transfer_summary(item, now=None):
    state = rules.state_at(item, now)
    waiting = (
        "Head approval"
        if state == "PREPARED" and item.submitted_at
        else item.receiving_counselor.get_full_name()
        if state == "AUTHORIZED"
        else None
    )
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "state": state,
        "version": item.version,
        "receiving_counselor": person(item.receiving_counselor),
        "waiting_for": waiting,
        "review_expires_at": item.review_expires_at,
        "independent_authorization": item.independent_authorization,
        "authorization_route": item.authorization_route or None,
        "needs_new_arrangement": state in {"DECLINED", "CANCELLED", "EXPIRED"},
    }


def history_event(event):
    return {
        "id": event.pk,
        "transfer_id": event.transfer_id,
        "reference_code": event.transfer.reference_code,
        "kind": event.kind,
        "version": event.version,
        "actor": person(event.actor),
        "occurred_at": event.occurred_at,
        "independent_authorization": event.independent_authorization,
        "authorization_route": event.authorization_route or None,
    }


def transfer_detail(item, actor, *, result=False):
    actor = rules.current_actor(actor)
    item = transfers().get(pk=item.pk)
    now = timezone.now()
    state = rules.state_at(item, now)
    current = (
        item.case.status == "ACTIVE"
        and item.case.primary_counselor_id == item.outgoing_counselor_id
    )
    office = item.prepared_by_id != item.outgoing_counselor_id
    preparer = actor.pk == item.prepared_by_id
    receiver = actor.pk == item.receiving_counselor_id
    review = (
        current
        and state == "AUTHORIZED"
        and item.authorized_version == item.version
        and receiver
        and rules.receiver_eligible(actor, now)
        and actor.has_capability("counseling.continuity.read_selected", at=now)
    )
    edit = (
        current
        and preparer
        and state in {"PREPARED", "AUTHORIZED", "EXPIRED"}
        and actor.has_capability("counseling.continuity.request", at=now)
    )
    head = can_authorize(actor, item, now)
    package = state in {"PREPARED", "AUTHORIZED"} and current and (review or preparer or head)
    tasks, appointments = [], []
    if package:
        for plan in item.task_plans.select_related("task__student__role", "assignee"):
            readable = preparer and not office and task_policy.authorized(actor, plan.task)
            tasks.append(
                {
                    "task_id": plan.task_id,
                    "category": plan.task.category,
                    "source_kind": plan.source_kind,
                    "due_at": plan.due_at,
                    "assignee": person(plan.assignee),
                    "disposition": plan.disposition,
                    "successor_due_at": plan.successor_due_at,
                    "successor_title": decrypt_text(
                        plan.pk, "title", plan.successor_title_ciphertext
                    )
                    if readable and plan.successor_title_ciphertext
                    else None,
                    "title": decrypt_text(plan.task_id, "title", plan.task.title_ciphertext)
                    if readable and plan.task.title_ciphertext
                    else None,
                    "record_accessible": readable,
                }
            )
        for plan in item.appointment_plans.select_related(
            "link__appointment__provider", "link__appointment__service"
        ):
            appointments.append(
                {
                    **appointment_context(plan.link, actor),
                    "disposition": plan.disposition,
                    "retention_reason": plan.retention_reason or None,
                }
            )
    return {
        **transfer_summary(item, now),
        "case": case_identity(item.case),
        "outgoing_counselor": person(item.outgoing_counselor),
        "prepared_by": person(item.prepared_by),
        "office_prepared": office,
        "reason": item.reason,
        "office_preparation_reason": item.office_preparation_reason or None,
        "authorized_by": person(item.authorized_by) if item.authorized_by else None,
        "authorized_at": item.authorized_at,
        "decided_by": person(item.decided_by) if item.decided_by else None,
        "decided_at": item.decided_at,
        "decision_reason": "REVIEW_WINDOW_ENDED"
        if state == "EXPIRED"
        else item.decision_reason or None,
        "student_communication": item.student_communication,
        "student_informed_at": item.student_informed_at,
        "communication_recorded_by": person(item.communication_recorded_by),
        "communication_deferral_reason": item.communication_deferral_reason or None,
        "communication_task_id": item.communication_task_id
        if preparer or (state == "ACCEPTED" and item.case.primary_counselor_id == actor.pk)
        else None,
        "communication_responsible": person(item.communication_task.assigned_to)
        if item.communication_task
        else None,
        "tasks": tasks,
        "appointments": appointments,
        "history": [
            history_event(event) for event in item.history.select_related("actor", "transfer")
        ],
        "review_accessible": review,
        "can_edit": edit,
        "can_submit": edit and item.state == "PREPARED" and item.submitted_at is None,
        "can_authorize": head,
        "can_accept": review,
        "can_decline": review or head,
        "can_cancel": current
        and state in {"PREPARED", "AUTHORIZED"}
        and (
            preparer
            or (
                is_head(actor)
                and not receiver
                and actor.has_capability("counseling.continuity.revoke", at=now)
            )
        ),
        "can_open_case": item.case.primary_counselor_id == actor.pk
        and actor.has_capability("counseling.view_assigned", at=now),
    }


def case_continuity(case, actor):
    if case.primary_counselor_id != actor.pk:
        rules.fail("case_not_found", "The case was not found.", 404)
    items = tuple(transfers().filter(case=case))
    periods = list(
        case.responsibility_periods.select_related(
            "counselor", "transfer__outgoing_counselor"
        ).order_by("started_at", "pk")
    )
    first_owner = periods[0].transfer.outgoing_counselor if periods else case.primary_counselor
    responsibility = [
        {
            "counselor": person(first_owner),
            "started_at": case.opened_at,
            "ended_at": periods[0].started_at if periods else None,
            "transfer_id": None,
            "derived_opening": True,
        }
    ]
    responsibility += [
        {
            "counselor": person(period.counselor),
            "started_at": period.started_at,
            "ended_at": period.ended_at,
            "transfer_id": period.transfer_id,
            "derived_opening": False,
        }
        for period in periods
    ]
    history = (
        CounselingCaseTransferEvent.objects.filter(transfer__case=case)
        .select_related("actor", "transfer")
        .order_by("-occurred_at", "-pk")
    )
    return {
        "transfers": [transfer_summary(item) for item in items],
        "responsibility": responsibility,
        "history": [history_event(event) for event in history],
        "can_transfer": case.status == "ACTIVE"
        and actor.has_capability("counseling.manage_assigned")
        and actor.has_capability("counseling.continuity.request"),
    }
