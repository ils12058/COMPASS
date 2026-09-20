"""Canonical authorization-oriented organizational access scope."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from compass.accounts.models import User

from .models import CounselorResponsibility, StaffSupervision

HEAD_GUIDANCE_DESIGNATION = "HEAD_GUIDANCE_COUNSELOR"


@dataclass(frozen=True, slots=True)
class OrganizationalAccessScope:
    institution_wide: bool
    college_ids: tuple[UUID, ...] = ()


EMPTY_ORGANIZATIONAL_ACCESS_SCOPE = OrganizationalAccessScope(institution_wide=False)
INSTITUTION_WIDE_ORGANIZATIONAL_ACCESS_SCOPE = OrganizationalAccessScope(
    institution_wide=True
)


def _is_head_guidance(actor: User) -> bool:
    return (
        bool(getattr(actor, "pk", None))
        and actor.is_active
        and actor.role.code == "COUNSELOR"
        and actor.designations.filter(code=HEAD_GUIDANCE_DESIGNATION).exists()
    )


def _active_counselor_college_ids(counselor_id: UUID) -> tuple[UUID, ...]:
    return tuple(
        CounselorResponsibility.objects.filter(
            counselor_id=counselor_id,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
            college__is_active=True,
            college__campus__is_active=True,
        )
        .order_by("college_id")
        .values_list("college_id", flat=True)
    )


def resolve_organizational_access_scope(actor: User) -> OrganizationalAccessScope:
    """Resolve organizational operational scope only, without domain capability checks."""

    if not getattr(actor, "pk", None) or not actor.is_active:
        return EMPTY_ORGANIZATIONAL_ACCESS_SCOPE

    if actor.role.code == "COUNSELOR":
        if _is_head_guidance(actor):
            return INSTITUTION_WIDE_ORGANIZATIONAL_ACCESS_SCOPE
        return OrganizationalAccessScope(
            institution_wide=False,
            college_ids=_active_counselor_college_ids(actor.pk),
        )

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
            return EMPTY_ORGANIZATIONAL_ACCESS_SCOPE
        return resolve_organizational_access_scope(supervision.supervisor)

    return EMPTY_ORGANIZATIONAL_ACCESS_SCOPE
