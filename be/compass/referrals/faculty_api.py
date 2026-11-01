"""Strict Faculty contracts; every call crosses live domain authorization."""

from datetime import datetime
from uuid import UUID

from ninja import Header, Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.rate_limit import client_ip
from compass.referrals.administrative_state import FacultyReferralSubmissionState
from compass.referrals.api import _raise
from compass.referrals.errors import ReferralError
from compass.referrals.faculty_policy import FacultyReferralError
from compass.referrals.faculty_services import (
    confirm_student,
    get_own_submission,
    list_own_submissions,
    referral_availability,
    submit_referral,
)

router = Router(tags=["referrals"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class FacultyStudentConfirmationRequest(StrictSchema):
    institutional_id: str = Field(min_length=1, max_length=64)


class FacultyConfirmedStudent(StrictSchema):
    display_name: str


class FacultyStudentConfirmationResponse(StrictSchema):
    confirmed: bool
    student: FacultyConfirmedStudent | None
    confirmation: str | None
    expires_at: datetime | None


class FacultyReferralSubmitRequest(StrictSchema):
    confirmation: str = Field(min_length=1, max_length=4096)
    course_year_block: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=10000)


class FacultyReferralSubmissionResponse(StrictSchema):
    id: UUID
    reference_code: str
    submitted_at: datetime
    state: FacultyReferralSubmissionState
    student: FacultyConfirmedStudent
    received_at: datetime | None
    closed_at: datetime | None


class FacultyReferralSubmissionPage(StrictSchema):
    items: list[FacultyReferralSubmissionResponse]
    page: int
    page_size: int
    has_next: bool


class FacultyReferralAvailability(StrictSchema):
    can_confirm_student: bool
    can_submit_referral: bool
    can_view_submissions: bool
    valid_until: datetime | None


def _actor_args(request):
    return {"actor": request.auth_user, "actor_session": request.auth_session}


def _error(exc):
    if isinstance(exc, FacultyReferralError):
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if hasattr(exc, "retry_after_seconds")
            else None
        )
        raise APIError(exc.status, exc.code, str(exc), headers=headers) from exc
    _raise(exc)


@router.get(
    "/availability",
    auth=session_auth,
    response=response_with_errors(FacultyReferralAvailability, 401, 403),
    operation_id="referralsFacultyAvailability",
    summary="Read separate current Faculty Referral availability facts",
)
def faculty_referral_availability(request):
    try:
        return referral_availability(**_actor_args(request))
    except ReferralError as exc:
        _error(exc)


@router.post(
    "/student-confirmation",
    auth=session_auth,
    response=response_with_errors(FacultyStudentConfirmationResponse, 401, 403, 422, 429, 503),
    operation_id="referralsFacultyConfirmStudent",
    summary="Confirm one exact Student identity under approved disclosure policy",
)
def faculty_confirm_student(request, payload: FacultyStudentConfirmationRequest):
    try:
        return confirm_student(
            **_actor_args(request),
            institutional_id=payload.institutional_id,
            ip_address=client_ip(request),
        )
    except ReferralError as exc:
        _error(exc)


@router.post(
    "",
    auth=session_auth,
    response={
        **response_with_errors(
            FacultyReferralSubmissionResponse, 401, 403, 404, 409, 422, success_status=201
        ),
        200: FacultyReferralSubmissionResponse,
    },
    operation_id="referralsFacultySubmit",
    summary="Submit an authenticated Faculty Referral under approved digital-form policy",
)
def faculty_submit_referral(
    request,
    payload: FacultyReferralSubmitRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    try:
        result, created = submit_referral(
            **_actor_args(request),
            **payload.model_dump(),
            idempotency_key=idempotency_key,
            context=AuditContext.from_request(request, actor=request.auth_user),
        )
    except ReferralError as exc:
        _error(exc)
    return Status(201 if created else 200, result)


@router.get(
    "",
    auth=session_auth,
    response=response_with_errors(FacultyReferralSubmissionPage, 401, 403, 422),
    operation_id="referralsFacultyListMine",
    summary="List only Faculty-safe own submissions",
)
def faculty_list_submissions(request, page: int = 1, page_size: int = 20):
    try:
        return list_own_submissions(**_actor_args(request), page=page, page_size=page_size)
    except ReferralError as exc:
        _error(exc)


@router.get(
    "/{referral_id}",
    auth=session_auth,
    response=response_with_errors(FacultyReferralSubmissionResponse, 401, 403, 404, 422),
    operation_id="referralsFacultyGetMine",
    summary="Read one allowlisted own Faculty submission",
)
def faculty_get_submission(request, referral_id: UUID):
    try:
        return get_own_submission(**_actor_args(request), referral_id=referral_id)
    except ReferralError as exc:
        _error(exc)
