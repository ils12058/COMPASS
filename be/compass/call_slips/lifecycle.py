"""Call Slip-owned lifecycle projections consumed by adjacent domains."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from .models import CallSlip, CallSlipLifecycleState


class ReferralCallSlipDependency(StrEnum):
    NONE = "NONE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


def referral_call_slip_dependency(
    *,
    referral_id: UUID,
    for_update: bool = False,
) -> ReferralCallSlipDependency:
    """Return the current Referral dependency using Call Slip lifecycle semantics.

    VOIDED rows remain historical provenance and do not block Referral voiding.
    The database permits at most one non-voided Call Slip for a Referral, while
    this scan remains deterministic across all linked history.
    """

    queryset = CallSlip.objects.filter(referral_id=referral_id).order_by("pk")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))

    dependency = ReferralCallSlipDependency.NONE
    for call_slip in queryset:
        state = call_slip.lifecycle_state
        if state == CallSlipLifecycleState.COMPLETED:
            return ReferralCallSlipDependency.COMPLETED
        if state == CallSlipLifecycleState.ACTIVE:
            dependency = ReferralCallSlipDependency.ACTIVE
    return dependency


__all__ = [
    "ReferralCallSlipDependency",
    "referral_call_slip_dependency",
]
