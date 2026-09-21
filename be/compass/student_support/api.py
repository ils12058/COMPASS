"""Read-only privacy-minimized Student Support Context API."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.student_support.services import (
    DEFAULT_PAGE_SIZE,
    StudentSupportConfigurationConflict,
    StudentSupportError,
    StudentSupportNotFound,
    get_student_support_context,
    list_student_support_students,
)

router = Router(tags=["student-support"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class InventoryStatusValue(StrEnum):
    MISSING = "MISSING"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class StudentReference(StrictSchema):
    id: UUID
    institutional_id: str | None = None
    display_name: str


class CollegeReference(StrictSchema):
    id: UUID
    code: str
    name: str


class AcademicYearReference(StrictSchema):
    id: UUID
    label: str


class SupportIndicatorResponse(StrictSchema):
    code: str
    label: str


class StudentSupportContextResponse(StrictSchema):
    student: StudentReference
    academic_year: AcademicYearReference
    inventory_status: InventoryStatusValue
    available: bool
    indicators: list[SupportIndicatorResponse]


class StudentSupportRosterRowResponse(StrictSchema):
    student: StudentReference
    college: CollegeReference | None
    academic_year: AcademicYearReference
    inventory_status: InventoryStatusValue
    available: bool
    indicators: list[SupportIndicatorResponse]


class StudentSupportRosterPageResponse(StrictSchema):
    items: list[StudentSupportRosterRowResponse]
    page: int
    page_size: int
    has_next: bool


def _require_viewer(request) -> None:
    actor = request.auth_user
    if (
        not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("student_support.view")
    ):
        raise APIError(
            403,
            "permission_denied",
            "Student Support Context access is required.",
        )


@router.get(
    "/students",
    response=response_with_errors(StudentSupportRosterPageResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="studentSupportListStudents",
)
def student_support_list_students(
    request,
    search: str | None = None,
    college_id: UUID | None = None,
    inventory_status: InventoryStatusValue | None = None,
    indicator: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_viewer(request)
    try:
        result = list_student_support_students(
            actor=request.auth_user,
            search=search,
            college_id=college_id,
            inventory_status=inventory_status.value if inventory_status is not None else None,
            indicator=indicator,
            page=page,
            page_size=page_size,
        )
    except StudentSupportNotFound as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
    except StudentSupportConfigurationConflict as exc:
        code = (
            "current_academic_year_not_configured"
            if "Academic Year" in str(exc)
            else "invalid_student_support_request"
        )
        status = 409 if code == "current_academic_year_not_configured" else 422
        raise APIError(status, code, str(exc)) from exc
    return {
        "items": [
            {
                "student": {
                    "id": row.student.pk,
                    "institutional_id": row.student.institutional_id,
                    "display_name": row.student.get_full_name(),
                },
                "college": (
                    {
                        "id": row.college.pk,
                        "code": row.college.code,
                        "name": row.college.name,
                    }
                    if row.college is not None
                    else None
                ),
                "academic_year": {
                    "id": row.academic_year.pk,
                    "label": row.academic_year.label,
                },
                "inventory_status": row.inventory_status,
                "available": row.available,
                "indicators": [{"code": item.code, "label": item.label} for item in row.indicators],
            }
            for row in result.items
        ],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/students/{student_id}/context",
    response=response_with_errors(StudentSupportContextResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="studentSupportGetContext",
)
def student_support_get_context(request, student_id: UUID):
    _require_viewer(request)
    try:
        context = get_student_support_context(actor=request.auth_user, student_id=student_id)
    except StudentSupportNotFound as exc:
        raise APIError(404, "student_support_not_found", str(exc)) from exc
    except StudentSupportConfigurationConflict as exc:
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    except StudentSupportError as exc:
        raise APIError(500, "internal_error", "Student Support Context is unavailable.") from exc
    return {
        "student": {
            "id": context.student.pk,
            "institutional_id": context.student.institutional_id,
            "display_name": context.student.get_full_name(),
        },
        "academic_year": {
            "id": context.academic_year.pk,
            "label": context.academic_year.label,
        },
        "inventory_status": context.inventory_status,
        "available": context.available,
        "indicators": [
            {"code": indicator.code, "label": indicator.label} for indicator in context.indicators
        ],
    }
