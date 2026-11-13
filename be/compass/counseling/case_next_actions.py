"""Bounded next-action facts, authorized before pagination or protected title reads."""

from dataclasses import dataclass

from compass.guidance_followups import policy
from compass.guidance_followups.models import GuidanceFollowUp

PENDING_LIMIT = 20
RECENT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class CaseNextActions:
    items: tuple[GuidanceFollowUp, ...]
    next_action: GuidanceFollowUp | None
    has_more: bool
    available: bool
    can_add: bool


def next_actions(*, actor, case):
    available = actor.has_capability("guidance_followups.view")
    can_add = (
        available
        and case.status == "ACTIVE"
        and actor.has_capability("guidance_followups.manage")
        and actor.has_capability("counseling.manage_assigned")
    )
    if not available:
        return CaseNextActions((), None, False, False, False)
    query = policy.scope(
        actor,
        GuidanceFollowUp.objects.filter(case_id=case.pk).select_related("student", "assigned_to"),
        include_owned_delegated=True,
    )
    pending = list(query.filter(status="PENDING").order_by("due_at", "id")[: PENDING_LIMIT + 1])
    recent = list(
        query.filter(status__in=["COMPLETED", "CANCELLED"]).order_by("-updated_at", "id")[
            : RECENT_LIMIT + 1
        ]
    )
    return CaseNextActions(
        tuple(pending[:PENDING_LIMIT] + recent[:RECENT_LIMIT]),
        pending[0] if pending else None,
        len(pending) > PENDING_LIMIT or len(recent) > RECENT_LIMIT,
        True,
        can_add,
    )
