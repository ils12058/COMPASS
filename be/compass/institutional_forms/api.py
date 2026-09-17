"""Narrow API for QMS-issued institutional form revision metadata."""

from __future__ import annotations

from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.institutional_forms.models import FormRevisionStatus
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    InstitutionalFormError,
    InstitutionalFormNotFound,
    InvalidInstitutionalFormInput,
    activate_form_revision,
    deactivate_form_revision,
    list_form_families,
    list_form_revisions,
    register_form_revision,
)

router = Router(tags=["institutional-forms"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class FormRevisionStatusValue(StrEnum):
    ACTIVE = FormRevisionStatus.ACTIVE
    INACTIVE = FormRevisionStatus.INACTIVE


class FormRevisionResponse(StrictSchema):
    id: UUID
    family_key: str
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int
    status: FormRevisionStatusValue


class FormFamilyResponse(StrictSchema):
    id: UUID
    key: str
    title: str


class FormFamilyListResponse(StrictSchema):
    items: list[FormFamilyResponse]


class FormRevisionListResponse(StrictSchema):
    items: list[FormRevisionResponse]


class FormRevisionRegisterRequest(StrictSchema):
    official_code: str
    official_revision: str
    internal_schema_version: int


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


def _raise(exc: InstitutionalFormError) -> NoReturn:
    if isinstance(exc, InstitutionalFormNotFound):
        raise APIError(404, "institutional_form_not_found", str(exc)) from exc
    if isinstance(exc, InstitutionalFormConflict):
        raise APIError(409, "institutional_form_conflict", str(exc)) from exc
    if isinstance(exc, InvalidInstitutionalFormInput):
        raise APIError(422, "invalid_institutional_form_request", str(exc)) from exc
    raise APIError(
        500,
        "internal_error",
        "The institutional form operation could not be completed.",
    ) from exc


def _family(item) -> dict[str, object]:
    return {"id": item.pk, "key": item.key, "title": item.title}


def _revision(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "family_key": item.family.key,
        "official_code": item.official_code,
        "official_revision": item.official_revision,
        "internal_schema_version": item.internal_schema_version,
        "status": item.status,
    }


@router.get(
    "",
    response=response_with_errors(FormFamilyListResponse, 401, 403),
    auth=session_auth,
    operation_id="institutionalFormsList",
)
def institutional_forms_list(request):
    _require(request, "institutional_forms.view")
    return {"items": [_family(item) for item in list_form_families()]}


@router.get(
    "/{family_key}/revisions",
    response=response_with_errors(FormRevisionListResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="institutionalFormRevisionsList",
)
def institutional_form_revisions_list(request, family_key: str):
    _require(request, "institutional_forms.view")
    try:
        items = list_form_revisions(family_key)
    except InstitutionalFormError as exc:
        _raise(exc)
    return {"items": [_revision(item) for item in items]}


@router.post(
    "/{family_key}/revisions",
    response=response_with_errors(
        FormRevisionResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="institutionalFormRevisionsRegister",
)
def institutional_form_revisions_register(
    request,
    family_key: str,
    payload: FormRevisionRegisterRequest,
):
    _require(request, "institutional_forms.manage", recent_mfa=True)
    try:
        item = register_form_revision(
            family_key=family_key,
            official_code=payload.official_code,
            official_revision=payload.official_revision,
            internal_schema_version=payload.internal_schema_version,
            context=_context(request),
        )
    except InstitutionalFormError as exc:
        _raise(exc)
    return Status(201, _revision(item))


@router.post(
    "/revisions/{revision_id}/activate",
    response=response_with_errors(FormRevisionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="institutionalFormRevisionsActivate",
)
def institutional_form_revision_activate(request, revision_id: UUID):
    _require(request, "institutional_forms.manage", recent_mfa=True)
    try:
        return _revision(activate_form_revision(revision_id=revision_id, context=_context(request)))
    except InstitutionalFormError as exc:
        _raise(exc)


@router.post(
    "/revisions/{revision_id}/deactivate",
    response=response_with_errors(FormRevisionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="institutionalFormRevisionsDeactivate",
)
def institutional_form_revision_deactivate(request, revision_id: UUID):
    _require(request, "institutional_forms.manage", recent_mfa=True)
    try:
        return _revision(
            deactivate_form_revision(revision_id=revision_id, context=_context(request))
        )
    except InstitutionalFormError as exc:
        _raise(exc)
