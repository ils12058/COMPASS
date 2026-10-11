"""Current handled College workload, separate from domain-owned Head oversight."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db.models import Q

from compass.accounts.models import User

from .models import College, CounselorResponsibility, StaffSupervision

HEAD_GUIDANCE_DESIGNATION = "HEAD_GUIDANCE_COUNSELOR"


@dataclass(frozen=True, slots=True)
class OperationalResponsibilityScope:
    college_ids: tuple[UUID, ...] = ()


EMPTY_OPERATIONAL_RESPONSIBILITY_SCOPE = OperationalResponsibilityScope()


@dataclass(frozen=True, slots=True)
class GeneralGuidanceCollegeScope:
    """Eligible College visibility, without capability or provider authority."""

    college_ids: tuple[UUID, ...] = ()


EMPTY_GENERAL_GUIDANCE_COLLEGE_SCOPE = GeneralGuidanceCollegeScope()


def is_head_guidance(actor: User) -> bool:
    """Check the actor's own designation; never resolve it through supervision."""
    return (
        bool(getattr(actor, "pk", None))
        and actor.is_active
        and actor.role.code == "COUNSELOR"
        and actor.designations.filter(code=HEAD_GUIDANCE_DESIGNATION).exists()
    )


def active_head_guidance_counselors():
    """The same valid Head candidates for default routing and derived workload."""
    return (
        User.objects.filter(
            is_active=True,
            role__code="COUNSELOR",
            designation_assignments__designation__code=HEAD_GUIDANCE_DESIGNATION,
        )
        .select_related("role")
        .distinct()
    )


def resolve_operational_responsibility_scope(actor: User) -> OperationalResponsibilityScope:
    """Resolve handled Colleges only. No capabilities, relationships or oversight are inherited."""
    if not getattr(actor, "pk", None) or not actor.is_active:
        return EMPTY_OPERATIONAL_RESPONSIBILITY_SCOPE

    if actor.role.code == "GUIDANCE_SERVICES_STAFF":
        supervision = (
            StaffSupervision.objects.select_related("supervisor__role")
            .filter(staff_id=actor.pk)
            .first()
        )
        if (
            supervision is None
            or not supervision.supervisor.is_active
            or supervision.supervisor.role.code != "COUNSELOR"
        ):
            return EMPTY_OPERATIONAL_RESPONSIBILITY_SCOPE
        return resolve_operational_responsibility_scope(supervision.supervisor)

    if actor.role.code != "COUNSELOR":
        return EMPTY_OPERATIONAL_RESPONSIBILITY_SCOPE

    valid_responsibilities = CounselorResponsibility.objects.filter(
        counselor__is_active=True, counselor__role__code="COUNSELOR"
    )
    handled = Q(pk__in=valid_responsibilities.filter(counselor_id=actor.pk).values("college_id"))
    heads = list(active_head_guidance_counselors().values_list("pk", flat=True)[:2])
    if heads == [actor.pk]:
        # A missing, inactive or non-Counselor assignment falls back only to the unique Head.
        handled |= ~Q(pk__in=valid_responsibilities.values("college_id"))
    return OperationalResponsibilityScope(
        college_ids=tuple(
            College.objects.filter(handled, is_active=True, campus__is_active=True)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    )


def resolve_general_guidance_college_scope(actor: User) -> GeneralGuidanceCollegeScope:
    """General Guidance College visibility, distinct from handled responsibility.

    Heads can see all active Colleges (even those assigned to other Counselors).
    Ordinary Counselors see only valid explicit assignments. GSS inherits only
    the currently valid supervising Counselor's College visibility, never the
    designation, capability or provider relationship. Callers enforce their own
    capabilities and resource policy; routing still uses the handled resolver.
    """
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        return EMPTY_GENERAL_GUIDANCE_COLLEGE_SCOPE
    # Never trust a stale actor role or active flag from an earlier request.
    current = User.objects.select_related("role").filter(pk=actor_id, is_active=True).first()
    if current is None:
        return EMPTY_GENERAL_GUIDANCE_COLLEGE_SCOPE

    if current.role.code == "GUIDANCE_SERVICES_STAFF":
        supervision = (
            StaffSupervision.objects.select_related("supervisor__role")
            .filter(staff_id=current.pk)
            .first()
        )
        if (
            supervision is None
            or not supervision.supervisor.is_active
            or supervision.supervisor.role.code != "COUNSELOR"
        ):
            return EMPTY_GENERAL_GUIDANCE_COLLEGE_SCOPE
        return resolve_general_guidance_college_scope(supervision.supervisor)

    if current.role.code != "COUNSELOR":
        return EMPTY_GENERAL_GUIDANCE_COLLEGE_SCOPE

    eligible = College.objects.filter(is_active=True, campus__is_active=True)
    if not is_head_guidance(current):
        eligible = eligible.filter(
            pk__in=CounselorResponsibility.objects.filter(
                counselor_id=current.pk,
                counselor__is_active=True,
                counselor__role__code="COUNSELOR",
            ).values("college_id")
        )
    return GeneralGuidanceCollegeScope(
        college_ids=tuple(eligible.order_by("pk").values_list("pk", flat=True))
    )
