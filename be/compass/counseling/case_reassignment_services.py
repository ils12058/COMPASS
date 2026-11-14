"""RA-1: reassigning a session of an Active Counseling case follows the case-transfer route.

* An Appointment with no current link to an Active case is reassigned directly, as before.
* Moving a case-linked session back to the case's own Counselor is also direct.
* Otherwise the move is a request. ``authorization_route`` (the transfer rule) decides it: an
  independent current Head approves it (INDEPENDENT_HEAD), or, when the case owner is the Head or
  the single-Head rule applies, it is applied at once and recorded with its route. With no eligible
  approver it is refused, exactly as a transfer would be.
* Until approval the Appointment stays with its current Counselor. A request whose Appointment,
  case or authorization route changed is no longer current and never applies.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.access import appointment_management_access_allowed
from compass.appointments.models import Appointment
from compass.audit.actions import (
    COUNSELING_CASE_REASSIGNMENT_APPROVED,
    COUNSELING_CASE_REASSIGNMENT_DECLINED,
    COUNSELING_CASE_REASSIGNMENT_EXPIRED,
    COUNSELING_CASE_REASSIGNMENT_REQUESTED,
    COUNSELING_CASE_REASSIGNMENT_WITHDRAWN,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import create_notification_for_event

from . import case_continuity_rules as rules
from .case_continuity_rules import fail
from .case_models import CounselingCase, CounselingCaseAppointment
from .case_reassignment_models import (
    MAX_DECISION_REASON,
    MAX_REASSIGNMENT_REASON,
    CaseAppointmentReassignment,
    CaseReassignmentState,
)
from .case_transfer_models import CaseAuthorizationRoute
from .continuity_rules import is_head

APPROVE_CAPABILITY = "counseling.continuity.approve"


def active_case_for(appointment: Appointment, *, lock: bool = False) -> CounselingCase | None:
    """The Active case this Appointment currently belongs to, if any."""

    link = (
        CounselingCaseAppointment.objects.filter(
            appointment_id=appointment.pk, removed_at__isnull=True, case__status="ACTIVE"
        )
        .order_by("linked_at")
        .first()
    )
    if link is None:
        return None
    query = CounselingCase.objects.select_related("primary_counselor__role")
    if lock:
        query = query.select_for_update(of=("self",))
    return query.get(pk=link.case_id)


def require_plain_reassignment(*, appointment: Appointment, provider_id: UUID) -> None:
    """Called by the direct reassignment: case-linked sessions use the request below."""

    case = active_case_for(appointment)
    if case is not None and provider_id != case.primary_counselor_id:
        fail(
            "reassignment_request_required",
            "This Appointment is part of a counseling case. Request the reassignment so it follows "
            "the case-continuity approval.",
        )


def _clean(value: str | None, *, limit: int, required: bool, label: str) -> str:
    text = (value or "").strip()
    if required and not text:
        fail("reassignment_reason_required", f"Enter the {label}.", 422)
    if len(text) > limit:
        fail(
            "reassignment_reason_too_long", f"The {label} must be {limit} characters or fewer.", 422
        )
    return text


def can_approve(actor: User, item: CaseAppointmentReassignment, now: datetime) -> bool:
    return bool(
        item.state == CaseReassignmentState.PENDING
        and item.route == CaseAuthorizationRoute.INDEPENDENT_HEAD
        and actor.pk not in {item.requested_by_id, item.to_provider_id}
        and is_head(actor)
        and actor.has_capability(APPROVE_CAPABILITY, at=now)
    )


def is_current(item: CaseAppointmentReassignment, *, now: datetime) -> bool:
    """A pending request applies only to the Appointment and case the Head reviewed."""

    appointment = item.appointment
    if (
        appointment.status != "SCHEDULED"
        or appointment.starts_at != item.appointment_starts_at
        or appointment.starts_at <= now
        or appointment.provider_id != item.from_provider_id
    ):
        return False
    case = active_case_for(appointment)
    return bool(
        case and case.pk == item.case_id and case.primary_counselor_id == item.case_owner_id
    )


def effective_state(item: CaseAppointmentReassignment, *, now: datetime) -> str:
    if item.state == CaseReassignmentState.PENDING and not is_current(item, now=now):
        return CaseReassignmentState.EXPIRED
    return item.state


def may_view(actor: User, item: CaseAppointmentReassignment, now: datetime) -> bool:
    if actor.pk in {item.requested_by_id, item.case_owner_id, item.decided_by_id}:
        return True
    if actor.pk == item.to_provider_id and item.state == CaseReassignmentState.APPROVED:
        return True
    return bool(is_head(actor) and actor.has_capability(APPROVE_CAPABILITY, at=now))


def _queryset():
    return CaseAppointmentReassignment.objects.select_related(
        "appointment__student__role",
        "appointment__provider__role",
        "appointment__service",
        "case",
        "requested_by__role",
        "from_provider__role",
        "to_provider__role",
        "case_owner__role",
        "decided_by__role",
    )


def _audit(item, action, *, context, extra=None):
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.caseappointmentreassignment",
        target_id=item.pk,
        metadata={
            "appointment_id": str(item.appointment_id),
            "case_id": str(item.case_id),
            "route": item.route,
            "from_provider_id": str(item.from_provider_id),
            "to_provider_id": str(item.to_provider_id),
            **(extra or {}),
        },
    )


def _notify(recipients, item, event):
    for recipient in {person.pk: person for person in recipients}.values():
        create_notification_for_event(
            recipient=recipient,
            event=event,
            source_type=f"case_reassignment:{item.state.lower()}",
            source_id=item.pk,
            target_type=NotificationTargetType.APPOINTMENT_REASSIGNMENT,
            target_id=item.pk,
        )


def _expire(item, *, now, context):
    item.state = CaseReassignmentState.EXPIRED
    item.decided_at = now
    item.version += 1
    item.save(update_fields=["state", "decided_at", "version", "updated_at"])
    _audit(item, COUNSELING_CASE_REASSIGNMENT_EXPIRED, context=context)


def reassignment_context(*, actor: User, appointment_id: UUID, now: datetime | None = None):
    """What the reassign dialog and the Appointment page need: the case owner and any request."""

    now = now or timezone.now()
    appointment = (
        Appointment.objects.select_related("provider", "student").filter(pk=appointment_id).first()
    )
    if appointment is None or not appointment_management_access_allowed(actor, appointment):
        fail("reassignment_not_found", "The requested Appointment was not found.", 404)
    case = active_case_for(appointment)
    pending = (
        _queryset().filter(appointment=appointment, state=CaseReassignmentState.PENDING).first()
    )
    return {
        "case_owner": case.primary_counselor if case is not None else None,
        "pending": pending,
        "now": now,
    }


def request_reassignment(
    *,
    actor: User,
    appointment_id: UUID,
    provider_id: UUID,
    reason: str,
    acknowledged: bool,
    context: AuditContext,
    now: datetime | None = None,
) -> CaseAppointmentReassignment:
    from compass.appointments.services import (
        apply_case_reassignment,
        lock_appointment_for_reassignment,
        validate_case_reassignment,
    )

    now = now or timezone.now()
    cleaned = _clean(reason, limit=MAX_REASSIGNMENT_REASON, required=True, label="reason")
    if not acknowledged:
        fail(
            "reassignment_acknowledgement_required",
            "Confirm that the case stays with its Counselor.",
            422,
        )
    try:
        with transaction.atomic():
            appointment = lock_appointment_for_reassignment(appointment_id)
            if not appointment_management_access_allowed(actor, appointment):
                fail("reassignment_not_found", "The requested Appointment was not found.", 404)
            case = active_case_for(appointment, lock=True)
            if case is None:
                fail(
                    "reassignment_not_case_linked",
                    "This Appointment isn't part of an Active case. Reassign it directly.",
                    422,
                )
            if provider_id in {appointment.provider_id, case.primary_counselor_id}:
                fail(
                    "reassignment_direct",
                    "Reassign it directly. This Counselor needs no case-continuity approval.",
                    422,
                )
            for stale in CaseAppointmentReassignment.objects.select_for_update().filter(
                appointment=appointment, state=CaseReassignmentState.PENDING
            ):
                if is_current(stale, now=now):
                    fail(
                        "reassignment_pending",
                        "A reassignment for this Appointment is already waiting for the Head.",
                    )
                _expire(stale, now=now, context=context)
            receiver = validate_case_reassignment(
                item=appointment, provider_id=provider_id, now=now
            )
            requester = User.objects.select_related("role").get(pk=actor.pk)
            route = rules.authorization_route(
                requester=requester, receiver=receiver, case=case, now=now
            )
            item = CaseAppointmentReassignment.objects.create(
                appointment=appointment,
                case=case,
                requested_by=requester,
                from_provider=appointment.provider,
                to_provider=receiver,
                case_owner=case.primary_counselor,
                appointment_starts_at=appointment.starts_at,
                reason=cleaned,
                route=route,
                created_at=now,
            )
            _audit(item, COUNSELING_CASE_REASSIGNMENT_REQUESTED, context=context)
            if route != CaseAuthorizationRoute.INDEPENDENT_HEAD:
                # The case owner is the Head, or the single-Head rule applies: no independent
                # approver exists, so the route itself is recorded as the authorization.
                apply_case_reassignment(
                    item=appointment,
                    provider_id=receiver.pk,
                    changed_by=requester,
                    reason=cleaned,
                    context=context,
                    now=now,
                    audit_extra={"case_reassignment_id": str(item.pk), "case_route": route},
                )
                item.state = CaseReassignmentState.APPROVED
                item.decided_by = requester
                item.decided_at = now
                item.version += 1
                item.save()
                _audit(
                    item,
                    COUNSELING_CASE_REASSIGNMENT_APPROVED,
                    context=context,
                    extra={"independent": False},
                )
                if case.primary_counselor_id != requester.pk:
                    _notify(
                        [case.primary_counselor], item, NotificationEvent.CASE_REASSIGNMENT_DECIDED
                    )
            else:
                approvers = rules.eligible_authorizers(
                    requester_id=requester.pk, receiver_id=receiver.pk, now=now
                )
                _notify(approvers, item, NotificationEvent.CASE_REASSIGNMENT_REVIEW)
            return _queryset().get(pk=item.pk)
    except IntegrityError:
        fail(
            "reassignment_pending",
            "A reassignment for this Appointment is already waiting for the Head.",
        )


class ReassignmentDecision:
    APPROVE = "approve"
    DECLINE = "decline"
    WITHDRAW = "withdraw"


def decide_reassignment(
    *,
    actor: User,
    reassignment_id: UUID,
    action: str,
    expected_version: int,
    reason: str | None,
    context: AuditContext,
    now: datetime | None = None,
) -> CaseAppointmentReassignment:
    from compass.appointments.services import (
        apply_case_reassignment,
        lock_appointment_for_reassignment,
    )

    now = now or timezone.now()
    if action not in {
        ReassignmentDecision.APPROVE,
        ReassignmentDecision.DECLINE,
        ReassignmentDecision.WITHDRAW,
    }:
        fail("reassignment_action_invalid", "Choose approve, decline or withdraw.", 422)
    note = _clean(reason, limit=MAX_DECISION_REASON, required=False, label="decision note")
    with transaction.atomic():
        found = (
            CaseAppointmentReassignment.objects.select_for_update()
            .filter(pk=reassignment_id)
            .first()
        )
        if found is None or not may_view(actor, found, now):
            fail("reassignment_not_found", "The reassignment request was not found.", 404)
        # The Appointment row is the first lock of every reassignment path.
        appointment = lock_appointment_for_reassignment(found.appointment_id)
        item = _queryset().select_for_update(of=("self",)).get(pk=found.pk)
        if item.version != expected_version:
            fail("reassignment_changed", "This request changed. Review the latest version.")
        if item.state != CaseReassignmentState.PENDING:
            fail("reassignment_not_pending", "This request has already been decided.")

        if action == ReassignmentDecision.WITHDRAW:
            if actor.pk != item.requested_by_id:
                fail("reassignment_not_found", "The reassignment request was not found.", 404)
            item.state = CaseReassignmentState.WITHDRAWN
            item.decided_at = now
            item.version += 1
            item.save()
            _audit(item, COUNSELING_CASE_REASSIGNMENT_WITHDRAWN, context=context)
            return _queryset().get(pk=item.pk)

        if not can_approve(actor, item, now):
            fail(
                "reassignment_approval_denied",
                "Only an independent current Head can decide this request.",
                403,
            )

        if action == ReassignmentDecision.DECLINE:
            item.state = CaseReassignmentState.DECLINED
            item.decided_by, item.decided_at, item.decision_reason = actor, now, note
            item.version += 1
            item.save()
            _audit(item, COUNSELING_CASE_REASSIGNMENT_DECLINED, context=context)
            _notify(
                [item.requested_by, item.case_owner],
                item,
                NotificationEvent.CASE_REASSIGNMENT_DECIDED,
            )
            return _queryset().get(pk=item.pk)

        current_route = None
        if is_current(item, now=now):
            case = active_case_for(appointment, lock=True)
            current_route = rules.authorization_route(
                requester=item.requested_by, receiver=item.to_provider, case=case, now=now
            )
        if current_route != CaseAuthorizationRoute.INDEPENDENT_HEAD:
            # The Appointment, case or route changed: the reviewed move never applies. The expiry is
            # saved and the API reports it, so the Head sees why nothing happened.
            _expire(item, now=now, context=context)
            return _queryset().get(pk=item.pk)
        apply_case_reassignment(
            item=appointment,
            provider_id=item.to_provider_id,
            changed_by=actor,
            reason=item.reason,
            context=context,
            now=now,
            audit_extra={
                "case_reassignment_id": str(item.pk),
                "case_route": item.route,
                "requested_by_id": str(item.requested_by_id),
            },
        )
        item.state = CaseReassignmentState.APPROVED
        item.decided_by, item.decided_at, item.decision_reason = actor, now, note
        item.version += 1
        item.save()
        _audit(
            item,
            COUNSELING_CASE_REASSIGNMENT_APPROVED,
            context=context,
            extra={"independent": True},
        )
        _notify(
            [item.requested_by, item.case_owner], item, NotificationEvent.CASE_REASSIGNMENT_DECIDED
        )
        return _queryset().get(pk=item.pk)


def get_reassignment(*, actor: User, reassignment_id: UUID, now: datetime | None = None):
    now = now or timezone.now()
    item = _queryset().filter(pk=reassignment_id).first()
    if item is None or not may_view(actor, item, now):
        fail("reassignment_not_found", "The reassignment request was not found.", 404)
    return item


def pending_reassignment_work(*, actor: User, limit: int, now: datetime):
    """Head Work Queue rows: current pending requests this Head may decide."""

    from compass.work_queue.schemas import WorkItem, WorkKind, WorkPriority, WorkStudent

    if not (is_head(actor) and actor.has_capability(APPROVE_CAPABILITY, at=now)):
        return ()
    rows = (
        _queryset()
        .filter(
            state=CaseReassignmentState.PENDING,
            route=CaseAuthorizationRoute.INDEPENDENT_HEAD,
            appointment_starts_at__gt=now,
        )
        .exclude(requested_by=actor)
        .exclude(to_provider=actor)
        .order_by("appointment_starts_at", "created_at", "pk")[: limit * 2]
    )
    items = [row for row in rows if is_current(row, now=now)][:limit]
    return tuple(
        WorkItem(
            id=f"case-reassignment:{row.pk}",
            kind=WorkKind.CASE_REASSIGNMENT_APPROVAL,
            priority=WorkPriority.TIME_SENSITIVE,
            source_id=row.pk,
            student=WorkStudent(
                id=row.appointment.student_id, display_name=row.appointment.student.get_full_name()
            ),
            conversation_kind=None,
            due_at=row.appointment_starts_at,
            waiting_since=row.created_at,
            case_reference_code=row.case.reference_code,
        )
        for row in items
    )
