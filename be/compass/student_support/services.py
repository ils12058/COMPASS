"""Privacy-minimized Student Support Context projection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from compass.accounts.models import User
from compass.inventory.models import CivilStatusCategory, PWDStatus, StudentInventory
from compass.organization.academic_years import get_current_academic_year
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import StudentAffiliation
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    StudentSupportProfile,
)


class StudentSupportError(RuntimeError):
    pass


class StudentSupportNotFound(StudentSupportError):
    pass


class StudentSupportConfigurationConflict(StudentSupportError):
    pass


@dataclass(frozen=True, slots=True)
class SupportIndicator:
    code: str
    label: str


@dataclass(frozen=True, slots=True)
class StudentSupportContext:
    student: User
    academic_year: object
    inventory_status: str
    available: bool
    indicators: tuple[SupportIndicator, ...]


_INDICATORS = (
    ("PWD", "PWD"),
    ("SOLO_PARENT", "Solo Parent"),
    ("FOUR_PS_BENEFICIARY", "4Ps Household Beneficiary"),
    ("INDIGENOUS_PEOPLES_MEMBER", "Indigenous Peoples Member"),
    ("MOTHER_DECEASED", "Mother Deceased"),
    ("FATHER_DECEASED", "Father Deceased"),
)


def _require_scoped_student(*, actor: User, student_id: UUID) -> User:
    student = (
        User.objects.select_related("role")
        .filter(pk=student_id, is_active=True, role__code="STUDENT")
        .first()
    )
    if student is None:
        raise StudentSupportNotFound("The requested Student was not found.")

    scope = resolve_organizational_access_scope(actor)
    if scope.institution_wide:
        return student
    if not scope.college_ids:
        raise StudentSupportNotFound("The requested Student was not found.")
    if not StudentAffiliation.objects.filter(
        student_id=student.pk,
        college_id__in=scope.college_ids,
        college__is_active=True,
        college__campus__is_active=True,
    ).exists():
        raise StudentSupportNotFound("The requested Student was not found.")
    return student


def _indicator_rows(
    *,
    inventory: StudentInventory,
    profile: StudentSupportProfile | None,
) -> tuple[SupportIndicator, ...]:
    active: set[str] = set()
    if inventory.pwd_status == PWDStatus.PWD:
        active.add("PWD")
    if inventory.civil_status_category == CivilStatusCategory.SOLO_PARENT:
        active.add("SOLO_PARENT")
    if profile is not None:
        if profile.four_ps_status == FourPsStatus.BENEFICIARY:
            active.add("FOUR_PS_BENEFICIARY")
        if profile.indigenous_peoples_status == IndigenousPeoplesStatus.MEMBER:
            active.add("INDIGENOUS_PEOPLES_MEMBER")
        if profile.mother_life_status == ParentLifeStatus.DECEASED:
            active.add("MOTHER_DECEASED")
        if profile.father_life_status == ParentLifeStatus.DECEASED:
            active.add("FATHER_DECEASED")
    return tuple(
        SupportIndicator(code=code, label=label) for code, label in _INDICATORS if code in active
    )


def get_student_support_context(*, actor: User, student_id: UUID) -> StudentSupportContext:
    if not actor.is_active or actor.role.code != "COUNSELOR":
        raise StudentSupportNotFound("The requested Student was not found.")

    student = _require_scoped_student(actor=actor, student_id=student_id)
    academic_year = get_current_academic_year()
    if academic_year is None:
        raise StudentSupportConfigurationConflict("No current Academic Year is configured.")

    inventory = (
        StudentInventory.objects.select_related("support_profile")
        .filter(student_id=student.pk, academic_year_id=academic_year.pk)
        .first()
    )
    if inventory is None:
        return StudentSupportContext(student, academic_year, "MISSING", False, ())
    if inventory.submitted_at is None:
        return StudentSupportContext(student, academic_year, "DRAFT", False, ())

    profile = getattr(inventory, "support_profile", None)
    return StudentSupportContext(
        student,
        academic_year,
        "SUBMITTED",
        True,
        _indicator_rows(inventory=inventory, profile=profile),
    )


__all__ = [
    "StudentSupportConfigurationConflict",
    "StudentSupportContext",
    "StudentSupportError",
    "StudentSupportNotFound",
    "SupportIndicator",
    "get_student_support_context",
]
