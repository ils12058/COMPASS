"""The single writer and reader of the canonical Student academic placement."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.db.models import Q

from compass.accounts.models import User
from compass.audit.actions import (
    STUDENT_ACADEMICS_PLACEMENT_CLEARED,
    STUDENT_ACADEMICS_PLACEMENT_SET,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.integrity import catalog_dependent_write
from compass.organization.models import College
from compass.student_academics.models import (
    PlacementVerificationStatus,
    StudentAcademicProfile,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class StudentAcademicError(RuntimeError):
    pass


class StudentAcademicNotFound(StudentAcademicError):
    pass


class StudentAcademicConflict(StudentAcademicError):
    pass


class InvalidStudentAcademicInput(StudentAcademicError):
    pass


@dataclass(frozen=True, slots=True)
class StudentPlacementPage:
    items: tuple[StudentAcademicProfile, ...]
    page: int
    page_size: int
    has_next: bool


def _actor(context: AuditContext) -> User | None:
    actor = context.actor
    return actor if isinstance(actor, User) else None


def _lock_student(student_id: UUID, *, require_active: bool) -> User:
    student = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=student_id)
        .first()
    )
    if student is None:
        raise StudentAcademicNotFound("The requested student was not found.")
    if student.role.code != "STUDENT":
        raise InvalidStudentAcademicInput("The student must have the STUDENT role.")
    if require_active and not student.is_active:
        raise InvalidStudentAcademicInput("The student account must be active.")
    return student


def _lock_active_college(college_id: UUID) -> College:
    college = (
        College.objects.select_for_update(of=("self", "campus"))
        .select_related("campus")
        .filter(pk=college_id)
        .first()
    )
    if college is None:
        raise StudentAcademicNotFound("The requested college was not found.")
    if not college.is_active or not college.campus.is_active:
        raise StudentAcademicConflict("The College and its Campus must both be active.")
    return college


@catalog_dependent_write
def set_current_placement(
    *, student_id: UUID, college_id: UUID, context: AuditContext
) -> StudentAcademicProfile:
    with transaction.atomic():
        student = _lock_student(student_id, require_active=True)
        college = _lock_active_college(college_id)
        profile = (
            StudentAcademicProfile.objects.select_for_update().filter(student_id=student.pk).first()
        )
        if (
            profile is not None
            and profile.current_college_id == college.pk
            and profile.current_program_id is None
            and profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
            and profile.placement_effective_at is None
        ):
            return profile
        previous = (
            str(profile.current_college_id)
            if profile is not None and profile.current_college_id is not None
            else None
        )
        if profile is None:
            profile = StudentAcademicProfile(student=student)
        profile.current_college = college
        profile.current_program = None
        profile.placement_verification_status = PlacementVerificationStatus.UNVERIFIED
        profile.placement_effective_at = None
        profile.updated_by = _actor(context)
        profile.save()
        record_event(
            context=context,
            action=STUDENT_ACADEMICS_PLACEMENT_SET,
            outcome=AuditOutcome.SUCCESS,
            target_type="student_academics.studentacademicprofile",
            target_id=student.pk,
            metadata={"previous_college_id": previous, "new_college_id": str(college.pk)},
        )
        return profile


@catalog_dependent_write
def clear_current_placement(*, student_id: UUID, context: AuditContext) -> bool:
    with transaction.atomic():
        student = _lock_student(student_id, require_active=False)
        profile = (
            StudentAcademicProfile.objects.select_for_update().filter(student_id=student.pk).first()
        )
        if profile is None:
            return False
        previous = (
            str(profile.current_college_id) if profile.current_college_id is not None else None
        )
        profile.current_college = None
        profile.current_program = None
        profile.placement_verification_status = PlacementVerificationStatus.UNVERIFIED
        profile.placement_effective_at = None
        profile.updated_by = _actor(context)
        profile.save()
        record_event(
            context=context,
            action=STUDENT_ACADEMICS_PLACEMENT_CLEARED,
            outcome=AuditOutcome.SUCCESS,
            target_type="student_academics.studentacademicprofile",
            target_id=student.pk,
            metadata={"previous_college_id": previous},
        )
        return True


def list_current_placements(
    *,
    student_id: UUID | None = None,
    college_id: UUID | None = None,
    campus_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> StudentPlacementPage:
    if type(page) is not int or page < 1:
        raise InvalidStudentAcademicInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidStudentAcademicInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    term = ""
    if search is not None:
        if not isinstance(search, str):
            raise InvalidStudentAcademicInput("search must be text")
        term = search.strip()
        if len(term) > 160:
            raise InvalidStudentAcademicInput("search must be at most 160 characters")

    queryset = StudentAcademicProfile.objects.filter(current_college__isnull=False).select_related(
        "student__role", "current_college__campus"
    )
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    if college_id is not None:
        queryset = queryset.filter(current_college_id=college_id)
    if campus_id is not None:
        queryset = queryset.filter(current_college__campus_id=campus_id)
    if term:
        queryset = queryset.filter(
            Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
        )
    queryset = queryset.order_by("student__last_name", "student__first_name", "student_id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return StudentPlacementPage(
        tuple(rows[:page_size]),
        page,
        page_size,
        len(rows) > page_size,
    )
