"""Strict, staff-only Follow-Up HTTP contract. All source policy is enforced server-side."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.conf import settings
from ninja import Header, Query, Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.step_up import require_recent_mfa_for_request
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint

from . import workspace
from .errors import (
    FollowUpConflict,
    FollowUpContentUnavailable,
    FollowUpError,
    FollowUpInvalid,
    FollowUpNotFound,
    FollowUpPermissionDenied,
)
from .services import (
    cancel_followup,
    complete_followup,
    create_followup,
    followup_detail,
    get_followup,
    list_followups,
    reassign_followup,
    record_activity,
    update_followup,
)

router = Router(tags=["guidance-followups"], auth=session_auth)
CREATE_ROUTE = "/api/v1/guidance-followups"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class SourceKind(StrEnum):
    COUNSELING_ENCOUNTER = "COUNSELING_ENCOUNTER"
    REFERRAL = "REFERRAL"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"


class Visibility(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    COUNSELOR_CONFIDENTIAL = "COUNSELOR_CONFIDENTIAL"


class Category(StrEnum):
    ADMINISTRATIVE = "ADMINISTRATIVE"
    STUDENT_CONTACT = "STUDENT_CONTACT"
    COUNSELING = "COUNSELING"
    REFERRAL_ACTION = "REFERRAL_ACTION"


class StatusValue(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FollowUpCreate(StrictSchema):
    student_id: UUID
    assigned_to_id: UUID
    category: Category
    due_at: datetime
    source_kind: SourceKind | None = None
    source_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    visibility: Visibility | None = None


class FollowUpUpdate(StrictSchema):
    expected_version: int = Field(ge=1)
    due_at: datetime | None = None
    category: Category | None = None
    description: str | None = Field(default=None, max_length=4000)


class FollowUpReassign(StrictSchema):
    expected_version: int = Field(ge=1)
    assigned_to_id: UUID


class FollowUpActivity(StrictSchema):
    expected_version: int = Field(ge=1)
    remarks: str = Field(min_length=1, max_length=4000)


class FollowUpComplete(StrictSchema):
    expected_version: int = Field(ge=1)
    outcome: str = Field(min_length=1, max_length=4000)


class FollowUpCancel(StrictSchema):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)


class DueWindow(StrEnum):
    OVERDUE = "OVERDUE"
    UPCOMING = "UPCOMING"


class FollowUpOrdering(StrEnum):
    EARLIEST_DUE = "EARLIEST_DUE"
    LATEST_DUE = "LATEST_DUE"


class FollowUpQuery(StrictSchema):
    status: StatusValue | None = None
    student_id: UUID | None = None
    assigned_to_id: UUID | None = None
    source_kind: SourceKind | None = None
    source_id: UUID | None = None
    due_window: DueWindow | None = None
    ordering: FollowUpOrdering | None = None
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=50)


class FollowUpSummary(StrictSchema):
    id: UUID
    student_id: UUID
    student_name: str
    assigned_to_id: UUID
    assigned_to_name: str
    category: Category
    visibility: Visibility
    due_at: datetime
    status: StatusValue
    overdue: bool
    version: int
    created_at: datetime
    updated_at: datetime


class SourceReference(StrictSchema):
    kind: SourceKind
    id: UUID


class FollowUpHistoryEvent(StrictSchema):
    id: UUID
    kind: str
    revision: int
    actor_id: UUID
    actor_name: str
    created_at: datetime
    old_assignee_id: UUID | None
    new_assignee_id: UUID | None
    old_due_at: datetime | None
    new_due_at: datetime | None
    remarks: str | None


class FollowUpDetail(FollowUpSummary):
    completed_at: datetime | None
    completed_by_name: str | None
    cancelled_at: datetime | None
    cancelled_by_name: str | None
    description: str | None
    outcome: str | None
    source: SourceReference | None
    source_unavailable: bool
    events: list[FollowUpHistoryEvent]
    events_has_next: bool


class FollowUpPage(StrictSchema):
    ordering: FollowUpOrdering
    items: list[FollowUpSummary]
    page: int
    page_size: int
    has_next: bool


def _context(request):
    return AuditContext.from_request(request, actor=request.auth_user)


def _strict_query(request, allowed):
    if set(request.GET) - set(allowed):
        raise APIError(422, "invalid_followup", "The requested filter is unsupported.")


def _enabled():
    if not settings.GUIDANCE_FOLLOWUPS_ENABLED:
        raise APIError(503, "followups_not_enabled", "Guidance Follow-Ups are not enabled.")


def _write(request):
    _enabled()
    require_recent_mfa_for_request(request)


def _raise(exc: FollowUpError) -> NoReturn:
    if isinstance(exc, FollowUpContentUnavailable):
        raise APIError(
            503, "followup_content_unavailable", "Protected Follow-Up content is unavailable."
        ) from exc
    if isinstance(exc, FollowUpPermissionDenied):
        raise APIError(
            403, "followup_access_denied", "Guidance Follow-Up access is required."
        ) from exc
    if isinstance(exc, FollowUpNotFound):
        raise APIError(404, "followup_not_found", "The requested record is unavailable.") from exc
    if isinstance(exc, FollowUpConflict):
        raise APIError(409, "followup_conflict", str(exc)) from exc
    if isinstance(exc, FollowUpInvalid):
        raise APIError(422, "invalid_followup", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The follow-up operation could not be completed."
    ) from exc


def _summary(item):
    from django.utils import timezone

    return {
        "id": item.pk,
        "student_id": item.student_id,
        "student_name": item.student.get_full_name(),
        "assigned_to_id": item.assigned_to_id,
        "assigned_to_name": item.assigned_to.get_full_name(),
        "category": item.category,
        "visibility": item.visibility,
        "due_at": item.due_at,
        "status": item.status,
        "overdue": item.status == "PENDING" and item.due_at < timezone.now(),
        "version": item.version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _detail(actor, item):
    extra = followup_detail(actor=actor, item=item)
    return {
        **_summary(item),
        **extra,
        "completed_at": item.completed_at,
        "completed_by_name": item.completed_by.get_full_name() if item.completed_by else None,
        "cancelled_at": item.cancelled_at,
        "cancelled_by_name": item.cancelled_by.get_full_name() if item.cancelled_by else None,
        "source_unavailable": bool(item.source_id is not None and extra["source"] is None),
    }


def _detail_or_receipt(actor, item):
    if item.assigned_to_id == actor.pk:
        return _detail(actor, item)
    return {
        **_summary(item),
        "description": None,
        "outcome": None,
        "source": None,
        "source_unavailable": bool(item.source_id),
        "events": [],
        "events_has_next": False,
        "completed_at": None,
        "completed_by_name": None,
        "cancelled_at": None,
        "cancelled_by_name": None,
    }


class StaffOption(StrictSchema):
    id: UUID
    display_name: str


class StaffOptionPage(StrictSchema):
    items: list[StaffOption]
    page: int
    page_size: int
    has_next: bool


class StudentOption(StaffOption):
    institutional_id: str | None


class StudentOptionPage(StrictSchema):
    items: list[StudentOption]
    page: int
    page_size: int
    has_next: bool


class SourceContext(StrictSchema):
    source_kind: SourceKind
    source_id: UUID
    student_id: UUID
    student_name: str
    category: Category
    visibility: Visibility
    can_create: bool


class CategoryCount(StrictSchema):
    category: Category
    count: int


class FollowUpReport(StrictSchema):
    pending: int
    completed: int
    cancelled: int
    overdue: int
    due_soon: int
    completed_in_period: int
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    horizon_days: int
    categories: list[CategoryCount]


@router.get(
    "/recoverable",
    response=response_with_errors(FollowUpPage, 401, 403, 422, 503),
    operation_id="guidanceFollowupsRecoverable",
)
def recoverable(request, page: int = 1, page_size: int = 20):
    from .recovery import list_recoverable

    _enabled()
    _strict_query(request, ["page", "page_size"])
    try:
        result = list_recoverable(actor=request.auth_user, page=page, page_size=page_size)
        return {
            **result,
            "items": [_summary(row) for row in result["items"]],
            "ordering": "EARLIEST_DUE",
        }
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "/eligible-students",
    response=response_with_errors(StudentOptionPage, 401, 403, 422, 503),
    operation_id="guidanceFollowupsEligibleStudents",
)
def eligible_students(request, search: str | None = None, page: int = 1, page_size: int = 20):
    from compass.operational_students import InvalidOperationalStudentQuery

    _enabled()
    _strict_query(request, ["search", "page", "page_size"])
    try:
        result = workspace.eligible_students(
            actor=request.auth_user, search=search, page=page, page_size=page_size
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "display_name": row.display_name,
                    "institutional_id": row.institutional_id,
                }
                for row in result.items
            ],
            "page": result.page,
            "page_size": result.page_size,
            "has_next": result.has_next,
        }
    except InvalidOperationalStudentQuery as exc:
        raise APIError(422, "invalid_followup", str(exc)) from exc
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "/eligible-assignees",
    response=response_with_errors(StaffOptionPage, 401, 403, 404, 422, 503),
    operation_id="guidanceFollowupsEligibleAssignees",
)
def eligible_assignees(
    request,
    student_id: UUID,
    category: Category,
    source_kind: SourceKind | None = None,
    source_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
):
    _enabled()
    _strict_query(
        request, ["student_id", "category", "source_kind", "source_id", "page", "page_size"]
    )
    try:
        result = workspace.eligible_assignees(
            actor=request.auth_user,
            student_id=student_id,
            category=category,
            source_kind=source_kind,
            source_id=source_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [{"id": row.pk, "display_name": row.get_full_name()} for row in result.items],
            "page": result.page,
            "page_size": result.page_size,
            "has_next": result.has_next,
        }
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "/context",
    response=response_with_errors(SourceContext, 401, 403, 404, 422, 503),
    operation_id="guidanceFollowupsGetContext",
)
def context(request, source_kind: SourceKind, source_id: UUID):
    _enabled()
    _strict_query(request, ["source_kind", "source_id"])
    try:
        return workspace.source_context(
            actor=request.auth_user, source_kind=source_kind, source_id=source_id
        )
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "/report",
    response=response_with_errors(FollowUpReport, 401, 403, 422, 503),
    operation_id="guidanceFollowupsReport",
)
def report(
    request,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    horizon_days: int = workspace.DUE_SOON_HORIZON_DAYS,
):
    _enabled()
    _strict_query(request, ["period_start", "period_end", "horizon_days"])
    try:
        return workspace.reporting(
            actor=request.auth_user,
            period_start=period_start,
            period_end=period_end,
            horizon_days=horizon_days,
        )
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "",
    response=response_with_errors(FollowUpPage, 401, 403, 422, 503),
    operation_id="guidanceFollowupsList",
)
def guidance_followups_list(request, query: Query[FollowUpQuery]):
    _enabled()
    if set(request.GET) - set(FollowUpQuery.model_fields):
        raise APIError(422, "invalid_followup", "The requested filter is unsupported.")
    try:
        result = list_followups(actor=request.auth_user, **query.model_dump())
        return {
            "ordering": query.ordering or FollowUpOrdering.EARLIEST_DUE,
            "items": [_summary(item) for item in result.items],
            "page": result.page,
            "page_size": result.page_size,
            "has_next": result.has_next,
        }
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503, success_status=201),
    operation_id="guidanceFollowupsCreate",
)
def guidance_followups_create(
    request,
    payload: FollowUpCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    fingerprint = request_fingerprint(
        method="POST",
        route=CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_followup(
            actor=request.auth_user,
            student_id=payload.student_id,
            assigned_to_id=payload.assigned_to_id,
            category=payload.category.value,
            due_at=payload.due_at,
            source_kind=payload.source_kind.value if payload.source_kind else None,
            source_id=payload.source_id,
            description=payload.description,
            visibility=payload.visibility.value if payload.visibility else None,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
        return Status(201, _detail_or_receipt(request.auth_user, item))
    except FollowUpError as exc:
        _raise(exc)


@router.get(
    "/{followup_id}",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 503),
    operation_id="guidanceFollowupsGet",
)
def guidance_followups_get(request, followup_id: UUID):
    _enabled()
    try:
        return _detail(
            request.auth_user, get_followup(actor=request.auth_user, followup_id=followup_id)
        )
    except FollowUpError as exc:
        _raise(exc)


@router.patch(
    "/{followup_id}",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsUpdate",
)
def guidance_followups_update(
    request,
    followup_id: UUID,
    payload: FollowUpUpdate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    try:
        if not (payload.model_fields_set - {"expected_version"}):
            raise FollowUpInvalid("Choose at least one field to update.")
        item = update_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            due_at=payload.due_at,
            category=payload.category.value if payload.category else None,
            description=payload.description,
            context=_context(request),
            mutation_key=idempotency_key,
            mutation_fingerprint=request_fingerprint(
                method=request.method,
                route=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/reassign",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsReassign",
)
def guidance_followups_reassign(
    request,
    followup_id: UUID,
    payload: FollowUpReassign,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    try:
        item = reassign_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            assigned_to_id=payload.assigned_to_id,
            context=_context(request),
            mutation_key=idempotency_key,
            mutation_fingerprint=request_fingerprint(
                method=request.method,
                route=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
        )
        return _detail_or_receipt(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/activities",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsRecordActivity",
)
def guidance_followups_activity(
    request,
    followup_id: UUID,
    payload: FollowUpActivity,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    try:
        item, _event = record_activity(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            remarks=payload.remarks,
            context=_context(request),
            mutation_key=idempotency_key,
            mutation_fingerprint=request_fingerprint(
                method=request.method,
                route=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/complete",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsComplete",
)
def guidance_followups_complete(
    request,
    followup_id: UUID,
    payload: FollowUpComplete,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    try:
        item = complete_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            outcome=payload.outcome,
            context=_context(request),
            mutation_key=idempotency_key,
            mutation_fingerprint=request_fingerprint(
                method=request.method,
                route=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/cancel",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsCancel",
)
def guidance_followups_cancel(
    request,
    followup_id: UUID,
    payload: FollowUpCancel,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _write(request)
    try:
        item = cancel_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
            context=_context(request),
            mutation_key=idempotency_key,
            mutation_fingerprint=request_fingerprint(
                method=request.method,
                route=request.path,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


class FollowUpHistoryPage(StrictSchema):
    items: list[FollowUpHistoryEvent]
    page: int
    page_size: int
    has_next: bool


@router.get(
    "/{followup_id}/history",
    response=response_with_errors(FollowUpHistoryPage, 401, 403, 404, 422, 503),
    operation_id="guidanceFollowupsHistory",
)
def history(request, followup_id: UUID, page: int = 1):
    _enabled()
    _strict_query(request, ["page"])
    try:
        item = get_followup(actor=request.auth_user, followup_id=followup_id)
        result = followup_detail(actor=request.auth_user, item=item, history_page=page)
        return {
            "items": result["events"],
            "page": page,
            "page_size": 20,
            "has_next": result["events_has_next"],
        }
    except FollowUpError as exc:
        _raise(exc)
