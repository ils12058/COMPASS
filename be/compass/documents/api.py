"""Head Guidance management API for institutional document branding facts."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .services import (
    DocumentBrandingConfigurationError,
    DocumentBrandingError,
    InvalidDocumentBrandingInput,
    get_branding_profile,
    update_branding_profile,
)

router = Router(tags=["document-branding"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class DocumentBrandingProfileResponse(StrictSchema):
    id: UUID
    key: str
    country_line: str
    institution_name: str
    institution_short_name: str
    former_institution_name: str | None
    institution_address: str | None
    institution_website_url: str | None
    institution_contact_email: str | None
    institution_social_url: str | None
    office_parent_unit_name: str | None
    office_name: str
    office_email: str | None
    office_phone: str | None
    office_location: str | None
    created_at: datetime
    updated_at: datetime


class DocumentBrandingUpdateRequest(StrictSchema):
    country_line: str | None = None
    institution_name: str | None = None
    institution_short_name: str | None = None
    former_institution_name: str | None = None
    institution_address: str | None = None
    institution_website_url: str | None = None
    institution_contact_email: str | None = None
    institution_social_url: str | None = None
    office_parent_unit_name: str | None = None
    office_name: str | None = None
    office_email: str | None = None
    office_phone: str | None = None
    office_location: str | None = None


def _serialize(profile) -> dict[str, object]:
    return {
        "id": profile.pk,
        "key": profile.key,
        "country_line": profile.country_line,
        "institution_name": profile.institution_name,
        "institution_short_name": profile.institution_short_name,
        "former_institution_name": profile.former_institution_name,
        "institution_address": profile.institution_address,
        "institution_website_url": profile.institution_website_url,
        "institution_contact_email": profile.institution_contact_email,
        "institution_social_url": profile.institution_social_url,
        "office_parent_unit_name": profile.office_parent_unit_name,
        "office_name": profile.office_name,
        "office_email": profile.office_email,
        "office_phone": profile.office_phone,
        "office_location": profile.office_location,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_capability(request, capability: str, *, recent_mfa: bool = False) -> None:
    user = request.auth_user
    if not user.is_active or not user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _raise_error(exc: DocumentBrandingError) -> NoReturn:
    if isinstance(exc, InvalidDocumentBrandingInput):
        raise APIError(422, "invalid_document_branding_request", str(exc)) from exc
    if isinstance(exc, DocumentBrandingConfigurationError):
        raise APIError(
            503,
            "document_branding_unavailable",
            "The document branding profile is not configured.",
        ) from exc
    raise APIError(
        500,
        "internal_error",
        "The document-branding operation could not be completed.",
    ) from exc


@router.get(
    "/profile",
    response=response_with_errors(DocumentBrandingProfileResponse, 401, 403, 503),
    auth=session_auth,
    operation_id="documentBrandingGetProfile",
)
def document_branding_get_profile(request):
    _require_capability(request, "document_branding.view")
    try:
        profile = get_branding_profile()
    except DocumentBrandingError as exc:
        _raise_error(exc)
    return _serialize(profile)


@router.patch(
    "/profile",
    response=response_with_errors(DocumentBrandingProfileResponse, 401, 403, 422, 503),
    auth=session_auth,
    operation_id="documentBrandingUpdateProfile",
)
def document_branding_update_profile(
    request,
    payload: DocumentBrandingUpdateRequest,
):
    _require_capability(request, "document_branding.manage", recent_mfa=True)
    changes = payload.model_dump(exclude_unset=True)
    try:
        result = update_branding_profile(changes=changes, context=_context(request))
    except DocumentBrandingError as exc:
        _raise_error(exc)
    return _serialize(result.profile)
