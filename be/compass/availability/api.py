"""Thin Django Ninja API for recurring and effective Availability."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.service_catalog.api import DeliveryMode

from .services import (
    DEFAULT_PROVIDER_PAGE_SIZE,
    AvailabilityConflict,
    AvailabilityError,
    AvailabilityNotApplicable,
    AvailabilityNotFound,
    InvalidAvailabilityInput,
    compute_base_availability,
    create_office_exception,
    create_provider_exception,
    list_availability_providers,
    list_office_exceptions,
    list_office_weekly,
    list_provider_exceptions,
    list_provider_weekly,
    remove_office_exception,
    remove_provider_exception,
    replace_office_weekly,
    replace_provider_weekly,
)

router = Router(tags=["availability"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class Weekday(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class AvailabilityModeScope(StrEnum):
    ALL = "ALL"
    IN_PERSON = "IN_PERSON"
    ONLINE = "ONLINE"


class WeeklyWindowRequest(StrictSchema):
    weekday: Weekday
    start_time: time
    end_time: time
    mode_scope: AvailabilityModeScope


class WeeklyReplacementRequest(StrictSchema):
    windows: list[WeeklyWindowRequest] = Field(default_factory=list)


class WeeklyWindowResponse(StrictSchema):
    id: UUID
    weekday: Weekday
    start_time: time
    end_time: time
    mode_scope: AvailabilityModeScope


class OfficeWeeklyResponse(StrictSchema):
    windows: list[WeeklyWindowResponse]


class ProviderWeeklyResponse(StrictSchema):
    provider_id: UUID
    windows: list[WeeklyWindowResponse]


class AvailabilityProviderSummary(StrictSchema):
    id: UUID
    full_name: str
    email: str
    role: str
    is_active: bool


class AvailabilityProviderListResponse(StrictSchema):
    items: list[AvailabilityProviderSummary]
    page: int
    page_size: int
    has_next: bool


class ExceptionCreateRequest(StrictSchema):
    starts_at: datetime
    ends_at: datetime
    mode_scope: AvailabilityModeScope
    reason: str = ""


class ExceptionResponse(StrictSchema):
    id: UUID
    starts_at: datetime
    ends_at: datetime
    mode_scope: AvailabilityModeScope
    reason: str
    created_at: datetime
    created_by: UUID | None


class OfficeExceptionListResponse(StrictSchema):
    items: list[ExceptionResponse]


class ProviderExceptionListResponse(StrictSchema):
    provider_id: UUID
    items: list[ExceptionResponse]


class RemovalResponse(StrictSchema):
    removed: bool


class EffectiveWindowResponse(StrictSchema):
    starts_at: datetime
    ends_at: datetime


class EffectiveAvailabilityResponse(StrictSchema):
    provider_id: UUID
    service_id: UUID
    delivery_mode: DeliveryMode
    timezone: str
    start_date: date
    end_date: date
    windows: list[EffectiveWindowResponse]


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _require_self_read(request) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR":
        raise APIError(403, "permission_denied", "Counselor self-service is required.")
    _require(request, "availability.view")


def _require_self_mutation(request) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR":
        raise APIError(403, "permission_denied", "Counselor self-service is required.")
    if not (
        user.has_capability("availability.manage_self")
        or user.has_capability("availability.manage")
    ):
        raise APIError(
            403,
            "permission_denied",
            "The availability.manage_self or availability.manage capability is required.",
        )


def _raise(exc: AvailabilityError) -> NoReturn:
    if isinstance(exc, AvailabilityNotFound):
        raise APIError(404, "availability_resource_not_found", str(exc)) from exc
    if isinstance(exc, InvalidAvailabilityInput):
        raise APIError(422, "invalid_availability_request", str(exc)) from exc
    if isinstance(exc, AvailabilityNotApplicable):
        raise APIError(409, "availability_not_applicable", str(exc)) from exc
    if isinstance(exc, AvailabilityConflict):
        raise APIError(409, "availability_conflict", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Availability operation could not be completed."
    ) from exc


def _provider_summary(user) -> dict[str, object]:
    return {
        "id": user.pk,
        "full_name": user.get_full_name(),
        "email": user.email,
        "role": user.role.code,
        "is_active": user.is_active,
    }


def _window(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "weekday": item.weekday,
        "start_time": item.start_time,
        "end_time": item.end_time,
        "mode_scope": item.mode_scope,
    }


def _exception(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "mode_scope": item.mode_scope,
        "reason": item.reason,
        "created_at": item.created_at,
        "created_by": item.created_by_id,
    }


def _window_values(payload: WeeklyReplacementRequest) -> list[dict[str, object]]:
    return [
        {
            "weekday": item.weekday.value,
            "start_time": item.start_time,
            "end_time": item.end_time,
            "mode_scope": item.mode_scope.value,
        }
        for item in payload.windows
    ]


@router.get(
    "/office/weekly",
    response=response_with_errors(OfficeWeeklyResponse, 401, 403),
    auth=session_auth,
    operation_id="availabilityGetOfficeWeekly",
)
def office_weekly_get(request):
    _require(request, "availability.manage")
    return {"windows": [_window(item) for item in list_office_weekly()]}


@router.put(
    "/office/weekly",
    response=response_with_errors(OfficeWeeklyResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="availabilityReplaceOfficeWeekly",
)
def office_weekly_replace(request, payload: WeeklyReplacementRequest):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        rows = replace_office_weekly(windows=_window_values(payload), context=_context(request))
    except AvailabilityError as exc:
        _raise(exc)
    return {"windows": [_window(item) for item in rows]}


@router.get(
    "/office/exceptions",
    response=response_with_errors(OfficeExceptionListResponse, 401, 403),
    auth=session_auth,
    operation_id="availabilityListOfficeExceptions",
)
def office_exceptions_list(request):
    _require(request, "availability.manage")
    return {"items": [_exception(item) for item in list_office_exceptions()]}


@router.post(
    "/office/exceptions",
    response=response_with_errors(ExceptionResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="availabilityCreateOfficeException",
)
def office_exception_create(request, payload: ExceptionCreateRequest):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        item = create_office_exception(
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            mode_scope=payload.mode_scope.value,
            reason=payload.reason,
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    return Status(201, _exception(item))


@router.delete(
    "/office/exceptions/{exception_id}",
    response=response_with_errors(RemovalResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="availabilityRemoveOfficeException",
)
def office_exception_remove(request, exception_id: UUID):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        removed = remove_office_exception(exception_id=exception_id, context=_context(request))
    except AvailabilityError as exc:
        _raise(exc)
    if not removed:
        raise APIError(404, "availability_resource_not_found", "The exception was not found.")
    return {"removed": True}


@router.get(
    "/me/weekly",
    response=response_with_errors(ProviderWeeklyResponse, 401, 403),
    auth=session_auth,
    operation_id="availabilityGetMyWeekly",
)
def my_weekly_get(request):
    _require_self_read(request)
    rows = list_provider_weekly(request.auth_user.pk)
    return {"provider_id": request.auth_user.pk, "windows": [_window(item) for item in rows]}


@router.put(
    "/me/weekly",
    response=response_with_errors(ProviderWeeklyResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="availabilityReplaceMyWeekly",
)
def my_weekly_replace(request, payload: WeeklyReplacementRequest):
    _require_self_mutation(request)
    try:
        rows = replace_provider_weekly(
            provider_id=request.auth_user.pk,
            windows=_window_values(payload),
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    return {"provider_id": request.auth_user.pk, "windows": [_window(item) for item in rows]}


@router.get(
    "/me/exceptions",
    response=response_with_errors(ProviderExceptionListResponse, 401, 403),
    auth=session_auth,
    operation_id="availabilityListMyExceptions",
)
def my_exceptions_list(request):
    _require_self_read(request)
    rows = list_provider_exceptions(request.auth_user.pk)
    return {"provider_id": request.auth_user.pk, "items": [_exception(item) for item in rows]}


@router.post(
    "/me/exceptions",
    response=response_with_errors(ExceptionResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="availabilityCreateMyException",
)
def my_exception_create(request, payload: ExceptionCreateRequest):
    _require_self_mutation(request)
    try:
        item = create_provider_exception(
            provider_id=request.auth_user.pk,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            mode_scope=payload.mode_scope.value,
            reason=payload.reason,
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    return Status(201, _exception(item))


@router.delete(
    "/me/exceptions/{exception_id}",
    response=response_with_errors(RemovalResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="availabilityRemoveMyException",
)
def my_exception_remove(request, exception_id: UUID):
    _require_self_mutation(request)
    try:
        removed = remove_provider_exception(
            exception_id=exception_id,
            provider_id=request.auth_user.pk,
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    if not removed:
        raise APIError(404, "availability_resource_not_found", "The exception was not found.")
    return {"removed": True}


@router.get(
    "/providers",
    response=response_with_errors(AvailabilityProviderListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="availabilityListProviders",
)
def providers_list(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PROVIDER_PAGE_SIZE,
):
    _require(request, "availability.manage")
    try:
        result = list_availability_providers(
            search=search,
            page=page,
            page_size=page_size,
        )
    except AvailabilityError as exc:
        _raise(exc)
    return {
        "items": [_provider_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/providers/{provider_id}/weekly",
    response=response_with_errors(ProviderWeeklyResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="availabilityGetProviderWeekly",
)
def provider_weekly_get(request, provider_id: UUID):
    _require(request, "availability.manage")
    try:
        rows = list_provider_weekly(provider_id)
    except AvailabilityError as exc:
        _raise(exc)
    return {"provider_id": provider_id, "windows": [_window(item) for item in rows]}


@router.put(
    "/providers/{provider_id}/weekly",
    response=response_with_errors(ProviderWeeklyResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="availabilityReplaceProviderWeekly",
)
def provider_weekly_replace(request, provider_id: UUID, payload: WeeklyReplacementRequest):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        rows = replace_provider_weekly(
            provider_id=provider_id,
            windows=_window_values(payload),
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    return {"provider_id": provider_id, "windows": [_window(item) for item in rows]}


@router.get(
    "/providers/{provider_id}/exceptions",
    response=response_with_errors(ProviderExceptionListResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="availabilityListProviderExceptions",
)
def provider_exceptions_list(request, provider_id: UUID):
    _require(request, "availability.manage")
    try:
        rows = list_provider_exceptions(provider_id)
    except AvailabilityError as exc:
        _raise(exc)
    return {"provider_id": provider_id, "items": [_exception(item) for item in rows]}


@router.post(
    "/providers/{provider_id}/exceptions",
    response=response_with_errors(ExceptionResponse, 401, 403, 404, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="availabilityCreateProviderException",
)
def provider_exception_create(request, provider_id: UUID, payload: ExceptionCreateRequest):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        item = create_provider_exception(
            provider_id=provider_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            mode_scope=payload.mode_scope.value,
            reason=payload.reason,
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    return Status(201, _exception(item))


@router.delete(
    "/providers/{provider_id}/exceptions/{exception_id}",
    response=response_with_errors(RemovalResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="availabilityRemoveProviderException",
)
def provider_exception_remove(request, provider_id: UUID, exception_id: UUID):
    _require(request, "availability.manage", recent_mfa=True)
    try:
        removed = remove_provider_exception(
            exception_id=exception_id,
            provider_id=provider_id,
            context=_context(request),
        )
    except AvailabilityError as exc:
        _raise(exc)
    if not removed:
        raise APIError(404, "availability_resource_not_found", "The exception was not found.")
    return {"removed": True}


@router.get(
    "/providers/{provider_id}/effective",
    response=response_with_errors(EffectiveAvailabilityResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="availabilityGetProviderEffective",
)
def provider_effective(
    request,
    provider_id: UUID,
    service_id: UUID,
    delivery_mode: DeliveryMode,
    start_date: date,
    end_date: date,
):
    _require(request, "availability.view")
    try:
        result = compute_base_availability(
            provider_id=provider_id,
            service_id=service_id,
            delivery_mode=delivery_mode.value,
            start_date=start_date,
            end_date=end_date,
        )
    except AvailabilityError as exc:
        _raise(exc)
    return {
        "provider_id": result.provider_id,
        "service_id": result.service_id,
        "delivery_mode": result.delivery_mode,
        "timezone": result.timezone_name,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "windows": [
            {"starts_at": item.starts_at, "ends_at": item.ends_at} for item in result.windows
        ],
    }
