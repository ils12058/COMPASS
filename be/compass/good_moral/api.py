"""Student self-service and Counselor operational API for Good Moral certificates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.privacy_governance.releases import (
    ReleaseAuditUnavailable,
    record_good_moral_release,
)

from .models import GoodMoralStatus, GoodMoralVariant
from .services import (
    DEFAULT_PAGE_SIZE,
    GoodMoralAffiliationRequired,
    GoodMoralConfigurationConflict,
    GoodMoralConflict,
    GoodMoralCurrentStudentRequired,
    GoodMoralDocumentUnavailable,
    GoodMoralError,
    GoodMoralGraduatedStudentRequired,
    GoodMoralInventoryRequired,
    GoodMoralNotFound,
    GoodMoralNotPermitted,
    InvalidGoodMoralInput,
    cancel_request,
    create_my_current_student,
    create_my_graduate,
    get_mine,
    get_request,
    issue_request,
    list_mine,
    list_requests,
    render_certificate_pdf,
    update_request,
)

router = Router(tags=["good-moral"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class GoodMoralVariantValue(StrEnum):
    CURRENT_STUDENT = GoodMoralVariant.CURRENT_STUDENT
    GRADUATE = GoodMoralVariant.GRADUATE


class GoodMoralStatusValue(StrEnum):
    REQUESTED = GoodMoralStatus.REQUESTED
    ISSUED = GoodMoralStatus.ISSUED
    CANCELLED = GoodMoralStatus.CANCELLED


class CurrentStudentRequestPayload(StrictSchema):
    year_level: str
    semester: str


class GraduateRequestPayload(StrictSchema):
    degree: str
    major: str = ""
    graduation_date: date


class GoodMoralCancellationPayload(StrictSchema):
    reason: str


class GoodMoralCorrectionPayload(StrictSchema):
    applicant_name: str | None = None
    year_level: str | None = None
    college: str | None = None
    course: str | None = None
    major: str | None = None
    semester: str | None = None
    degree: str | None = None
    graduation_date: date | None = None
    official_receipt_number: str | None = None
    official_receipt_date: date | None = None
    official_receipt_amount: Decimal | None = None


class PersonSummary(StrictSchema):
    id: UUID
    display_name: str


class AcademicYearSummary(StrictSchema):
    id: UUID
    label: str


class FormRevisionSummary(StrictSchema):
    id: UUID
    family_key: str
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class GoodMoralSummaryResponse(StrictSchema):
    id: UUID
    variant: GoodMoralVariantValue
    status: GoodMoralStatusValue
    applicant_name: str
    issued_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoodMoralDetailResponse(GoodMoralSummaryResponse):
    student: PersonSummary
    inventory_id: UUID | None
    academic_year: AcademicYearSummary | None
    major: str
    year_level: str
    college: str
    course: str
    semester: str
    degree: str
    graduation_date: date | None
    official_receipt_number: str
    official_receipt_date: date | None
    official_receipt_amount: Decimal | None
    form_revision: FormRevisionSummary | None
    document_template_key: str | None
    document_template_version: int | None
    issued_by: PersonSummary | None
    issued_by_name_snapshot: str


class GoodMoralHistoryResponse(StrictSchema):
    items: list[GoodMoralSummaryResponse]


class GoodMoralPageResponse(StrictSchema):
    items: list[GoodMoralSummaryResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT" or not user.has_capability(capability):
        raise APIError(403, "permission_denied", "Student Good Moral access is required.")


def _require_counselor(request, capability: str, *, recent_mfa: bool = False) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR" or not user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _raise(exc: GoodMoralError) -> NoReturn:
    if isinstance(exc, GoodMoralNotFound):
        raise APIError(404, "good_moral_not_found", str(exc)) from exc
    if isinstance(exc, GoodMoralNotPermitted):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, GoodMoralCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, GoodMoralGraduatedStudentRequired):
        raise APIError(409, "graduated_student_required", str(exc)) from exc
    if isinstance(exc, GoodMoralInventoryRequired):
        raise APIError(409, "good_moral_inventory_required", str(exc)) from exc
    if isinstance(exc, GoodMoralAffiliationRequired):
        raise APIError(409, "good_moral_affiliation_required", str(exc)) from exc
    if isinstance(exc, GoodMoralConfigurationConflict):
        raise APIError(409, "good_moral_configuration_conflict", str(exc)) from exc
    if isinstance(exc, GoodMoralConflict):
        raise APIError(409, "good_moral_conflict", str(exc)) from exc
    if isinstance(exc, GoodMoralDocumentUnavailable):
        raise APIError(503, "good_moral_document_unavailable", str(exc)) from exc
    if isinstance(exc, InvalidGoodMoralInput):
        raise APIError(422, "invalid_good_moral_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Good Moral operation could not be completed."
    ) from exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "variant": item.variant,
        "status": item.status,
        "applicant_name": item.applicant_name_snapshot,
        "issued_at": item.issued_at,
        "cancelled_at": item.cancelled_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _detail(item) -> dict[str, object]:
    revision = item.form_revision
    return {
        **_summary(item),
        "student": _person(item.student),
        "inventory_id": item.inventory_id,
        "academic_year": (
            {"id": item.academic_year_id, "label": item.academic_year.label}
            if item.academic_year_id
            else None
        ),
        "major": item.major_snapshot,
        "year_level": item.year_level_snapshot,
        "college": item.college_snapshot,
        "course": item.course_snapshot,
        "semester": item.semester_snapshot,
        "degree": item.degree_snapshot,
        "graduation_date": item.graduation_date,
        "official_receipt_number": item.official_receipt_number,
        "official_receipt_date": item.official_receipt_date,
        "official_receipt_amount": item.official_receipt_amount,
        "form_revision": (
            {
                "id": revision.pk,
                "family_key": revision.family.key,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            }
            if revision is not None
            else None
        ),
        "document_template_key": item.document_template_key,
        "document_template_version": item.document_template_version,
        "issued_by": _person(item.issued_by) if item.issued_by_id else None,
        "issued_by_name_snapshot": item.issued_by_name_snapshot,
    }


def _correction_values(payload: GoodMoralCorrectionPayload) -> dict[str, object]:
    values = payload.model_dump(exclude_unset=True)
    mapping = {
        "applicant_name": "applicant_name_snapshot",
        "year_level": "year_level_snapshot",
        "college": "college_snapshot",
        "course": "course_snapshot",
        "major": "major_snapshot",
        "semester": "semester_snapshot",
        "degree": "degree_snapshot",
    }
    return {mapping.get(name, name): value for name, value in values.items()}


def _pdf_response(
    item,
    *,
    context: AuditContext,
    access_mode: str,
) -> HttpResponse:
    try:
        pdf_bytes = render_certificate_pdf(item)
    except GoodMoralError as exc:
        _raise(exc)
    try:
        record_good_moral_release(
            context=context,
            request_id=item.pk,
            variant=item.variant,
            access_mode=access_mode,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            (
                "The certificate could not be released because its required privacy audit "
                "is unavailable."
            ),
        ) from exc
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="good-moral-{item.pk}.pdf"'
    return response


# Static self-service routes are registered before UUID routes.


@router.post(
    "/me/requests/current-student",
    response=response_with_errors(
        GoodMoralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="goodMoralCreateMyCurrentStudentRequest",
)
def good_moral_create_my_current_student(request, payload: CurrentStudentRequestPayload):
    _require_student(request, "good_moral.request_self")
    try:
        item = create_my_current_student(
            student=request.auth_user,
            year_level=payload.year_level,
            semester=payload.semester,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return Status(201, _detail(item))


@router.post(
    "/me/requests/graduate",
    response=response_with_errors(
        GoodMoralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="goodMoralCreateMyGraduateRequest",
)
def good_moral_create_my_graduate(request, payload: GraduateRequestPayload):
    _require_student(request, "good_moral.request_self")
    try:
        item = create_my_graduate(
            student=request.auth_user,
            degree=payload.degree,
            major=payload.major,
            graduation_date=payload.graduation_date,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return Status(201, _detail(item))


@router.get(
    "/me",
    response=response_with_errors(GoodMoralHistoryResponse, 401, 403),
    auth=session_auth,
    operation_id="goodMoralListMyRequests",
)
def good_moral_list_my(request):
    _require_student(request, "good_moral.view_self")
    try:
        items = list_mine(request.auth_user)
    except GoodMoralError as exc:
        _raise(exc)
    return {"items": [_summary(item) for item in items]}


@router.post(
    "/me/{request_id}/cancel",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralCancelMyRequest",
)
def good_moral_cancel_my(
    request,
    request_id: UUID,
    payload: GoodMoralCancellationPayload,
):
    _require_student(request, "good_moral.request_self")
    try:
        item = cancel_request(
            actor=request.auth_user,
            request_id=request_id,
            reason=payload.reason,
            self_service=True,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/me/{request_id}/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 503),
    auth=session_auth,
    operation_id="goodMoralDownloadMyCertificate",
)
def good_moral_download_my(request, request_id: UUID):
    _require_student(request, "good_moral.view_self")
    try:
        item = get_mine(student=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _pdf_response(item, context=_context(request), access_mode="SELF")


@router.get(
    "/me/{request_id}",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="goodMoralGetMyRequest",
)
def good_moral_get_my(request, request_id: UUID):
    _require_student(request, "good_moral.view_self")
    try:
        item = get_mine(student=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/requests",
    response=response_with_errors(GoodMoralPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="goodMoralListRequests",
)
def good_moral_list_requests(
    request,
    variant: GoodMoralVariantValue | None = None,
    status: GoodMoralStatusValue | None = None,
    student_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, "good_moral.view")
    try:
        result = list_requests(
            actor=request.auth_user,
            variant=variant.value if variant is not None else None,
            status=status.value if status is not None else None,
            student_id=student_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    except GoodMoralError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/requests/{request_id}/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 503),
    auth=session_auth,
    operation_id="goodMoralDownloadCertificate",
)
def good_moral_download(request, request_id: UUID):
    _require_counselor(request, "good_moral.view")
    try:
        item = get_request(actor=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _pdf_response(item, context=_context(request), access_mode="GCO")


@router.post(
    "/requests/{request_id}/cancel",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralCancelRequest",
)
def good_moral_cancel_request(
    request,
    request_id: UUID,
    payload: GoodMoralCancellationPayload,
):
    _require_counselor(request, "good_moral.manage")
    try:
        item = cancel_request(
            actor=request.auth_user,
            request_id=request_id,
            reason=payload.reason,
            self_service=False,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/requests/{request_id}/issue",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralIssueRequest",
)
def good_moral_issue(request, request_id: UUID):
    _require_counselor(request, "good_moral.issue", recent_mfa=True)
    try:
        item = issue_request(
            actor=request.auth_user,
            request_id=request_id,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/requests/{request_id}",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="goodMoralGetRequest",
)
def good_moral_get(request, request_id: UUID):
    _require_counselor(request, "good_moral.view")
    try:
        item = get_request(actor=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.patch(
    "/requests/{request_id}",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralUpdateRequest",
)
def good_moral_update(request, request_id: UUID, payload: GoodMoralCorrectionPayload):
    _require_counselor(request, "good_moral.manage")
    try:
        item = update_request(
            actor=request.auth_user,
            request_id=request_id,
            changes=_correction_values(payload),
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)
