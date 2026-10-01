"""Read-only API for synchronized institutional controlled-form metadata."""

from __future__ import annotations

from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.institutional_forms.canonical import get_canonical_form_family
from compass.institutional_forms.models import FormRevisionStatus
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    InstitutionalFormError,
    InstitutionalFormNotFound,
    is_supported_form_revision,
    list_form_families,
    list_form_revisions,
)

router = Router(tags=["institutional-forms"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class FormRevisionStatusValue(StrEnum):
    ACTIVE = FormRevisionStatus.ACTIVE
    INACTIVE = FormRevisionStatus.INACTIVE


class FormFamilyConfigurationState(StrEnum):
    READY = "READY"
    REVISION_NOT_REQUIRED = "REVISION_NOT_REQUIRED"
    MISSING_REQUIRED_REVISION = "MISSING_REQUIRED_REVISION"
    ACTIVE_UNSUPPORTED = "ACTIVE_UNSUPPORTED"


class FormRevisionResponse(StrictSchema):
    id: UUID
    family_key: str
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int
    status: FormRevisionStatusValue
    supported: bool


class FormFamilyResponse(StrictSchema):
    id: UUID
    key: str
    title: str
    revision_required: bool
    configuration_state: FormFamilyConfigurationState


class FormFamilyListResponse(StrictSchema):
    items: list[FormFamilyResponse]


class FormRevisionListResponse(StrictSchema):
    items: list[FormRevisionResponse]


def _require(request, capability: str) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _raise(exc: InstitutionalFormError) -> NoReturn:
    if isinstance(exc, InstitutionalFormNotFound):
        raise APIError(404, "institutional_form_not_found", str(exc)) from exc
    if isinstance(exc, InstitutionalFormConflict):
        raise APIError(409, "institutional_form_conflict", str(exc)) from exc
    raise APIError(
        500,
        "internal_error",
        "The institutional form operation could not be completed.",
    ) from exc


def _family(item) -> dict[str, object]:
    canonical = get_canonical_form_family(item.key)
    # list_form_families only returns code-owned families.
    assert canonical is not None
    active = next(
        (
            revision
            for revision in item.revisions.all()
            if revision.status == FormRevisionStatus.ACTIVE
        ),
        None,
    )
    if active is not None:
        state = (
            FormFamilyConfigurationState.READY
            if is_supported_form_revision(active)
            else FormFamilyConfigurationState.ACTIVE_UNSUPPORTED
        )
    elif canonical.revision_required:
        state = FormFamilyConfigurationState.MISSING_REQUIRED_REVISION
    else:
        state = FormFamilyConfigurationState.REVISION_NOT_REQUIRED
    return {
        "id": item.pk,
        "key": item.key,
        "title": item.title,
        "revision_required": canonical.revision_required,
        "configuration_state": state,
    }


def _revision(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "family_key": item.family.key,
        "official_code": item.official_code,
        "official_revision": item.official_revision,
        "internal_schema_version": item.internal_schema_version,
        "status": item.status,
        "supported": is_supported_form_revision(item),
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
    operation_id="institutionalFormsRevisionsList",
)
def institutional_form_revisions_list(request, family_key: str):
    _require(request, "institutional_forms.view")
    try:
        items = list_form_revisions(family_key)
    except InstitutionalFormError as exc:
        _raise(exc)
    return {"items": [_revision(item) for item in items]}
