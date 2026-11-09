"""Initial Student placement for account provisioning. College-only per D-SAR-01."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from compass.organization.models import Campus, College, normalize_code

from .services import InvalidManagementInput

STUDENT_ONLY_MESSAGE = "Only Student accounts accept an initial academic placement."
CAMPUS_AND_COLLEGE_MESSAGE = "Select both Campus and College, or neither."


@dataclass(frozen=True, slots=True)
class CsvStudentPlacement:
    campus_id: UUID
    campus_code: str
    college_id: UUID
    college_code: str


def _parse_uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidManagementInput("Campus and College must be catalog UUIDs.") from exc


def validate_initial_student_placement(*, role, campus_id, college_id) -> College | None:
    if campus_id is None and college_id is None:
        return None
    if (campus_id is None) != (college_id is None):
        raise InvalidManagementInput(CAMPUS_AND_COLLEGE_MESSAGE)
    if role != "STUDENT":
        raise InvalidManagementInput(STUDENT_ONLY_MESSAGE)

    campus_uuid = _parse_uuid(campus_id)
    college_uuid = _parse_uuid(college_id)

    campus = Campus.objects.filter(pk=campus_uuid).first()
    if campus is None or not campus.is_active:
        raise InvalidManagementInput("Select an active Campus.")

    college = College.objects.select_related("campus").filter(pk=college_uuid).first()
    if college is None or not college.is_active or not college.campus.is_active:
        raise InvalidManagementInput("Select an active College beneath an active Campus.")
    if college.campus_id != campus.pk:
        raise InvalidManagementInput("The College must belong to the selected Campus.")
    return college


def resolve_csv_student_placement(*, role, campus_code, college_code) -> CsvStudentPlacement | None:
    campus_code = (campus_code or "").strip()
    college_code = (college_code or "").strip()
    if not campus_code and not college_code:
        return None
    if not campus_code or not college_code:
        raise InvalidManagementInput("Choose both a Campus and College, or leave both blank.")
    if role != "STUDENT":
        raise InvalidManagementInput(STUDENT_ONLY_MESSAGE)

    normalized_campus = normalize_code(campus_code)
    normalized_college = normalize_code(college_code)

    campus = Campus.objects.filter(code=normalized_campus, is_active=True).first()
    if campus is None:
        raise InvalidManagementInput("Choose an active Campus.")

    college = College.objects.filter(
        code=normalized_college,
        is_active=True,
        campus_id=campus.pk,
        campus__is_active=True,
    ).first()
    if college is None:
        raise InvalidManagementInput("Choose an active College in the selected Campus.")

    return CsvStudentPlacement(
        campus_id=campus.pk,
        campus_code=campus.code,
        college_id=college.pk,
        college_code=college.code,
    )


__all__ = [
    "CsvStudentPlacement",
    "resolve_csv_student_placement",
    "validate_initial_student_placement",
]
