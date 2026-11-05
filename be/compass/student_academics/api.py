"""Django Ninja API for canonical Student academic records."""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn
from uuid import UUID

from ninja import Router

from compass.accounts.models import StudentLifecycleStatus
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.organization.academic_years_api import AcademicYearResponse
from compass.organization.api import (
    CollegeSummary,
    OrganizationPersonSummary,
    RemovedResponse,
    StrictSchema,
    _college,
    _context,
    _person,
    _require,
)
from compass.student_academics.models import (
    AcademicTerm,
    EnrollmentStatus,
    PlacementVerificationStatus,
)
from compass.student_academics.services import (
    DEFAULT_PAGE_SIZE,
    InvalidStudentAcademicInput,
    StudentAcademicConflict,
    StudentAcademicError,
    StudentAcademicNotFound,
    clear_current_placement,
    get_student_academic_record,
    list_current_placements,
    record_academic_period,
    record_graduation,
    set_current_placement,
)

router = Router(tags=["student-academics"])


class PlacementRequest(StrictSchema):
    college_id: UUID


class PlacementResponse(StrictSchema):
    student: OrganizationPersonSummary
    college: CollegeSummary
    verification_status: PlacementVerificationStatus


class PlacementListResponse(StrictSchema):
    items: list[PlacementResponse]
    page: int
    page_size: int
    has_next: bool


class AcademicPeriodRecordRequest(StrictSchema):
    academic_year_id: UUID
    term: AcademicTerm
    college_id: UUID
    year_level: int | None = None
    enrollment_status: EnrollmentStatus = EnrollmentStatus.UNKNOWN


class AcademicPeriodRecordResponse(StrictSchema):
    id: UUID
    academic_year: AcademicYearResponse
    term: AcademicTerm
    college: CollegeSummary
    year_level: int | None
    enrollment_status: EnrollmentStatus
    created_at: datetime
    updated_at: datetime


class GraduationRecordRequest(StrictSchema):
    graduated_college_id: UUID
    graduation_date: date
    verification_source: str


class GraduationRecordResponse(StrictSchema):
    id: UUID
    graduated_college: CollegeSummary
    graduation_date: date
    verification_source: str
    verified_by: OrganizationPersonSummary | None
    verified_at: datetime
    created_at: datetime
    updated_at: datetime


class StudentAcademicRecordResponse(StrictSchema):
    student: OrganizationPersonSummary
    lifecycle_status: StudentLifecycleStatus | None
    placement: PlacementResponse | None
    periods: list[AcademicPeriodRecordResponse]
    graduation: GraduationRecordResponse | None


def _raise(exc: StudentAcademicError) -> NoReturn:
    if isinstance(exc, StudentAcademicNotFound):
        raise APIError(404, "student_academic_not_found", str(exc)) from exc
    if isinstance(exc, StudentAcademicConflict):
        raise APIError(409, "student_academic_conflict", str(exc)) from exc
    if isinstance(exc, InvalidStudentAcademicInput):
        raise APIError(422, "invalid_student_academic_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The student academic operation could not be completed."
    ) from exc


def _placement(profile) -> dict[str, object]:
    return {
        "student": _person(profile.student),
        "college": _college(profile.current_college),
        "verification_status": profile.placement_verification_status,
    }


def _academic_year(academic_year) -> dict[str, object]:
    return {
        "id": academic_year.pk,
        "label": academic_year.label,
        "is_current": academic_year.is_current,
    }


def _period(record) -> dict[str, object]:
    return {
        "id": record.pk,
        "academic_year": _academic_year(record.academic_year),
        "term": record.term,
        "college": _college(record.college),
        "year_level": record.year_level,
        "enrollment_status": record.enrollment_status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _graduation(record) -> dict[str, object]:
    return {
        "id": record.pk,
        "graduated_college": _college(record.graduated_college),
        "graduation_date": record.graduation_date,
        "verification_source": record.verification_source,
        "verified_by": _person(record.verified_by) if record.verified_by is not None else None,
        "verified_at": record.verified_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _record_payload(record) -> dict[str, object]:
    return {
        "student": _person(record.student),
        "lifecycle_status": record.lifecycle_status,
        "placement": _placement(record.placement) if record.placement is not None else None,
        "periods": [_period(item) for item in record.periods],
        "graduation": _graduation(record.graduation) if record.graduation is not None else None,
    }


@router.get(
    "/placements",
    response=response_with_errors(PlacementListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="studentAcademicsListPlacements",
)
def placements(
    request,
    student_id: UUID | None = None,
    college_id: UUID | None = None,
    campus_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "student_academics.view")
    try:
        result = list_current_placements(
            student_id=student_id,
            college_id=college_id,
            campus_id=campus_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return {
        "items": [_placement(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/record",
    response=response_with_errors(StudentAcademicRecordResponse, 401, 403),
    auth=session_auth,
    operation_id="studentAcademicsGetMyRecord",
)
def my_record(request):
    _require(request, "student_academics.view_self")
    if request.auth_user.role.code != "STUDENT":
        raise APIError(
            403,
            "permission_denied",
            "Academic record self-view is available only to Student accounts.",
        )
    try:
        record = get_student_academic_record(student_id=request.auth_user.pk)
    except StudentAcademicError as exc:
        _raise(exc)
    return _record_payload(record)


@router.put(
    "/students/{student_id}/placement",
    response=response_with_errors(PlacementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsSetPlacement",
)
def placement_set(request, student_id: UUID, payload: PlacementRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = set_current_placement(
            student_id=student_id,
            college_id=payload.college_id,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _placement(item)


@router.delete(
    "/students/{student_id}/placement",
    response=response_with_errors(RemovedResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsClearPlacement",
)
def placement_clear(request, student_id: UUID):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        removed = clear_current_placement(student_id=student_id, context=_context(request))
    except StudentAcademicError as exc:
        _raise(exc)
    return {"removed": removed}


@router.get(
    "/students/{student_id}/record",
    response=response_with_errors(StudentAcademicRecordResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="studentAcademicsGetStudentRecord",
)
def student_record(request, student_id: UUID):
    _require(request, "student_academics.view")
    try:
        record = get_student_academic_record(student_id=student_id)
    except StudentAcademicError as exc:
        _raise(exc)
    return _record_payload(record)


@router.put(
    "/students/{student_id}/periods",
    response=response_with_errors(AcademicPeriodRecordResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsRecordPeriod",
)
def period_record(request, student_id: UUID, payload: AcademicPeriodRecordRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = record_academic_period(
            student_id=student_id,
            academic_year_id=payload.academic_year_id,
            term=payload.term,
            college_id=payload.college_id,
            year_level=payload.year_level,
            enrollment_status=payload.enrollment_status,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _period(item)


@router.put(
    "/students/{student_id}/graduation",
    response=response_with_errors(GraduationRecordResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsRecordGraduation",
)
def graduation_record(request, student_id: UUID, payload: GraduationRecordRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = record_graduation(
            student_id=student_id,
            graduated_college_id=payload.graduated_college_id,
            graduation_date=payload.graduation_date,
            verification_source=payload.verification_source,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _graduation(item)
