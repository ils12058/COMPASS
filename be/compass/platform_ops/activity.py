"""Curated technical runtime activity projection over the shared Audit Trail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import Q

from compass.activity.retrieval import (
    ActivityCriteria,
    ActivityRetrievalError,
    bounded_candidates,
    matches_text,
    page_items,
)
from compass.audit.actions import (
    NOTIFICATION_EMAIL_RETRY_REQUESTED,
    PLATFORM_MAINTENANCE_DISABLED,
    PLATFORM_MAINTENANCE_ENABLED,
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED,
    PLATFORM_MAINTENANCE_SCHEDULED,
)
from compass.audit.models import AuditActorType, AuditEvent, AuditOutcome

from .email_operations import EMAIL_DELIVERY_TARGET_TYPE
from .services import MAINTENANCE_TARGET_TYPE

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000


class TechnicalActivityPaginationError(ActivityRetrievalError):
    """The requested technical activity page is outside supported bounds."""


@dataclass(frozen=True, slots=True)
class TechnicalActivityItem:
    id: UUID
    type: str
    title: str
    description: str
    occurred_at: datetime
    actor_type: str
    actor_display_name: str | None


@dataclass(frozen=True, slots=True)
class TechnicalActivityPage:
    items: tuple[TechnicalActivityItem, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class TechnicalActivityPresenter:
    item_type: str
    title: str
    description: str
    target_type: str
    target_id: str | None = None
    include_target_id_in_description: bool = False

    def present(self, event: AuditEvent) -> TechnicalActivityItem | None:
        if event.target_type != self.target_type:
            return None
        if self.target_id is not None and event.target_id != self.target_id:
            return None

        description = self.description
        if self.include_target_id_in_description:
            try:
                UUID(str(event.target_id))
            except (TypeError, ValueError):
                return None
            description = f"{description} {event.target_id}."

        actor_display_name = None
        if event.actor_type == AuditActorType.USER and event.actor_user is not None:
            actor_display_name = event.actor_user.get_full_name().strip() or "COMPASS operator"

        return TechnicalActivityItem(
            id=event.pk,
            type=self.item_type,
            title=self.title,
            description=description,
            occurred_at=event.occurred_at,
            actor_type=event.actor_type,
            actor_display_name=actor_display_name,
        )


TECHNICAL_ACTIVITY_PRESENTERS = {
    PLATFORM_MAINTENANCE_ENABLED: TechnicalActivityPresenter(
        item_type="platform.maintenance.enabled",
        title="Maintenance Mode enabled",
        description="Manual Maintenance Mode was enabled.",
        target_type=MAINTENANCE_TARGET_TYPE,
        target_id="1",
    ),
    PLATFORM_MAINTENANCE_DISABLED: TechnicalActivityPresenter(
        item_type="platform.maintenance.disabled",
        title="Maintenance Mode disabled",
        description="Manual Maintenance Mode was disabled.",
        target_type=MAINTENANCE_TARGET_TYPE,
        target_id="1",
    ),
    PLATFORM_MAINTENANCE_SCHEDULED: TechnicalActivityPresenter(
        item_type="platform.maintenance.scheduled",
        title="Maintenance scheduled",
        description="A Maintenance Mode window was scheduled.",
        target_type=MAINTENANCE_TARGET_TYPE,
        target_id="1",
    ),
    PLATFORM_MAINTENANCE_SCHEDULE_CANCELLED: TechnicalActivityPresenter(
        item_type="platform.maintenance.schedule_cancelled",
        title="Maintenance schedule cancelled",
        description="A Maintenance Mode schedule was cancelled.",
        target_type=MAINTENANCE_TARGET_TYPE,
        target_id="1",
    ),
    NOTIFICATION_EMAIL_RETRY_REQUESTED: TechnicalActivityPresenter(
        item_type="notification.email.retry_requested",
        title="Email delivery retry requested",
        description="Manual retry requested for email delivery",
        target_type=EMAIL_DELIVERY_TARGET_TYPE,
        include_target_id_in_description=True,
    ),
}


TechnicalActivityType = StrEnum(
    "TechnicalActivityType",
    {action.replace(".", "_").upper(): action for action in TECHNICAL_ACTIVITY_PRESENTERS},
)


def _selection_filter() -> Q:
    selection: Q | None = None
    for action, presenter in TECHNICAL_ACTIVITY_PRESENTERS.items():
        branch = Q(
            action=action,
            outcome=AuditOutcome.SUCCESS,
            actor_type=AuditActorType.USER,
            actor_user__isnull=False,
            target_type=presenter.target_type,
        )
        if presenter.target_id is not None:
            branch &= Q(target_id=presenter.target_id)
        selection = branch if selection is None else selection | branch
    return selection if selection is not None else Q(pk__in=[])


def list_technical_activity(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
    operator: str | None = None,
    event_type: TechnicalActivityType | str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> TechnicalActivityPage:
    try:
        criteria = ActivityCriteria.build(
            search=search, actor=operator, date_from=date_from, date_to=date_to
        )
        if event_type is not None:
            event_type = TechnicalActivityType(event_type)
        queryset = (
            AuditEvent.objects.select_related("actor_user")
            .only(
                "id",
                "action",
                "target_type",
                "target_id",
                "occurred_at",
                "actor_type",
                "actor_user_id",
                "actor_user__id",
                "actor_user__first_name",
                "actor_user__middle_name",
                "actor_user__last_name",
                "actor_user__suffix",
            )
            .filter(_selection_filter())
        )
        if event_type is not None:
            queryset = queryset.filter(action=event_type)
        queryset = criteria.apply_dates(queryset).order_by("-occurred_at", "-id")

        def matching_items():
            for event in bounded_candidates(queryset):
                item = TECHNICAL_ACTIVITY_PRESENTERS[event.action].present(event)
                if item is None:
                    continue
                if not matches_text(criteria.actor, (item.actor_display_name,)):
                    continue
                if matches_text(
                    criteria.search,
                    (item.type, item.title, item.description, item.actor_display_name),
                ):
                    yield item

        items, has_next = page_items(matching_items(), page=page, page_size=page_size)
    except ValueError as exc:
        raise TechnicalActivityPaginationError(str(exc)) from exc
    return TechnicalActivityPage(items=items, page=page, page_size=page_size, has_next=has_next)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_NUMBER",
    "MAX_PAGE_SIZE",
    "TECHNICAL_ACTIVITY_PRESENTERS",
    "TechnicalActivityItem",
    "TechnicalActivityType",
    "TechnicalActivityPage",
    "TechnicalActivityPaginationError",
    "list_technical_activity",
]
