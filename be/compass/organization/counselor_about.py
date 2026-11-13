"""The shared safe Counselor About summary (CW-6, ABOUT-01 to ABOUT-03).

About answers one question: where in the Guidance Office is this Counselor currently assigned?
It returns the Counselor's display identity, optional photo and the active Colleges they handle,
grouped by Campus. A College the unique Head handles only because no valid Counselor is assigned
is reported as fallback coverage, never as a direct assignment.

It is deliberately not the Organization administration payload: no email, role, designation,
supervision, capability, assignment author or timestamp. It says nothing about who is
responsible for a particular Counseling case, and it promises no availability. The handled-College
calculation is the existing operational responsibility resolver, so About and routing cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.db.models import Q

from compass.accounts.models import User
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.models import College, CounselorResponsibility

STUDENT_CAPABILITIES = frozenset(
    {"appointments.view_self", "appointments.manage_self", "guidance_messages.view_self"}
)
# Staff open About from Messages, Appointments, Counseling cases and continuity preparation.
STAFF_CAPABILITIES = frozenset(
    {
        "guidance_messages.view",
        "appointments.manage",
        "counseling.view_assigned",
        "counseling.continuity.view",
        "counseling.continuity.request",
    }
)
STAFF_ROLES = frozenset({"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"})


class AssignmentBasis(StrEnum):
    ASSIGNED = "ASSIGNED"
    HEAD_FALLBACK = "HEAD_FALLBACK"


class CounselorAboutDenied(Exception):
    """The viewer's account has no surface that shows Counselor About."""


class CounselorAboutUnavailable(Exception):
    """Unknown, inactive, not a Counselor, or not a Counselor this viewer is offered."""


@dataclass(frozen=True, slots=True)
class AboutCollege:
    college: College
    basis: AssignmentBasis


@dataclass(frozen=True, slots=True)
class CounselorAbout:
    counselor: User
    colleges: tuple[AboutCollege, ...]


def _current(user_id) -> User | None:
    # Never trust a role, active flag or capability set from an earlier request.
    return User.objects.select_related("role").filter(pk=user_id, is_active=True).first()


def _has_any(user: User, codes: frozenset[str]) -> bool:
    return any(user.has_capability(code) for code in codes)


def _offered_to_student(student: User, counselor: User) -> bool:
    """A Counselor the Student is shown elsewhere: in booking or through their own records."""
    from compass.appointments.models import Appointment
    from compass.guidance_messages.models import GuidanceThread
    from compass.service_catalog.models import Service
    from compass.service_catalog.services import (
        service_accepts_appointments,
        service_eligible_counselors,
    )

    if Appointment.objects.filter(student_id=student.pk, provider_id=counselor.pk).exists():
        return True
    if GuidanceThread.objects.filter(student_id=student.pk, counselor_id=counselor.pk).exists():
        return True
    for service in Service.objects.filter(is_active=True).order_by("pk"):
        if (
            service_accepts_appointments(service)
            and service_eligible_counselors(service).filter(pk=counselor.pk).exists()
        ):
            return True
    return False


def _authorize(viewer: User, counselor: User | None) -> None:
    role = viewer.role.code
    if role == "STUDENT":
        if not _has_any(viewer, STUDENT_CAPABILITIES):
            raise CounselorAboutDenied()
        if counselor is None or not _offered_to_student(viewer, counselor):
            raise CounselorAboutUnavailable()
        return
    if role in STAFF_ROLES and _has_any(viewer, STAFF_CAPABILITIES):
        if counselor is None:
            raise CounselorAboutUnavailable()
        return
    raise CounselorAboutDenied()


def _handled_colleges(counselor: User) -> tuple[AboutCollege, ...]:
    scope = resolve_operational_responsibility_scope(counselor)
    if not scope.college_ids:
        return ()
    direct = set(
        CounselorResponsibility.objects.filter(
            counselor_id=counselor.pk,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
        ).values_list("college_id", flat=True)
    )
    colleges = (
        College.objects.filter(Q(pk__in=scope.college_ids), is_active=True, campus__is_active=True)
        .select_related("campus")
        .order_by("campus__code", "campus__name", "code", "pk")
    )
    return tuple(
        AboutCollege(
            college=college,
            basis=(
                AssignmentBasis.ASSIGNED if college.pk in direct else AssignmentBasis.HEAD_FALLBACK
            ),
        )
        for college in colleges
    )


def get_counselor_about(*, viewer: User, counselor_id: UUID) -> CounselorAbout:
    current_viewer = _current(getattr(viewer, "pk", None))
    if current_viewer is None:
        raise CounselorAboutDenied()
    counselor = _current(counselor_id)
    if counselor is not None and counselor.role.code != "COUNSELOR":
        counselor = None
    _authorize(current_viewer, counselor)
    if counselor is None:
        raise CounselorAboutUnavailable()
    return CounselorAbout(counselor=counselor, colleges=_handled_colleges(counselor))
