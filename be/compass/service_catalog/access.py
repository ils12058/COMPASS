"""Resource authorization for fixed-date Appointment slot management."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from django.db.models import QuerySet

from compass.accounts.models import User
from compass.organization.models import StaffSupervision

SLOT_STAFF_ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


def current_slot_staff(actor: User | None, *, lock_supervision: bool = False) -> User | None:
    """Reload current staff identity and capability, including current GSS supervision."""

    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        return None
    users = User.objects.select_related("role").filter(pk=actor_id, is_active=True)
    if lock_supervision:
        users = users.select_for_update(of=("self",))
    current = users.first()
    if (
        current is None
        or current.role.code not in SLOT_STAFF_ROLES
        or not current.has_capability("appointments.manage")
    ):
        return None
    if (
        current.role.code == "GUIDANCE_SERVICES_STAFF"
        and supervised_counselor(current, lock=lock_supervision) is None
    ):
        return None
    return current


def supervised_counselor(staff: User | None, *, lock: bool = False) -> User | None:
    """Resolve only the current direct, active Counselor supervisor for one GSS account."""

    staff_id = getattr(staff, "pk", None)
    if not staff_id or not getattr(staff, "is_active", False):
        return None
    if getattr(getattr(staff, "role", None), "code", None) != "GUIDANCE_SERVICES_STAFF":
        return None
    queryset = StaffSupervision.objects.filter(
        staff_id=staff_id,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
    ).order_by("pk")
    supervision = queryset.first()
    if supervision is None:
        return None
    supervisors = User.objects.select_related("role").filter(
        pk=supervision.supervisor_id,
        is_active=True,
        role__code="COUNSELOR",
    )
    if lock:
        supervisors = supervisors.select_for_update(of=("self",))
    supervisor = supervisors.first()
    if supervisor is None or not supervisor.has_capability("appointments.manage"):
        return None
    if lock:
        # Lock user rows before the supervision row. Counselor-side authorization also locks
        # the Counselor before checking supervision, so reversing this order here can deadlock.
        supervision = (
            StaffSupervision.objects.select_for_update(of=("self",))
            .filter(pk=supervision.pk, staff_id=staff_id, supervisor_id=supervisor.pk)
            .first()
        )
        if supervision is None:
            return None
    return supervisor


def slot_provider_scope(actor: User | None, *, lock_supervision: bool = False) -> tuple[UUID, ...]:
    """Return provider IDs the current actor may manage, without Head designation overrides."""

    current = current_slot_staff(actor, lock_supervision=lock_supervision)
    if current is None:
        return ()
    if current.role.code == "COUNSELOR":
        return (current.pk,)
    supervisor = supervised_counselor(current, lock=lock_supervision)
    return (supervisor.pk,) if supervisor is not None else ()


def can_manage_slot_provider(
    actor: User | None, provider_id: UUID, *, lock_supervision: bool = False
) -> bool:
    return provider_id in slot_provider_scope(actor, lock_supervision=lock_supervision)


def scope_fixed_slots(queryset: QuerySet, actor: User | None) -> QuerySet:
    provider_ids: Iterable[UUID] = slot_provider_scope(actor)
    if not provider_ids:
        return queryset.none()
    return queryset.filter(provider_id__in=provider_ids)
