"""Narrow operational API for institution-wide Academic Year configuration."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.organization.academic_years import (
    AcademicYearConflict,
    AcademicYearError,
    AcademicYearNotFound,
    InvalidAcademicYearInput,
    create_academic_year,
    list_academic_years,
    set_current_academic_year,
)

router = Router(tags=["academic-years"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AcademicYearResponse(StrictSchema):
    id: UUID
    label: str
    is_current: bool


class AcademicYearListResponse(StrictSchema):
    items: list[AcademicYearResponse]


class AcademicYearCreateRequest(StrictSchema):
    label: str


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


def _raise(exc: AcademicYearError) -> NoReturn:
    if isinstance(exc, AcademicYearNotFound):
        raise APIError(404, "academic_year_not_found", str(exc)) from exc
    if isinstance(exc, AcademicYearConflict):
        raise APIError(409, "academic_year_conflict", str(exc)) from exc
    if isinstance(exc, InvalidAcademicYearInput):
        raise APIError(422, "invalid_academic_year_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Academic Year operation could not be completed."
    ) from exc


def _serialize(item) -> dict[str, object]:
    return {"id": item.pk, "label": item.label, "is_current": item.is_current}


@router.get(
    "",
    response=response_with_errors(AcademicYearListResponse, 401, 403),
    auth=session_auth,
    operation_id="academicYearsList",
)
def academic_years_list(request):
    _require(request, "academic_years.view")
    return {"items": [_serialize(item) for item in list_academic_years()]}


@router.post(
    "",
    response=response_with_errors(AcademicYearResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="academicYearsCreate",
)
def academic_years_create(request, payload: AcademicYearCreateRequest):
    _require(request, "academic_years.manage", recent_mfa=True)
    try:
        item = create_academic_year(label=payload.label, context=_context(request))
    except AcademicYearError as exc:
        _raise(exc)
    return Status(201, _serialize(item))


@router.post(
    "/{academic_year_id}/set-current",
    response=response_with_errors(AcademicYearResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="academicYearsSetCurrent",
)
def academic_years_set_current(request, academic_year_id: UUID):
    _require(request, "academic_years.manage", recent_mfa=True)
    try:
        item = set_current_academic_year(
            academic_year_id=academic_year_id,
            context=_context(request),
        )
    except AcademicYearError as exc:
        _raise(exc)
    return _serialize(item)
