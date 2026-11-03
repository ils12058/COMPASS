"""Read-only placement boundary for Faculty intake.

Home College, inventory form text and Head fallback are never Student placement.
Caller takes catalog gate and Student row lock before resolving mutable placement.
"""

from dataclasses import dataclass
from uuid import UUID

from compass.student_academics.models import StudentAcademicProfile


@dataclass(frozen=True)
class FacultyReferralStudentPlacement:
    student_id: UUID
    college_id: UUID
    revision: str


def resolve_student_placement(student):
    if not student.is_active or student.role.code != "STUDENT":
        return None
    profile = (
        StudentAcademicProfile.objects.select_related("current_college__campus")
        .filter(
            student_id=student.pk,
        )
        .first()
    )
    if (
        profile is None
        or profile.current_college is None
        or not profile.current_college.is_active
        or not profile.current_college.campus.is_active
    ):
        return None
    return FacultyReferralStudentPlacement(
        student_id=student.pk,
        college_id=profile.current_college_id,
        revision=f"student_academics:{profile.pk}:{profile.updated_at.isoformat()}",
    )
