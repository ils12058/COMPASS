"""Django Ninja API for scoped Guidance Referral intake and source actions."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Header, Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint

from .models import ReferralActionType
from .services import (
    DEFAULT_PAGE_SIZE,
    InvalidReferralInput,
    ReferralActionConflict,
    ReferralConfigurationConflict,
    ReferralCreationConflict,
    ReferralError,
    ReferralNotFound,
    ReferralNotPermitted,
    ReferralReferenceConflict,
    create_referral,
    get_referral,
    list_referrals,
    record_action,
    update_status_note,
)

router = Router(tags=["referrals"])
CREATE_ROUTE = "/api/v1/referrals"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ReferralActionTypeValue(StrEnum):
    CALL_PARENT_GUARDIAN = ReferralActionType.CALL_PARENT_GUARDIAN
    SEND_PARENT_NOTIFICATION_LETTER = ReferralActionType.SEND_PARENT_NOTIFICATION_LETTER
    SEND_CALL_SLIP_INTERVIEW_PERMIT = ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT


class ReferralCreateRequest(StrictSchema):
    student_id: UUID
    course_year_block: str
    reason: str
    referrer_name: str
    referred_on: date
    received_at: datetime | None = None


class ReferralStatusUpdateRequest(StrictSchema):
    status_note: str


class ReferralActionCreateRequest(StrictSchema):
    action_type: ReferralActionTypeValue
    occurred_at: datetime
    remarks: str = ""


class ReferralPersonSummary(StrictSchema):
    id: UUID
    display_name: str


class ReferralFormRevisionSummary(StrictSchema):
    id: UUID
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class ReferralActionResponse(StrictSchema):
    id: UUID
    action_type: ReferralActionTypeValue
    occurred_at: datetime
    remarks: str
    created_at: datetime


class ReferralSummaryResponse(StrictSchema):
    id: UUID
    reference_code: str
    student: ReferralPersonSummary
    student_name_snapshot: str
    course_year_block_snapshot: str
    referred_on: date
    received_at: datetime | None
    status_note: str
    created_at: datetime


class ReferralDetailResponse(ReferralSummaryResponse):
    reason: str
    referrer_name: str
    form_revision: ReferralFormRevisionSummary
    actions: list[ReferralActionResponse]
    updated_at: datetime


class ReferralPageResponse(StrictSchema):
    items: list[ReferralSummaryResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not user.has_capability(capability)
    ):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _raise(exc: ReferralError) -> NoReturn:
    if isinstance(exc, ReferralNotFound):
        raise APIError(404, "referral_not_found", str(exc)) from exc
    if isinstance(exc, ReferralNotPermitted):
        raise APIError(403, "referral_not_permitted", str(exc)) from exc
    if isinstance(exc, InvalidReferralInput):
        raise APIError(422, "invalid_referral_request", str(exc)) from exc
    if isinstance(
        exc,
        (
            ReferralConfigurationConflict,
            ReferralReferenceConflict,
            ReferralCreationConflict,
            ReferralActionConflict,
        ),
    ):
        raise APIError(409, "referral_conflict", str(exc)) from exc
    raise APIError(500, "internal_error", "The Referral operation could not be completed.") from exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _revision(revision) -> dict[str, object]:
    return {
        "id": revision.pk,
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
        "internal_schema_version": revision.internal_schema_version,
    }


def _action(action) -> dict[str, object]:
    return {
        "id": action.pk,
        "action_type": action.action_type,
        "occurred_at": action.occurred_at,
        "remarks": action.remarks,
        "created_at": action.created_at,
    }


def _summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "student": _person(item.student),
        "student_name_snapshot": item.student_name_snapshot,
        "course_year_block_snapshot": item.course_year_block_snapshot,
        "referred_on": item.referred_on,
        "received_at": item.received_at,
        "status_note": item.status_note,
        "created_at": item.created_at,
    }


def _detail(item) -> dict[str, object]:
    return {
        **_summary(item),
        "reason": item.reason,
        "referrer_name": item.referrer_name,
        "form_revision": _revision(item.form_revision),
        "actions": [_action(action) for action in item.actions.all()],
        "updated_at": item.updated_at,
    }


@router.post(
    "",
    response=response_with_errors(
        ReferralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="referralsCreate",
)
def referrals_create(
    request,
    payload: ReferralCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require(request, "referrals.manage")
    fingerprint = request_fingerprint(
        method="POST",
        route=CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_referral(
            actor=request.auth_user,
            student_id=payload.student_id,
            course_year_block=payload.course_year_block,
            reason=payload.reason,
            referrer_name=payload.referrer_name,
            referred_on=payload.referred_on,
            received_at=payload.received_at,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return Status(201, _detail(item))


@router.get(
    "",
    response=response_with_errors(ReferralPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="referralsList",
)
def referrals_list(
    request,
    search: str | None = None,
    student_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "referrals.view")
    try:
        result = list_referrals(
            actor=request.auth_user,
            search=search,
            student_id=student_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except ReferralError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{referral_id}",
    response=response_with_errors(ReferralDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="referralsGet",
)
def referrals_get(request, referral_id: UUID):
    _require(request, "referrals.view")
    try:
        item = get_referral(actor=request.auth_user, referral_id=referral_id)
    except ReferralError as exc:
        _raise(exc)
    return _detail(item)


@router.patch(
    "/{referral_id}/status",
    response=response_with_errors(ReferralDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="referralsUpdateStatus",
)
def referrals_update_status(
    request,
    referral_id: UUID,
    payload: ReferralStatusUpdateRequest,
):
    _require(request, "referrals.manage")
    try:
        item = update_status_note(
            actor=request.auth_user,
            referral_id=referral_id,
            status_note=payload.status_note,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/{referral_id}/actions",
    response=response_with_errors(
        ReferralActionResponse,
        401,
        403,
        404,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="referralsRecordAction",
)
def referrals_record_action(
    request,
    referral_id: UUID,
    payload: ReferralActionCreateRequest,
):
    _require(request, "referrals.manage")
    try:
        action = record_action(
            actor=request.auth_user,
            referral_id=referral_id,
            action_type=payload.action_type.value,
            occurred_at=payload.occurred_at,
            remarks=payload.remarks,
            context=_context(request),
        )
    except ReferralError as exc:
        _raise(exc)
    return Status(201, _action(action))
