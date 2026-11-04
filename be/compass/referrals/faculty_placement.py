"""Read-only placement boundary for Faculty intake.

Home College, inventory form text and Head fallback are never Student placement.
Caller takes catalog gate and Student row lock before resolving mutable placement.
"""

from dataclasses import dataclass
from uuid import UUID

from compass.student_academics.reads import get_current_placement


@dataclass(frozen=True)
class FacultyReferralStudentPlacement:
    student_id: UUID
    college_id: UUID
    revision: str


def resolve_student_placement(student):
    if not student.is_active or student.role.code != "STUDENT":
        return None
    facts = get_current_placement(student_id=student.pk, require_active_college=True)
    if facts is None:
        return None
    return FacultyReferralStudentPlacement(
        student_id=student.pk,
        college_id=facts.college.id,
        revision=facts.revision,
    )
