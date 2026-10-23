"""Explicit structural workflow and professional Handoff operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from ninja import Query, Router, Schema
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.counseling import coverage_selection, handoff_services
from compass.counseling.continuity_models import (
    ContinuityProjection,
    ContinuityReason,
    ContinuitySourceKind,
)
from compass.counseling.continuity_policy import ContinuityError

router = Router(auth=session_auth)


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class OfficeCaseReference(StrictSchema):
    student_id: UUID
    original_counselor_id: UUID


class CoverageConfiguration(StrictSchema):
    server_now: datetime
    valid_until: datetime
    maximum_duration_seconds: int
    maximum_advance_seconds: int
    reason_categories: list[ContinuityReason]
    office_cases: list[OfficeCaseReference]
    can_request: bool
    can_approve: bool


class CoverageSourceOption(StrictSchema):
    resource_kind: ContinuitySourceKind
    source_id: UUID
    projection: ContinuityProjection
    counselor_id: UUID
    recorded_at: datetime
    eligible: Literal[True]


class CoverageReceiverOption(StrictSchema):
    id: UUID
    name: str


class CoverageSelectionPage(StrictSchema):
    items: list[CoverageSourceOption]
    receivers: list[CoverageReceiverOption]
    page: int
    has_next: bool


class HandoffMetadata(StrictSchema):
    id: UUID
    grant_id: UUID
    student_id: UUID
    author_id: UUID
    receiving_counselor_id: UUID
    state: Literal["DRAFT", "SUBMITTED"]
    submitted_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class HandoffPresence(StrictSchema):
    handoff: HandoffMetadata | None


class HandoffBody(HandoffMetadata):
    content: str


class HandoffVersionInput(StrictSchema):
    expected_grant_version: int = Field(ge=1)
    expected_version: int = Field(ge=0)


class HandoffDraftInput(HandoffVersionInput):
    content: str = Field(max_length=12000)


def _call(service, **kwargs):
    try:
        return service(**kwargs)
    except ContinuityError as exc:
        raise APIError(exc.status, exc.code, str(exc)) from exc


def _session(request, allowed):
    if set(request.GET) - set(allowed):
        raise APIError(422, "continuity_invalid_query", "Unsupported coverage query.")
    return dict(
        actor=request.auth_user,
        context=AuditContext.from_request(request, actor=request.auth_user),
        actor_session_id=request.auth_session.pk,
        actor_session_digest=request.auth_session.token_digest,
    )


@router.get(
    "/workflow/configuration",
    response=response_with_errors(CoverageConfiguration, 401, 403, 409, 422),
    operation_id="counselingCoverageGetConfiguration",
)
def configuration(request):
    _session(request, ())
    return _call(coverage_selection.configuration, actor=request.auth_user)


@router.get(
    "/workflow/selection",
    response=response_with_errors(CoverageSelectionPage, 401, 403, 404, 409, 422),
    operation_id="counselingCoverageSelectSources",
)
def selection(request, student_id: UUID, original_counselor_id: UUID, page: int = Query(1, ge=1)):
    _session(request, ("student_id", "original_counselor_id", "page"))
    return _call(
        coverage_selection.select,
        actor=request.auth_user,
        student_id=student_id,
        original_counselor_id=original_counselor_id,
        page=page,
        context=AuditContext.from_request(request, actor=request.auth_user),
    )


@router.get(
    "/{grant_id}/handoff/metadata",
    response=response_with_errors(HandoffPresence, 401, 403, 404, 409, 422),
    operation_id="counselingHandoffGetMetadata",
)
def metadata(request, grant_id: UUID, expected_grant_version: int = Query(..., ge=1)):
    return _call(
        handoff_services.operate,
        **_session(request, ("expected_grant_version",)),
        grant_id=grant_id,
        operation="metadata",
        expected_grant_version=expected_grant_version,
    )


@router.get(
    "/{grant_id}/handoff/author",
    response=response_with_errors(HandoffBody, 401, 403, 404, 409, 422, 503),
    operation_id="counselingHandoffGetAuthorDraft",
)
def author_body(request, grant_id: UUID, expected_grant_version: int = Query(..., ge=1)):
    return _call(
        handoff_services.operate,
        **_session(request, ("expected_grant_version",)),
        grant_id=grant_id,
        operation="author_read",
        expected_grant_version=expected_grant_version,
    )


@router.put(
    "/{grant_id}/handoff/draft",
    response=response_with_errors(HandoffMetadata, 401, 403, 404, 409, 422, 503),
    operation_id="counselingHandoffSaveDraft",
)
def save_draft(request, grant_id: UUID, payload: HandoffDraftInput):
    return _call(
        handoff_services.operate,
        **_session(request, ()),
        grant_id=grant_id,
        operation="save",
        body=payload.content,
        expected_grant_version=payload.expected_grant_version,
        expected_version=payload.expected_version,
    )


@router.post(
    "/{grant_id}/handoff/submit",
    response=response_with_errors(HandoffMetadata, 401, 403, 404, 409, 422, 503),
    operation_id="counselingHandoffSubmit",
)
def submit(request, grant_id: UUID, payload: HandoffVersionInput):
    return _call(
        handoff_services.operate,
        **_session(request, ()),
        grant_id=grant_id,
        operation="submit",
        **payload.model_dump(),
    )


@router.get(
    "/{grant_id}/handoff/submitted",
    response=response_with_errors(HandoffBody, 401, 403, 404, 409, 422, 503),
    operation_id="counselingHandoffReadSubmitted",
)
def receiver_body(request, grant_id: UUID, expected_grant_version: int = Query(..., ge=1)):
    return _call(
        handoff_services.operate,
        **_session(request, ("expected_grant_version",)),
        grant_id=grant_id,
        operation="receive",
        expected_grant_version=expected_grant_version,
    )
