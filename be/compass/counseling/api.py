"""Thin Django Ninja API for assigned Counseling and Shared Summary workflows."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.service_catalog.api import DeliveryMode

from .services import (
    DEFAULT_PAGE_SIZE,
    CounselingAppointmentAlreadyUsed,
    CounselingAppointmentInvalid,
    CounselingConfigurationConflict,
    CounselingError,
    CounselingInvalidTime,
    CounselingNotFound,
    CounselingNotPermitted,
    InvalidCounselingInput,
    _institution_zone,
    create_encounter,
    get_encounter_for_actor,
    list_my_encounters,
    list_students,
    update_encounter,
)
from .shared_summaries import (
    CounselingSharedSummaryAlreadyPublished,
    CounselingSharedSummaryEmpty,
    CounselingSharedSummaryNotFound,
    get_assigned_shared_summary,
    get_my_shared_summary,
    list_my_shared_summaries,
    publish_assigned_shared_summary,
    put_assigned_shared_summary,
)

router = Router(tags=["counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CounselingEntryMode(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    WALK_IN = "WALK_IN"
    CALLED_IN = "CALLED_IN"
    REFERRED = "REFERRED"


class CounselingCreateRequest(StrictSchema):
    entry_mode: CounselingEntryMode
    appointment_id: UUID | None = None
    student_id: UUID | None = None
    delivery_mode: DeliveryMode | None = None
    started_at: datetime
    ended_at: datetime


class CounselingUpdateRequest(StrictSchema):
    entry_mode: CounselingEntryMode | None = None
    appointment_id: UUID | None = None
    delivery_mode: DeliveryMode | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class CounselingSharedSummaryPutRequest(StrictSchema):
    content: str


class IdentitySummaryResponse(StrictSchema):
    id: UUID
    display_name: str


class ServiceSummaryResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class AppointmentLinkResponse(StrictSchema):
    id: UUID
    reference_code: str


class CounselingEncounterResponse(StrictSchema):
    id: UUID
    student: IdentitySummaryResponse
    counselor: IdentitySummaryResponse
    service: ServiceSummaryResponse
    appointment: AppointmentLinkResponse | None
    entry_mode: CounselingEntryMode
    delivery_mode: DeliveryMode
    started_at: datetime
    ended_at: datetime
    created_at: datetime
    updated_at: datetime


class CounselingEncounterPageResponse(StrictSchema):
    items: list[CounselingEncounterResponse]
    page: int
    page_size: int
    has_next: bool


class CounselingStudentResponse(StrictSchema):
    id: UUID
    display_name: str


class CounselingStudentPageResponse(StrictSchema):
    items: list[CounselingStudentResponse]
    page: int
    page_size: int
    has_next: bool


class CounselingAssignedSharedSummaryResponse(StrictSchema):
    id: UUID
    encounter_id: UUID
    content: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CounselingStudentSharedSummaryResponse(StrictSchema):
    id: UUID
    content: str
    published_at: datetime
    counseling_ended_at: datetime
    delivery_mode: DeliveryMode


class CounselingStudentSharedSummaryPageResponse(StrictSchema):
    items: list[CounselingStudentSharedSummaryResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_counselor(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR":
        raise APIError(403, "permission_denied", "Active Counselor access is required.")
    if not user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _require_student(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT":
        raise APIError(403, "permission_denied", "Active Student access is required.")
    if not user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _raise(exc: CounselingError) -> NoReturn:
    if isinstance(exc, CounselingSharedSummaryNotFound):
        raise APIError(404, "shared_summary_not_found", str(exc)) from exc
    if isinstance(exc, CounselingSharedSummaryAlreadyPublished):
        raise APIError(409, "shared_summary_already_published", str(exc)) from exc
    if isinstance(exc, CounselingSharedSummaryEmpty):
        raise APIError(409, "shared_summary_empty", str(exc)) from exc
    if isinstance(exc, CounselingNotFound):
        raise APIError(404, "counseling_resource_not_found", str(exc)) from exc
    if isinstance(exc, InvalidCounselingInput):
        raise APIError(422, "counseling_invalid_request", str(exc)) from exc
    if isinstance(exc, CounselingInvalidTime):
        raise APIError(422, "counseling_invalid_time", str(exc)) from exc
    if isinstance(exc, CounselingAppointmentAlreadyUsed):
        raise APIError(409, "counseling_appointment_already_used", str(exc)) from exc
    if isinstance(exc, CounselingAppointmentInvalid):
        raise APIError(409, "counseling_appointment_invalid", str(exc)) from exc
    if isinstance(exc, CounselingConfigurationConflict):
        raise APIError(409, "counseling_service_not_configured", str(exc)) from exc
    if isinstance(exc, CounselingNotPermitted):
        raise APIError(409, "counseling_not_permitted", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Counseling operation could not be completed."
    ) from exc


def _institutional(value: datetime) -> datetime:
    return value.astimezone(_institution_zone())


def _encounter(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student": {
            "id": item.student_id,
            "display_name": item.student.get_full_name(),
        },
        "counselor": {
            "id": item.counselor_id,
            "display_name": item.counselor.get_full_name(),
        },
        "service": {
            "id": item.service_id,
            "code": item.service.code,
            "name": item.service.name,
        },
        "appointment": (
            {
                "id": item.appointment_id,
                "reference_code": item.appointment.reference_code,
            }
            if item.appointment_id is not None
            else None
        ),
        "entry_mode": item.entry_mode,
        "delivery_mode": item.delivery_mode,
        "started_at": _institutional(item.started_at),
        "ended_at": _institutional(item.ended_at),
        "created_at": _institutional(item.created_at),
        "updated_at": _institutional(item.updated_at),
    }


def _assigned_shared_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "encounter_id": item.encounter_id,
        "content": item.content,
        "published_at": _institutional(item.published_at) if item.published_at else None,
        "created_at": _institutional(item.created_at),
        "updated_at": _institutional(item.updated_at),
    }


def _student_shared_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "content": item.content,
        "published_at": _institutional(item.published_at),
        "counseling_ended_at": _institutional(item.encounter.ended_at),
        "delivery_mode": item.encounter.delivery_mode,
    }


@router.get(
    "/students",
    response=response_with_errors(CounselingStudentPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="counselingListStudents",
)
def counseling_list_students(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, "counseling.manage_assigned")
    try:
        result = list_students(search=search, page=page, page_size=page_size)
    except CounselingError as exc:
        _raise(exc)
    return {
        "items": [
            {"id": student.pk, "display_name": student.get_full_name()} for student in result.items
        ],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/encounters",
    response=response_with_errors(CounselingEncounterPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="counselingListMyEncounters",
)
def counseling_list_my_encounters(
    request,
    entry_mode: CounselingEntryMode | None = None,
    delivery_mode: DeliveryMode | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    student_id: UUID | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, "counseling.view_assigned")
    try:
        result = list_my_encounters(
            counselor=request.auth_user,
            entry_mode=entry_mode.value if entry_mode else None,
            delivery_mode=delivery_mode.value if delivery_mode else None,
            from_date=from_date,
            to_date=to_date,
            student_id=student_id,
            page=page,
            page_size=page_size,
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "items": [_encounter(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/shared-summaries",
    response=response_with_errors(CounselingStudentSharedSummaryPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="counselingListMySharedSummaries",
)
def counseling_list_my_shared_summaries(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_student(request, "shared_summaries.view_self")
    try:
        result = list_my_shared_summaries(
            student=request.auth_user,
            page=page,
            page_size=page_size,
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "items": [_student_shared_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/shared-summaries/{summary_id}",
    response=response_with_errors(CounselingStudentSharedSummaryResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="counselingGetMySharedSummary",
)
def counseling_get_my_shared_summary(request, summary_id: UUID):
    _require_student(request, "shared_summaries.view_self")
    try:
        item = get_my_shared_summary(student=request.auth_user, summary_id=summary_id)
    except CounselingError as exc:
        _raise(exc)
    return _student_shared_summary(item)


@router.post(
    "/encounters",
    response=response_with_errors(
        CounselingEncounterResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="counselingCreateEncounter",
)
def counseling_create_encounter(request, payload: CounselingCreateRequest):
    _require_counselor(request, "counseling.manage_assigned")
    try:
        item = create_encounter(
            counselor=request.auth_user,
            entry_mode=payload.entry_mode.value,
            appointment_id=payload.appointment_id,
            student_id=payload.student_id,
            delivery_mode=payload.delivery_mode.value if payload.delivery_mode else None,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return 201, _encounter(item)


@router.get(
    "/encounters/{encounter_id}",
    response=response_with_errors(CounselingEncounterResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="counselingGetEncounter",
)
def counseling_get_encounter(request, encounter_id: UUID):
    _require_counselor(request, "counseling.view_assigned")
    try:
        item = get_encounter_for_actor(encounter_id=encounter_id, actor=request.auth_user)
    except CounselingError as exc:
        _raise(exc)
    return _encounter(item)


@router.patch(
    "/encounters/{encounter_id}",
    response=response_with_errors(CounselingEncounterResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingUpdateEncounter",
)
def counseling_update_encounter(
    request,
    encounter_id: UUID,
    payload: CounselingUpdateRequest,
):
    _require_counselor(request, "counseling.manage_assigned")
    changes = payload.model_dump(exclude_unset=True)
    try:
        item = update_encounter(
            encounter_id=encounter_id,
            counselor=request.auth_user,
            changes=changes,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return _encounter(item)


@router.get(
    "/encounters/{encounter_id}/shared-summary",
    response=response_with_errors(CounselingAssignedSharedSummaryResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="counselingGetAssignedSharedSummary",
)
def counseling_get_assigned_shared_summary(request, encounter_id: UUID):
    _require_counselor(request, "shared_summaries.view_assigned")
    try:
        item = get_assigned_shared_summary(
            encounter_id=encounter_id,
            counselor=request.auth_user,
        )
    except CounselingError as exc:
        _raise(exc)
    return _assigned_shared_summary(item)


@router.put(
    "/encounters/{encounter_id}/shared-summary",
    response=response_with_errors(
        CounselingAssignedSharedSummaryResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="counselingPutAssignedSharedSummary",
)
def counseling_put_assigned_shared_summary(
    request,
    encounter_id: UUID,
    payload: CounselingSharedSummaryPutRequest,
):
    _require_counselor(request, "shared_summaries.manage_assigned")
    try:
        item = put_assigned_shared_summary(
            encounter_id=encounter_id,
            counselor=request.auth_user,
            content=payload.content,
        )
    except CounselingError as exc:
        _raise(exc)
    return _assigned_shared_summary(item)


@router.post(
    "/encounters/{encounter_id}/shared-summary/publish",
    response=response_with_errors(
        CounselingAssignedSharedSummaryResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="counselingPublishAssignedSharedSummary",
)
def counseling_publish_assigned_shared_summary(request, encounter_id: UUID):
    _require_counselor(request, "shared_summaries.manage_assigned")
    try:
        item = publish_assigned_shared_summary(
            encounter_id=encounter_id,
            counselor=request.auth_user,
            context=_context(request),
        )
    except CounselingError as exc:
        _raise(exc)
    return _assigned_shared_summary(item)
