"""Explicit case coverage authorization and acceptance, serialized on the case."""

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.guidance_followups import policy as task_policy
from compass.guidance_followups.models import GuidanceFollowUp
from compass.routine_interviews.models import RoutineInterview

from . import case_continuity_rules as rules
from .case_coverage_models import (
    CaseCoverageReturnPlan,
    CounselingCaseCoverage,
    CounselingCaseCoverageEvent,
    CounselingCaseCoverageTask,
)
from .case_transfer_models import (
    CaseArrangementDecisionReason,
    CaseAuthorizationRoute,
    CaseContinuityReason,
)
from .case_transfer_services import _check_communication, require_current_authorization
from .continuity_models import CounselorCaseContinuityGrant
from .continuity_rules import ContinuityError, is_head, validate_interval
from .models import CounselingEncounter


def coverages():
    return CounselingCaseCoverage.objects.select_related(
        "case__student__role",
        "case__primary_counselor__role",
        "primary_counselor__role",
        "prepared_by__role",
        "receiving_counselor__role",
        "authorized_by__role",
        "decided_by__role",
        "revoked_by",
        "communication_recorded_by",
        "communication_task__assigned_to",
    )


def state_at(item, now=None):
    now = now or timezone.now()
    if item.state == "ACCEPTED":
        return (
            "ENDED" if now >= item.expires_at else "SCHEDULED" if now < item.starts_at else "ACTIVE"
        )
    if item.state in {"PREPARED", "AUTHORIZED"} and (
        item.expires_at <= now or (item.review_expires_at and item.review_expires_at <= now)
    ):
        return "EXPIRED"
    return item.state


def can_authorize(actor, item, now):
    return bool(
        state_at(item, now) == "PREPARED"
        and item.submitted_at
        and item.case.status == "ACTIVE"
        and item.case.primary_counselor_id == item.primary_counselor_id
        and actor.pk
        in {
            person.pk
            for person in rules.eligible_authorizers(
                requester_id=item.prepared_by_id,
                receiver_id=item.receiving_counselor_id,
                now=now,
            )
        }
    )


def may_view(actor, item, now):
    return (
        (
            actor.pk == item.case.primary_counselor_id
            and actor.has_capability("counseling.view_assigned", at=now)
        )
        or actor.pk in {item.prepared_by_id, item.authorized_by_id}
        or (actor.pk == item.receiving_counselor_id and item.state != "PREPARED")
        or can_authorize(actor, item, now)
        or (
            is_head(actor)
            and actor.has_capability("counseling.continuity.approve", at=now)
            and item.task_plans.filter(recovery_required=True).exists()
        )
    )


def get_coverage(*, actor, coverage_id):
    actor = rules.current_actor(actor)
    item = coverages().filter(pk=coverage_id).first()
    if item is None or not may_view(actor, item, timezone.now()):
        rules.fail("arrangement_not_found", "The coverage review was not found.", 404)
    from .case_coverage_tasks import reconcile_returns

    reconcile_returns(actor=actor, case_id=item.case_id)
    return coverages().get(pk=item.pk)


def audit(item, verb, *, actor, context):
    CounselingCaseCoverageEvent.objects.create(
        coverage=item,
        kind=verb,
        version=item.version,
        actor=actor,
        independent_authorization=item.independent_authorization,
        authorization_route=item.authorization_route,
    )
    record_event(
        context=context,
        action="counseling.case_coverage." + verb,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case_coverage",
        target_id=item.pk,
        metadata={
            "case_id": str(item.case_id),
            "reference_code": item.reference_code,
            "version": item.version,
            "independent_authorization": item.independent_authorization,
            "authorization_route": item.authorization_route,
        },
    )


def _save(item):
    item.version += 1
    item.save()


def lock_work(item, *, task_ids=None):
    tasks = GuidanceFollowUp.objects.filter(case_id=item.case_id)
    tasks = tasks.filter(
        pk__in=task_ids if task_ids is not None else item.task_plans.values("task_id")
    )
    sources = tuple(tasks.values("source_kind", "source_id", "assigned_to_id"))
    rules.locked_rows(
        CounselingEncounter.objects.filter(
            pk__in=[
                row["source_id"] for row in sources if row["source_kind"] == "COUNSELING_ENCOUNTER"
            ]
        )
    )
    rules.locked_rows(
        RoutineInterview.objects.filter(
            pk__in=[
                row["source_id"] for row in sources if row["source_kind"] == "ROUTINE_INTERVIEW"
            ]
        )
    )
    return {
        item.case.student_id,
        item.primary_counselor_id,
        item.receiving_counselor_id,
        item.prepared_by_id,
        item.authorized_by_id,
        item.decided_by_id,
        *(row["assigned_to_id"] for row in sources),
    } - {None}


def _interval(starts_at, expires_at, now):
    try:
        validate_interval(starts_at, expires_at, now)
    except ContinuityError:
        rules.fail(
            "interval_invalid",
            "Coverage must end after it starts, last at most 30 days, "
            "and start at most 14 days ahead.",
            422,
        )


def task_can_delegate(task, primary, *, now=None):
    now = now or timezone.now()
    return bool(
        task.status == "PENDING"
        and task.category == "COUNSELING"
        and task.visibility == "COUNSELOR_CONFIDENTIAL"
        and task.assigned_to_id == primary.pk
        and rules.receiver_eligible(primary, now)
        and primary.has_capability("guidance_followups.manage", at=now)
        and task_policy.authorized(primary, task, manage=True)
    )


def _store_plans(item, inputs, *, primary, now):
    if len(inputs) > 2000 or len({row["task_id"] for row in inputs}) != len(inputs):
        rules.fail("task_plan_invalid", "Choose each selected task once (at most 2,000).", 422)
    tasks = {
        task.pk: task
        for task in rules.locked_rows(
            GuidanceFollowUp.objects.select_related("student__role", "assigned_to__role").filter(
                case_id=item.case_id, pk__in=[row["task_id"] for row in inputs]
            )
        )
    }
    plans = []
    for value in inputs:
        task = tasks.get(value["task_id"])
        if task is None or not task_can_delegate(task, primary, now=now):
            rules.fail(
                "task_not_delegable",
                "Only an authorized pending task of the primary Counselor "
                "can be selected. Arrange case responsibility first if necessary.",
            )
        if task.version != value["expected_version"]:
            rules.fail(
                "task_changed", "A selected next action changed. Review its current details."
            )
        if value.get("return_plan") not in CaseCoverageReturnPlan.values:
            rules.fail("return_plan_required", "Choose a return plan for every selected task.", 422)
        plans.append(
            CounselingCaseCoverageTask(
                coverage=item,
                task=task,
                task_version=task.version,
                source_kind=task.source_kind,
                source_id=task.source_id,
                due_at=task.due_at,
                return_plan=value["return_plan"],
            )
        )
    item.task_plans.all().delete()
    CounselingCaseCoverageTask.objects.bulk_create(plans)


def validate_tasks(item, *, primary, now):
    plans = rules.locked_rows(item.task_plans.all())
    tasks = {
        task.pk: task
        for task in rules.locked_rows(
            GuidanceFollowUp.objects.select_related("student__role", "assigned_to__role").filter(
                pk__in=[plan.task_id for plan in plans]
            )
        )
    }
    for plan in plans:
        task = tasks.get(plan.task_id)
        if (
            task is None
            or task.case_id != item.case_id
            or task.student_id != item.case.student_id
            or task.version != plan.task_version
            or task.due_at != plan.due_at
            or task.source_kind != plan.source_kind
            or task.source_id != plan.source_id
            or not task_can_delegate(task, primary, now=now)
        ):
            rules.fail(
                "task_changed", "A selected task or its authority changed. Prepare a fresh review."
            )
    return plans, tasks


@transaction.atomic
def prepare_coverage(*, actor, case_id, values, context, coverage_id=None, expected_version=None):
    from .case_coverage_tasks import reconcile_returns

    actor = rules.current_actor(actor, "request")
    case = rules.lock_case(case_id)
    rules.require_preparer(actor, case, values.get("office_preparation_reason"))
    reconcile_returns(case_id=case.pk, actor=actor)
    if values.get("expected_case_version") != case.version:
        rules.fail("case_changed", "This case changed. Review the latest pending work.")
    if coverage_id is None:
        item = CounselingCaseCoverage(
            case=case,
            primary_counselor_id=case.primary_counselor_id,
            prepared_by=actor,
            communication_recorded_by=actor,
        )
        item.reference_code = f"COV-{case.reference_code}-{case.coverages.count() + 1:03d}"
    else:
        item = (
            coverages()
            .select_for_update(of=("self",))
            .filter(
                pk=coverage_id,
                case=case,
                prepared_by=actor,
            )
            .first()
        )
        if not item:
            rules.fail("arrangement_not_found", "The coverage request was not found.", 404)
        rules.require_version(item, expected_version)
        if item.state not in {"PREPARED", "AUTHORIZED"}:
            rules.fail(
                "terminal_arrangement",
                "End accepted coverage explicitly, then arrange new coverage.",
            )
    item.case = case
    item.receiving_counselor_id = values["receiving_counselor_id"]
    task_ids = [value["task_id"] for value in values.get("tasks", [])]
    people = rules.lock_people(lock_work(item, task_ids=task_ids) | {actor.pk})
    actor = rules.current_actor(people[actor.pk], "request")
    now = timezone.now()
    rules.require_preparer(actor, case, values.get("office_preparation_reason"))
    rules.require_case_current(case, item.primary_counselor_id)
    receiver = people.get(item.receiving_counselor_id)
    if not rules.receiver_eligible(receiver, now):
        rules.fail("receiver_ineligible", "Choose another active eligible Counselor.", 422)
    rules.authorization_route(requester=actor, receiver=receiver, case=case, now=now)
    if values["reason"] not in CaseContinuityReason.values:
        rules.fail("reason_invalid", "Choose a neutral coverage reason.", 422)
    _interval(values["starts_at"], values["expires_at"], now)
    item.reason, item.office_preparation_reason = (
        values["reason"],
        values.get("office_preparation_reason") or "",
    )
    item.starts_at, item.expires_at = values["starts_at"], values["expires_at"]
    item.state = "PREPARED"
    item.submitted_at = item.authorized_at = item.authorized_by = item.authorized_version = (
        item.review_expires_at
    ) = None
    item.authorization_route, item.independent_authorization = "", True
    _check_communication(
        item,
        values,
        actor=actor,
        people=people,
        now=now,
        context=context,
        identity_prefix="coverage",
    )
    if item._state.adding:
        item.save(force_insert=True)
    else:
        _save(item)
    _store_plans(item, values.get("tasks", []), primary=people[item.primary_counselor_id], now=now)
    audit(item, "prepared" if coverage_id is None else "updated", actor=actor, context=context)
    return item


def notify_next_actor(item):
    from compass.notifications.policy import NotificationEvent, NotificationTargetType
    from compass.notifications.services import create_notification_for_event

    now = timezone.now()
    recipients = (
        (item.receiving_counselor,)
        if state_at(item, now) == "AUTHORIZED"
        else rules.eligible_authorizers(
            requester_id=item.prepared_by_id, receiver_id=item.receiving_counselor_id, now=now
        )
        if state_at(item, now) == "PREPARED" and item.submitted_at
        else ()
    )
    for recipient in recipients:
        create_notification_for_event(
            recipient=recipient,
            event=NotificationEvent.CASE_COVERAGE_REVIEW,
            source_type=f"case_coverage_v{item.version}",
            source_id=item.pk,
            target_type=NotificationTargetType.CASE_COVERAGE,
            target_id=item.pk,
        )


@transaction.atomic
def submit_coverage(*, actor, coverage_id, expected_version, context):
    visible = get_coverage(actor=actor, coverage_id=coverage_id)
    case = rules.lock_case(visible.case_id)
    item = coverages().select_for_update(of=("self",)).get(pk=visible.pk)
    item.case = case
    rules.require_version(item, expected_version)
    if actor.pk != item.prepared_by_id or item.state != "PREPARED" or item.submitted_at:
        rules.fail("submission_unavailable", "This coverage cannot be submitted again.")
    people = rules.lock_people(lock_work(item) | {actor.pk})
    actor = rules.current_actor(people[actor.pk], "request")
    now = timezone.now()
    rules.require_case_current(case, item.primary_counselor_id)
    rules.require_preparer(actor, case, item.office_preparation_reason)
    _interval(item.starts_at, item.expires_at, now)
    receiver = people[item.receiving_counselor_id]
    if not rules.receiver_eligible(receiver, now):
        rules.fail("receiver_ineligible", "The covering Counselor is no longer eligible.")
    validate_tasks(item, primary=people[item.primary_counselor_id], now=now)
    route = rules.authorization_route(requester=actor, receiver=receiver, case=case, now=now)
    item.submitted_at, item.authorization_route = now, route
    item.independent_authorization = route == "INDEPENDENT_HEAD"
    if route != "INDEPENDENT_HEAD":
        item.state, item.authorized_at = "AUTHORIZED", now
        item.authorized_by = actor if route == "DIRECT_OUTGOING_HEAD" else None
        item.authorized_version = item.version + 1
        item.review_expires_at = min(now + rules.REVIEW_WINDOW, item.expires_at)
    _save(item)
    audit(item, "submitted", actor=actor, context=context)
    if item.state == "AUTHORIZED":
        audit(item, "authorized", actor=actor, context=context)
    notify_next_actor(item)
    return item


def conflicting_case_coverage(case, now, *, exclude_id=None):
    return (
        CounselingCaseCoverage.objects.filter(case=case, state="ACCEPTED", expires_at__gt=now)
        .exclude(pk=exclude_id)
        .exists()
    )


def can_revoke(actor, item, now):
    return bool(
        item.state == "ACCEPTED"
        and item.expires_at > now
        and actor.has_capability("counseling.continuity.revoke", at=now)
        and (
            actor.pk in {item.prepared_by_id, item.case.primary_counselor_id}
            or (is_head(actor) and actor.pk != item.receiving_counselor_id)
        )
    )


@transaction.atomic
def decide_coverage(*, actor, coverage_id, expected_version, action, context, reason=None):
    from .case_coverage_tasks import reconcile_returns, task_event

    visible = get_coverage(actor=actor, coverage_id=coverage_id)
    case = rules.lock_case(visible.case_id)
    item = coverages().select_for_update(of=("self",)).get(pk=visible.pk)
    item.case = case
    rules.require_version(item, expected_version)
    people = rules.lock_people(lock_work(item) | {actor.pk, case.primary_counselor_id})
    actor = rules.current_actor(people[actor.pk])
    now = timezone.now()
    if action == "revoke":
        if not can_revoke(actor, item, now):
            rules.fail(
                "revocation_denied",
                "Only the primary, preparer or an uninvolved Head can end this coverage.",
                403,
            )
    else:
        if state_at(item, now) in {
            "EXPIRED",
            "ACTIVE",
            "SCHEDULED",
            "ENDED",
            "DECLINED",
            "CANCELLED",
            "REVOKED",
        }:
            rules.fail("terminal_arrangement", "This review ended. Another arrangement is needed.")
        rules.require_case_current(case, item.primary_counselor_id)
    if action == "authorize":
        if not can_authorize(actor, item, now):
            rules.fail(
                "authorization_denied",
                "Only an independent current Head can authorize this coverage.",
                403,
            )
        validate_tasks(item, primary=people[item.primary_counselor_id], now=now)
        if not rules.receiver_eligible(people[item.receiving_counselor_id], now):
            rules.fail("receiver_ineligible", "The covering Counselor is no longer eligible.")
        item.state, item.authorized_by, item.authorized_at = "AUTHORIZED", actor, now
        item.authorization_route, item.independent_authorization = (
            CaseAuthorizationRoute.INDEPENDENT_HEAD,
            True,
        )
        item.authorized_version = item.version + 1
        item.review_expires_at = min(now + rules.REVIEW_WINDOW, item.expires_at)
    elif action == "accept":
        if (
            actor.pk != item.receiving_counselor_id
            or not rules.receiver_eligible(actor, now)
            or not actor.has_capability("counseling.continuity.read_selected", at=now)
        ):
            rules.fail("acceptance_denied", "Only the eligible covering Counselor can accept.", 403)
        rules.require_review(item, now)
        require_current_authorization(item, people, now)
        if conflicting_case_coverage(case, now, exclude_id=item.pk):
            rules.fail(
                "coverage_conflict",
                "This case already has active or accepted upcoming coverage. "
                "End it explicitly first.",
            )
        if CounselorCaseContinuityGrant.objects.filter(
            student_id=case.student_id,
            decision="APPROVED",
            starts_at__lt=item.expires_at,
            expires_at__gt=max(item.starts_at, now),
        ).exists():
            rules.fail(
                "coverage_conflict",
                "Overlapping legacy coverage must be ended explicitly or expire first.",
            )
        plans, tasks = validate_tasks(item, primary=people[item.primary_counselor_id], now=now)
        if plans and not (
            actor.has_capability("guidance_followups.manage", at=now)
            and actor.has_capability("guidance_followups.view", at=now)
        ):
            rules.fail(
                "receiver_tasks_ineligible",
                "The covering Counselor cannot manage these selected actions.",
            )
        item.state, item.decided_at, item.decided_by = "ACCEPTED", now, actor
        for plan in plans:
            plan.delegated_at = max(now, item.starts_at)
            plan.save(update_fields=["delegated_at"])
            task_event(
                tasks[plan.task_id],
                item,
                actor=actor,
                effective_at=plan.delegated_at,
                old_assignee=people[item.primary_counselor_id],
                new_assignee=actor,
            )
        case.version += 1
        case.save(update_fields=["version", "updated_at"])
    elif action in {"decline", "cancel", "revoke"}:
        if reason not in CaseArrangementDecisionReason.values or reason == "REVIEW_WINDOW_ENDED":
            rules.fail("decision_reason_required", "Choose a bounded decision reason.", 422)
        if action == "decline":
            permitted = can_authorize(actor, item, now) or (
                actor.pk == item.receiving_counselor_id
                and item.state == "AUTHORIZED"
                and rules.receiver_eligible(actor, now)
                and actor.has_capability("counseling.continuity.read_selected", at=now)
            )
        elif action == "cancel":
            permitted = (
                actor.pk == item.prepared_by_id
                and actor.has_capability("counseling.continuity.request", at=now)
            ) or (
                is_head(actor)
                and actor.pk != item.receiving_counselor_id
                and actor.has_capability("counseling.continuity.revoke", at=now)
            )
        else:
            permitted = True  # Already checked independently above, including accepted-pending.
        if not permitted:
            rules.fail(
                "decision_denied", "This coverage decision is unavailable to your account.", 403
            )
        if action == "revoke":
            item.state, item.revoked_at, item.revoked_by, item.revocation_reason = (
                "REVOKED",
                now,
                actor,
                reason,
            )
            case.version += 1
            case.save(update_fields=["version", "updated_at"])
        else:
            item.state = "DECLINED" if action == "decline" else "CANCELLED"
            item.decided_at, item.decided_by, item.decision_reason = now, actor, reason
    else:
        rules.fail("action_invalid", "Choose a supported coverage action.", 422)
    _save(item)
    audit(
        item,
        {
            "authorize": "authorized",
            "accept": "accepted",
            "decline": "declined",
            "cancel": "cancelled",
            "revoke": "revoked",
        }[action],
        actor=actor,
        context=context,
    )
    if action == "authorize":
        notify_next_actor(item)
    if action == "revoke":
        reconcile_returns(actor=actor, case_id=case.pk)
    if action == "accept":
        final_now = timezone.now()
        if item.expires_at <= final_now or item.review_expires_at <= final_now:
            rules.fail(
                "review_expired",
                "Coverage expired before acceptance completed. Nothing was delegated.",
            )
        if not rules.receiver_eligible(actor, final_now) or not actor.has_capability(
            "counseling.continuity.read_selected", at=final_now
        ):
            rules.fail(
                "receiver_ineligible",
                "The covering Counselor's authority changed before acceptance completed.",
            )
        require_current_authorization(item, people, final_now)
    return item


def notification_is_current(notification, now=None):
    now = now or timezone.now()
    actor = (
        User.objects.select_related("role")
        .filter(pk=notification.recipient_id, is_active=True)
        .first()
    )
    item = coverages().filter(pk=notification.target_id).first()
    if (
        not actor
        or not item
        or notification.source_id != item.pk
        or notification.source_type != f"case_coverage_v{item.version}"
        or not actor.has_capability("counseling.continuity.view", at=now)
    ):
        return False
    return can_authorize(actor, item, now) or (
        state_at(item, now) == "AUTHORIZED"
        and actor.pk == item.receiving_counselor_id
        and rules.receiver_eligible(actor, now)
        and actor.has_capability("counseling.continuity.read_selected", at=now)
    )
