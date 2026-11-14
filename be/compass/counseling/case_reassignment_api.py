"""RA-1 API: case-continuity approval for reassigning a session of an Active case.

Responses name people and the Appointment only. They carry no case narrative, notes or handoff
content: the receiving Counselor learns that the session belongs to another Counselor's case and
nothing else.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.utils import timezone
from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.accounts.profile_photos import profile_photo_projection
from compass.appointments.services import AppointmentError
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .case_continuity_rules import CaseContinuityError
from .case_reassignment_models import (
    MAX_DECISION_REASON,
    MAX_REASSIGNMENT_REASON,
    CaseReassignmentState,
)
from .case_reassignment_services import (
    can_approve,
    decide_reassignment,
    effective_state,
    get_reassignment,
    reassignment_context,
    request_reassignment,
)

router = Router(tags=["counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CaseReassignmentStateValue(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class CaseReassignmentRouteValue(StrEnum):
    INDEPENDENT_HEAD = "INDEPENDENT_HEAD"
    DIRECT_OUTGOING_HEAD = "DIRECT_OUTGOING_HEAD"
    OWNER_TO_HEAD = "OWNER_TO_HEAD"


class CaseReassignmentAction(StrEnum):
    APPROVE = "approve"
    DECLINE = "decline"
    WITHDRAW = "withdraw"


class CaseReassignmentPerson(StrictSchema):
    id: UUID
    display_name: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class CaseReassignmentAppointment(StrictSchema):
    id: UUID
    reference_code: str
    status: str
    service_name: str
    delivery_mode: str
    starts_at: datetime
    ends_at: datetime


class CaseReassignmentResponse(StrictSchema):
    id: UUID
    state: CaseReassignmentStateValue
    route: CaseReassignmentRouteValue
    appointment: CaseReassignmentAppointment
    student: CaseReassignmentPerson
    case_reference_code: str
    case_owner: CaseReassignmentPerson
    requested_by: CaseReassignmentPerson
    from_provider: CaseReassignmentPerson
    to_provider: CaseReassignmentPerson
    reason: str
    requested_at: datetime
    decided_by: CaseReassignmentPerson | None
    decided_at: datetime | None
    decision_reason: str
    version: int
    can_approve: bool
    can_withdraw: bool


class CaseReassignmentContextResponse(StrictSchema):
    # Present when the Appointment is part of an Active case: moving it to anyone but this
    # Counselor needs the case-continuity request.
    case_owner: CaseReassignmentPerson | None
    pending: CaseReassignmentResponse | None


class CaseReassignmentRequest(StrictSchema):
    provider_id: UUID
    reason: str = Field(max_length=MAX_REASSIGNMENT_REASON)
    acknowledged: bool


class CaseReassignmentDecisionRequest(StrictSchema):
    action: CaseReassignmentAction
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=MAX_DECISION_REASON)


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _raise(exc: Exception) -> NoReturn:
    if isinstance(exc, CaseContinuityError):
        raise APIError(exc.status, exc.code, exc.message) from None
    if isinstance(exc, AppointmentError):
        from compass.appointments.api import _raise as appointment_raise

        appointment_raise(exc)
    raise exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name(), **profile_photo_projection(user)}


def _payload(item, actor, now) -> dict[str, object]:
    appointment = item.appointment
    state = effective_state(item, now=now)
    return {
        "id": item.pk,
        "state": state,
        "route": item.route,
        "appointment": {
            "id": appointment.pk,
            "reference_code": appointment.reference_code,
            "status": appointment.status,
            "service_name": appointment.service.name,
            "delivery_mode": appointment.delivery_mode,
            "starts_at": appointment.starts_at,
            "ends_at": appointment.ends_at,
        },
        "student": _person(appointment.student),
        "case_reference_code": item.case.reference_code,
        "case_owner": _person(item.case_owner),
        "requested_by": _person(item.requested_by),
        "from_provider": _person(item.from_provider),
        "to_provider": _person(item.to_provider),
        "reason": item.reason,
        "requested_at": item.created_at,
        "decided_by": _person(item.decided_by) if item.decided_by_id else None,
        "decided_at": item.decided_at,
        "decision_reason": item.decision_reason,
        "version": item.version,
        "can_approve": state == CaseReassignmentState.PENDING and can_approve(actor, item, now),
        "can_withdraw": state == CaseReassignmentState.PENDING and actor.pk == item.requested_by_id,
    }


@router.get(
    "/appointments/{appointment_id}/reassignment",
    response=response_with_errors(CaseReassignmentContextResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="counselingGetAppointmentReassignmentContext",
)
def appointment_reassignment_context(request, appointment_id: UUID):
    try:
        found = reassignment_context(actor=request.auth_user, appointment_id=appointment_id)
    except CaseContinuityError as exc:
        _raise(exc)
    now = found["now"]
    return {
        "case_owner": _person(found["case_owner"]) if found["case_owner"] is not None else None,
        "pending": _payload(found["pending"], request.auth_user, now) if found["pending"] else None,
    }


@router.post(
    "/appointments/{appointment_id}/reassignment-requests",
    response=response_with_errors(
        CaseReassignmentResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="counselingRequestAppointmentReassignment",
)
def appointment_reassignment_request(
    request, appointment_id: UUID, payload: CaseReassignmentRequest
):
    try:
        item = request_reassignment(
            actor=request.auth_user,
            appointment_id=appointment_id,
            provider_id=payload.provider_id,
            reason=payload.reason,
            acknowledged=payload.acknowledged,
            context=_context(request),
        )
    except (CaseContinuityError, AppointmentError) as exc:
        _raise(exc)
    return Status(201, _payload(item, request.auth_user, timezone.now()))


@router.get(
    "/appointment-reassignments/{reassignment_id}",
    response=response_with_errors(CaseReassignmentResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="counselingGetAppointmentReassignment",
)
def appointment_reassignment_detail(request, reassignment_id: UUID):
    now = timezone.now()
    try:
        item = get_reassignment(actor=request.auth_user, reassignment_id=reassignment_id, now=now)
    except CaseContinuityError as exc:
        _raise(exc)
    return _payload(item, request.auth_user, now)


@router.post(
    "/appointment-reassignments/{reassignment_id}/decision",
    response=response_with_errors(CaseReassignmentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingDecideAppointmentReassignment",
)
def appointment_reassignment_decision(
    request, reassignment_id: UUID, payload: CaseReassignmentDecisionRequest
):
    try:
        item = decide_reassignment(
            actor=request.auth_user,
            reassignment_id=reassignment_id,
            action=payload.action.value,
            expected_version=payload.expected_version,
            reason=payload.reason,
            context=_context(request),
        )
    except (CaseContinuityError, AppointmentError) as exc:
        _raise(exc)
    if (
        payload.action == CaseReassignmentAction.APPROVE
        and item.state == CaseReassignmentState.EXPIRED
    ):
        raise APIError(
            409,
            "case_continuity_reassignment_expired",
            "The Appointment or case changed after this request, so it no longer applies. "
            "Ask for a new request if the session still needs another Counselor.",
        )
    return _payload(item, request.auth_user, timezone.now())
