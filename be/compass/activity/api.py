"""Thin authenticated routes for the self-only activity projections."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from ninja import Router, Schema

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .projections import (
    DEFAULT_PAGE_SIZE,
    ActivityPaginationError,
    get_my_activity,
    get_security_activity,
)
from .retrieval import ActivityRetrievalError
from .supervised import (
    SupervisedActivityPermissionDenied,
    SupervisedActivityType,
    list_supervised_activity,
    list_supervised_staff,
)

router = Router(tags=["activity"])


class ActivityItemResponse(Schema):
    id: UUID
    type: str
    title: str
    description: str
    occurred_at: datetime


class ActivityPageResponse(Schema):
    items: list[ActivityItemResponse]
    page: int
    page_size: int
    has_next: bool


def _invalid_pagination(exc: ActivityPaginationError) -> None:
    raise APIError(422, "invalid_pagination", str(exc)) from exc


@router.get(
    "/activity",
    response=response_with_errors(ActivityPageResponse, 401, 422),
    auth=session_auth,
    operation_id="meListActivity",
    summary="View my activity",
)
def my_activity(request, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
    try:
        result = get_my_activity(
            user=request.auth_user,
            page=page,
            page_size=page_size,
        )
    except ActivityPaginationError as exc:
        _invalid_pagination(exc)
    return result.as_dict()


@router.get(
    "/security-activity",
    response=response_with_errors(ActivityPageResponse, 401, 422),
    auth=session_auth,
    operation_id="meListSecurityActivity",
    summary="View my security activity",
)
def security_activity(request, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
    try:
        result = get_security_activity(
            user=request.auth_user,
            page=page,
            page_size=page_size,
        )
    except ActivityPaginationError as exc:
        _invalid_pagination(exc)
    return result.as_dict()


__all__ = ["ActivityItemResponse", "ActivityPageResponse", "router"]


class SupervisedStaffSummary(Schema):
    id: UUID
    display_name: str


class SupervisedStaffPageResponse(Schema):
    items: list[SupervisedStaffSummary]
    page: int
    page_size: int
    has_next: bool


class SupervisedActivityItemResponse(Schema):
    id: UUID
    type: SupervisedActivityType
    title: str
    description: str
    occurred_at: datetime
    staff: SupervisedStaffSummary


class SupervisedActivityPageResponse(Schema):
    items: list[SupervisedActivityItemResponse]
    page: int
    page_size: int
    has_next: bool


def _supervised_error(exc):
    if isinstance(exc, SupervisedActivityPermissionDenied):
        raise APIError(403, "permission_denied", str(exc)) from exc
    raise APIError(422, "invalid_supervised_activity_request", str(exc)) from exc


@router.get(
    "/supervised-staff",
    auth=session_auth,
    response=response_with_errors(SupervisedStaffPageResponse, 401, 403, 422),
    operation_id="meListSupervisedStaff",
    summary="List my directly supervised staff",
)
def supervised_staff(request, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
    try:
        return list_supervised_staff(actor=request.auth_user, page=page, page_size=page_size)
    except (SupervisedActivityPermissionDenied, ActivityRetrievalError) as exc:
        _supervised_error(exc)


@router.get(
    "/supervised-staff-activity",
    auth=session_auth,
    response=response_with_errors(SupervisedActivityPageResponse, 401, 403, 422),
    operation_id="meListSupervisedStaffActivity",
    summary="View current supervised staff operational activity",
)
def supervised_staff_activity(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
    staff_id: UUID | None = None,
    event_type: SupervisedActivityType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    try:
        return list_supervised_activity(
            actor=request.auth_user,
            page=page,
            page_size=page_size,
            search=search,
            staff_id=staff_id,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
        )
    except (SupervisedActivityPermissionDenied, ActivityRetrievalError) as exc:
        _supervised_error(exc)
