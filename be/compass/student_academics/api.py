"""Django Ninja API for canonical Student academic placements."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from ninja import Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
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
from compass.student_academics.models import PlacementVerificationStatus
from compass.student_academics.services import (
    DEFAULT_PAGE_SIZE,
    InvalidStudentAcademicInput,
    StudentAcademicConflict,
    StudentAcademicError,
    StudentAcademicNotFound,
    clear_current_placement,
    list_current_placements,
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
    _require(request, "organization.manage")
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


@router.put(
    "/students/{student_id}/placement",
    response=response_with_errors(PlacementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsSetPlacement",
)
def placement_set(request, student_id: UUID, payload: PlacementRequest):
    _require(request, "organization.manage", recent_mfa=True)
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
    _require(request, "organization.manage", recent_mfa=True)
    try:
        removed = clear_current_placement(student_id=student_id, context=_context(request))
    except StudentAcademicError as exc:
        _raise(exc)
    return {"removed": removed}
