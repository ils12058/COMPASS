"""Read-only projections of canonical current Student placement.

This module deliberately exposes only current placement. Period and graduation
read functions are deferred: no cross-domain consumer reads them today, and
adding speculative projections would invent an API without a caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from compass.student_academics.models import StudentAcademicProfile


@dataclass(frozen=True, slots=True)
class AcademicCollegeFacts:
    id: UUID
    code: str
    name: str
    is_active: bool
    campus_id: UUID
    campus_code: str
    campus_name: str
    campus_is_active: bool

    @property
    def is_usable(self) -> bool:
        return self.is_active and self.campus_is_active


@dataclass(frozen=True, slots=True)
class StudentPlacementFacts:
    student_id: UUID
    profile_id: UUID
    college: AcademicCollegeFacts
    updated_at: datetime

    @property
    def revision(self) -> str:
        # Must stay byte-identical to the existing Faculty Referral revision token.
        return f"student_academics:{self.profile_id}:{self.updated_at.isoformat()}"


def get_current_placement(
    *, student_id: UUID, require_active_college: bool = False
) -> StudentPlacementFacts | None:
    profile = (
        StudentAcademicProfile.objects.select_related("current_college__campus")
        .filter(student_id=student_id)
        .first()
    )
    if profile is None or profile.current_college is None:
        return None
    college = profile.current_college
    if require_active_college and (not college.is_active or not college.campus.is_active):
        return None
    return StudentPlacementFacts(
        student_id=profile.student_id,
        profile_id=profile.pk,
        college=AcademicCollegeFacts(
            id=college.pk,
            code=college.code,
            name=college.name,
            is_active=college.is_active,
            campus_id=college.campus_id,
            campus_code=college.campus.code,
            campus_name=college.campus.name,
            campus_is_active=college.campus.is_active,
        ),
        updated_at=profile.updated_at,
    )


def student_is_placed_in_colleges(
    *, student_id: UUID, college_ids, require_active_college: bool = True
) -> bool:
    ids = tuple(college_ids)
    if not ids:
        return False
    queryset = StudentAcademicProfile.objects.filter(
        student_id=student_id, current_college_id__in=ids
    )
    if require_active_college:
        queryset = queryset.filter(
            current_college__is_active=True,
            current_college__campus__is_active=True,
        )
    return queryset.exists()


__all__ = [
    "AcademicCollegeFacts",
    "StudentPlacementFacts",
    "get_current_placement",
    "student_is_placed_in_colleges",
]
