"""Read-only placement boundary for Faculty intake and Referral student verification.

Home College, inventory form text and Head fallback are never Student placement.
Caller takes catalog gate and Student row lock before resolving mutable placement.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from compass.inventory.models import StudentInventory
from compass.organization.academic_years import get_current_academic_year
from compass.student_academics.models import StudentAcademicPeriodRecord
from compass.student_academics.reads import get_current_placement


@dataclass(frozen=True)
class FacultyReferralStudentPlacement:
    student_id: UUID
    college_id: UUID
    college_code: str
    college_name: str
    revision: str


@dataclass(frozen=True)
class StudentAcademicSummary:
    program_id: UUID | None = None
    program_code: str | None = None
    program_name: str | None = None
    year_level: int | None = None


def resolve_student_placement(student):
    if not student.is_active or student.role.code != "STUDENT":
        return None
    facts = get_current_placement(student_id=student.pk, require_active_college=True)
    if facts is None:
        return None
    return FacultyReferralStudentPlacement(
        student_id=student.pk,
        college_id=facts.college.id,
        college_code=facts.college.code,
        college_name=facts.college.name,
        revision=facts.revision,
    )


def resolve_students_academic_summaries(
    student_colleges: dict[UUID, UUID | None],
) -> dict[UUID, StudentAcademicSummary]:
    """Resolve minimum-necessary Program and Year Level facts for Student verification.

    Reads only non-confidential academic columns (never decrypts Inventory ciphertext and
    never reads unsubmitted Inventory drafts). Any Program or period record from a different
    College than the Student's canonical current placement is ignored.
    """
    if not student_colleges:
        return {}

    student_ids = tuple(student_colleges)
    current_year = get_current_academic_year()

    year_levels: dict[UUID, int] = {}
    period_qs = StudentAcademicPeriodRecord.objects.filter(
        student_id__in=student_ids,
        year_level__isnull=False,
    )
    if current_year is not None:
        period_qs = period_qs.filter(academic_year_id=current_year.pk)
    for row in period_qs.order_by("-academic_year__label", "-term").values(
        "student_id",
        "college_id",
        "year_level",
    ):
        sid = row["student_id"]
        if sid in year_levels:
            continue
        expected_college_id = student_colleges.get(sid)
        if expected_college_id is not None and row["college_id"] != expected_college_id:
            continue
        year_levels[sid] = row["year_level"]

    programs: dict[UUID, tuple[UUID, str, str]] = {}
    current_year_programs: set[UUID] = set()
    inventory_qs = (
        StudentInventory.objects.filter(
            student_id__in=student_ids,
            submitted_at__isnull=False,
        )
        .order_by("-academic_year__label", "-submitted_at")
        .values(
            "student_id",
            "academic_year_id",
            "program_id",
            "program__code",
            "program__name",
            "program__college_id",
            "year_level",
        )
    )
    for row in inventory_qs:
        sid = row["student_id"]
        expected_college_id = student_colleges.get(sid)
        program_id = row["program_id"]
        program_college_id = row["program__college_id"]
        matches_college = (
            program_id is None
            or expected_college_id is None
            or program_college_id == expected_college_id
        )
        is_current = current_year is not None and row["academic_year_id"] == current_year.pk

        if program_id is not None and matches_college:
            if is_current and sid not in current_year_programs:
                programs[sid] = (program_id, row["program__code"], row["program__name"])
                current_year_programs.add(sid)
            elif sid not in programs:
                programs[sid] = (program_id, row["program__code"], row["program__name"])

        if sid not in year_levels and row["year_level"] is not None and matches_college:
            if current_year is None or is_current:
                year_levels[sid] = row["year_level"]

    results: dict[UUID, StudentAcademicSummary] = {}
    for sid in student_ids:
        program = programs.get(sid)
        results[sid] = StudentAcademicSummary(
            program_id=program[0] if program is not None else None,
            program_code=program[1] if program is not None else None,
            program_name=program[2] if program is not None else None,
            year_level=year_levels.get(sid),
        )
    return results
