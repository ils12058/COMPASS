"""NS-1 session proposals: Counselor proposes, Student accepts or declines.

Student responses carry no case information at all. Staff responses go only to the proposing
Counselor and the case's primary Counselor.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.utils import timezone
from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.accounts.profile_photos import profile_photo_projection
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.institutional_time import to_institution_time
from compass.service_catalog.api import DeliveryMode

from .services import CounselingError
from .session_proposal_models import (
    MAX_PROPOSAL_OPTIONS,
    CounselingCaseCallSlip,
    SessionProposalState,
)
from .session_proposal_services import (
    SessionProposalStudentAction,
    SessionProposalTimeUnavailable,
    accept_proposal,
    decline_proposal,
    effective_state,
    get_my_proposal,
    get_proposal_context,
    get_staff_proposal,
    list_my_proposals,
    list_proposal_slots,
    may_propose,
    propose_session,
    withdraw_proposal,
)

router = Router(tags=["counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class SessionProposalStateValue(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class SessionProposalPurposeValue(StrEnum):
    FOLLOW_UP_SESSION = "FOLLOW_UP_SESSION"
    CHECK_IN = "CHECK_IN"
    CONTINUING_SESSION = "CONTINUING_SESSION"


class SessionProposalOptionInput(StrictSchema):
    delivery_mode: DeliveryMode
    starts_at: datetime


class SessionProposalCreateRequest(StrictSchema):
    case_id: UUID
    purpose: SessionProposalPurposeValue
    options: list[SessionProposalOptionInput] = Field(min_length=1, max_length=MAX_PROPOSAL_OPTIONS)
    call_slip_requested: bool = False
    follow_up_id: UUID | None = None
    # Sent from the case page; omitted from a Follow-up, where the case version isn't shown.
    expected_case_version: int | None = Field(default=None, ge=1)


class SessionProposalVersionRequest(StrictSchema):
    expected_version: int = Field(ge=1)


class SessionProposalAcceptRequest(StrictSchema):
    option_id: UUID
    expected_version: int = Field(ge=1)


class SessionProposalOption(StrictSchema):
    id: UUID
    position: int
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime


class SessionProposalPerson(StrictSchema):
    id: UUID
    display_name: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class SessionProposalStudentPerson(SessionProposalPerson):
    institutional_id: str | None


class SessionProposalAppointment(StrictSchema):
    id: UUID
    reference_code: str
    status: str
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime


class SessionProposalCaseReference(StrictSchema):
    id: UUID
    reference_code: str


class SessionProposalCallSlip(StrictSchema):
    id: UUID
    state: str
    report_at: datetime


class SessionProposalStaffResponse(StrictSchema):
    id: UUID
    case: SessionProposalCaseReference
    student: SessionProposalStudentPerson
    proposed_by: SessionProposalPerson
    purpose: SessionProposalPurposeValue
    state: SessionProposalStateValue
    options: list[SessionProposalOption]
    accepted_option_id: UUID | None
    appointment: SessionProposalAppointment | None
    call_slip_requested: bool
    call_slip: SessionProposalCallSlip | None
    # An accepted In person session whose case Call Slip hasn't been issued yet.
    can_issue_call_slip: bool
    can_withdraw: bool
    follow_up_id: UUID | None
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None
    version: int


class SessionProposalStudentResponse(StrictSchema):
    id: UUID
    counselor: SessionProposalPerson
    purpose: SessionProposalPurposeValue
    state: SessionProposalStateValue
    options: list[SessionProposalOption]
    accepted_option_id: UUID | None
    appointment: SessionProposalAppointment | None
    can_respond: bool
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None
    version: int


class SessionProposalStudentPage(StrictSchema):
    items: list[SessionProposalStudentResponse]


class SessionProposalSlot(StrictSchema):
    starts_at: datetime
    ends_at: datetime


class SessionProposalSlotList(StrictSchema):
    date: date
    timezone: str
    duration_minutes: int
    items: list[SessionProposalSlot]


class SessionProposalContextResponse(StrictSchema):
    case: SessionProposalCaseReference
    case_version: int
    student: SessionProposalStudentPerson
    # OWNER, or COVERAGE while a temporary case coverage is active.
    authority: str
    open_proposal: SessionProposalStaffResponse | None
    duration_minutes: int | None
    delivery_modes: list[DeliveryMode]


class CaseCallSlipResponse(StrictSchema):
    id: UUID
    state: str
    report_at: datetime
    appointment: SessionProposalCaseReference | None


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _t(value):
    return to_institution_time(value) if value is not None else None


def _raise(exc: CounselingError) -> NoReturn:
    status = getattr(exc, "status", 409)
    code = getattr(exc, "code", "counseling_not_permitted")
    details = None
    if isinstance(exc, SessionProposalTimeUnavailable):
        details = {"option": exc.option, "reason": exc.reason}
    elif isinstance(exc, SessionProposalStudentAction):
        details = {"reason": exc.reason}
    raise APIError(status, code, str(exc), details=details) from exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name(), **profile_photo_projection(user)}


def _options(proposal) -> list[dict[str, object]]:
    return [
        {
            "id": option.pk,
            "position": option.position,
            "delivery_mode": option.delivery_mode,
            "starts_at": _t(option.starts_at),
            "ends_at": _t(option.ends_at),
        }
        for option in proposal.options.all()
    ]


def _accepted_option_id(proposal):
    if proposal.accepted_position is None:
        return None
    return next(
        (o.pk for o in proposal.options.all() if o.position == proposal.accepted_position), None
    )


def _appointment(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "status": item.status,
        "delivery_mode": item.delivery_mode,
        "starts_at": _t(item.starts_at),
        "ends_at": _t(item.ends_at),
    }


def _call_slip(proposal):
    if proposal.appointment_id is None:
        return None
    link = (
        CounselingCaseCallSlip.objects.filter(appointment_id=proposal.appointment_id)
        .select_related("call_slip")
        .order_by("-linked_at", "-id")
        .first()
    )
    return link.call_slip if link else None


def staff_projection(proposal, *, reader, now=None) -> dict[str, object]:
    at = now or timezone.now()
    state = effective_state(proposal, at=at)
    slip = _call_slip(proposal)
    appointment = proposal.appointment
    can_issue = bool(
        state == SessionProposalState.ACCEPTED
        and appointment is not None
        and appointment.status == "SCHEDULED"
        and appointment.delivery_mode == "IN_PERSON"
        and appointment.starts_at > at
        and (slip is None or slip.voided_at is not None)
        and reader.role.code == "COUNSELOR"
        and reader.has_capability("call_slips.manage")
        and may_propose(actor=reader, case=proposal.case, at=at)
    )
    follow_up_id = None
    if proposal.follow_up_id is not None:
        from compass.guidance_followups import policy

        if policy.authorized(reader, proposal.follow_up):
            follow_up_id = proposal.follow_up_id
    return {
        "id": proposal.pk,
        "case": {"id": proposal.case_id, "reference_code": proposal.case.reference_code},
        "student": {
            **_person(proposal.student),
            "institutional_id": proposal.student.institutional_id,
        },
        "proposed_by": _person(proposal.proposed_by),
        "purpose": proposal.purpose,
        "state": state,
        "options": _options(proposal),
        "accepted_option_id": _accepted_option_id(proposal),
        "appointment": _appointment(appointment),
        "call_slip_requested": proposal.call_slip_requested,
        "call_slip": (
            {"id": slip.pk, "state": slip.lifecycle_state, "report_at": _t(slip.report_at)}
            if slip is not None
            else None
        ),
        "can_issue_call_slip": can_issue,
        "can_withdraw": state == SessionProposalState.PENDING
        and reader.has_capability("counseling.manage_assigned"),
        "follow_up_id": follow_up_id,
        "expires_at": _t(proposal.expires_at),
        "created_at": _t(proposal.created_at),
        "decided_at": _t(proposal.decided_at),
        "version": proposal.version,
    }


def student_projection(proposal, *, now=None) -> dict[str, object]:
    at = now or timezone.now()
    state = effective_state(proposal, at=at)
    return {
        "id": proposal.pk,
        "counselor": _person(proposal.proposed_by),
        "purpose": proposal.purpose,
        "state": state,
        "options": _options(proposal),
        "accepted_option_id": _accepted_option_id(proposal),
        "appointment": _appointment(proposal.appointment),
        "can_respond": state == SessionProposalState.PENDING and proposal.case.status == "ACTIVE",
        "expires_at": _t(proposal.expires_at),
        "created_at": _t(proposal.created_at),
        "decided_at": _t(proposal.decided_at),
        "version": proposal.version,
    }


def case_call_slip_projection(link) -> dict[str, object]:
    return {
        "id": link.call_slip_id,
        "state": link.call_slip.lifecycle_state,
        "report_at": _t(link.call_slip.report_at),
        "appointment": (
            {"id": link.appointment_id, "reference_code": link.appointment.reference_code}
            if link.appointment_id
            else None
        ),
    }


def _require_counselor(request) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code != "COUNSELOR"
        or not user.has_capability("counseling.view_assigned")
    ):
        raise APIError(403, "permission_denied", "You don't have permission to propose sessions.")


def _require_student(request) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code != "STUDENT"
        or not user.has_capability("appointments.manage_self")
    ):
        raise APIError(
            403, "permission_denied", "You don't have permission to answer session proposals."
        )


# --- Student ---------------------------------------------------------------------------------


@router.get(
    "/me",
    response=response_with_errors(SessionProposalStudentPage, 401, 403),
    auth=session_auth,
    operation_id="counselingListMySessionProposals",
)
def counseling_list_my_session_proposals(request):
    _require_student(request)
    try:
        rows = list_my_proposals(actor=request.auth_user)
    except CounselingError as exc:
        _raise(exc)
    return {"items": [student_projection(row) for row in rows]}


@router.get(
    "/me/{proposal_id}",
    response=response_with_errors(SessionProposalStudentResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="counselingGetMySessionProposal",
)
def counseling_get_my_session_proposal(request, proposal_id: UUID):
    _require_student(request)
    try:
        proposal = get_my_proposal(actor=request.auth_user, proposal_id=proposal_id)
    except CounselingError as exc:
        _raise(exc)
    return student_projection(proposal)


@router.post(
    "/me/{proposal_id}/accept",
    response=response_with_errors(SessionProposalStudentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingAcceptSessionProposal",
)
def counseling_accept_session_proposal(
    request, proposal_id: UUID, payload: SessionProposalAcceptRequest
):
    _require_student(request)
    try:
        proposal = accept_proposal(
            actor=request.auth_user,
            proposal_id=proposal_id,
            option_id=payload.option_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return student_projection(proposal)


@router.post(
    "/me/{proposal_id}/decline",
    response=response_with_errors(SessionProposalStudentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingDeclineSessionProposal",
)
def counseling_decline_session_proposal(
    request, proposal_id: UUID, payload: SessionProposalVersionRequest
):
    _require_student(request)
    try:
        proposal = decline_proposal(
            actor=request.auth_user,
            proposal_id=proposal_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return student_projection(proposal)


# --- Counselor -------------------------------------------------------------------------------


@router.get(
    "/context",
    response=response_with_errors(SessionProposalContextResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="counselingGetSessionProposalContext",
)
def counseling_get_session_proposal_context(request, case_id: UUID):
    _require_counselor(request)
    try:
        result = get_proposal_context(actor=request.auth_user, case_id=case_id)
    except CounselingError as exc:
        _raise(exc)
    return {
        "case": {"id": result.case.pk, "reference_code": result.case.reference_code},
        "case_version": result.case.version,
        "student": {**_person(result.student), "institutional_id": result.student.institutional_id},
        "authority": result.authority,
        "open_proposal": (
            staff_projection(result.open_proposal, reader=request.auth_user)
            if result.open_proposal is not None
            else None
        ),
        "duration_minutes": result.duration_minutes,
        "delivery_modes": list(result.delivery_modes),
    }


@router.get(
    "/slots",
    response=response_with_errors(SessionProposalSlotList, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingListSessionProposalSlots",
)
def counseling_list_session_proposal_slots(
    request, case_id: UUID, delivery_mode: DeliveryMode, date: date
):
    _require_counselor(request)
    try:
        result = list_proposal_slots(
            actor=request.auth_user,
            case_id=case_id,
            delivery_mode=delivery_mode.value,
            target_date=date,
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "date": result.date,
        "timezone": result.timezone_name,
        "duration_minutes": result.duration_minutes,
        "items": [
            {"starts_at": _t(item.starts_at), "ends_at": _t(item.ends_at)} for item in result.items
        ],
    }


@router.post(
    "",
    response=response_with_errors(
        SessionProposalStaffResponse, 401, 403, 404, 409, 422, 503, success_status=201
    ),
    auth=session_auth,
    operation_id="counselingProposeSession",
)
def counseling_propose_session(request, payload: SessionProposalCreateRequest):
    _require_counselor(request)
    try:
        proposal = propose_session(
            actor=request.auth_user,
            case_id=payload.case_id,
            purpose=payload.purpose.value,
            options=payload.options,
            call_slip_requested=payload.call_slip_requested,
            follow_up_id=payload.follow_up_id,
            expected_version=payload.expected_case_version,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return Status(201, staff_projection(proposal, reader=request.auth_user))


@router.get(
    "/{proposal_id}",
    response=response_with_errors(SessionProposalStaffResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="counselingGetSessionProposal",
)
def counseling_get_session_proposal(request, proposal_id: UUID):
    _require_counselor(request)
    try:
        proposal = get_staff_proposal(actor=request.auth_user, proposal_id=proposal_id)
    except CounselingError as exc:
        _raise(exc)
    return staff_projection(proposal, reader=request.auth_user)


@router.post(
    "/{proposal_id}/withdraw",
    response=response_with_errors(SessionProposalStaffResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingWithdrawSessionProposal",
)
def counseling_withdraw_session_proposal(
    request, proposal_id: UUID, payload: SessionProposalVersionRequest
):
    _require_counselor(request)
    try:
        proposal = withdraw_proposal(
            actor=request.auth_user,
            proposal_id=proposal_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return staff_projection(proposal, reader=request.auth_user)
