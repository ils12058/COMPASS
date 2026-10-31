"""Read-only placement boundary for Faculty intake; SAR may replace this adapter.

Home College, inventory form text and Head fallback are never Student placement.
Caller takes catalog gate and Student row lock before resolving mutable placement.
"""

from dataclasses import dataclass
from uuid import UUID

from compass.organization.models import StudentAffiliation


@dataclass(frozen=True)
class FacultyReferralStudentPlacement:
    student_id: UUID
    college_id: UUID
    revision: str


def resolve_student_placement(student):
    if not student.is_active or student.role.code != "STUDENT":
        return None
    affiliation = (
        StudentAffiliation.objects.select_related("college__campus")
        .filter(
            student_id=student.pk,
        )
        .first()
    )
    if (
        affiliation is None
        or not affiliation.college.is_active
        or not affiliation.college.campus.is_active
    ):
        return None
    return FacultyReferralStudentPlacement(
        student_id=student.pk,
        college_id=affiliation.college_id,
        revision=f"organization:{affiliation.pk}:{affiliation.updated_at.isoformat()}",
    )
