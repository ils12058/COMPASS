"""Authenticated self-service API for in-app Notifications and optional-email preference."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict, Field

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .models import Notification
from .services import (
    DEFAULT_PAGE_SIZE,
    InvalidNotificationInput,
    NotificationError,
    NotificationNotFound,
    list_my_notifications,
    mark_my_notification_read,
    optional_email_enabled_for,
    unread_count_for,
    update_my_notification_preference,
)

router = Router(tags=["notifications"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class NotificationResponse(StrictSchema):
    id: UUID
    event_code: str
    policy: str
    title: str
    message: str
    target_type: str
    target_id: UUID | None
    created_at: datetime
    read_at: datetime | None
    is_read: bool


class NotificationPageResponse(StrictSchema):
    items: list[NotificationResponse]
    page: int
    page_size: int
    has_next: bool


class UnreadCountResponse(StrictSchema):
    unread_count: int


class NotificationPreferenceResponse(StrictSchema):
    optional_email_enabled: bool = Field(
        description=(
            "Controls only OPTIONAL_INFORMATIONAL email. Mandatory security and operational "
            "email is not disabled by this preference."
        )
    )


class NotificationPreferenceUpdateRequest(StrictSchema):
    optional_email_enabled: bool


def _raise(exc: NotificationError) -> NoReturn:
    if isinstance(exc, NotificationNotFound):
        raise APIError(404, "notification_not_found", str(exc)) from exc
    if isinstance(exc, InvalidNotificationInput):
        raise APIError(422, "invalid_notification_input", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Notification request could not be completed."
    ) from exc


def _view(item: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=item.pk,
        event_code=item.event_code,
        policy=item.policy,
        title=item.title,
        message=item.message,
        target_type=item.target_type,
        target_id=item.target_id,
        created_at=item.created_at,
        read_at=item.read_at,
        is_read=item.is_read,
    )


@router.get(
    "",
    response=response_with_errors(NotificationPageResponse, 401, 422),
    auth=session_auth,
    operation_id="notificationsListMine",
)
def notifications_list_mine(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    try:
        result = list_my_notifications(actor=request.auth_user, page=page, page_size=page_size)
    except NotificationError as exc:
        _raise(exc)
    return NotificationPageResponse(
        items=[_view(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.get(
    "/unread-count",
    response=response_with_errors(UnreadCountResponse, 401),
    auth=session_auth,
    operation_id="notificationsGetUnreadCount",
)
def notifications_get_unread_count(request):
    return UnreadCountResponse(unread_count=unread_count_for(actor=request.auth_user))


@router.patch(
    "/{notification_id}/read",
    response=response_with_errors(NotificationResponse, 401, 404),
    auth=session_auth,
    operation_id="notificationsMarkRead",
)
def notifications_mark_read(request, notification_id: UUID):
    try:
        item = mark_my_notification_read(
            actor=request.auth_user,
            notification_id=notification_id,
        )
    except NotificationError as exc:
        _raise(exc)
    return _view(item)


@router.get(
    "/preferences",
    response=response_with_errors(NotificationPreferenceResponse, 401),
    auth=session_auth,
    operation_id="notificationsGetPreferences",
)
def notifications_get_preferences(request):
    return NotificationPreferenceResponse(
        optional_email_enabled=optional_email_enabled_for(request.auth_user)
    )


@router.patch(
    "/preferences",
    response=response_with_errors(NotificationPreferenceResponse, 401),
    auth=session_auth,
    operation_id="notificationsUpdatePreferences",
)
def notifications_update_preferences(request, payload: NotificationPreferenceUpdateRequest):
    enabled = update_my_notification_preference(
        actor=request.auth_user,
        optional_email_enabled=payload.optional_email_enabled,
    )
    return NotificationPreferenceResponse(optional_email_enabled=enabled)
