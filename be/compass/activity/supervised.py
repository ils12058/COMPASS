"""Operational-only activity under the authenticated actor's current direct supervision."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import Exists, OuterRef, Q

from compass.audit import actions
from compass.audit.models import AuditActorType, AuditEvent, AuditOutcome
from compass.organization.models import StaffSupervision

from .retrieval import (
    DEFAULT_PAGE_SIZE,
    ActivityCriteria,
    ActivityRetrievalError,
    bounded_candidates,
    matches_text,
    page_items,
    validate_page,
)

CAPABILITY = "activity.supervised_staff.view"

# Audited against actual GSS-capable service/API call sites. Appointment creation is self-Student.
# Referral actions target referralaction; all other targets below are the owning resource UUID.
SUPERVISED_PRESENTERS = {
    actions.APPOINTMENT_CANCELLED: (
        "Appointment cancelled",
        "An appointment was cancelled.",
        "appointments.appointment",
    ),
    actions.APPOINTMENT_RESCHEDULED: (
        "Appointment rescheduled",
        "An appointment was rescheduled.",
        "appointments.appointment",
    ),
    actions.APPOINTMENT_REASSIGNED: (
        "Appointment reassigned",
        "An appointment was reassigned.",
        "appointments.appointment",
    ),
    actions.APPOINTMENT_COMPLETED: (
        "Appointment completed",
        "An appointment was marked completed.",
        "appointments.appointment",
    ),
    actions.APPOINTMENT_NO_SHOW: (
        "Appointment marked no-show",
        "An appointment was marked no-show.",
        "appointments.appointment",
    ),
    actions.REFERRAL_CREATED: (
        "Referral recorded",
        "A referral was recorded.",
        "referrals.referral",
    ),
    actions.REFERRAL_ACTION_RECORDED: (
        "Referral action recorded",
        "An operational referral action was recorded.",
        "referrals.referralaction",
    ),
    actions.REFERRAL_STATUS_UPDATED: (
        "Referral status updated",
        "A referral status note was updated.",
        "referrals.referral",
    ),
    actions.REFERRAL_VOIDED: ("Referral voided", "A referral was voided.", "referrals.referral"),
    actions.CALL_SLIP_CREATED: (
        "Call Slip issued",
        "A Call Slip was issued.",
        "callslips.callslip",
    ),
    actions.CALL_SLIP_INTERVIEW_ENDED: (
        "Call Slip interview ended",
        "Interview completion was recorded for a Call Slip.",
        "callslips.callslip",
    ),
    actions.CALL_SLIP_VOIDED: ("Call Slip voided", "A Call Slip was voided.", "callslips.callslip"),
    actions.ANNOUNCEMENT_CREATED: (
        "Announcement created",
        "An announcement draft was created.",
        "announcements.announcement",
    ),
    actions.ANNOUNCEMENT_UPDATED: (
        "Announcement updated",
        "An announcement was updated.",
        "announcements.announcement",
    ),
    actions.ANNOUNCEMENT_PUBLISHED: (
        "Announcement published",
        "An announcement was published.",
        "announcements.announcement",
    ),
    actions.ANNOUNCEMENT_ARCHIVED: (
        "Announcement archived",
        "An announcement was archived.",
        "announcements.announcement",
    ),
    actions.RESOURCE_CREATED: (
        "Resource created",
        "A resource draft was created.",
        "resources.resource",
    ),
    actions.RESOURCE_UPDATED: ("Resource updated", "A resource was updated.", "resources.resource"),
    actions.RESOURCE_FILE_ATTACHED: (
        "Resource file attached",
        "A PDF was attached to a resource.",
        "resources.resource",
    ),
    actions.RESOURCE_FILE_REMOVED: (
        "Resource file removed",
        "A draft resource file was removed.",
        "resources.resource",
    ),
    actions.RESOURCE_PUBLISHED: (
        "Resource published",
        "A resource was published.",
        "resources.resource",
    ),
    actions.RESOURCE_ARCHIVED: (
        "Resource archived",
        "A resource was archived.",
        "resources.resource",
    ),
}
SupervisedActivityType = StrEnum(
    "SupervisedActivityType",
    {action.replace(".", "_").upper(): action for action in SUPERVISED_PRESENTERS},
)


class SupervisedActivityPermissionDenied(PermissionError):
    pass


def _require(actor):
    if not actor.is_active or not actor.has_capability(CAPABILITY):
        raise SupervisedActivityPermissionDenied(f"The {CAPABILITY} capability is required.")


def current_supervisions(actor):
    return StaffSupervision.objects.filter(
        supervisor_id=actor.pk,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
        staff__is_active=True,
        staff__role__code="GUIDANCE_SERVICES_STAFF",
    )


def list_supervised_staff(*, actor, page=1, page_size=DEFAULT_PAGE_SIZE):
    _require(actor)
    validate_page(page, page_size)
    offset = (page - 1) * page_size
    rows = list(
        current_supervisions(actor)
        .select_related("staff")
        .only(
            "staff_id",
            "staff__id",
            "staff__first_name",
            "staff__middle_name",
            "staff__last_name",
            "staff__suffix",
        )
        .order_by("staff__first_name", "staff__last_name", "staff_id")[
            offset : offset + page_size + 1
        ]
    )
    return {
        "items": [
            {
                "id": row.staff_id,
                "display_name": row.staff.get_full_name().strip() or "Guidance Services Staff",
            }
            for row in rows[:page_size]
        ],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }


@dataclass(frozen=True, slots=True)
class SupervisedActivityItem:
    id: UUID
    type: SupervisedActivityType
    title: str
    description: str
    occurred_at: datetime
    staff: dict[str, object]


def supervised_queryset(*, actor, criteria, staff_id=None, event_type=None):
    _require(actor)
    if event_type is not None:
        try:
            event_type = SupervisedActivityType(event_type)
        except ValueError as exc:
            raise ActivityRetrievalError("Unsupported supervised activity type.") from exc
    selection = Q(pk__in=[])
    for action, (_, _, target) in SUPERVISED_PRESENTERS.items():
        if event_type is None or action == event_type:
            selection |= Q(action=action, target_type=target)
    # The relationship and its time boundary are checked in the event SELECT, not a stale ID list.
    scope = current_supervisions(actor).filter(
        staff_id=OuterRef("actor_user_id"), updated_at__lte=OuterRef("occurred_at")
    )
    queryset = (
        AuditEvent.objects.select_related("actor_user")
        .only(
            "id",
            "action",
            "target_id",
            "occurred_at",
            "actor_user_id",
            "actor_user__id",
            "actor_user__first_name",
            "actor_user__middle_name",
            "actor_user__last_name",
            "actor_user__suffix",
        )
        .filter(
            selection, Exists(scope), actor_type=AuditActorType.USER, outcome=AuditOutcome.SUCCESS
        )
    )
    if staff_id is not None:
        queryset = queryset.filter(actor_user_id=staff_id)
    return criteria.apply_dates(queryset).order_by("-occurred_at", "-id")


def supervised_items(queryset, criteria):
    for event in bounded_candidates(queryset):
        try:
            UUID(str(event.target_id))
        except (ValueError, TypeError):
            continue
        title, description, _ = SUPERVISED_PRESENTERS[event.action]
        name = event.actor_user.get_full_name().strip() or "Guidance Services Staff"
        if not matches_text(criteria.search, (event.action, title, description, name)):
            continue
        yield SupervisedActivityItem(
            event.pk,
            SupervisedActivityType(event.action),
            title,
            description,
            event.occurred_at,
            {"id": event.actor_user_id, "display_name": name},
        )


def list_supervised_activity(
    *,
    actor,
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
    search=None,
    staff_id=None,
    event_type=None,
    date_from=None,
    date_to=None,
):
    criteria = ActivityCriteria.build(search=search, date_from=date_from, date_to=date_to)
    queryset = supervised_queryset(
        actor=actor, criteria=criteria, staff_id=staff_id, event_type=event_type
    )
    items, has_next = page_items(
        supervised_items(queryset, criteria), page=page, page_size=page_size
    )
    return {"items": items, "page": page, "page_size": page_size, "has_next": has_next}
