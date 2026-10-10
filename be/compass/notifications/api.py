"""Authenticated self-service API for in-app Notifications and optional-email preference."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from django.conf import settings
from ninja import Router, Schema
from pydantic import ConfigDict, Field

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .models import Notification
from .policy import NotificationPolicy, NotificationTargetType
from .push import (
    InvalidPushSubscription,
    register_subscription,
    remove_subscription,
    subscription_enabled,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    InvalidNotificationInput,
    NotificationError,
    NotificationNotFound,
    list_my_notifications,
    mark_all_my_notifications_read,
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
    policy: NotificationPolicy
    title: str
    message: str
    target_type: NotificationTargetType | None
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


class MarkAllReadResponse(StrictSchema):
    updated_count: int


class NotificationPreferenceResponse(StrictSchema):
    optional_email_enabled: bool = Field(
        description=(
            "Controls only OPTIONAL_INFORMATIONAL email. Mandatory security and operational "
            "email is not disabled by this preference."
        )
    )


class NotificationPreferenceUpdateRequest(StrictSchema):
    optional_email_enabled: bool


class PushConfigResponse(StrictSchema):
    enabled: bool
    public_key: str


class PushEndpointRequest(StrictSchema):
    endpoint: str = Field(max_length=2048)


class PushKeysRequest(StrictSchema):
    p256dh: str = Field(max_length=180)
    auth: str = Field(max_length=180)


class PushRegisterRequest(PushEndpointRequest):
    keys: PushKeysRequest


class PushStatusResponse(StrictSchema):
    enabled_on_this_device: bool


def _require_push_enabled() -> None:
    if not settings.WEB_PUSH_ENABLED:
        raise APIError(503, "push_unavailable", "Browser notifications are unavailable.")


def _push_invalid(exc: InvalidPushSubscription) -> NoReturn:
    raise APIError(422, "invalid_push_subscription", str(exc)) from exc


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
        target_type=item.target_type or None,
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
    "/read-all",
    response=response_with_errors(MarkAllReadResponse, 401),
    auth=session_auth,
    operation_id="notificationsMarkAllRead",
)
def notifications_mark_all_read(request):
    return MarkAllReadResponse(
        updated_count=mark_all_my_notifications_read(actor=request.auth_user)
    )


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


@router.get(
    "/push/config",
    response=response_with_errors(PushConfigResponse, 401),
    auth=session_auth,
    operation_id="notificationsGetPushConfig",
)
def notifications_get_push_config(request):
    return PushConfigResponse(
        enabled=settings.WEB_PUSH_ENABLED,
        public_key=settings.WEB_PUSH_PUBLIC_KEY if settings.WEB_PUSH_ENABLED else "",
    )


@router.post(
    "/push/status",
    response=response_with_errors(PushStatusResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="notificationsGetPushStatus",
)
def notifications_get_push_status(request, payload: PushEndpointRequest):
    _require_push_enabled()
    try:
        enabled = subscription_enabled(
            user=request.auth_user, session=request.auth_session, endpoint=payload.endpoint
        )
    except InvalidPushSubscription as exc:
        _push_invalid(exc)
    return PushStatusResponse(enabled_on_this_device=enabled)


@router.post(
    "/push/subscription",
    response=response_with_errors(PushStatusResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="notificationsRegisterPushSubscription",
)
def notifications_register_push_subscription(request, payload: PushRegisterRequest):
    _require_push_enabled()
    try:
        register_subscription(
            user=request.auth_user,
            session=request.auth_session,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
    except InvalidPushSubscription as exc:
        _push_invalid(exc)
    return PushStatusResponse(enabled_on_this_device=True)


@router.delete(
    "/push/subscription",
    response=response_with_errors(PushStatusResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="notificationsRemovePushSubscription",
)
def notifications_remove_push_subscription(request, payload: PushEndpointRequest):
    _require_push_enabled()
    try:
        remove_subscription(user=request.auth_user, endpoint=payload.endpoint)
    except InvalidPushSubscription as exc:
        _push_invalid(exc)
    return PushStatusResponse(enabled_on_this_device=False)
