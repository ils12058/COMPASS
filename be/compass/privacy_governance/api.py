"""Capability-authorized retained Privacy Governance API."""

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

from .activity import DEFAULT_PAGE_SIZE as ACTIVITY_DEFAULT_PAGE_SIZE
from .activity import (
    PrivacyActivityArtifactFormat,
    PrivacyActivityArtifactType,
    PrivacyActivityCategory,
    PrivacyActivityPaginationError,
    list_privacy_activity,
)
from .services import (
    PrivacyConflict,
    PrivacyGovernanceError,
    PrivacyInputError,
    PrivacyRecordNotFound,
)

router = Router(tags=["privacy-governance"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class PrivacyActivityItemResponse(StrictSchema):
    id: UUID
    category: PrivacyActivityCategory
    type: str
    title: str
    description: str
    occurred_at: datetime
    actor_display_name: str | None
    artifact_type: PrivacyActivityArtifactType | None
    artifact_format: PrivacyActivityArtifactFormat | None
    scope: str | None
    resource_reference: str | None


class PrivacyActivityPageResponse(StrictSchema):
    items: list[PrivacyActivityItemResponse]
    page: int
    page_size: int
    has_next: bool


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _raise(exc: PrivacyGovernanceError) -> NoReturn:
    if isinstance(exc, PrivacyRecordNotFound):
        raise APIError(404, "privacy_record_not_found", str(exc)) from exc
    if isinstance(exc, PrivacyConflict):
        raise APIError(409, exc.code.value, str(exc)) from exc
    if isinstance(exc, PrivacyInputError):
        raise APIError(422, "invalid_privacy_governance_input", str(exc)) from exc
    raise APIError(500, "internal_error", "The privacy governance operation failed.") from exc


@router.get(
    "/activity",
    response=response_with_errors(PrivacyActivityPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListActivity",
)
def privacy_activity(
    request,
    page: int = 1,
    page_size: int = ACTIVITY_DEFAULT_PAGE_SIZE,
    category: PrivacyActivityCategory | None = None,
):
    _require(request, "privacy_governance.view")
    try:
        result = list_privacy_activity(
            page=page,
            page_size=page_size,
            category=category,
        )
    except PrivacyActivityPaginationError as exc:
        raise APIError(422, "invalid_privacy_activity_request", str(exc)) from exc
    return {
        "items": [
            {
                "id": item.id,
                "category": item.category,
                "type": item.type,
                "title": item.title,
                "description": item.description,
                "occurred_at": item.occurred_at,
                "actor_display_name": item.actor_display_name,
                "artifact_type": item.artifact_type,
                "artifact_format": item.artifact_format,
                "scope": item.scope,
                "resource_reference": item.resource_reference,
            }
            for item in result.items
        ],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


__all__ = ["router"]
