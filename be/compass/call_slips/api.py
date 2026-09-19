"""Django Ninja API for Guidance Call Slips and Student self-view."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Header, Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint

from .models import CallSlipDestinationType
from .services import (
    DEFAULT_PAGE_SIZE,
    CallSlipConfigurationConflict,
    CallSlipCreationConflict,
    CallSlipError,
    CallSlipInterviewEndConflict,
    CallSlipNotFound,
    CallSlipNotPermitted,
    CallSlipReferralConflict,
    InvalidCallSlipInput,
    create_call_slip,
    get_call_slip,
    get_my_call_slip,
    list_call_slips,
    list_my_call_slips,
    record_interview_ended,
)

router = Router(tags=["call-slips"])
CREATE_ROUTE = "/api/v1/call-slips"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CallSlipDestinationTypeValue(StrEnum):
    GUIDANCE_OFFICE = CallSlipDestinationType.GUIDANCE_OFFICE
    OTHER = CallSlipDestinationType.OTHER


class CallSlipCreateRequest(StrictSchema):
    student_id: UUID
    course_year: str
    destination_type: CallSlipDestinationTypeValue
    other_destination: str = ""
    report_at: datetime
    referral_id: UUID | None = None
    notify_student: bool = True


class CallSlipInterviewEndedRequest(StrictSchema):
    interview_ended_at: datetime


class CallSlipPersonSummary(StrictSchema):
    id: UUID
    display_name: str


class CallSlipFormRevisionSummary(StrictSchema):
    id: UUID
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class CallSlipReferralSummary(StrictSchema):
    id: UUID
    reference_code: str


class CallSlipStudentResponse(StrictSchema):
    id: UUID
    student: CallSlipPersonSummary
    student_name_snapshot: str
    course_year_snapshot: str
    destination_type: CallSlipDestinationTypeValue
    other_destination: str
    report_at: datetime
    issued_by: CallSlipPersonSummary
    issued_by_name_snapshot: str
    form_revision: CallSlipFormRevisionSummary
    interview_ended_at: datetime | None
    created_at: datetime


class CallSlipOperationalResponse(CallSlipStudentResponse):
    referral: CallSlipReferralSummary | None
    recorded_by: CallSlipPersonSummary | None
    updated_at: datetime


class CallSlipStudentPageResponse(StrictSchema):
    items: list[CallSlipStudentResponse]
    page: int
    page_size: int
    has_next: bool


class CallSlipOperationalPageResponse(StrictSchema):
    items: list[CallSlipOperationalResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_operational(request, capability: str) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not user.has_capability(capability)
    ):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _require_student(request) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code != "STUDENT"
        or not user.has_capability("call_slips.view_self")
    ):
        raise APIError(403, "permission_denied", "Call Slip self-view access is required.")


def _raise(exc: CallSlipError) -> NoReturn:
    if isinstance(exc, CallSlipNotFound):
        raise APIError(404, "call_slip_not_found", str(exc)) from exc
    if isinstance(exc, CallSlipNotPermitted):
        raise APIError(403, "call_slip_not_permitted", str(exc)) from exc
    if isinstance(exc, InvalidCallSlipInput):
        raise APIError(422, "invalid_call_slip_request", str(exc)) from exc
    if isinstance(
        exc,
        (
            CallSlipConfigurationConflict,
            CallSlipCreationConflict,
            CallSlipReferralConflict,
            CallSlipInterviewEndConflict,
        ),
    ):
        raise APIError(409, "call_slip_conflict", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Call Slip operation could not be completed."
    ) from exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _revision(revision) -> dict[str, object]:
    return {
        "id": revision.pk,
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
        "internal_schema_version": revision.internal_schema_version,
    }


def _student_view(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student": _person(item.student),
        "student_name_snapshot": item.student_name_snapshot,
        "course_year_snapshot": item.course_year_snapshot,
        "destination_type": item.destination_type,
        "other_destination": item.other_destination,
        "report_at": item.report_at,
        "issued_by": _person(item.issued_by),
        "issued_by_name_snapshot": item.issued_by_name_snapshot,
        "form_revision": _revision(item.form_revision),
        "interview_ended_at": item.interview_ended_at,
        "created_at": item.created_at,
    }


def _operational_view(item) -> dict[str, object]:
    return {
        **_student_view(item),
        "referral": (
            {"id": item.referral_id, "reference_code": item.referral.reference_code}
            if item.referral_id
            else None
        ),
        "recorded_by": _person(item.recorded_by) if item.recorded_by_id else None,
        "updated_at": item.updated_at,
    }


@router.get(
    "/me",
    response=response_with_errors(CallSlipStudentPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="callSlipsListMy",
)
def call_slips_list_my(
    request,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_student(request)
    try:
        result = list_my_call_slips(
            actor=request.auth_user,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except CallSlipError as exc:
        _raise(exc)
    return {
        "items": [_student_view(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/{call_slip_id}",
    response=response_with_errors(CallSlipStudentResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="callSlipsGetMy",
)
def call_slips_get_my(request, call_slip_id: UUID):
    _require_student(request)
    try:
        item = get_my_call_slip(actor=request.auth_user, call_slip_id=call_slip_id)
    except CallSlipError as exc:
        _raise(exc)
    return _student_view(item)


@router.post(
    "",
    response=response_with_errors(
        CallSlipOperationalResponse,
        401,
        403,
        404,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="callSlipsCreate",
)
def call_slips_create(
    request,
    payload: CallSlipCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_operational(request, "call_slips.manage")
    fingerprint = request_fingerprint(
        method="POST",
        route=CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_call_slip(
            actor=request.auth_user,
            student_id=payload.student_id,
            course_year=payload.course_year,
            destination_type=payload.destination_type.value,
            other_destination=payload.other_destination,
            report_at=payload.report_at,
            referral_id=payload.referral_id,
            notify_student=payload.notify_student,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
    except CallSlipError as exc:
        _raise(exc)
    return Status(201, _operational_view(item))


@router.get(
    "",
    response=response_with_errors(CallSlipOperationalPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="callSlipsList",
)
def call_slips_list(
    request,
    student_id: UUID | None = None,
    issued_by_id: UUID | None = None,
    destination_type: CallSlipDestinationTypeValue | None = None,
    referral_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_operational(request, "call_slips.view")
    try:
        result = list_call_slips(
            actor=request.auth_user,
            student_id=student_id,
            issued_by_id=issued_by_id,
            destination_type=destination_type.value if destination_type else None,
            referral_id=referral_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except CallSlipError as exc:
        _raise(exc)
    return {
        "items": [_operational_view(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{call_slip_id}",
    response=response_with_errors(CallSlipOperationalResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="callSlipsGet",
)
def call_slips_get(request, call_slip_id: UUID):
    _require_operational(request, "call_slips.view")
    try:
        item = get_call_slip(actor=request.auth_user, call_slip_id=call_slip_id)
    except CallSlipError as exc:
        _raise(exc)
    return _operational_view(item)


@router.patch(
    "/{call_slip_id}/interview-ended",
    response=response_with_errors(
        CallSlipOperationalResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="callSlipsRecordInterviewEnded",
)
def call_slips_record_interview_ended(
    request,
    call_slip_id: UUID,
    payload: CallSlipInterviewEndedRequest,
):
    _require_operational(request, "call_slips.manage")
    try:
        item = record_interview_ended(
            actor=request.auth_user,
            call_slip_id=call_slip_id,
            interview_ended_at=payload.interview_ended_at,
            context=_context(request),
        )
    except CallSlipError as exc:
        _raise(exc)
    return _operational_view(item)
