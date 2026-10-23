"""Explicit metadata-only routes. No professional source-read operation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.counseling import continuity_services as services
from compass.counseling.continuity_models import (
    ContinuityDecision,
    ContinuityProjection,
    ContinuityReason,
    ContinuityRevocationReason,
    ContinuitySourceKind,
    CoverageKind,
)
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.continuity_sources import SelectedSource

router = Router(tags=["counseling"])


class ContinuitySchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ContinuityStatus(StrEnum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    REVOKED = "REVOKED"
    UNAVAILABLE = "UNAVAILABLE"


class ContinuityScopeInput(ContinuitySchema):
    resource_kind: ContinuitySourceKind
    source_id: UUID
    projection: ContinuityProjection


class ContinuityRequestInput(ContinuitySchema):
    student_id: UUID
    original_counselor_id: UUID | None = None
    receiving_counselor_id: UUID
    coverage_kind: CoverageKind
    reason_category: ContinuityReason
    starts_at: datetime
    expires_at: datetime
    request_id: UUID
    expected_version: int = Field(ge=0, le=0)
    scopes: list[ContinuityScopeInput] = Field(min_length=1, max_length=32)


class ContinuityVersionInput(ContinuitySchema):
    expected_version: int = Field(gt=0)


class ContinuityRevokeInput(ContinuityVersionInput):
    reason_code: ContinuityRevocationReason


class ContinuityScopeMetadata(ContinuityScopeInput):
    id: UUID
    source_revision: str


class ContinuityGrantMetadata(ContinuitySchema):
    id: UUID
    student_id: UUID
    original_counselor_id: UUID | None
    receiving_counselor_id: UUID
    coverage_kind: CoverageKind
    reason_category: ContinuityReason
    requested_by_id: UUID
    requested_at: datetime
    starts_at: datetime
    expires_at: datetime
    decision: ContinuityDecision
    effective_status: ContinuityStatus
    decision_by_id: UUID | None
    decided_at: datetime | None
    revoked_by_id: UUID | None
    revoked_at: datetime | None
    revocation_reason: ContinuityRevocationReason | None
    version: int
    policy_version: str
    policy_evidence: str
    scopes: list[ContinuityScopeMetadata]


class ContinuityGrantPage(ContinuitySchema):
    items: list[ContinuityGrantMetadata]
    page: int
    page_size: int
    has_next: bool


def _call(operation, **kwargs):
    try:
        return operation(**kwargs)
    except ContinuityError as exc:
        raise APIError(exc.status, exc.code, str(exc)) from exc


@router.get(
    "",
    response=response_with_errors(ContinuityGrantPage, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityListGrants",
)
def list_grants(request, page: int = 1, page_size: int = 20):
    return _call(
        services.list_metadata_page, actor=request.auth_user, page=page, page_size=page_size
    )


@router.get(
    "/{grant_id}",
    response=response_with_errors(ContinuityGrantMetadata, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityGetGrant",
)
def get_grant(request, grant_id: UUID):
    return _call(services.get_grant_metadata, actor=request.auth_user, grant_id=grant_id)


@router.post(
    "",
    response=response_with_errors(
        ContinuityGrantMetadata, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="counselingContinuityRequestCoverage",
)
def request_coverage(request, payload: ContinuityRequestInput):
    data = payload.model_dump(exclude={"scopes"})
    data["scopes"] = [SelectedSource(**s.model_dump()) for s in payload.scopes]
    return Status(
        201,
        _call(
            services.request_coverage,
            actor=request.auth_user,
            context=AuditContext.from_request(request, actor=request.auth_user),
            **data,
        ),
    )


@router.post(
    "/{grant_id}/approve",
    response=response_with_errors(ContinuityGrantMetadata, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityApproveGrant",
)
def approve_grant(request, grant_id: UUID, payload: ContinuityVersionInput):
    return _call(
        services.decide_coverage,
        context=AuditContext.from_request(request, actor=request.auth_user),
        actor=request.auth_user,
        grant_id=grant_id,
        decision="APPROVED",
        expected_version=payload.expected_version,
    )


@router.post(
    "/{grant_id}/decline",
    response=response_with_errors(ContinuityGrantMetadata, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityDeclineGrant",
)
def decline_grant(request, grant_id: UUID, payload: ContinuityVersionInput):
    return _call(
        services.decide_coverage,
        context=AuditContext.from_request(request, actor=request.auth_user),
        actor=request.auth_user,
        grant_id=grant_id,
        decision="DECLINED",
        expected_version=payload.expected_version,
    )


@router.post(
    "/{grant_id}/cancel",
    response=response_with_errors(ContinuityGrantMetadata, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityCancelGrant",
)
def cancel_grant(request, grant_id: UUID, payload: ContinuityVersionInput):
    return _call(
        services.decide_coverage,
        context=AuditContext.from_request(request, actor=request.auth_user),
        actor=request.auth_user,
        grant_id=grant_id,
        decision="CANCELLED",
        expected_version=payload.expected_version,
    )


@router.post(
    "/{grant_id}/revoke",
    response=response_with_errors(ContinuityGrantMetadata, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingContinuityRevokeGrant",
)
def revoke_grant(request, grant_id: UUID, payload: ContinuityRevokeInput):
    return _call(
        services.decide_coverage,
        context=AuditContext.from_request(request, actor=request.auth_user),
        actor=request.auth_user,
        grant_id=grant_id,
        decision="REVOKED",
        expected_version=payload.expected_version,
        revocation_reason=payload.reason_code,
    )
