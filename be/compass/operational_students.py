"""Narrow Student selection for scoped Guidance operational workflows."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db.models import Q

from compass.accounts.models import User
from compass.organization.access_scope import resolve_organizational_access_scope

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = 160


class InvalidOperationalStudentQuery(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OperationalCollegeOption:
    id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class OperationalStudentOption:
    id: UUID
    institutional_id: str | None
    display_name: str
    college: OperationalCollegeOption | None


@dataclass(frozen=True, slots=True)
class OperationalStudentPage:
    items: tuple[OperationalStudentOption, ...]
    page: int
    page_size: int
    has_next: bool


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidOperationalStudentQuery("page must be a positive integer.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidOperationalStudentQuery(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _search_term(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidOperationalStudentQuery("search must be text.")
    term = search.strip()
    if len(term) > MAX_SEARCH_LENGTH:
        raise InvalidOperationalStudentQuery(
            f"search must be at most {MAX_SEARCH_LENGTH} characters."
        )
    return term


def _college_option(student: User) -> OperationalCollegeOption | None:
    affiliation = getattr(student, "organization_student_affiliation", None)
    if affiliation is None:
        return None
    college = affiliation.college
    if not college.is_active or not college.campus.is_active:
        return None
    return OperationalCollegeOption(id=college.pk, code=college.code, name=college.name)


def list_scoped_operational_students(
    *,
    actor: User,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> OperationalStudentPage:
    page, page_size = _pagination(page, page_size)
    term = _search_term(search)
    scope = resolve_organizational_access_scope(actor)
    queryset = User.objects.filter(is_active=True, role__code="STUDENT").select_related(
        "role",
        "organization_student_affiliation__college",
        "organization_student_affiliation__college__campus",
    )
    if not scope.institution_wide:
        if not scope.college_ids:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(
                organization_student_affiliation__college_id__in=scope.college_ids,
                organization_student_affiliation__college__is_active=True,
                organization_student_affiliation__college__campus__is_active=True,
            )
    if term:
        queryset = queryset.filter(
            Q(institutional_id__icontains=term)
            | Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
        )
    queryset = queryset.order_by("last_name", "first_name", "institutional_id", "id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return OperationalStudentPage(
        items=tuple(
            OperationalStudentOption(
                id=row.pk,
                institutional_id=row.institutional_id,
                display_name=row.get_full_name(),
                college=_college_option(row),
            )
            for row in rows[:page_size]
        ),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )
