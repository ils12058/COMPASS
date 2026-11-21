"""Thin Django Ninja API for Student counselor-change requests and Head approvals (ADR-120)."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.accounts.profile_photos import profile_photo_projection
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.institutional_time import institution_zone

from .counselor_access_models import CounselorBookingRequestState
from .counselor_access_services import (
    DEFAULT_PAGE_SIZE,
    CounselorBookingAccessConflict,
    CounselorBookingAccessDenied,
    CounselorBookingAccessError,
    CounselorBookingAccessInvalid,
    CounselorBookingAccessNotFound,
    CounselorBookingContentUnavailable,
    CounselorBookingHeadUnavailable,
    CounselorBookingRequestPendingConflict,
    CounselorBookingVersionConflict,
    CounselorRequestDecisionAction,
    change_counselor_approval,
    decide_counselor_booking_request,
    end_counselor_approval,
    get_head_counselor_request,
    get_student_counselor_request_state,
    list_head_counselor_approvals,
    list_head_counselor_requests,
    submit_counselor_booking_request,
)

router = Router(tags=["appointments"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CounselorOptionResponse(StrictSchema):
    id: UUID
    display_name: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class CounselorActorSummary(StrictSchema):
    id: UUID
    display_name: str


class StudentActiveCounselorApprovalResponse(StrictSchema):
    id: UUID
    counselor: CounselorOptionResponse
    approved_at: datetime


class StudentCounselorRequestSummary(StrictSchema):
    """Student-visible request summary; never exposes confidential reason text."""

    id: UUID
    state: CounselorBookingRequestState
    preferred_counselor: CounselorOptionResponse | None
    created_at: datetime


class StudentCounselorRequestDecisionSummary(StrictSchema):
    """Student-visible outcome of a decided request; never exposes confidential reason text."""

    id: UUID
    state: CounselorBookingRequestState
    preferred_counselor: CounselorOptionResponse | None
    approved_counselor: CounselorOptionResponse | None
    decision_note: str
    decided_at: datetime


class StudentCounselorRequestStateResponse(StrictSchema):
    default_counselor: CounselorOptionResponse | None
    active_approval: StudentActiveCounselorApprovalResponse | None
    pending_request: StudentCounselorRequestSummary | None
    latest_decision: StudentCounselorRequestDecisionSummary | None
    head_available: bool
    requestable_counselors: list[CounselorOptionResponse]


class CounselorBookingRequestCreate(StrictSchema):
    preferred_counselor_id: UUID | None = None
    reason: str | None = None


class CounselorRequestStudentSummary(StrictSchema):
    id: UUID
    institutional_id: str | None
    display_name: str
    college_name: str | None
    campus_name: str | None


class HeadCounselorApprovalItem(StrictSchema):
    id: UUID
    student: CounselorRequestStudentSummary
    default_counselor: CounselorOptionResponse | None
    counselor: CounselorOptionResponse
    counselor_is_active: bool
    source_request_id: UUID | None
    approved_by: CounselorActorSummary
    approved_at: datetime
    ended_at: datetime | None
    ended_by: CounselorActorSummary | None
    version: int


class HeadCounselorRequestSummary(StrictSchema):
    id: UUID
    student: CounselorRequestStudentSummary
    default_counselor: CounselorOptionResponse | None
    preferred_counselor: CounselorOptionResponse | None
    approved_counselor: CounselorOptionResponse | None
    state: CounselorBookingRequestState
    created_at: datetime
    decided_at: datetime | None
    version: int


class HeadCounselorRequestDetailResponse(HeadCounselorRequestSummary):
    """Head-only detail projection; the only API surface that returns the confidential reason."""

    reason: str | None
    decision_note: str
    decided_by: CounselorActorSummary | None
    current_approval: StudentActiveCounselorApprovalResponse | None
    available_counselors: list[CounselorOptionResponse]
    can_decide: bool


class HeadCounselorRequestPageResponse(StrictSchema):
    items: list[HeadCounselorRequestSummary]
    page: int
    page_size: int
    has_next: bool


class HeadCounselorRequestDecisionRequest(StrictSchema):
    action: CounselorRequestDecisionAction
    approved_counselor_id: UUID | None = None
    note: str | None = None
    expected_version: int


class HeadCounselorApprovalPageResponse(StrictSchema):
    items: list[HeadCounselorApprovalItem]
    page: int
    page_size: int
    has_next: bool
    available_counselors: list[CounselorOptionResponse]
    can_manage: bool


class HeadCounselorApprovalChangeRequest(StrictSchema):
    counselor_id: UUID
    expected_version: int


class HeadCounselorApprovalEndRequest(StrictSchema):
    expected_version: int


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _institutional(value: datetime | None) -> datetime | None:
    return value.astimezone(institution_zone()) if value is not None else None


def _counselor(user) -> dict[str, object] | None:
    if user is None:
        return None
    return {
        "id": user.pk,
        "display_name": user.get_full_name(),
        **profile_photo_projection(user),
    }


def _actor(user) -> dict[str, object] | None:
    if user is None:
        return None
    return {"id": user.pk, "display_name": user.get_full_name()}


def _student_context(ctx) -> dict[str, object]:
    return {
        "id": ctx.student.pk,
        "institutional_id": ctx.student.institutional_id,
        "display_name": ctx.student.get_full_name(),
        "college_name": ctx.college_name,
        "campus_name": ctx.campus_name,
    }


def _student_request(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "state": item.state,
        "preferred_counselor": _counselor(item.preferred_counselor),
        "created_at": _institutional(item.created_at),
    }


def _student_decision(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "state": item.state,
        "preferred_counselor": _counselor(item.preferred_counselor),
        "approved_counselor": _counselor(item.approved_counselor),
        "decision_note": item.decision_note,
        "decided_at": _institutional(item.decided_at),
    }


def _active_approval(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "id": item.pk,
        "counselor": _counselor(item.counselor),
        "approved_at": _institutional(item.approved_at),
    }


def _head_request_summary(entry) -> dict[str, object]:
    item = entry.request
    return {
        "id": item.pk,
        "student": _student_context(entry.student_context),
        "default_counselor": _counselor(entry.student_context.default_counselor),
        "preferred_counselor": _counselor(item.preferred_counselor),
        "approved_counselor": _counselor(item.approved_counselor),
        "state": item.state,
        "created_at": _institutional(item.created_at),
        "decided_at": _institutional(item.decided_at),
        "version": item.version,
    }


def _head_request_detail(detail) -> dict[str, object]:
    item = detail.request
    return {
        "id": item.pk,
        "student": _student_context(detail.student_context),
        "default_counselor": _counselor(detail.student_context.default_counselor),
        "preferred_counselor": _counselor(item.preferred_counselor),
        "approved_counselor": _counselor(item.approved_counselor),
        "state": item.state,
        "created_at": _institutional(item.created_at),
        "decided_at": _institutional(item.decided_at),
        "version": item.version,
        "reason": detail.reason,
        "decision_note": item.decision_note,
        "decided_by": _actor(item.decided_by),
        "current_approval": _active_approval(detail.current_approval),
        "available_counselors": [_counselor(c) for c in detail.available_counselors],
        "can_decide": detail.can_decide,
    }


def _head_approval(entry) -> dict[str, object]:
    item = entry.approval
    return {
        "id": item.pk,
        "student": _student_context(entry.student_context),
        "default_counselor": _counselor(entry.student_context.default_counselor),
        "counselor": _counselor(item.counselor),
        "counselor_is_active": entry.counselor_is_active,
        "source_request_id": item.source_request_id,
        "approved_by": _actor(item.approved_by),
        "approved_at": _institutional(item.approved_at),
        "ended_at": _institutional(item.ended_at),
        "ended_by": _actor(item.ended_by),
        "version": item.version,
    }


def _raise(exc: CounselorBookingAccessError) -> NoReturn:
    if isinstance(exc, CounselorBookingAccessDenied):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, CounselorBookingAccessNotFound):
        raise APIError(404, "counselor_request_not_found", str(exc)) from exc
    if isinstance(exc, CounselorBookingAccessInvalid):
        raise APIError(422, "invalid_counselor_request", str(exc)) from exc
    if isinstance(exc, CounselorBookingHeadUnavailable):
        raise APIError(409, "head_guidance_unavailable", str(exc)) from exc
    if isinstance(exc, CounselorBookingRequestPendingConflict):
        raise APIError(409, "counselor_request_pending", str(exc)) from exc
    if isinstance(exc, CounselorBookingVersionConflict):
        raise APIError(409, "counselor_request_changed", str(exc)) from exc
    if isinstance(exc, CounselorBookingAccessConflict):
        raise APIError(409, "counselor_request_conflict", str(exc)) from exc
    if isinstance(exc, CounselorBookingContentUnavailable):
        raise APIError(503, "counselor_request_content_unavailable", str(exc)) from exc
    raise APIError(
        500, "internal_error", "Couldn't process the counselor request. Try again."
    ) from exc


@router.get(
    "/booking/counselor-request",
    response=response_with_errors(StudentCounselorRequestStateResponse, 401, 403),
    auth=session_auth,
    operation_id="appointmentsGetMyCounselorRequest",
)
def appointments_get_my_counselor_request(request):
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT":
        raise APIError(403, "permission_denied", "You don't have permission to book Appointments.")
    if not (
        user.has_capability("appointments.view_self")
        or user.has_capability("appointments.manage_self")
    ):
        raise APIError(
            403, "permission_denied", "You don't have permission to view your counselor options."
        )
    try:
        state = get_student_counselor_request_state(student=user)
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return {
        "default_counselor": _counselor(state.default_counselor),
        "active_approval": _active_approval(state.active_approval),
        "pending_request": (
            _student_request(state.pending_request) if state.pending_request is not None else None
        ),
        "latest_decision": (
            _student_decision(state.latest_decision) if state.latest_decision is not None else None
        ),
        "head_available": state.head_available,
        "requestable_counselors": [_counselor(c) for c in state.requestable_counselors],
    }


@router.post(
    "/booking/counselor-request",
    response=response_with_errors(
        StudentCounselorRequestSummary, 401, 403, 409, 422, 503, success_status=201
    ),
    auth=session_auth,
    operation_id="appointmentsCreateCounselorRequest",
)
def appointments_create_counselor_request(request, payload: CounselorBookingRequestCreate):
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code != "STUDENT"
        or not user.has_capability("appointments.manage_self")
    ):
        raise APIError(
            403, "permission_denied", "You don't have permission to ask for a different counselor."
        )
    try:
        item = submit_counselor_booking_request(
            student=user,
            preferred_counselor_id=payload.preferred_counselor_id,
            reason=payload.reason,
            context=_context(request),
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return Status(201, _student_request(item))


@router.get(
    "/counselor-requests",
    response=response_with_errors(HeadCounselorRequestPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="appointmentsListCounselorRequests",
)
def appointments_list_counselor_requests(
    request,
    state: CounselorBookingRequestState | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    try:
        result = list_head_counselor_requests(
            actor=request.auth_user,
            state=state.value if state is not None else None,
            page=page,
            page_size=page_size,
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return {
        "items": [_head_request_summary(entry) for entry in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/counselor-requests/{request_id}",
    response=response_with_errors(HeadCounselorRequestDetailResponse, 401, 403, 404, 503),
    auth=session_auth,
    operation_id="appointmentsGetCounselorRequest",
)
def appointments_get_counselor_request(request, request_id: UUID):
    try:
        detail = get_head_counselor_request(actor=request.auth_user, request_id=request_id)
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return _head_request_detail(detail)


@router.post(
    "/counselor-requests/{request_id}/decide",
    response=response_with_errors(HeadCounselorRequestDetailResponse, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="appointmentsDecideCounselorRequest",
)
def appointments_decide_counselor_request(
    request,
    request_id: UUID,
    payload: HeadCounselorRequestDecisionRequest,
):
    try:
        detail = decide_counselor_booking_request(
            actor=request.auth_user,
            request_id=request_id,
            action=payload.action,
            approved_counselor_id=payload.approved_counselor_id,
            note=payload.note,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return _head_request_detail(detail)


@router.get(
    "/counselor-approvals",
    response=response_with_errors(HeadCounselorApprovalPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="appointmentsListCounselorApprovals",
)
def appointments_list_counselor_approvals(
    request,
    include_ended: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    try:
        result = list_head_counselor_approvals(
            actor=request.auth_user,
            include_ended=include_ended,
            page=page,
            page_size=page_size,
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return {
        "items": [_head_approval(entry) for entry in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "available_counselors": [_counselor(c) for c in result.available_counselors],
        "can_manage": result.can_manage,
    }


@router.patch(
    "/counselor-approvals/{approval_id}",
    response=response_with_errors(HeadCounselorApprovalItem, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="appointmentsChangeCounselorApproval",
)
def appointments_change_counselor_approval(
    request,
    approval_id: UUID,
    payload: HeadCounselorApprovalChangeRequest,
):
    try:
        entry = change_counselor_approval(
            actor=request.auth_user,
            approval_id=approval_id,
            counselor_id=payload.counselor_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return _head_approval(entry)


@router.post(
    "/counselor-approvals/{approval_id}/end",
    response=response_with_errors(HeadCounselorApprovalItem, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="appointmentsEndCounselorApproval",
)
def appointments_end_counselor_approval(
    request,
    approval_id: UUID,
    payload: HeadCounselorApprovalEndRequest,
):
    try:
        entry = end_counselor_approval(
            actor=request.auth_user,
            approval_id=approval_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
    except CounselorBookingAccessError as exc:
        _raise(exc)
    return _head_approval(entry)
