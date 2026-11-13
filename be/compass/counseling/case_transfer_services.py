"""Case-first atomic transfer, with independent authorization and explicit receiver decisions."""

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling.continuity_models import CounselorCaseContinuityGrant
from compass.counseling.continuity_rules import is_head
from compass.counseling.models import CounselingEncounter
from compass.routine_interviews.models import RoutineInterview

from . import case_continuity_rules as rules
from .case_transfer_models import (
    CaseArrangementState,
    CaseAuthorizationRoute,
    CaseCommunicationDeferral,
    CaseContinuityReason,
    CaseStudentCommunication,
    CounselingCaseResponsibility,
    CounselingCaseTransfer,
    CounselingCaseTransferEvent,
)
from .case_transfer_plans import apply_task_plans, new_case_task, store_plans, validate_plans


def transfers():
    return CounselingCaseTransfer.objects.select_related(
        "case__student",
        "case__primary_counselor",
        "prepared_by__role",
        "outgoing_counselor__role",
        "receiving_counselor__role",
        "authorized_by__role",
        "decided_by",
        "communication_recorded_by",
        "communication_task__assigned_to",
        "case_handoff__author",
        "handoff_exception__recorded_by__role",
    )


def can_authorize(actor, item, now):
    return bool(
        item.state == "PREPARED"
        and item.submitted_at
        and actor.pk not in {item.prepared_by_id, item.receiving_counselor_id}
        and is_head(actor)
        and actor.has_capability("counseling.continuity.approve", at=now)
        and item.case.primary_counselor_id == item.outgoing_counselor_id
        and item.case.status == "ACTIVE"
    )


def may_view(actor, item, now):
    if actor.pk == item.case.primary_counselor_id and actor.has_capability(
        "counseling.view_assigned", at=now
    ):
        return True
    if actor.pk in {item.prepared_by_id, item.authorized_by_id}:
        return True
    if actor.pk == item.receiving_counselor_id:
        return rules.state_at(item, now) != "PREPARED"
    from .case_handoff_services import may_record_exception

    if may_record_exception(actor, item, now):
        return True
    return can_authorize(actor, item, now)


def get_transfer(*, actor, transfer_id):
    actor = rules.current_actor(actor)
    item = transfers().filter(pk=transfer_id).first()
    if item is None or not may_view(actor, item, timezone.now()):
        rules.fail("arrangement_not_found", "The transfer review was not found.", 404)
    return item


def audit(item, verb, *, actor, context):
    CounselingCaseTransferEvent.objects.create(
        transfer=item,
        kind=verb,
        version=item.version,
        actor=actor,
        independent_authorization=item.independent_authorization,
        authorization_route=item.authorization_route,
    )
    record_event(
        context=context,
        action="counseling.case_transfer." + verb,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case_transfer",
        target_id=item.pk,
        metadata={
            "case_id": str(item.case_id),
            "reference_code": item.reference_code,
            "version": item.version,
            "independent_authorization": item.independent_authorization,
            "authorization_route": item.authorization_route,
        },
    )


def notify_next_actor(item):
    from compass.notifications.policy import NotificationEvent, NotificationTargetType
    from compass.notifications.services import create_notification_for_event

    now = timezone.now()
    if rules.state_at(item, now) == "AUTHORIZED":
        recipients = (item.receiving_counselor,)
    elif item.state == "PREPARED" and not item.submitted_at and item.handoff_exception_id:
        recipients = (item.prepared_by,)
    elif item.state == "PREPARED" and (item.submitted_at or item.office_preparation_reason):
        recipients = rules.eligible_authorizers(
            requester_id=item.prepared_by_id, receiver_id=item.receiving_counselor_id, now=now
        )
    else:
        recipients = ()
    for recipient in recipients:
        create_notification_for_event(
            recipient=recipient,
            event=NotificationEvent.CASE_TRANSFER_REVIEW,
            source_type=f"case_transfer_v{item.version}",
            source_id=item.pk,
            target_type=NotificationTargetType.CASE_TRANSFER,
            target_id=item.pk,
        )


def lock_work(item):
    # Case -> Encounter -> other reviewed sources -> sorted Users -> task rows. NOWAIT avoids
    # inversions with source-domain writers. No booking service is called by this module.
    plans = tuple(item.task_plans.all())
    rules.locked_rows(
        CounselingEncounter.objects.filter(
            pk__in=[plan.source_id for plan in plans if plan.source_kind == "COUNSELING_ENCOUNTER"]
        )
    )
    rules.locked_rows(
        RoutineInterview.objects.filter(
            pk__in=[plan.source_id for plan in plans if plan.source_kind == "ROUTINE_INTERVIEW"]
        )
    )
    appointment_ids = item.appointment_plans.values("link__appointment_id")
    rules.locked_rows(Appointment.objects.filter(pk__in=appointment_ids))
    ids = {
        item.prepared_by_id,
        item.outgoing_counselor_id,
        item.receiving_counselor_id,
        item.authorized_by_id,
        item.case.student_id,
    }
    ids.update(plan.assignee_id for plan in plans)
    if item.handoff_exception_id:
        ids.add(item.handoff_exception.recorded_by_id)
    return ids


def _save(item):
    item.version += 1
    item.save()


def _check_communication(item, values, *, actor, people, now, context, identity_prefix="transfer"):
    status = values.get("student_communication", "NO")
    if status not in CaseStudentCommunication.values:
        rules.fail("communication_invalid", "Choose the Student communication status.", 422)
    informed_at = values.get("student_informed_at")
    if status == "YES" and (
        informed_at is None or timezone.is_naive(informed_at) or informed_at > now
    ):
        rules.fail("communication_time_required", "Record when you informed the Student.", 422)
    if status != "YES" and informed_at is not None:
        rules.fail(
            "communication_invalid", "An informed time belongs only to Student informed.", 422
        )
    item.student_communication = status
    item.student_informed_at = informed_at
    item.communication_recorded_by = actor
    item.communication_deferral_reason = values.get("communication_deferral_reason") or ""
    if status == "DEFERRED":
        title, due = values.get("communication_next_action"), values.get("communication_due_at")
        if item.communication_task_id and title is None and due is None:
            if (
                item.communication_deferral_reason not in CaseCommunicationDeferral.values
                or item.communication_task.status != "PENDING"
            ):
                rules.fail(
                    "communication_task_changed", "Review the recorded communication action."
                )
            return
        if (
            item.communication_deferral_reason not in CaseCommunicationDeferral.values
            or not title
            or due is None
            or timezone.is_naive(due)
            or due <= now
        ):
            rules.fail(
                "communication_action_required",
                "Deferred informing needs a reason, a named next action and a future deadline.",
                422,
            )
        if item.communication_task_id:
            task = item.communication_task
            if task.status != "PENDING" or task.due_at != due:
                rules.fail(
                    "communication_task_changed",
                    "Review the existing communication action through Follow-ups "
                    "before changing this arrangement.",
                )
            from compass.guidance_followups.content import decrypt_text

            if decrypt_text(task.pk, "title", task.title_ciphertext) != title:
                rules.fail(
                    "communication_task_changed",
                    "Change the communication action through Follow-ups, "
                    "then review the arrangement.",
                )
        else:
            item.communication_task = new_case_task(
                case=item.case,
                author=actor,
                assignee=people[item.outgoing_counselor_id],
                title=title,
                due_at=due,
                identity=f"{identity_prefix}-communication:{item.pk}",
                context=context,
            )
    elif (
        item.communication_deferral_reason
        or values.get("communication_next_action")
        or values.get("communication_due_at")
    ):
        rules.fail(
            "communication_invalid", "Deferral details belong only to deferred informing.", 422
        )


@transaction.atomic
def prepare_transfer(*, actor, case_id, values, context, transfer_id=None, expected_version=None):
    actor = rules.current_actor(actor, "request")
    case = rules.lock_case(case_id)
    from .case_coverage_tasks import reconcile_returns

    reconcile_returns(actor=actor, case_id=case.pk)
    if transfer_id is None:
        if values.get("expected_case_version") != case.version:
            rules.fail("case_changed", "This case changed. Review the latest pending work.")
        item = CounselingCaseTransfer(
            case=case,
            outgoing_counselor_id=case.primary_counselor_id,
            prepared_by=actor,
            communication_recorded_by=actor,
        )
        item.reference_code = f"TRF-{case.reference_code}-{case.transfers.count() + 1:03d}"
    else:
        item = (
            transfers()
            .select_for_update(of=("self",))
            .filter(pk=transfer_id, case=case, prepared_by=actor)
            .first()
        )
        if item is None:
            rules.fail("arrangement_not_found", "The transfer was not found.", 404)
        rules.require_version(item, expected_version)
        if item.state not in {"PREPARED", "AUTHORIZED"}:
            rules.fail(
                "terminal_arrangement",
                "A completed decision cannot be edited. Prepare a new transfer.",
            )
    ids = {actor.pk, case.student_id, case.primary_counselor_id, values["receiving_counselor_id"]}
    people = rules.lock_people(ids)
    actor = rules.current_actor(people[actor.pk], "request")
    now = timezone.now()
    rules.require_case_current(case, item.outgoing_counselor_id)
    rules.require_preparer(actor, case, values.get("office_preparation_reason"))
    if values.get("handoff_sections") is not None and actor.pk != case.primary_counselor_id:
        rules.fail(
            "handoff_write_denied",
            "Office preparation cannot include counseling handoff content.",
            403,
        )
    receiver = people.get(values["receiving_counselor_id"])
    if not rules.receiver_eligible(receiver, now):
        rules.fail("receiver_ineligible", "The receiving Counselor is no longer eligible.", 422)
    reason = values["reason"]
    if reason not in CaseContinuityReason.values:
        rules.fail("reason_invalid", "Choose a neutral transfer reason.", 422)
    # Validate the exceptional route before creating a communication task or any plan rows.
    rules.authorization_route(requester=actor, receiver=receiver, case=case, now=now)
    item.receiving_counselor = receiver
    item.reason = reason
    item.office_preparation_reason = values.get("office_preparation_reason") or ""
    item.state = CaseArrangementState.PREPARED
    item.submitted_at = item.authorized_at = item.authorized_by = item.authorized_version = (
        item.review_expires_at
    ) = None
    item.authorization_route = ""
    item.independent_authorization = True
    item.case_handoff = item.handoff_exception = None
    item.handoff_required_at = item.handoff_required_at or now
    _check_communication(item, values, actor=actor, people=people, now=now, context=context)
    if item._state.adding:
        item.save(force_insert=True)
    else:
        _save(item)
    tasks = list(values.get("tasks", []))
    if item.communication_task_id and not any(
        plan["task_id"] == item.communication_task_id for plan in tasks
    ):
        tasks.append(
            {
                "task_id": item.communication_task_id,
                "expected_version": item.communication_task.version,
                "disposition": "TRANSFER",
            }
        )
    store_plans(
        item, actor=actor, tasks=tasks, appointments=values.get("appointments", []), now=now
    )
    if values.get("handoff_sections") is not None:
        from .case_handoff_services import save_prepared_draft

        save_prepared_draft(item, actor=actor, sections=values["handoff_sections"], context=context)
    audit(item, "prepared" if transfer_id is None else "updated", actor=actor, context=context)
    if item.office_preparation_reason:
        notify_next_actor(item)
    return item


def require_current_authorization(item, people, now):
    requester, receiver = people[item.prepared_by_id], people[item.receiving_counselor_id]
    current_route = rules.authorization_route(
        requester=requester, receiver=receiver, case=item.case, now=now
    )
    if current_route != item.authorization_route:
        rules.fail(
            "authorization_changed", "The authorization route changed. Arrange a fresh review."
        )
    if item.authorization_route == CaseAuthorizationRoute.INDEPENDENT_HEAD:
        approver = people.get(item.authorized_by_id)
        if (
            not approver
            or not is_head(approver)
            or not approver.has_capability("counseling.continuity.approve", at=now)
            or approver.pk in {requester.pk, receiver.pk}
        ):
            rules.fail(
                "authorization_changed", "The independent authorization is no longer current."
            )


@transaction.atomic
def submit_transfer(*, actor, transfer_id, expected_version, context):
    visible = get_transfer(actor=actor, transfer_id=transfer_id)
    case = rules.lock_case(visible.case_id)
    item = transfers().select_for_update(of=("self",)).get(pk=visible.pk)
    item.case = case
    rules.require_version(item, expected_version)
    if actor.pk != item.prepared_by_id or item.state != "PREPARED" or item.submitted_at:
        rules.fail("submission_unavailable", "This transfer cannot be submitted again.")
    ids = lock_work(item) | {actor.pk}
    people = rules.lock_people(ids)
    actor = rules.current_actor(people[actor.pk], "request")
    now = timezone.now()
    rules.require_case_current(case, item.outgoing_counselor_id)
    rules.require_preparer(actor, case, item.office_preparation_reason)
    if not rules.receiver_eligible(people[item.receiving_counselor_id], now):
        rules.fail("receiver_ineligible", "The receiving Counselor is no longer eligible.")
    validate_plans(item, actor=actor, now=now)
    route = rules.authorization_route(
        requester=actor, receiver=people[item.receiving_counselor_id], case=case, now=now
    )
    from .case_handoff_services import require_ready

    require_ready(item, new_submission=True, now=now)
    item.handoff_required_at = item.handoff_required_at or now
    item.submitted_at = now
    item.authorization_route = route
    item.independent_authorization = route == CaseAuthorizationRoute.INDEPENDENT_HEAD
    if route != CaseAuthorizationRoute.INDEPENDENT_HEAD:
        item.state = CaseArrangementState.AUTHORIZED
        item.authorized_at = now
        item.authorized_by = actor if route == CaseAuthorizationRoute.DIRECT_OUTGOING_HEAD else None
        item.review_expires_at = now + rules.REVIEW_WINDOW
        item.authorized_version = item.version + 1
    _save(item)
    audit(item, "submitted", actor=actor, context=context)
    if item.state == "AUTHORIZED":
        audit(item, "authorized", actor=actor, context=context)
    notify_next_actor(item)
    return item


def conflicting_coverage(case, now):
    # Student-keyed legacy coverage is left unchanged. Its active interval must be explicitly
    # revoked/ended before changing this case's responsibility.
    from .case_coverage_services import conflicting_case_coverage

    return (
        conflicting_case_coverage(case, now)
        or CounselorCaseContinuityGrant.objects.filter(
            student_id=case.student_id, decision="APPROVED", starts_at__lte=now, expires_at__gt=now
        ).exists()
    )


@transaction.atomic
def decide_transfer(*, actor, transfer_id, expected_version, action, context, reason=None):
    visible = get_transfer(actor=actor, transfer_id=transfer_id)
    case = rules.lock_case(visible.case_id)
    from .case_coverage_tasks import reconcile_returns

    reconcile_returns(actor=actor, case_id=case.pk)
    item = transfers().select_for_update(of=("self",)).get(pk=visible.pk)
    item.case = case
    rules.require_version(item, expected_version)
    if rules.state_at(item) in {"ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"}:
        rules.fail("terminal_arrangement", "This review ended. Another arrangement is needed.")
    ids = lock_work(item) | {actor.pk}
    people = rules.lock_people(ids)
    actor = rules.current_actor(people[actor.pk])
    now = timezone.now()  # Recheck after the case/User waits, never before them.
    if rules.state_at(item, now) == "EXPIRED":
        rules.fail("review_expired", "The review window ended. Another arrangement is needed.")
    rules.require_case_current(case, item.outgoing_counselor_id)
    from .case_transfer_models import CaseArrangementDecisionReason

    if action == "authorize":
        if not can_authorize(actor, item, now):
            rules.fail(
                "authorization_denied",
                "Only an independent current Head can authorize this request.",
                403,
            )
        validate_plans(item, actor=people[item.prepared_by_id], now=now)
        if not rules.receiver_eligible(people[item.receiving_counselor_id], now):
            rules.fail("receiver_ineligible", "The receiving Counselor is no longer eligible.")
        from .case_handoff_services import require_ready

        require_ready(item, now=now)
        item.state = CaseArrangementState.AUTHORIZED
        item.authorization_route = CaseAuthorizationRoute.INDEPENDENT_HEAD
        item.independent_authorization = True
        item.authorized_by, item.authorized_at = actor, now
        item.authorized_version = item.version + 1
        item.review_expires_at = now + rules.REVIEW_WINDOW
    elif action == "accept":
        if (
            actor.pk != item.receiving_counselor_id
            or not rules.receiver_eligible(actor, now)
            or not actor.has_capability("counseling.continuity.read_selected", at=now)
        ):
            rules.fail(
                "acceptance_denied",
                "Only the eligible receiving Counselor can accept this case.",
                403,
            )
        rules.require_review(item, now)
        require_current_authorization(item, people, now)
        from .case_handoff_services import require_ready

        require_ready(item, now=now, verify_content=True)
        if item.case_handoff_id and not actor.has_capability(
            "counseling.handoff.read_received", at=now
        ):
            rules.fail(
                "handoff_read_denied", "The receiving Counselor cannot read the submitted handoff."
            )
        if conflicting_coverage(case, now):
            rules.fail(
                "coverage_conflict",
                "The case has conflicting coverage. End it explicitly or wait for expiry.",
            )
        plans, tasks = validate_plans(
            item, actor=people[item.prepared_by_id], now=now, accepting=True
        )
        if plans and not actor.has_capability("guidance_followups.manage", at=now):
            rules.fail(
                "receiver_tasks_ineligible",
                "The receiving Counselor cannot manage the planned case actions.",
            )
        case.primary_counselor = actor
        case.version += 1
        case.save(update_fields=["primary_counselor", "version", "updated_at"])
        CounselingCaseResponsibility.objects.filter(case=case, ended_at__isnull=True).update(
            ended_at=now
        )
        CounselingCaseResponsibility.objects.create(
            case=case, counselor=actor, transfer=item, started_at=now
        )
        apply_task_plans(
            item,
            plans,
            tasks,
            receiver=actor,
            requester=people[item.prepared_by_id],
            context=context,
            now=now,
        )
        item.state = CaseArrangementState.ACCEPTED
        item.decided_at, item.decided_by = now, actor
    elif action in {"decline", "cancel"}:
        if reason not in CaseArrangementDecisionReason.values or reason == "REVIEW_WINDOW_ENDED":
            rules.fail(
                "decision_reason_required", "Choose a bounded reason for this decision.", 422
            )
        if action == "decline":
            permitted = can_authorize(actor, item, now) or (
                actor.pk == item.receiving_counselor_id
                and item.state == "AUTHORIZED"
                and rules.receiver_eligible(actor, now)
                and actor.has_capability("counseling.continuity.read_selected", at=now)
            )
        else:
            permitted = (
                actor.pk == item.prepared_by_id
                and actor.has_capability("counseling.continuity.request", at=now)
            ) or (
                is_head(actor)
                and actor.pk != item.receiving_counselor_id
                and actor.has_capability("counseling.continuity.revoke", at=now)
            )
        if not permitted:
            rules.fail("decision_denied", "This decision is unavailable to your account.", 403)
        item.state = (
            CaseArrangementState.DECLINED if action == "decline" else CaseArrangementState.CANCELLED
        )
        item.decided_at, item.decided_by, item.decision_reason = now, actor, reason
    else:
        rules.fail("action_invalid", "Choose a supported transfer decision.", 422)
    _save(item)
    audit(
        item,
        {
            "authorize": "authorized",
            "accept": "accepted",
            "decline": "declined",
            "cancel": "cancelled",
        }[action],
        actor=actor,
        context=context,
    )
    if action == "authorize":
        notify_next_actor(item)
    return item


def notification_is_current(notification, now=None):
    now = now or timezone.now()
    actor = (
        User.objects.select_related("role")
        .filter(pk=notification.recipient_id, is_active=True)
        .first()
    )
    item = transfers().filter(pk=notification.target_id).first()
    if (
        not actor
        or not item
        or notification.source_id != item.pk
        or notification.source_type != f"case_transfer_v{item.version}"
        or not actor.has_capability("counseling.continuity.view", at=now)
    ):
        return False
    from .case_handoff_services import may_record_exception

    return (
        can_authorize(actor, item, now)
        or (item.office_preparation_reason and may_record_exception(actor, item, now))
        or (
            item.state == "PREPARED"
            and item.submitted_at is None
            and item.handoff_exception_id
            and actor.pk == item.prepared_by_id
            and actor.has_capability("counseling.continuity.request", at=now)
        )
        or (
            rules.state_at(item, now) == "AUTHORIZED"
            and item.receiving_counselor_id == actor.pk
            and rules.receiver_eligible(actor, now)
            and actor.has_capability("counseling.continuity.read_selected", at=now)
        )
    )
