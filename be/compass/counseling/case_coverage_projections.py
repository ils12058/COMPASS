"""Audience-bound case coverage facts and a separate, read-only acceptance package."""

from django.utils import timezone

from compass.accounts.models import User
from compass.guidance_followups import policy as task_policy
from compass.guidance_followups.content import decrypt_text
from compass.guidance_followups.models import GuidanceFollowUp

from . import case_continuity_rules as rules
from .case_coverage_services import (
    can_authorize,
    can_revoke,
    get_coverage,
    state_at,
    task_can_delegate,
)
from .case_coverage_tasks import effective_assignee, reconcile_returns
from .case_models import CounselingCase
from .case_transfer_projections import case_identity, person
from .continuity_rules import is_head


def coverage_context(*, actor, case_id):
    actor = rules.current_actor(actor, "request")
    case = (
        CounselingCase.objects.select_related("student", "primary_counselor__role")
        .filter(pk=case_id)
        .first()
    )
    if case is None or not rules.may_prepare(actor, case):
        rules.fail("case_not_found", "The case is not available for this arrangement.", 404)
    if case.status != "ACTIVE":
        rules.fail("case_not_active", "Only an Active case can have coverage.")
    reconcile_returns(case_id=case.pk, actor=actor)
    office = actor.pk != case.primary_counselor_id
    now = timezone.now()
    options = []
    for receiver in (
        User.objects.select_related("role")
        .filter(
            is_active=True,
            role__code="COUNSELOR",
        )
        .exclude(pk=case.primary_counselor_id)
        .order_by("last_name", "first_name", "pk")
    ):
        if not rules.receiver_eligible(receiver, now):
            continue
        route = blocked = None
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
    for task in (
        GuidanceFollowUp.objects.select_related("student__role", "assigned_to__role")
        .filter(
            case=case,
            status="PENDING",
        )
        .order_by("due_at", "pk")
    ):
        readable = (
            not office
            and actor.has_capability("guidance_followups.view", at=now)
            and task_policy.authorized(actor, task)
        )
        allowed = task_can_delegate(task, case.primary_counselor, now=now)
        tasks.append(
            {
                "task_id": task.pk,
                "version": task.version,
                "category": task.category,
                "source_kind": task.source_kind,
                "due_at": task.due_at,
                "assignee": person(effective_assignee(task)),
                "title": decrypt_text(task.pk, "title", task.title_ciphertext)
                if readable and task.title_ciphertext
                else None,
                "record_accessible": readable,
                "can_delegate": allowed,
                "blocked_reason": None
                if allowed
                else "This task needs its current source or case responsibility resolved first.",
            }
        )
    return {
        "case": case_identity(case),
        "office_prepared": office,
        "receiver_options": options,
        "tasks": tasks,
    }


def summary(item, now=None):
    now = now or timezone.now()
    state = state_at(item, now)
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "state": state,
        "version": item.version,
        "receiving_counselor": person(item.receiving_counselor),
        "starts_at": item.starts_at,
        "expires_at": item.expires_at,
        "waiting_for": "HEAD"
        if state == "PREPARED" and item.submitted_at
        else "REQUESTER"
        if state == "PREPARED"
        else "RECEIVER"
        if state == "AUTHORIZED"
        else None,
        "review_expires_at": item.review_expires_at,
        "independent_authorization": item.independent_authorization,
        "authorization_route": item.authorization_route or None,
        "needs_new_arrangement": state in {"DECLINED", "CANCELLED", "EXPIRED", "REVOKED"},
        "recovery_required_count": item.task_plans.filter(recovery_required=True).count(),
    }


def history_event(event):
    return {
        "id": event.pk,
        "coverage_id": event.coverage_id,
        "reference_code": event.coverage.reference_code,
        "kind": event.kind,
        "version": event.version,
        "actor": person(event.actor),
        "occurred_at": event.occurred_at,
        "independent_authorization": event.independent_authorization,
        "authorization_route": event.authorization_route or None,
    }


def coverage_detail(*, actor, coverage_id):
    actor = rules.current_actor(actor)
    item = get_coverage(actor=actor, coverage_id=coverage_id)
    now = timezone.now()
    state = state_at(item, now)
    current = (
        item.case.status == "ACTIVE" and item.case.primary_counselor_id == item.primary_counselor_id
    )
    preparer = actor.pk == item.prepared_by_id
    primary = actor.pk == item.case.primary_counselor_id
    receiver = actor.pk == item.receiving_counselor_id
    head = can_authorize(actor, item, now)
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
    recovery = item.task_plans.filter(recovery_required=True).exists()
    tasks = []
    package = (
        (
            current
            and state in {"PREPARED", "AUTHORIZED"}
            and (preparer or primary or head or review or actor.pk == item.authorized_by_id)
        )
        or (current and state in {"SCHEDULED", "ACTIVE"} and (preparer or primary or receiver))
        or (
            state in {"ENDED", "REVOKED"}
            and not receiver
            and (primary or preparer or actor.pk == item.authorized_by_id or recovery)
        )
    )
    if package:
        for plan in item.task_plans.select_related(
            "task__student__role", "task__assigned_to", "returned_by"
        ):
            readable = actor.has_capability(
                "guidance_followups.view", at=now
            ) and task_policy.authorized(actor, plan.task)
            # Head/office review never needs a title, even when a separate source right exists.
            titles = primary and not item.office_preparation_reason and readable
            tasks.append(
                {
                    "task_id": plan.task_id,
                    "category": plan.task.category,
                    "source_kind": plan.source_kind,
                    "due_at": plan.task.due_at
                    if item.state in {"ACCEPTED", "REVOKED"}
                    else plan.due_at,
                    "assigned_counselor": person(item.receiving_counselor)
                    if state in {"PREPARED", "AUTHORIZED", "SCHEDULED", "ACTIVE"}
                    else person(plan.task.assigned_to),
                    "return_plan": plan.return_plan,
                    "title": decrypt_text(plan.task_id, "title", plan.task.title_ciphertext)
                    if titles and plan.task.title_ciphertext
                    else None,
                    "record_accessible": readable and (primary or (receiver and state == "ACTIVE")),
                    "returned_at": plan.returned_at,
                    "returned_by": person(plan.returned_by) if plan.returned_by else None,
                    "recovery_required": plan.recovery_required,
                }
            )
    return {
        **summary(item, now),
        "case": case_identity(item.case),
        "primary_counselor": person(item.primary_counselor),
        "prepared_by": person(item.prepared_by),
        "office_prepared": bool(item.office_preparation_reason),
        "reason": item.reason,
        "office_preparation_reason": item.office_preparation_reason or None,
        "authorized_by": person(item.authorized_by) if item.authorized_by else None,
        "authorized_at": item.authorized_at,
        "decided_by": person(item.decided_by) if item.decided_by else None,
        "decided_at": item.decided_at,
        "decision_reason": "REVIEW_WINDOW_ENDED"
        if state == "EXPIRED"
        else item.decision_reason or None,
        "revoked_by": person(item.revoked_by) if item.revoked_by else None,
        "revoked_at": item.revoked_at,
        "revocation_reason": item.revocation_reason or None,
        "student_communication": item.student_communication,
        "student_informed_at": item.student_informed_at,
        "communication_recorded_by": person(item.communication_recorded_by),
        "communication_deferral_reason": item.communication_deferral_reason or None,
        "communication_task_id": item.communication_task_id if primary or preparer else None,
        "communication_responsible": person(effective_assignee(item.communication_task))
        if item.communication_task
        else None,
        "tasks": tasks,
        "history": [
            history_event(event) for event in item.history.select_related("actor", "coverage")
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
            (preparer and actor.has_capability("counseling.continuity.request", at=now))
            or (
                not receiver
                and actor.has_capability("counseling.continuity.revoke", at=now)
                and is_head(actor)
            )
        ),
        "can_revoke": can_revoke(actor, item, now),
        "can_open_case": primary and actor.has_capability("counseling.view_assigned", at=now),
        "can_arrange_transfer": recovery
        and rules.may_prepare(actor, item.case)
        and actor.has_capability("counseling.continuity.request", at=now),
    }
