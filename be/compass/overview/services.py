"""Read-only composition of exact, domain-owned Portal Overview counts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.services import (
    count_upcoming_managed_appointments,
    count_upcoming_self_appointments,
)
from compass.call_slips.services import count_active_call_slips, count_my_active_call_slips
from compass.good_moral.services import count_my_requested_requests, count_requested_requests
from compass.platform_ops.email_operations import get_email_delivery_summary
from compass.privacy_governance.services import (
    count_active_incidents,
    count_open_reviews,
    privacy_overview_access_allowed,
)
from compass.routine_interviews.services import (
    count_my_draft_intakes,
    count_pending_assigned_evaluations,
)


class OverviewAccessDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StudentOverviewSummary:
    upcoming_appointments_count: int | None
    routine_intake_draft_count: int | None
    good_moral_requested_count: int | None
    active_call_slip_count: int | None


@dataclass(frozen=True, slots=True)
class GuidanceOverviewSummary:
    upcoming_self_appointments_count: int | None
    upcoming_managed_appointments_count: int | None
    routine_evaluation_pending_count: int | None
    good_moral_requested_count: int | None
    active_call_slip_count: int | None


@dataclass(frozen=True, slots=True)
class PlatformOverviewSummary:
    email_pending_count: int | None
    email_due_pending_count: int | None
    email_failed_count: int | None
    email_sent_today_count: int | None


@dataclass(frozen=True, slots=True)
class PrivacyOverviewSummary:
    open_review_count: int | None
    active_incident_count: int | None


@dataclass(frozen=True, slots=True)
class OverviewSummary:
    generated_at: datetime
    student: StudentOverviewSummary | None = None
    guidance: GuidanceOverviewSummary | None = None
    platform: PlatformOverviewSummary | None = None
    privacy: PrivacyOverviewSummary | None = None


def build_overview_summary(actor: User, *, now: datetime | None = None) -> OverviewSummary:
    if not getattr(actor, "pk", None) or not actor.is_active:
        raise OverviewAccessDenied("Active authenticated Portal access is required.")

    current = now or timezone.now()
    role = actor.role.code
    student: StudentOverviewSummary | None = None
    guidance: GuidanceOverviewSummary | None = None
    platform: PlatformOverviewSummary | None = None
    privacy: PrivacyOverviewSummary | None = None

    if role == "STUDENT":
        student = StudentOverviewSummary(
            upcoming_appointments_count=count_upcoming_self_appointments(
                actor=actor,
                now=current,
            ),
            routine_intake_draft_count=count_my_draft_intakes(actor),
            good_moral_requested_count=count_my_requested_requests(actor),
            active_call_slip_count=count_my_active_call_slips(actor),
        )
    elif role == "COUNSELOR":
        guidance = GuidanceOverviewSummary(
            upcoming_self_appointments_count=count_upcoming_self_appointments(
                actor=actor,
                now=current,
            ),
            upcoming_managed_appointments_count=None,
            routine_evaluation_pending_count=count_pending_assigned_evaluations(actor),
            good_moral_requested_count=count_requested_requests(actor),
            active_call_slip_count=count_active_call_slips(actor),
        )
    elif role == "GUIDANCE_SERVICES_STAFF":
        guidance = GuidanceOverviewSummary(
            upcoming_self_appointments_count=None,
            upcoming_managed_appointments_count=count_upcoming_managed_appointments(
                actor=actor,
                now=current,
            ),
            routine_evaluation_pending_count=None,
            good_moral_requested_count=None,
            active_call_slip_count=count_active_call_slips(actor),
        )
    elif role == "IT_ADMIN" and actor.has_capability("platform_operations.view"):
        email = get_email_delivery_summary(now=current)
        platform = PlatformOverviewSummary(
            email_pending_count=email.pending_count,
            email_due_pending_count=email.due_pending_count,
            email_failed_count=email.failed_count,
            email_sent_today_count=email.sent_today,
        )
    elif role == "INSTITUTIONAL_OFFICER" and privacy_overview_access_allowed(actor):
        privacy = PrivacyOverviewSummary(
            open_review_count=count_open_reviews(actor),
            active_incident_count=count_active_incidents(actor),
        )

    return OverviewSummary(
        generated_at=current,
        student=student,
        guidance=guidance,
        platform=platform,
        privacy=privacy,
    )
