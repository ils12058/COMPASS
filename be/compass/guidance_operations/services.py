"""Composition only: each source owns its population, authority and SQL aggregates."""

from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.services import (
    count_upcoming_managed_appointments,
    count_upcoming_self_appointments,
)
from compass.call_slips.services import count_active_call_slips
from compass.call_slips.work import due_call_slip_summary
from compass.good_moral.work import issuance_summary, preparation_summary
from compass.guidance_messages.work import reply_needed_summary
from compass.routine_interviews.work import pending_evaluation_summary

from .schemas import (
    DueMetric,
    GuidanceOperationsBacklog,
    GuidanceOperationsResponse,
    GuidanceOperationsSchedule,
    WaitingMetric,
)


class GuidanceOperationsAccessDenied(PermissionError):
    pass


def _waiting(summary):
    return None if summary is None else WaitingMetric.model_validate(summary, from_attributes=True)


def get_guidance_operations(*, actor, now=None):
    actor = (
        User.objects.select_related("role")
        .filter(pk=getattr(actor, "pk", None), is_active=True)
        .first()
    )
    if actor is None or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}:
        raise GuidanceOperationsAccessDenied("An active Guidance staff account is required.")
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise ValueError("Guidance operations requires an aware server timestamp.")
    due = due_call_slip_summary(actor=actor, now=current)
    # Expected ineligibility is None. Unexpected failures propagate; partial facts mislead.
    return GuidanceOperationsResponse(
        generated_at=current,
        backlog=GuidanceOperationsBacklog(
            guidance_messages=_waiting(reply_needed_summary(actor=actor)),
            routine_evaluations=_waiting(pending_evaluation_summary(actor=actor)),
            good_moral_preparation=_waiting(preparation_summary(actor=actor)),
            good_moral_issuance=_waiting(issuance_summary(actor=actor)),
            call_slips_due=None
            if due is None
            else DueMetric.model_validate(due, from_attributes=True),
        ),
        schedule=GuidanceOperationsSchedule(
            upcoming_self_appointments_count=(
                count_upcoming_self_appointments(actor=actor, now=current)
                if actor.role.code == "COUNSELOR"
                else None
            ),
            upcoming_managed_appointments_count=(
                count_upcoming_managed_appointments(actor=actor, now=current)
                if actor.role.code == "GUIDANCE_SERVICES_STAFF"
                else None
            ),
            active_call_slips_count=count_active_call_slips(actor),
        ),
    )
