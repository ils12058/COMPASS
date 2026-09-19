"""Capability-authorized Privacy Governance API."""

from __future__ import annotations

from datetime import datetime
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

from .activity import (
    DEFAULT_PAGE_SIZE as ACTIVITY_DEFAULT_PAGE_SIZE,
    PrivacyActivityCategory,
    PrivacyActivityPaginationError,
    list_privacy_activity,
)
from .models import (
    PrivacyIncidentStatus,
    PrivacyNotificationAssessment,
    PrivacyReviewStatus,
    PrivacyReviewType,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    PrivacyConflict,
    PrivacyGovernanceError,
    PrivacyInputError,
    PrivacyRecordNotFound,
    create_privacy_incident,
    create_privacy_review,
    create_processing_activity,
    get_privacy_incident,
    get_privacy_review,
    get_processing_activity,
    list_privacy_incidents,
    list_privacy_reviews,
    list_processing_activities,
    resolve_privacy_incident,
    resolve_privacy_review,
    retire_processing_activity,
    update_privacy_incident,
    update_privacy_review,
    update_processing_activity,
)

router = Router(tags=["privacy-governance"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ReviewTypeValue(StrEnum):
    PRIVACY_REVIEW = PrivacyReviewType.PRIVACY_REVIEW
    PIA = PrivacyReviewType.PIA


class ReviewStatusValue(StrEnum):
    OPEN = PrivacyReviewStatus.OPEN
    RESOLVED = PrivacyReviewStatus.RESOLVED


class IncidentStatusValue(StrEnum):
    OPEN = PrivacyIncidentStatus.OPEN
    ASSESSING = PrivacyIncidentStatus.ASSESSING
    CONTAINED = PrivacyIncidentStatus.CONTAINED
    RESOLVED = PrivacyIncidentStatus.RESOLVED


class NotificationAssessmentValue(StrEnum):
    NOT_ASSESSED = PrivacyNotificationAssessment.NOT_ASSESSED
    NOT_REQUIRED = PrivacyNotificationAssessment.NOT_REQUIRED
    REQUIRED = PrivacyNotificationAssessment.REQUIRED
    COMPLETED = PrivacyNotificationAssessment.COMPLETED


class ActorSummary(StrictSchema):
    id: UUID
    display_name: str


class ProcessingActivityResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    purpose: str
    data_subject_categories: list[str]
    personal_data_categories: list[str]
    authorized_access_summary: str
    safeguards_summary: str
    retention_policy_reference: str
    policy_basis_reference: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProcessingActivityPageResponse(StrictSchema):
    items: list[ProcessingActivityResponse]
    page: int
    page_size: int
    has_next: bool


class ProcessingActivityCreateRequest(StrictSchema):
    code: str
    name: str
    purpose: str
    data_subject_categories: list[str]
    personal_data_categories: list[str]
    authorized_access_summary: str
    safeguards_summary: str
    retention_policy_reference: str = ""
    policy_basis_reference: str = ""


class ProcessingActivityUpdateRequest(StrictSchema):
    name: str | None = None
    purpose: str | None = None
    data_subject_categories: list[str] | None = None
    personal_data_categories: list[str] | None = None
    authorized_access_summary: str | None = None
    safeguards_summary: str | None = None
    retention_policy_reference: str | None = None
    policy_basis_reference: str | None = None


class PrivacyReviewResponse(StrictSchema):
    id: UUID
    processing_activity_id: UUID
    review_type: ReviewTypeValue
    status: ReviewStatusValue
    scope_summary: str
    findings_summary: str
    recommendations_summary: str
    resolution_summary: str
    reviewed_by: ActorSummary
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class PrivacyReviewPageResponse(StrictSchema):
    items: list[PrivacyReviewResponse]
    page: int
    page_size: int
    has_next: bool


class PrivacyReviewCreateRequest(StrictSchema):
    review_type: ReviewTypeValue
    scope_summary: str
    findings_summary: str = ""
    recommendations_summary: str = ""


class PrivacyReviewUpdateRequest(StrictSchema):
    scope_summary: str | None = None
    findings_summary: str | None = None
    recommendations_summary: str | None = None


class PrivacyReviewResolveRequest(StrictSchema):
    resolution_summary: str


class PrivacyIncidentResponse(StrictSchema):
    id: UUID
    reference_code: str
    title: str
    summary: str
    affected_area: str
    personal_data_categories: list[str]
    status: IncidentStatusValue
    occurred_at: datetime | None
    discovered_at: datetime
    estimated_affected_subjects: int | None
    assessment_summary: str
    containment_summary: str
    notification_assessment: NotificationAssessmentValue
    notification_reference: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class PrivacyIncidentPageResponse(StrictSchema):
    items: list[PrivacyIncidentResponse]
    page: int
    page_size: int
    has_next: bool


class PrivacyIncidentCreateRequest(StrictSchema):
    title: str
    summary: str
    affected_area: str
    personal_data_categories: list[str]
    discovered_at: datetime
    occurred_at: datetime | None = None
    estimated_affected_subjects: int | None = None
    assessment_summary: str = ""
    containment_summary: str = ""
    notification_assessment: NotificationAssessmentValue = NotificationAssessmentValue.NOT_ASSESSED
    notification_reference: str = ""


class PrivacyActivityItemResponse(StrictSchema):
    id: UUID
    category: PrivacyActivityCategory
    type: str
    title: str
    description: str
    occurred_at: datetime
    actor_display_name: str | None
    artifact_type: str | None
    artifact_format: str | None
    scope: str | None
    resource_reference: str | None


class PrivacyActivityPageResponse(StrictSchema):
    items: list[PrivacyActivityItemResponse]
    page: int
    page_size: int
    has_next: bool


class PrivacyIncidentUpdateRequest(StrictSchema):
    title: str | None = None
    summary: str | None = None
    affected_area: str | None = None
    personal_data_categories: list[str] | None = None
    status: IncidentStatusValue | None = None
    occurred_at: datetime | None = None
    discovered_at: datetime | None = None
    estimated_affected_subjects: int | None = None
    assessment_summary: str | None = None
    containment_summary: str | None = None
    notification_assessment: NotificationAssessmentValue | None = None
    notification_reference: str | None = None


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
        raise APIError(409, "privacy_governance_conflict", str(exc)) from exc
    if isinstance(exc, PrivacyInputError):
        raise APIError(422, "invalid_privacy_governance_input", str(exc)) from exc
    raise APIError(500, "internal_error", "The privacy governance operation failed.") from exc


def _processing(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "code": item.code,
        "name": item.name,
        "purpose": item.purpose,
        "data_subject_categories": item.data_subject_categories,
        "personal_data_categories": item.personal_data_categories,
        "authorized_access_summary": item.authorized_access_summary,
        "safeguards_summary": item.safeguards_summary,
        "retention_policy_reference": item.retention_policy_reference,
        "policy_basis_reference": item.policy_basis_reference,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _review(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "processing_activity_id": item.processing_activity_id,
        "review_type": item.review_type,
        "status": item.status,
        "scope_summary": item.scope_summary,
        "findings_summary": item.findings_summary,
        "recommendations_summary": item.recommendations_summary,
        "resolution_summary": item.resolution_summary,
        "reviewed_by": {
            "id": item.reviewed_by_id,
            "display_name": item.reviewed_by.get_full_name().strip() or "COMPASS DPO",
        },
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "resolved_at": item.resolved_at,
    }


def _incident(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "title": item.title,
        "summary": item.summary,
        "affected_area": item.affected_area,
        "personal_data_categories": item.personal_data_categories,
        "status": item.status,
        "occurred_at": item.occurred_at,
        "discovered_at": item.discovered_at,
        "estimated_affected_subjects": item.estimated_affected_subjects,
        "assessment_summary": item.assessment_summary,
        "containment_summary": item.containment_summary,
        "notification_assessment": item.notification_assessment,
        "notification_reference": item.notification_reference,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "resolved_at": item.resolved_at,
    }


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


@router.get(
    "/processing-activities",
    response=response_with_errors(ProcessingActivityPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListProcessingActivities",
)
def processing_list(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    is_active: bool | None = None,
):
    _require(request, "privacy_governance.view")
    try:
        result = list_processing_activities(
            page=page,
            page_size=page_size,
            is_active=is_active,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return {
        "items": [_processing(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.post(
    "/processing-activities",
    response=response_with_errors(
        ProcessingActivityResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="privacyGovernanceCreateProcessingActivity",
)
def processing_create(request, payload: ProcessingActivityCreateRequest):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = create_processing_activity(
            actor=request.auth_user,
            context=_context(request),
            **payload.model_dump(),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return Status(201, _processing(item))


@router.get(
    "/processing-activities/{processing_id}",
    response=response_with_errors(ProcessingActivityResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetProcessingActivity",
)
def processing_get(request, processing_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        item = get_processing_activity(processing_id)
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _processing(item)


@router.patch(
    "/processing-activities/{processing_id}",
    response=response_with_errors(ProcessingActivityResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateProcessingActivity",
)
def processing_update(
    request,
    processing_id: UUID,
    payload: ProcessingActivityUpdateRequest,
):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = update_processing_activity(
            processing_id=processing_id,
            context=_context(request),
            changes=payload.model_dump(exclude_unset=True),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _processing(item)


@router.post(
    "/processing-activities/{processing_id}/retire",
    response=response_with_errors(ProcessingActivityResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="privacyGovernanceRetireProcessingActivity",
)
def processing_retire(request, processing_id: UUID):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = retire_processing_activity(
            processing_id=processing_id,
            context=_context(request),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _processing(item)


@router.get(
    "/processing-activities/{processing_id}/reviews",
    response=response_with_errors(PrivacyReviewPageResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListReviews",
)
def review_list(
    request,
    processing_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "privacy_governance.view")
    try:
        result = list_privacy_reviews(
            processing_id=processing_id,
            page=page,
            page_size=page_size,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return {
        "items": [_review(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.post(
    "/processing-activities/{processing_id}/reviews",
    response=response_with_errors(
        PrivacyReviewResponse,
        401,
        403,
        404,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="privacyGovernanceCreateReview",
)
def review_create(
    request,
    processing_id: UUID,
    payload: PrivacyReviewCreateRequest,
):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = create_privacy_review(
            actor=request.auth_user,
            context=_context(request),
            processing_id=processing_id,
            **payload.model_dump(),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return Status(201, _review(item))


@router.get(
    "/reviews/{review_id}",
    response=response_with_errors(PrivacyReviewResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetReview",
)
def review_get(request, review_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        item = get_privacy_review(review_id)
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _review(item)


@router.patch(
    "/reviews/{review_id}",
    response=response_with_errors(PrivacyReviewResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateReview",
)
def review_update(request, review_id: UUID, payload: PrivacyReviewUpdateRequest):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = update_privacy_review(
            review_id=review_id,
            context=_context(request),
            changes=payload.model_dump(exclude_unset=True),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _review(item)


@router.post(
    "/reviews/{review_id}/resolve",
    response=response_with_errors(PrivacyReviewResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceResolveReview",
)
def review_resolve(request, review_id: UUID, payload: PrivacyReviewResolveRequest):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = resolve_privacy_review(
            review_id=review_id,
            context=_context(request),
            resolution_summary=payload.resolution_summary,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _review(item)


@router.get(
    "/incidents",
    response=response_with_errors(PrivacyIncidentPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListIncidents",
)
def incident_list(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: IncidentStatusValue | None = None,
):
    _require(request, "privacy_governance.view")
    try:
        result = list_privacy_incidents(
            page=page,
            page_size=page_size,
            status=status.value if status is not None else None,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return {
        "items": [_incident(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.post(
    "/incidents",
    response=response_with_errors(
        PrivacyIncidentResponse,
        401,
        403,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="privacyGovernanceCreateIncident",
)
def incident_create(request, payload: PrivacyIncidentCreateRequest):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    values = payload.model_dump()
    values["notification_assessment"] = payload.notification_assessment.value
    try:
        item = create_privacy_incident(
            context=_context(request),
            **values,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return Status(201, _incident(item))


@router.get(
    "/incidents/{incident_id}",
    response=response_with_errors(PrivacyIncidentResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetIncident",
)
def incident_get(request, incident_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        item = get_privacy_incident(incident_id)
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _incident(item)


@router.patch(
    "/incidents/{incident_id}",
    response=response_with_errors(PrivacyIncidentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateIncident",
)
def incident_update(
    request,
    incident_id: UUID,
    payload: PrivacyIncidentUpdateRequest,
):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    changes = payload.model_dump(exclude_unset=True)
    if payload.status is not None and "status" in changes:
        changes["status"] = payload.status.value
    if payload.notification_assessment is not None and "notification_assessment" in changes:
        changes["notification_assessment"] = payload.notification_assessment.value
    try:
        item = update_privacy_incident(
            incident_id=incident_id,
            context=_context(request),
            changes=changes,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _incident(item)


@router.post(
    "/incidents/{incident_id}/resolve",
    response=response_with_errors(PrivacyIncidentResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="privacyGovernanceResolveIncident",
)
def incident_resolve(request, incident_id: UUID):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = resolve_privacy_incident(
            incident_id=incident_id,
            context=_context(request),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return _incident(item)


__all__ = ["router"]
