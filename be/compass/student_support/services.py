"""Privacy-minimized Student Support Context projection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db.models import Q

from compass.accounts.models import User
from compass.inventory.models import CivilStatusCategory, PWDStatus, StudentInventory
from compass.organization.academic_years import get_current_academic_year
from compass.organization.models import CounselorResponsibility, StudentAffiliation
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    StudentSupportProfile,
)

HEAD_DESIGNATION = "HEAD_GUIDANCE_COUNSELOR"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = 160


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


@dataclass(frozen=True, slots=True)
class StudentSupportRosterRow:
    student: User
    college: object | None
    academic_year: object
    inventory_status: str
    available: bool
    indicators: tuple[SupportIndicator, ...]


@dataclass(frozen=True, slots=True)
class StudentSupportRosterPage:
    items: tuple[StudentSupportRosterRow, ...]
    page: int
    page_size: int
    has_next: bool


_INDICATORS = (
    ("PWD", "PWD"),
    ("SOLO_PARENT", "Solo Parent"),
    ("FOUR_PS_BENEFICIARY", "4Ps Household Beneficiary"),
    ("INDIGENOUS_PEOPLES_MEMBER", "Indigenous Peoples Member"),
    ("MOTHER_DECEASED", "Mother Deceased"),
    ("FATHER_DECEASED", "Father Deceased"),
)


def _is_head(actor: User) -> bool:
    return actor.designations.filter(code=HEAD_DESIGNATION).exists()


def _require_scoped_student(*, actor: User, student_id: UUID) -> User:
    student = (
        User.objects.select_related("role")
        .filter(pk=student_id, is_active=True, role__code="STUDENT")
        .first()
    )
    if student is None:
        raise StudentSupportNotFound("The requested Student was not found.")

    if _is_head(actor):
        return student

    affiliation = (
        StudentAffiliation.objects.select_related("college__campus")
        .filter(student_id=student.pk)
        .first()
    )
    if affiliation is None:
        raise StudentSupportNotFound("The requested Student was not found.")
    college = affiliation.college
    if not college.is_active or not college.campus.is_active:
        raise StudentSupportNotFound("The requested Student was not found.")
    if not CounselorResponsibility.objects.filter(
        college_id=college.pk,
        counselor_id=actor.pk,
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
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "StudentSupportRosterPage",
    "StudentSupportRosterRow",
    "SupportIndicator",
    "get_student_support_context",
    "list_student_support_students",
]

def _roster_scope_students(actor: User):
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("student_support.view")
    ):
        raise StudentSupportNotFound("Student Support roster access is unavailable.")

    queryset = User.objects.filter(is_active=True, role__code="STUDENT").select_related(
        "role",
        "organization_student_affiliation__college__campus",
    )
    if _is_head(actor):
        return queryset

    college_ids = tuple(
        CounselorResponsibility.objects.filter(
            counselor_id=actor.pk,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
            college__is_active=True,
            college__campus__is_active=True,
        )
        .order_by("college_id")
        .values_list("college_id", flat=True)
    )
    if not college_ids:
        return queryset.none()
    return queryset.filter(
        organization_student_affiliation__college_id__in=college_ids,
        organization_student_affiliation__college__is_active=True,
        organization_student_affiliation__college__campus__is_active=True,
    )


def list_student_support_students(
    *,
    actor: User,
    search: str | None = None,
    college_id: UUID | None = None,
    inventory_status: str | None = None,
    indicator: str | None = None,
    page: int = DEFAULT_PAGE_SIZE // DEFAULT_PAGE_SIZE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> StudentSupportRosterPage:
    if type(page) is not int or page < 1:
        raise StudentSupportConfigurationConflict("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise StudentSupportConfigurationConflict(
            f"page_size must be between 1 and {MAX_PAGE_SIZE}."
        )

    year = get_current_academic_year()
    if year is None:
        raise StudentSupportConfigurationConflict("No current Academic Year is configured.")

    queryset = _roster_scope_students(actor)

    if search is not None:
        if not isinstance(search, str):
            raise StudentSupportConfigurationConflict("search must be text.")
        term = search.strip()
        if len(term) > MAX_SEARCH_LENGTH:
            raise StudentSupportConfigurationConflict(
                f"search must be at most {MAX_SEARCH_LENGTH} characters."
            )
        if term:
            queryset = queryset.filter(
                Q(institutional_id__icontains=term)
                | Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
            )

    if college_id is not None:
        queryset = queryset.filter(organization_student_affiliation__college_id=college_id)

    if inventory_status is not None:
        if inventory_status not in {"MISSING", "DRAFT", "SUBMITTED"}:
            raise StudentSupportConfigurationConflict(
                "inventory_status must be MISSING, DRAFT, or SUBMITTED."
            )
        if inventory_status == "MISSING":
            queryset = queryset.exclude(individual_inventories__academic_year_id=year.pk)
        elif inventory_status == "DRAFT":
            queryset = queryset.filter(
                individual_inventories__academic_year_id=year.pk,
                individual_inventories__submitted_at__isnull=True,
            )
        else:
            queryset = queryset.filter(
                individual_inventories__academic_year_id=year.pk,
                individual_inventories__submitted_at__isnull=False,
            )

    indicator_codes = {code for code, _label in _INDICATORS}
    if indicator is not None:
        if indicator not in indicator_codes:
            raise StudentSupportConfigurationConflict("indicator is not supported.")
        inventory_filter = {
            "individual_inventories__academic_year_id": year.pk,
            "individual_inventories__submitted_at__isnull": False,
        }
        queryset = queryset.filter(**inventory_filter)
        if indicator == "PWD":
            queryset = queryset.filter(individual_inventories__pwd_status=PWDStatus.PWD)
        elif indicator == "SOLO_PARENT":
            queryset = queryset.filter(
                individual_inventories__civil_status_category=CivilStatusCategory.SOLO_PARENT
            )
        elif indicator == "FOUR_PS_BENEFICIARY":
            queryset = queryset.filter(
                individual_inventories__support_profile__four_ps_status=FourPsStatus.BENEFICIARY
            )
        elif indicator == "INDIGENOUS_PEOPLES_MEMBER":
            queryset = queryset.filter(
                individual_inventories__support_profile__indigenous_peoples_status=(
                    IndigenousPeoplesStatus.MEMBER
                )
            )
        elif indicator == "MOTHER_DECEASED":
            queryset = queryset.filter(
                individual_inventories__support_profile__mother_life_status=ParentLifeStatus.DECEASED
            )
        elif indicator == "FATHER_DECEASED":
            queryset = queryset.filter(
                individual_inventories__support_profile__father_life_status=ParentLifeStatus.DECEASED
            )

    queryset = queryset.order_by("last_name", "first_name", "id").distinct()
    offset = (page - 1) * page_size
    students = list(queryset[offset : offset + page_size + 1])
    selected = students[:page_size]

    inventory_by_student = {
        item.student_id: item
        for item in StudentInventory.objects.select_related("support_profile").filter(
            student_id__in=[student.pk for student in selected],
            academic_year_id=year.pk,
        )
    }

    rows: list[StudentSupportRosterRow] = []
    for student in selected:
        inventory = inventory_by_student.get(student.pk)
        affiliation = getattr(student, "organization_student_affiliation", None)
        college = None
        if (
            affiliation is not None
            and affiliation.college.is_active
            and affiliation.college.campus.is_active
        ):
            college = affiliation.college

        if inventory is None:
            status = "MISSING"
            available = False
            indicators = ()
        elif inventory.submitted_at is None:
            status = "DRAFT"
            available = False
            indicators = ()
        else:
            status = "SUBMITTED"
            available = True
            indicators = _indicator_rows(
                inventory=inventory,
                profile=getattr(inventory, "support_profile", None),
            )
        rows.append(
            StudentSupportRosterRow(
                student=student,
                college=college,
                academic_year=year,
                inventory_status=status,
                available=available,
                indicators=indicators,
            )
        )

    return StudentSupportRosterPage(
        items=tuple(rows),
        page=page,
        page_size=page_size,
        has_next=len(students) > page_size,
    )

