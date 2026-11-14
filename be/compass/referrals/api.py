"""Django Ninja API for scoped Guidance Referral intake and source actions."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Header, Router, Schema, Status
from pydantic import ConfigDict

from compass.accounts.profile_photos import profile_photo_projection
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint
from compass.documents.filenames import institutional_pdf_content_disposition
from compass.institutional_forms.filter_options import (
    CollectionFilterOptions,
    project_filter_options,
)
from compass.privacy_governance.releases import (
    ReleaseAuditUnavailable,
    record_referral_release,
)

from .administrative_state import FacultyReferralSubmissionState, administrative_state
from .confidential_content import (
    ReferralConfidentialContentUnavailable,
    read_referral_action_remarks,
    read_referral_confidential_content,
)
from .models import ReferralActionType, ReferralSubmissionChannel
from .services import (
    DEFAULT_PAGE_SIZE,
    InvalidReferralInput,
    ReferralActionConflict,
    ReferralActiveCallSlipConflict,
    ReferralCompletedCallSlipConflict,
    ReferralConfigurationConflict,
    ReferralCreationConflict,
    ReferralDocumentUnavailable,
    ReferralError,
    ReferralNotFound,
    ReferralNotPermitted,
    ReferralOrdering,
    ReferralReferenceConflict,
    ReferralVoidConflict,
    create_referral,
    get_referral,
    list_eligible_students,
    list_referrals,
    record_action,
    render_referral_pdf,
    update_status_note,
    void_referral,
)
from .timing_rules import InvalidReferralTiming
from .timing_schemas import (
    ReferralSchedulingStatementRequest,
    ReferralTimingResponse,
    ReferralTimingStatus,
    ReferralTimingVerificationRequest,
)
from .timing_services import (
    ReferralTimingChanged,
    ReferralTimingSessionUnavailable,
    get_timing,
    record_verification,
    timing_status,
)

router = Router(tags=["referrals"])
CREATE_ROUTE = "/api/v1/referrals"
PDF_SUCCESS_OPENAPI = {
    "responses": {
        200: {
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"},
                }
            }
        }
    }
}


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ReferralActionTypeValue(StrEnum):
    CALL_PARENT_GUARDIAN = ReferralActionType.CALL_PARENT_GUARDIAN
    SEND_PARENT_NOTIFICATION_LETTER = ReferralActionType.SEND_PARENT_NOTIFICATION_LETTER
    SEND_CALL_SLIP_INTERVIEW_PERMIT = ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT


class ReferralCreateRequest(StrictSchema):
    student_id: UUID
    course_year_block: str
    reason: str
    referrer_name: str
    referred_on: date
    received_at: datetime | None = None
    scheduling_statement: ReferralSchedulingStatementRequest | None = None


class ReferralStatusUpdateRequest(StrictSchema):
    status_note: str


class ReferralActionCreateRequest(StrictSchema):
    action_type: ReferralActionTypeValue
    occurred_at: datetime
    remarks: str = ""


class ReferralVoidRequest(StrictSchema):
    reason: str


class ReferralPersonSummary(StrictSchema):
    id: UUID
    display_name: str
    institutional_id: str | None
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class ReferralActorSummary(StrictSchema):
    id: UUID
    display_name: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class ReferralFormRevisionSummary(StrictSchema):
    id: UUID
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class ReferralStudentCollegeResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class ReferralStudentOptionResponse(StrictSchema):
    id: UUID
    institutional_id: str | None
    display_name: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None
    college: ReferralStudentCollegeResponse | None


class ReferralStudentOptionPage(StrictSchema):
    items: list[ReferralStudentOptionResponse]
    page: int
    page_size: int
    has_next: bool


class ReferralActionResponse(StrictSchema):
    id: UUID
    action_type: ReferralActionTypeValue
    occurred_at: datetime
    remarks: str
    created_at: datetime
    recorded_by: ReferralActorSummary | None


class ReferralSummaryResponse(StrictSchema):
    id: UUID
    reference_code: str
    student: ReferralPersonSummary
    student_name_snapshot: str
    course_year_block_snapshot: str
    referred_on: date
    received_at: datetime | None
    status_note: str
    voided_at: datetime | None
    created_at: datetime
    submission_channel: ReferralSubmissionChannel
    submitted_at: datetime | None = None
    administrative_state: FacultyReferralSubmissionState | None = None
    timing_status: ReferralTimingStatus = ReferralTimingStatus.NOT_PROVIDED


class ReferralDetailResponse(ReferralSummaryResponse):
    reason: str
    referrer_name: str
    form_revision: ReferralFormRevisionSummary
    actions: list[ReferralActionResponse]
    void_reason: str
    updated_at: datetime
    recorded_by: ReferralActorSummary | None
    voided_by: ReferralActorSummary | None


class ReferralPageResponse(StrictSchema):
    items: list[ReferralSummaryResponse]
    page: int
    page_size: int
    has_next: bool
    # The ordering applied: the requested one, or newest referred first.
    ordering: ReferralOrdering
    filter_options: CollectionFilterOptions


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code not in {"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"}
        or not user.has_capability(capability)
    ):
        action = "manage Referrals" if capability == "referrals.manage" else "view Referrals"
        raise APIError(403, "permission_denied", f"You don't have permission to {action}.")


def _raise(exc: ReferralError, *, timing_prefix=()) -> NoReturn:
    if isinstance(exc, ReferralTimingSessionUnavailable):
        raise APIError(401, "session_unavailable", str(exc)) from None
    if isinstance(exc, InvalidReferralTiming):
        details = [
            {**issue, "loc": [issue["loc"][0], *timing_prefix, *issue["loc"][1:]]}
            for issue in exc.details
        ]
        raise APIError(422, "referral_timing_invalid", str(exc), details=details) from None
    if isinstance(exc, ReferralTimingChanged):
        raise APIError(409, "referral_timing_changed", str(exc)) from None
    if isinstance(exc, ReferralConfidentialContentUnavailable):
        raise APIError(
            500,
            "referral_confidential_content_unavailable",
            "Couldn't load the Referral. Try again.",
        ) from None
    if isinstance(exc, ReferralNotFound):
        raise APIError(404, "referral_not_found", str(exc)) from exc
    if isinstance(exc, ReferralNotPermitted):
        raise APIError(403, "referral_not_permitted", str(exc)) from exc
    if isinstance(exc, ReferralDocumentUnavailable):
        raise APIError(503, "referral_document_unavailable", str(exc)) from exc
    if isinstance(exc, InvalidReferralInput):
        raise APIError(422, "invalid_referral_request", str(exc)) from exc
    if isinstance(exc, ReferralActiveCallSlipConflict):
        raise APIError(409, "referral_active_call_slip_conflict", str(exc)) from exc
    if isinstance(exc, ReferralCompletedCallSlipConflict):
        raise APIError(409, "referral_completed_call_slip_conflict", str(exc)) from exc
    if isinstance(
        exc,
        (
            ReferralConfigurationConflict,
            ReferralReferenceConflict,
            ReferralCreationConflict,
            ReferralActionConflict,
            ReferralVoidConflict,
        ),
    ):
        raise APIError(409, "referral_conflict", str(exc)) from exc
    raise APIError(
        500, "internal_error", "Couldn't complete the Referral change. Try again."
    ) from exc


def _person(user) -> dict[str, object]:
    return {
        "id": user.pk,
        "display_name": user.get_full_name(),
        "institutional_id": user.institutional_id,
        **profile_photo_projection(user),
    }


def _actor(user) -> dict[str, object]:
    return {
        "id": user.pk,
        "display_name": user.get_full_name(),
        **profile_photo_projection(user),
    }


def _revision(revision) -> dict[str, object]:
    return {
        "id": revision.pk,
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
        "internal_schema_version": revision.internal_schema_version,
    }


def _action(action) -> dict[str, object]:
    return {
        "id": action.pk,
        "action_type": action.action_type,
        "occurred_at": action.occurred_at,
        "remarks": _read_action(action),
        "created_at": action.created_at,
        "recorded_by": _actor(action.recorded_by) if action.recorded_by_id else None,
    }


def _read_content(item):
    try:
        return read_referral_confidential_content(item)
    except ReferralConfidentialContentUnavailable as exc:
        _raise(exc)


def _read_action(action):
    try:
        return read_referral_action_remarks(action)
    except ReferralConfidentialContentUnavailable as exc:
        _raise(exc)


def _summary(item, *, content=None) -> dict[str, object]:
    content = content if content is not None else _read_content(item)
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "student": _person(item.student),
        "student_name_snapshot": item.student_name_snapshot,
        "course_year_block_snapshot": item.course_year_block_snapshot,
        "referred_on": item.referred_on,
        "received_at": item.received_at,
        "status_note": content.status_note,
        "voided_at": item.voided_at,
        "created_at": item.created_at,
        "submission_channel": item.submission_channel,
        "submitted_at": item.submitted_at,
        "administrative_state": administrative_state(item),
        "timing_status": timing_status(item),
    }


def _student_option(item) -> dict[str, object]:
    return {
        "id": item.id,
        "institutional_id": item.institutional_id,
        "display_name": item.display_name,
        "profile_photo_url": item.profile_photo_url,
        "profile_photo_updated_at": item.profile_photo_updated_at,
        "college": (
            {
                "id": item.college.id,
                "code": item.college.code,
                "name": item.college.name,
            }
            if item.college is not None
            else None
        ),
    }


def _pdf_response(item, *, context: AuditContext) -> HttpResponse:
    try:
        pdf_bytes = render_referral_pdf(item)
    except ReferralError as exc:
        _raise(exc)
    revision = item.form_revision
    try:
        record_referral_release(
            context=context,
            referral_id=item.pk,
            form_revision_id=revision.pk,
            official_code=revision.official_code,
            official_revision=revision.official_revision,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            ("Couldn't release the Referral Slip because its privacy check failed. Try again."),
        ) from exc
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = institutional_pdf_content_disposition(
        "referral_slip", item.pk
    )
    return response


def _detail(item) -> dict[str, object]:
    content = _read_content(item)
    return {
        **_summary(item, content=content),
        "reason": content.reason,
        "referrer_name": content.referrer_name,
        "form_revision": _revision(item.form_revision),
        "actions": [_action(action) for action in item.actions.all()],
        "void_reason": content.void_reason,
        "updated_at": item.updated_at,
        "recorded_by": _actor(item.recorded_by) if item.recorded_by_id else None,
        "voided_by": _actor(item.voided_by) if item.voided_by_id else None,
    }


@router.post(
    "",
    response=response_with_errors(
        ReferralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="referralsCreate",
)
def referrals_create(
    request,
    payload: ReferralCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require(request, "referrals.manage")
    fingerprint = request_fingerprint(
        method="POST",
        route=CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_referral(
            actor=request.auth_user,
            student_id=payload.student_id,
            course_year_block=payload.course_year_block,
            reason=payload.reason,
            referrer_name=payload.referrer_name,
            referred_on=payload.referred_on,
            received_at=payload.received_at,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
            scheduling_statement=payload.scheduling_statement.model_dump()
            if payload.scheduling_statement
            else None,
        )
    except ReferralError as exc:
        _raise(exc, timing_prefix=("scheduling_statement",))
    return Status(201, _detail(item))


@router.get(
    "",
    response=response_with_errors(ReferralPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="referralsList",
)
def referrals_list(
    request,
    search: str | None = None,
    student_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_voided: bool = False,
    submission_channel: ReferralSubmissionChannel | None = None,
    form_revision_id: UUID | None = None,
    ordering: ReferralOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "referrals.view")
    try:
        result = list_referrals(
            actor=request.auth_user,
            search=search,
            student_id=student_id,
            from_date=from_date,
            to_date=to_date,
            include_voided=include_voided,
            submission_channel=submission_channel,
            form_revision_id=form_revision_id,
            ordering=ordering,
            page=page,
            page_size=page_size,
        )
    except ReferralError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "ordering": result.ordering,
        "filter_options": project_filter_options(result.form_revisions),
    }


@router.get(
    "/students",
    response=response_with_errors(ReferralStudentOptionPage, 401, 403, 422),
    auth=session_auth,
    operation_id="referralsListEligibleStudents",
)
def referrals_list_eligible_students(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "referrals.manage")
    try:
        result = list_eligible_students(
            actor=request.auth_user,
            search=search,
            page=page,
            page_size=page_size,
        )
    except ReferralError as exc:
        _raise(exc)
    return {
        "items": [_student_option(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{referral_id}/pdf",
    response=response_with_errors(None, 401, 403, 404, 503),
    auth=session_auth,
    operation_id="referralsDownloadPdf",
    openapi_extra=PDF_SUCCESS_OPENAPI,
)
def referrals_download_pdf(request, referral_id: UUID):
    _require(request, "referrals.view")
    try:
        item = get_referral(actor=request.auth_user, referral_id=referral_id)
    except ReferralError as exc:
        _raise(exc)
    return _pdf_response(item, context=_context(request))


@router.get(
    "/{referral_id}",
    response=response_with_errors(ReferralDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="referralsGet",
)
def referrals_get(request, referral_id: UUID):
    _require(request, "referrals.view")
    try:
        item = get_referral(actor=request.auth_user, referral_id=referral_id)
    except ReferralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/{referral_id}/timing",
    response=response_with_errors(ReferralTimingResponse, 401, 403, 404, 422, 500),
    auth=session_auth,
    operation_id="referralsGetTiming",
    summary="Read the COMPASS timing supplement within existing Referral scope",
)
def referrals_get_timing(request, referral_id: UUID):
    _require(request, "referrals.view")
    try:
        return get_timing(actor=request.auth_user, referral_id=referral_id)
    except ReferralError as exc:
        _raise(exc)


@router.post(
    "/{referral_id}/timing/verifications",
    response=response_with_errors(
        ReferralTimingResponse, 401, 403, 404, 409, 422, 500, success_status=201
    ),
    auth=session_auth,
    operation_id="referralsRecordTimingVerification",
    summary="Append staff verification without changing the referrer's statement",
)
def referrals_record_timing_verification(
    request, referral_id: UUID, payload: ReferralTimingVerificationRequest
):
    _require(request, "referrals.manage")
    try:
        result = record_verification(
            actor=request.auth_user,
            actor_session=request.auth_session,
            referral_id=referral_id,
            context=_context(request),
            **payload.model_dump(),
        )
    except ReferralError as exc:
        _raise(exc)
    return Status(201, result)


@router.patch(
    "/{referral_id}/status",
    response=response_with_errors(ReferralDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="referralsUpdateStatus",
)
def referrals_update_status(
    request,
    referral_id: UUID,
    payload: ReferralStatusUpdateRequest,
):
    _require(request, "referrals.manage")
    try:
        item = update_status_note(
            actor=request.auth_user,
            referral_id=referral_id,
            status_note=payload.status_note,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/{referral_id}/actions",
    response=response_with_errors(
        ReferralActionResponse,
        401,
        403,
        404,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="referralsRecordAction",
)
def referrals_record_action(
    request,
    referral_id: UUID,
    payload: ReferralActionCreateRequest,
):
    _require(request, "referrals.manage")
    try:
        action = record_action(
            actor=request.auth_user,
            referral_id=referral_id,
            action_type=payload.action_type.value,
            occurred_at=payload.occurred_at,
            remarks=payload.remarks,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return Status(201, _action(action))


@router.post(
    "/{referral_id}/void",
    response=response_with_errors(ReferralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="referralsVoid",
)
def referrals_void(request, referral_id: UUID, payload: ReferralVoidRequest):
    _require(request, "referrals.manage")
    try:
        item = void_referral(
            actor=request.auth_user,
            referral_id=referral_id,
            reason=payload.reason,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return _detail(item)
