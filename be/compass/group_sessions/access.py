"""Resource-specific staff access for Group Sessions and participant records."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

from compass.accounts.models import User
from compass.organization.models import StaffSupervision

GROUP_SESSION_STAFF_ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


@dataclass(frozen=True, slots=True)
class GroupSessionAccess:
    can_view: bool = False
    can_manage: bool = False
    can_access_participants: bool = False
    can_record_attendance: bool = False
    can_export_roster: bool = False


def current_group_session_staff(actor: User | None, *, lock_supervision: bool = False) -> User | None:
    """Reload the actor, effective capability, and current GSS supervision relationship."""

    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        return None
    users = User.objects.select_related("role").filter(pk=actor_id, is_active=True)
    if lock_supervision:
        users = users.select_for_update(of=("self",))
    current = users.first()
    if (
        current is None
        or current.role.code not in GROUP_SESSION_STAFF_ROLES
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
    """Return the current active Counselor supervisor, if that account retains event authority."""

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


def _counselor_supervises_session_organizer(
    actor: User, session, *, lock_supervision: bool = False
) -> bool:
    if actor.role.code != "COUNSELOR":
        return False
    queryset = StaffSupervision.objects.filter(
        staff_id=session.organizer_id,
        staff__is_active=True,
        staff__role__code="GUIDANCE_SERVICES_STAFF",
        supervisor_id=actor.pk,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
    )
    if lock_supervision:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.exists()


def group_session_access(
    actor: User | None, session, *, lock_supervision: bool = False
) -> GroupSessionAccess:
    """Resolve event permissions independently from general eligibility and facilitator status."""

    current = current_group_session_staff(actor, lock_supervision=lock_supervision)
    if current is None:
        return GroupSessionAccess()

    manages = session.organizer_id == current.pk or _counselor_supervises_session_organizer(
        current, session, lock_supervision=lock_supervision
    )
    facilitates = (
        current.role.code == "COUNSELOR"
        and session.facilitators.filter(counselor_id=current.pk).exists()
    )
    can_access_participants = manages or facilitates
    return GroupSessionAccess(
        can_view=can_access_participants,
        can_manage=manages,
        can_access_participants=can_access_participants,
        can_record_attendance=can_access_participants,
        can_export_roster=manages,
    )


def require_group_session_access(
    *, actor: User, session, permission: str, lock_supervision: bool = False
) -> GroupSessionAccess:
    """Fail closed with a non-enumerating error for an out-of-scope resource."""

    access = group_session_access(actor, session, lock_supervision=lock_supervision)
    if not getattr(access, permission, False):
        raise ValidationError("Group session not found.")
    return access


def scope_group_sessions(queryset: QuerySet, actor: User | None, *, permission: str) -> QuerySet:
    """Filter a staff collection before serialization or aggregation."""

    current = current_group_session_staff(actor)
    if current is None:
        return queryset.none()

    if current.role.code == "GUIDANCE_SERVICES_STAFF":
        allowed = Q(organizer_id=current.pk)
    else:
        allowed = Q(organizer_id=current.pk) | Q(
            organizer__role__code="GUIDANCE_SERVICES_STAFF",
            organizer__is_active=True,
            organizer__organization_staff_supervision__supervisor_id=current.pk,
        )

    if permission in {"view", "participants"} and current.role.code == "COUNSELOR":
        allowed |= Q(facilitators__counselor_id=current.pk)
    elif permission not in {"view", "participants", "manage"}:
        raise ValueError("Unknown Group Session collection permission.")

    return queryset.filter(allowed).distinct()
