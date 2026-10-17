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


class FollowUpQuery(StrictSchema):
    status: StatusValue | None = None
    student_id: UUID | None = None
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=50)


class FollowUpSummary(StrictSchema):
    id: UUID
    student_id: UUID
    student_name: str
    assigned_to_id: UUID
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
    created_at: datetime
    old_assignee_id: UUID | None
    new_assignee_id: UUID | None
    old_due_at: datetime | None
    new_due_at: datetime | None
    remarks: str | None


class FollowUpDetail(FollowUpSummary):
    description: str | None
    outcome: str | None
    source: SourceReference | None
    source_unavailable: bool
    events: list[FollowUpHistoryEvent]


class FollowUpPage(StrictSchema):
    items: list[FollowUpSummary]
    page: int
    page_size: int
    has_next: bool


def _context(request):
    return AuditContext.from_request(request, actor=request.auth_user)


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
        "source_unavailable": bool(item.source_id is not None and extra["source"] is None),
    }


@router.get(
    "",
    response=response_with_errors(FollowUpPage, 401, 403, 422, 503),
    operation_id="guidanceFollowupsList",
)
def guidance_followups_list(request, query: Query[FollowUpQuery]):
    _enabled()
    try:
        result = list_followups(actor=request.auth_user, **query.model_dump())
        return {
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
        return Status(201, _detail(request.auth_user, item))
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
def guidance_followups_update(request, followup_id: UUID, payload: FollowUpUpdate):
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
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/reassign",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsReassign",
)
def guidance_followups_reassign(request, followup_id: UUID, payload: FollowUpReassign):
    _write(request)
    try:
        item = reassign_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            assigned_to_id=payload.assigned_to_id,
            context=_context(request),
        )
        # Transfer of ownership means the old owner no longer has detail access.
        if item.assigned_to_id != request.auth_user.pk:
            return {
                **_summary(item),
                "description": None,
                "outcome": None,
                "source": None,
                "source_unavailable": bool(item.source_id),
                "events": [],
            }
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/activities",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsRecordActivity",
)
def guidance_followups_activity(request, followup_id: UUID, payload: FollowUpActivity):
    _write(request)
    try:
        item, _event = record_activity(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            remarks=payload.remarks,
            context=_context(request),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/complete",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsComplete",
)
def guidance_followups_complete(request, followup_id: UUID, payload: FollowUpComplete):
    _write(request)
    try:
        item = complete_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            outcome=payload.outcome,
            context=_context(request),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)


@router.post(
    "/{followup_id}/cancel",
    response=response_with_errors(FollowUpDetail, 401, 403, 404, 409, 422, 503),
    operation_id="guidanceFollowupsCancel",
)
def guidance_followups_cancel(request, followup_id: UUID, payload: FollowUpCancel):
    _write(request)
    try:
        item = cancel_followup(
            actor=request.auth_user,
            followup_id=followup_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
            context=_context(request),
        )
        return _detail(request.auth_user, item)
    except FollowUpError as exc:
        _raise(exc)
