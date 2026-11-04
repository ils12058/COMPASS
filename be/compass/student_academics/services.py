"""The single writer and reader of canonical Student academic records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.audit.actions import (
    STUDENT_ACADEMICS_GRADUATION_RECORDED,
    STUDENT_ACADEMICS_PERIOD_RECORDED,
    STUDENT_ACADEMICS_PLACEMENT_CLEARED,
    STUDENT_ACADEMICS_PLACEMENT_SET,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.integrity import catalog_dependent_write
from compass.organization.models import AcademicYear, College
from compass.student_academics.models import (
    AcademicTerm,
    EnrollmentStatus,
    PlacementVerificationStatus,
    StudentAcademicPeriodRecord,
    StudentAcademicProfile,
    StudentGraduationRecord,
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


@dataclass(frozen=True, slots=True)
class StudentAcademicRecord:
    student: User
    lifecycle_status: str | None
    placement: StudentAcademicProfile | None
    periods: tuple[StudentAcademicPeriodRecord, ...]
    graduation: StudentGraduationRecord | None


def _actor(context: AuditContext) -> User | None:
    actor = context.actor
    return actor if isinstance(actor, User) else None


def _require_student_role(student: User) -> User:
    if student.role.code != "STUDENT":
        raise InvalidStudentAcademicInput("The student must have the STUDENT role.")
    return student


def _lock_student(student_id: UUID, *, require_active: bool) -> User:
    student = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=student_id)
        .first()
    )
    if student is None:
        raise StudentAcademicNotFound("The requested student was not found.")
    _require_student_role(student)
    if require_active and not student.is_active:
        raise InvalidStudentAcademicInput("The student account must be active.")
    return student


def _read_student(student_id: UUID) -> User:
    student = User.objects.select_related("role").filter(pk=student_id).first()
    if student is None:
        raise StudentAcademicNotFound("The requested student was not found.")
    return _require_student_role(student)


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


def _has_placement_facts(profile: StudentAcademicProfile) -> bool:
    return (
        profile.current_college_id is not None
        or profile.current_program_id is not None
        or profile.placement_verification_status != PlacementVerificationStatus.UNVERIFIED
        or profile.placement_effective_at is not None
    )


def _clear_placement_facts(
    *,
    student: User,
    profile: StudentAcademicProfile | None,
    context: AuditContext,
    cause: str | None = None,
) -> bool:
    """Clear every placement fact and audit once; a cleared profile is a no-op."""

    if profile is None or not _has_placement_facts(profile):
        return False
    previous = str(profile.current_college_id) if profile.current_college_id is not None else None
    profile.current_college = None
    profile.current_program = None
    profile.placement_verification_status = PlacementVerificationStatus.UNVERIFIED
    profile.placement_effective_at = None
    profile.updated_by = _actor(context)
    profile.save()
    metadata: dict[str, object] = {"previous_college_id": previous}
    if cause is not None:
        metadata["cause"] = cause
    record_event(
        context=context,
        action=STUDENT_ACADEMICS_PLACEMENT_CLEARED,
        outcome=AuditOutcome.SUCCESS,
        target_type="student_academics.studentacademicprofile",
        target_id=student.pk,
        metadata=metadata,
    )
    return True


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
        return _clear_placement_facts(student=student, profile=profile, context=context)


def _validate_term(term: str) -> str:
    if not isinstance(term, str) or term not in AcademicTerm.values:
        raise InvalidStudentAcademicInput(f"term must be one of {', '.join(AcademicTerm.values)}")
    return term


def _validate_enrollment_status(enrollment_status: str) -> str:
    if not isinstance(enrollment_status, str) or enrollment_status not in EnrollmentStatus.values:
        raise InvalidStudentAcademicInput(
            f"enrollment_status must be one of {', '.join(EnrollmentStatus.values)}"
        )
    return enrollment_status


def _validate_year_level(year_level: int | None) -> int | None:
    if year_level is None:
        return None
    if type(year_level) is not int or not 1 <= year_level <= 8:
        raise InvalidStudentAcademicInput("year_level must be an integer from 1 to 8.")
    return year_level


@catalog_dependent_write
def record_academic_period(
    *,
    student_id: UUID,
    academic_year_id: UUID,
    term: str,
    college_id: UUID,
    year_level: int | None,
    enrollment_status: str,
    context: AuditContext,
) -> StudentAcademicPeriodRecord:
    term = _validate_term(term)
    enrollment_status = _validate_enrollment_status(enrollment_status)
    year_level = _validate_year_level(year_level)
    with transaction.atomic():
        student = _lock_student(student_id, require_active=False)
        academic_year = AcademicYear.objects.filter(pk=academic_year_id).first()
        if academic_year is None:
            raise StudentAcademicNotFound("The requested academic year was not found.")
        college = _lock_active_college(college_id)
        record = (
            StudentAcademicPeriodRecord.objects.select_for_update()
            .filter(student=student, academic_year=academic_year, term=term)
            .first()
        )
        if record is not None and (
            record.college_id == college.pk
            and record.program_id is None
            and record.year_level == year_level
            and record.enrollment_status == enrollment_status
        ):
            return record
        created = record is None
        previous_college_id = (
            str(record.college_id) if record is not None and record.college_id else None
        )
        previous_year_level = record.year_level if record is not None else None
        previous_enrollment_status = record.enrollment_status if record is not None else None
        actor = _actor(context)
        if record is None:
            record = StudentAcademicPeriodRecord(
                student=student,
                academic_year=academic_year,
                term=term,
                created_by=actor,
            )
        record.college = college
        record.program = None
        record.year_level = year_level
        record.enrollment_status = enrollment_status
        record.updated_by = actor
        if created:
            record.save()
        else:
            record.save(
                update_fields=[
                    "college",
                    "program",
                    "year_level",
                    "enrollment_status",
                    "updated_by",
                    "updated_at",
                ]
            )
        record_event(
            context=context,
            action=STUDENT_ACADEMICS_PERIOD_RECORDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="student_academics.studentacademicperiodrecord",
            target_id=record.pk,
            metadata={
                "created": created,
                "student_id": str(student.pk),
                "academic_year_id": str(academic_year.pk),
                "term": term,
                "previous_college_id": previous_college_id,
                "new_college_id": str(college.pk),
                "previous_year_level": previous_year_level,
                "new_year_level": year_level,
                "previous_enrollment_status": previous_enrollment_status,
                "new_enrollment_status": enrollment_status,
            },
        )
        return record


@catalog_dependent_write
def record_graduation(
    *,
    student_id: UUID,
    graduated_college_id: UUID,
    graduation_date: date,
    verification_source: str,
    context: AuditContext,
) -> StudentGraduationRecord:
    if type(graduation_date) is not date:
        raise InvalidStudentAcademicInput("graduation_date must be a date.")
    if not isinstance(verification_source, str):
        raise InvalidStudentAcademicInput("verification_source must be text.")
    source = verification_source.strip()
    if not source:
        raise InvalidStudentAcademicInput("verification_source is required.")
    if len(source) > 200:
        raise InvalidStudentAcademicInput("verification_source must be at most 200 characters.")
    with transaction.atomic():
        student = _lock_student(student_id, require_active=False)
        college = _lock_active_college(graduated_college_id)
        profile = (
            StudentAcademicProfile.objects.select_for_update().filter(student_id=student.pk).first()
        )
        record = (
            StudentGraduationRecord.objects.select_for_update()
            .filter(student_id=student.pk)
            .first()
        )
        lifecycle_from = student.student_lifecycle_status
        placement_has_facts = profile is not None and _has_placement_facts(profile)
        if (
            record is not None
            and record.graduated_college_id == college.pk
            and record.graduated_program_id is None
            and record.graduation_date == graduation_date
            and record.verification_source == source
            and lifecycle_from == StudentLifecycleStatus.GRADUATED
            and not placement_has_facts
        ):
            return record
        created = record is None
        previous_college_id = str(record.graduated_college_id) if record is not None else None
        previous_graduation_date = record.graduation_date if record is not None else None
        previous_source = record.verification_source if record is not None else None
        actor = _actor(context)
        if record is None:
            record = StudentGraduationRecord(student=student)
        record.graduated_college = college
        record.graduated_program = None
        record.graduation_date = graduation_date
        record.verification_source = source
        record.verified_by = actor
        record.verified_at = timezone.now()
        record.save()
        placement_cleared = _clear_placement_facts(
            student=student,
            profile=profile,
            context=context,
            cause="graduation",
        )
        if lifecycle_from != StudentLifecycleStatus.GRADUATED:
            student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
            student.save(update_fields=["student_lifecycle_status", "updated_at"])
        record_event(
            context=context,
            action=STUDENT_ACADEMICS_GRADUATION_RECORDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="student_academics.studentgraduationrecord",
            target_id=record.pk,
            metadata={
                "created": created,
                "student_id": str(student.pk),
                "previous_college_id": previous_college_id,
                "new_college_id": str(college.pk),
                "previous_graduation_date": (
                    previous_graduation_date.isoformat()
                    if previous_graduation_date is not None
                    else None
                ),
                "new_graduation_date": graduation_date.isoformat(),
                "previous_source": previous_source,
                "new_source": source,
                "lifecycle_from": lifecycle_from,
                "lifecycle_to": StudentLifecycleStatus.GRADUATED,
                "placement_cleared": placement_cleared,
            },
        )
        return record


def get_student_academic_record(*, student_id: UUID) -> StudentAcademicRecord:
    student = _read_student(student_id)
    profile = (
        StudentAcademicProfile.objects.select_related("current_college__campus")
        .filter(student_id=student.pk)
        .first()
    )
    placement = profile if profile is not None and profile.current_college_id is not None else None
    periods = tuple(
        StudentAcademicPeriodRecord.objects.select_related("academic_year", "college__campus")
        .filter(student_id=student.pk)
        .order_by("-academic_year__label", "term")
    )
    graduation = (
        StudentGraduationRecord.objects.select_related(
            "graduated_college__campus", "verified_by__role"
        )
        .filter(student_id=student.pk)
        .first()
    )
    return StudentAcademicRecord(
        student=student,
        lifecycle_status=student.student_lifecycle_status,
        placement=placement,
        periods=periods,
        graduation=graduation,
    )


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

    queryset = StudentAcademicProfile.objects.filter(
        current_college__isnull=False, student__role__code="STUDENT"
    ).select_related("student__role", "current_college__campus")
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
