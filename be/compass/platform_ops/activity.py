"""Curated technical runtime activity projection over the shared Audit Trail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import Q

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


class TechnicalActivityPaginationError(ValueError):
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


def _validate_pagination(*, page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1 or page > MAX_PAGE_NUMBER:
        raise TechnicalActivityPaginationError(
            f"page must be an integer between 1 and {MAX_PAGE_NUMBER}"
        )
    if type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise TechnicalActivityPaginationError(
            f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}"
        )
    return page, page_size


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
) -> TechnicalActivityPage:
    page, page_size = _validate_pagination(page=page, page_size=page_size)
    offset = (page - 1) * page_size
    records = list(
        AuditEvent.objects.select_related("actor_user")
        .filter(_selection_filter())
        .order_by("-occurred_at", "-id")[offset : offset + page_size + 1]
    )
    has_next = len(records) > page_size

    items: list[TechnicalActivityItem] = []
    for event in records[:page_size]:
        presenter = TECHNICAL_ACTIVITY_PRESENTERS.get(event.action)
        if presenter is None:
            continue
        item = presenter.present(event)
        if item is not None:
            items.append(item)

    return TechnicalActivityPage(
        items=tuple(items),
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_NUMBER",
    "MAX_PAGE_SIZE",
    "TECHNICAL_ACTIVITY_PRESENTERS",
    "TechnicalActivityItem",
    "TechnicalActivityPage",
    "TechnicalActivityPaginationError",
    "list_technical_activity",
]
