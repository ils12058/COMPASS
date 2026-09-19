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
    StudentSupportConfigurationConflict,
    StudentSupportError,
    StudentSupportNotFound,
    get_student_support_context,
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
    display_name: str


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
