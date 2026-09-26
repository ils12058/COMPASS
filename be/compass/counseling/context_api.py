"""Read-only API surface for relationship-bound Counseling Context projections."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.appointments.api import AppointmentStatus
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.inventory.api import (
    CounselorInventoryDetailResponse,
    counselor_inventory_detail_payload,
)
from compass.inventory.services import CurrentAcademicYearNotConfigured
from compass.routine_interviews.api import RoutineEvaluationStatus, RoutineIntakeStatus
from compass.service_catalog.api import DeliveryMode
from compass.student_support.services import StudentSupportConfigurationConflict

from .api import CounselingEntryMode
from .context_access import (
    CounselingContextNotFound,
    CounselingContextSource,
    resolve_counseling_context,
)
from .context_services import (
    get_context_inventory,
    get_context_overview,
    get_context_support_indicators,
    list_context_history,
    list_context_shared_summaries,
)

router = Router(tags=["counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CounselingContextAnchorType(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"


class CounselingContextInventoryStatus(StrEnum):
    MISSING = "MISSING"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class CounselingContextSection(StrEnum):
    SUPPORT_INDICATORS = "SUPPORT_INDICATORS"
    INVENTORY = "INVENTORY"
    HISTORY = "HISTORY"
    SHARED_SUMMARIES = "SHARED_SUMMARIES"


class ContextHistoryKind(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    REFERRAL = "REFERRAL"
    CALL_SLIP = "CALL_SLIP"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"


class ContextHistoryStatus(StrEnum):
    """Per-kind history states: Appointment status, Referral receipt, Call Slip interview end,
    Routine Intake submission, and VOIDED for voided Referrals and Call Slips."""

    SCHEDULED = AppointmentStatus.SCHEDULED
    CANCELLED = AppointmentStatus.CANCELLED
    COMPLETED = AppointmentStatus.COMPLETED
    NO_SHOW = AppointmentStatus.NO_SHOW
    RECORDED = "RECORDED"
    RECEIVED = "RECEIVED"
    PENDING = "PENDING"
    ENDED = "ENDED"
    DRAFT = RoutineIntakeStatus.DRAFT
    SUBMITTED = RoutineIntakeStatus.SUBMITTED
    VOIDED = "VOIDED"


class ContextIdentityResponse(StrictSchema):
    id: UUID
    display_name: str


class ContextOrganizationResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class ContextProgramResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class ContextAcademicYearResponse(StrictSchema):
    id: UUID
    label: str


class ContextStudentOverviewResponse(StrictSchema):
    id: UUID
    institutional_id: str | None
    display_name: str
    campus: ContextOrganizationResponse | None
    college: ContextOrganizationResponse | None
    program: ContextProgramResponse | None
    year_level: int | None


class ContextRoutineInterviewResponse(StrictSchema):
    id: UUID
    entry_mode: CounselingEntryMode
    intake_status: RoutineIntakeStatus
    evaluation_status: RoutineEvaluationStatus


class ContextEncounterResponse(StrictSchema):
    id: UUID
    started_at: datetime
    ended_at: datetime


class CounselingContextOverviewResponse(StrictSchema):
    student: ContextStudentOverviewResponse
    source_type: CounselingContextAnchorType
    source_id: UUID
    entry_mode: CounselingEntryMode
    delivery_mode: DeliveryMode
    valid_from: datetime
    valid_until: datetime
    routine_interview: ContextRoutineInterviewResponse | None
    matching_encounter: ContextEncounterResponse | None
    available_sections: list[CounselingContextSection]


class ContextSupportIndicatorResponse(StrictSchema):
    code: str
    label: str


class CounselingContextSupportResponse(StrictSchema):
    academic_year: ContextAcademicYearResponse
    inventory_source_status: CounselingContextInventoryStatus
    available: bool
    indicators: list[ContextSupportIndicatorResponse]


class CounselingContextInventoryResponse(StrictSchema):
    inventory_source_status: CounselingContextInventoryStatus
    available: bool
    inventory: CounselorInventoryDetailResponse | None


class ContextHistoryItemResponse(StrictSchema):
    id: UUID
    kind: ContextHistoryKind
    occurred_at: datetime
    title: str
    status: ContextHistoryStatus
    reference_code: str | None
    delivery_mode: DeliveryMode | None
    provider: ContextIdentityResponse | None


class CounselingContextHistoryResponse(StrictSchema):
    items: list[ContextHistoryItemResponse]
    limit: int


class ContextSharedSummaryResponse(StrictSchema):
    id: UUID
    content: str
    published_at: datetime
    counseling_ended_at: datetime
    counselor: ContextIdentityResponse


class CounselingContextSharedSummariesResponse(StrictSchema):
    items: list[ContextSharedSummaryResponse]
    limit: int


def _require_context_viewer(request) -> None:
    actor = request.auth_user
    if not actor.is_active or actor.role.code != "COUNSELOR":
        raise APIError(403, "permission_denied", "Active Counselor access is required.")
    if not actor.has_capability("counseling.view_assigned"):
        raise APIError(
            403,
            "permission_denied",
            "Assigned Counseling read access is required.",
        )


def _resolve(request, anchor_type: CounselingContextAnchorType, anchor_id: UUID):
    _require_context_viewer(request)
    try:
        return resolve_counseling_context(
            actor=request.auth_user,
            anchor_type=CounselingContextSource(anchor_type.value),
            anchor_id=anchor_id,
        )
    except CounselingContextNotFound as exc:
        raise APIError(
            404,
            "counseling_context_not_found",
            "The requested Counseling Context was not found.",
        ) from exc


def _overview_payload(item) -> dict[str, object]:
    return {
        "student": {
            "id": item.student_id,
            "institutional_id": item.institutional_id,
            "display_name": item.display_name,
            "campus": (
                {"id": item.campus.id, "code": item.campus.code, "name": item.campus.name}
                if item.campus is not None
                else None
            ),
            "college": (
                {"id": item.college.id, "code": item.college.code, "name": item.college.name}
                if item.college is not None
                else None
            ),
            "program": (
                {"id": item.program.id, "code": item.program.code, "name": item.program.name}
                if item.program is not None
                else None
            ),
            "year_level": item.year_level,
        },
        "source_type": item.source_type,
        "source_id": item.source_id,
        "entry_mode": item.entry_mode,
        "delivery_mode": item.delivery_mode,
        "valid_from": item.valid_from,
        "valid_until": item.valid_until,
        "routine_interview": (
            {
                "id": item.routine_interview.id,
                "entry_mode": item.routine_interview.entry_mode,
                "intake_status": item.routine_interview.intake_status,
                "evaluation_status": item.routine_interview.evaluation_status,
            }
            if item.routine_interview is not None
            else None
        ),
        "matching_encounter": (
            {
                "id": item.encounter.id,
                "started_at": item.encounter.started_at,
                "ended_at": item.encounter.ended_at,
            }
            if item.encounter is not None
            else None
        ),
        "available_sections": list(item.available_sections),
    }


def _validate_limit(limit: int) -> int:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise APIError(422, "counseling_context_invalid_limit", "limit must be between 1 and 50.")
    return limit


@router.get(
    "/{anchor_type}/{anchor_id}",
    response=response_with_errors(CounselingContextOverviewResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="counselingContextGetOverview",
)
def counseling_context_get_overview(
    request,
    anchor_type: CounselingContextAnchorType,
    anchor_id: UUID,
):
    access = _resolve(request, anchor_type, anchor_id)
    try:
        item = get_context_overview(access)
    except CurrentAcademicYearNotConfigured as exc:
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    return _overview_payload(item)


@router.get(
    "/{anchor_type}/{anchor_id}/support-indicators",
    response=response_with_errors(CounselingContextSupportResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="counselingContextGetSupportIndicators",
)
def counseling_context_get_support_indicators(
    request,
    anchor_type: CounselingContextAnchorType,
    anchor_id: UUID,
):
    access = _resolve(request, anchor_type, anchor_id)
    try:
        item = get_context_support_indicators(access)
    except StudentSupportConfigurationConflict as exc:
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    return {
        "academic_year": {"id": item.academic_year.pk, "label": item.academic_year.label},
        "inventory_source_status": item.inventory_status,
        "available": item.available,
        "indicators": [
            {"code": indicator.code, "label": indicator.label} for indicator in item.indicators
        ],
    }


@router.get(
    "/{anchor_type}/{anchor_id}/inventory",
    response=response_with_errors(CounselingContextInventoryResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="counselingContextGetInventory",
)
def counseling_context_get_inventory(
    request,
    anchor_type: CounselingContextAnchorType,
    anchor_id: UUID,
):
    access = _resolve(request, anchor_type, anchor_id)
    try:
        result = get_context_inventory(access)
    except CurrentAcademicYearNotConfigured as exc:
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc

    item = result.inventory
    return {
        "inventory_source_status": result.inventory_source_status,
        "available": result.available,
        "inventory": counselor_inventory_detail_payload(item) if item is not None else None,
    }


@router.get(
    "/{anchor_type}/{anchor_id}/history",
    response=response_with_errors(CounselingContextHistoryResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="counselingContextListHistory",
)
def counseling_context_list_history(
    request,
    anchor_type: CounselingContextAnchorType,
    anchor_id: UUID,
    limit: int = 20,
):
    bounded_limit = _validate_limit(limit)
    access = _resolve(request, anchor_type, anchor_id)
    items = list_context_history(access, limit=bounded_limit)
    return {
        "items": [
            {
                "id": item.id,
                "kind": item.kind,
                "occurred_at": item.occurred_at,
                "title": item.title,
                "status": item.status,
                "reference_code": item.reference_code,
                "delivery_mode": item.delivery_mode,
                "provider": (
                    {
                        "id": item.provider_id,
                        "display_name": item.provider_display_name,
                    }
                    if item.provider_id is not None and item.provider_display_name is not None
                    else None
                ),
            }
            for item in items
        ],
        "limit": bounded_limit,
    }


@router.get(
    "/{anchor_type}/{anchor_id}/shared-summaries",
    response=response_with_errors(
        CounselingContextSharedSummariesResponse,
        401,
        403,
        404,
        422,
    ),
    auth=session_auth,
    operation_id="counselingContextListSharedSummaries",
)
def counseling_context_list_shared_summaries(
    request,
    anchor_type: CounselingContextAnchorType,
    anchor_id: UUID,
    limit: int = 20,
):
    bounded_limit = _validate_limit(limit)
    access = _resolve(request, anchor_type, anchor_id)
    items = list_context_shared_summaries(access, limit=bounded_limit)
    return {
        "items": [
            {
                "id": item.id,
                "content": item.content,
                "published_at": item.published_at,
                "counseling_ended_at": item.counseling_ended_at,
                "counselor": {
                    "id": item.counselor_id,
                    "display_name": item.counselor_display_name,
                },
            }
            for item in items
        ],
        "limit": bounded_limit,
    }
