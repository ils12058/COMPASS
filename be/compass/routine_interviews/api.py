"""Privacy-separated Django Ninja API for Routine Interview workflows."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Header, Router, Schema
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint
from compass.inventory.services import CurrentAcademicYearNotConfigured
from compass.service_catalog.api import DeliveryMode

from .models import RoutineConcern
from .services import (
    DEFAULT_PAGE_SIZE,
    EVALUATION_FIELDS,
    INTAKE_FIELDS,
    InvalidRoutineInterviewInput,
    RoutineInterviewAppointmentInvalid,
    RoutineInterviewCreationConflict,
    RoutineInterviewCurrentStudentRequired,
    RoutineInterviewEncounterMismatch,
    RoutineInterviewEncounterRequired,
    RoutineInterviewError,
    RoutineInterviewEvaluationFinalized,
    RoutineInterviewFormRevisionUnsupported,
    RoutineInterviewIntakeRequired,
    RoutineInterviewIntakeSubmitted,
    RoutineInterviewInventoryRequired,
    RoutineInterviewNotFound,
    RoutineInterviewNotPermitted,
    create_direct,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    get_assigned,
    get_mine,
    list_assigned,
    list_mine,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)

router = Router(tags=["routine-interviews"])
DIRECT_CREATE_ROUTE = "/api/v1/routine-interviews"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class RoutineEntryMode(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    WALK_IN = "WALK_IN"
    CALLED_IN = "CALLED_IN"
    REFERRED = "REFERRED"


class DirectRoutineEntryMode(StrEnum):
    WALK_IN = "WALK_IN"
    CALLED_IN = "CALLED_IN"
    REFERRED = "REFERRED"


class RoutineConcernValue(StrEnum):
    FAMILY = RoutineConcern.FAMILY
    FINANCIAL = RoutineConcern.FINANCIAL
    ACADEMIC = RoutineConcern.ACADEMIC
    FRIENDS = RoutineConcern.FRIENDS
    CLASSMATES = RoutineConcern.CLASSMATES
    VICES = RoutineConcern.VICES
    LOVE_LIFE = RoutineConcern.LOVE_LIFE
    SLEEPING_PROBLEMS = RoutineConcern.SLEEPING_PROBLEMS
    SUICIDAL_THOUGHT_TENDENCY = RoutineConcern.SUICIDAL_THOUGHT_TENDENCY
    DORM_BOARDING_HOUSE = RoutineConcern.DORM_BOARDING_HOUSE
    PAST_PAINFUL_EXPERIENCE = RoutineConcern.PAST_PAINFUL_EXPERIENCE
    OTHER = RoutineConcern.OTHER


class RoutineIntakeStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class RoutineEvaluationStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class RoutineAppointmentEnsureRequest(StrictSchema):
    appointment_id: UUID


class RoutineDirectCreateRequest(StrictSchema):
    student_id: UUID
    entry_mode: DirectRoutineEntryMode
    delivery_mode: DeliveryMode


class RoutineReferenceResponse(StrictSchema):
    id: UUID


class RoutineIntakePayload(StrictSchema):
    coping_with_college_challenges: str = ""
    coping_remarks: str = ""
    college_experience: str = ""
    reason_for_choosing_institution: str = ""
    difficulties_encountered: str = ""
    stress_anxiety_causes: str = ""
    stress_anxiety_management: str = ""
    family_description: str = ""
    concerns: list[RoutineConcernValue] = Field(default_factory=list)
    other_concern_specification: str = ""
    concerns_explanation: str = ""
    college_adjustment_and_peer_group: str = ""
    academic_goals: str = ""
    career_goals: str = ""


class RoutineEvaluationPayload(StrictSchema):
    academic_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    physical_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    social_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    spiritual_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    financial_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    emotional_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    other_adjustment: str = ""
    special_concern: str = ""
    recommendations: str = ""


class RoutineFinalizeRequest(StrictSchema):
    encounter_id: UUID | None = None


class RoutineAcademicYearSummary(StrictSchema):
    id: UUID
    label: str


class RoutineFormRevisionSummary(StrictSchema):
    id: UUID
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class RoutinePersonSummary(StrictSchema):
    id: UUID
    display_name: str


class RoutineInventoryContext(StrictSchema):
    id: UUID
    academic_year: RoutineAcademicYearSummary
    full_name: str
    course: str
    major: str


class RoutineAppointmentSummary(StrictSchema):
    id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime


class RoutineEncounterSummary(StrictSchema):
    id: UUID
    started_at: datetime
    ended_at: datetime


class StudentRoutineSummaryResponse(StrictSchema):
    id: UUID
    counselor: RoutinePersonSummary
    inventory_context: RoutineInventoryContext
    entry_mode: RoutineEntryMode
    delivery_mode: DeliveryMode
    intake_status: RoutineIntakeStatus
    intake_submitted_at: datetime | None
    form_revision: RoutineFormRevisionSummary | None
    appointment: RoutineAppointmentSummary | None
    counseling_encounter: RoutineEncounterSummary | None
    created_at: datetime


class StudentRoutineListResponse(StrictSchema):
    items: list[StudentRoutineSummaryResponse]


class StudentRoutineDetailResponse(StudentRoutineSummaryResponse):
    intake: RoutineIntakePayload


class CounselorRoutineSummaryResponse(StrictSchema):
    id: UUID
    student: RoutinePersonSummary
    inventory_context: RoutineInventoryContext
    entry_mode: RoutineEntryMode
    delivery_mode: DeliveryMode
    intake_status: RoutineIntakeStatus
    intake_submitted_at: datetime | None
    evaluation_status: RoutineEvaluationStatus
    evaluation_finalized_at: datetime | None
    form_revision: RoutineFormRevisionSummary | None
    appointment: RoutineAppointmentSummary | None
    counseling_encounter: RoutineEncounterSummary | None
    created_at: datetime


class CounselorRoutinePageResponse(StrictSchema):
    items: list[CounselorRoutineSummaryResponse]
    page: int
    page_size: int
    has_next: bool


class CounselorRoutineDetailResponse(StrictSchema):
    id: UUID
    student: RoutinePersonSummary
    inventory_context: RoutineInventoryContext
    entry_mode: RoutineEntryMode
    delivery_mode: DeliveryMode
    intake_status: RoutineIntakeStatus
    intake_submitted_at: datetime | None
    intake: RoutineIntakePayload | None
    evaluation_status: RoutineEvaluationStatus
    evaluation_finalized_at: datetime | None
    evaluation: RoutineEvaluationPayload
    form_revision: RoutineFormRevisionSummary | None
    appointment: RoutineAppointmentSummary | None
    counseling_encounter: RoutineEncounterSummary | None
    created_at: datetime


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    actor = request.auth_user
    if not actor.is_active or actor.role.code != "STUDENT" or not actor.has_capability(capability):
        raise APIError(403, "permission_denied", "Student Routine Interview access is required.")


def _require_counselor(request, capability: str) -> None:
    actor = request.auth_user
    if (
        not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability(capability)
    ):
        raise APIError(
            403,
            "permission_denied",
            "Assigned Counselor Routine Interview access is required.",
        )


def _raise(exc: Exception) -> NoReturn:
    if isinstance(exc, CurrentAcademicYearNotConfigured):
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    if isinstance(exc, RoutineInterviewCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, RoutineInterviewNotFound):
        raise APIError(404, "routine_interview_not_found", str(exc)) from exc
    if isinstance(exc, RoutineInterviewNotPermitted):
        raise APIError(403, "routine_interview_not_permitted", str(exc)) from exc
    if isinstance(exc, RoutineInterviewInventoryRequired):
        raise APIError(409, "routine_interview_inventory_required", str(exc)) from exc
    if isinstance(exc, RoutineInterviewAppointmentInvalid):
        raise APIError(409, "routine_interview_appointment_invalid", str(exc)) from exc
    if isinstance(exc, RoutineInterviewIntakeSubmitted):
        raise APIError(409, "routine_interview_intake_already_submitted", str(exc)) from exc
    if isinstance(exc, RoutineInterviewIntakeRequired):
        raise APIError(409, "routine_interview_intake_required", str(exc)) from exc
    if isinstance(exc, RoutineInterviewEvaluationFinalized):
        raise APIError(409, "routine_interview_evaluation_finalized", str(exc)) from exc
    if isinstance(exc, RoutineInterviewEncounterRequired):
        raise APIError(409, "routine_interview_encounter_required", str(exc)) from exc
    if isinstance(exc, RoutineInterviewEncounterMismatch):
        raise APIError(409, "routine_interview_encounter_mismatch", str(exc)) from exc
    if isinstance(exc, RoutineInterviewFormRevisionUnsupported):
        raise APIError(409, "routine_interview_form_revision_unsupported", str(exc)) from exc
    if isinstance(exc, RoutineInterviewCreationConflict):
        raise APIError(409, "idempotency_key_conflict", str(exc)) from exc
    if isinstance(exc, InvalidRoutineInterviewInput):
        raise APIError(422, "routine_interview_invalid", str(exc)) from exc
    if isinstance(exc, RoutineInterviewError):
        raise APIError(
            500,
            "internal_error",
            "The Routine Interview operation could not be completed.",
        ) from exc
    raise exc


def _revision(item) -> dict[str, object] | None:
    revision = item.form_revision
    if revision is None:
        return None
    return {
        "id": revision.pk,
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
        "internal_schema_version": revision.internal_schema_version,
    }


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _inventory_context(item) -> dict[str, object]:
    inventory = item.inventory
    return {
        "id": inventory.pk,
        "academic_year": {
            "id": inventory.academic_year_id,
            "label": inventory.academic_year.label,
        },
        "full_name": inventory.full_name_snapshot or item.student.get_full_name(),
        "course": inventory.course_currently_enrolled,
        "major": inventory.major,
    }


def _appointment(item) -> dict[str, object] | None:
    appointment = item.appointment
    if appointment is None:
        return None
    return {
        "id": appointment.pk,
        "reference_code": appointment.reference_code,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
    }


def _encounter(item) -> dict[str, object] | None:
    encounter = item.counseling_encounter
    if encounter is None:
        return None
    return {
        "id": encounter.pk,
        "started_at": encounter.started_at,
        "ended_at": encounter.ended_at,
    }


def _intake(item) -> dict[str, object]:
    return {field: getattr(item, field) for field in INTAKE_FIELDS}


def _evaluation(item) -> dict[str, object]:
    return {field: getattr(item, field) for field in EVALUATION_FIELDS}


def _student_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "counselor": _person(item.counselor),
        "inventory_context": _inventory_context(item),
        "entry_mode": item.entry_mode,
        "delivery_mode": item.delivery_mode,
        "intake_status": "SUBMITTED" if item.intake_submitted_at else "DRAFT",
        "intake_submitted_at": item.intake_submitted_at,
        "form_revision": _revision(item),
        "appointment": _appointment(item),
        "counseling_encounter": _encounter(item),
        "created_at": item.created_at,
    }


def _student_detail(item) -> dict[str, object]:
    return {**_student_summary(item), "intake": _intake(item)}


def _counselor_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student": _person(item.student),
        "inventory_context": _inventory_context(item),
        "entry_mode": item.entry_mode,
        "delivery_mode": item.delivery_mode,
        "intake_status": "SUBMITTED" if item.intake_submitted_at else "DRAFT",
        "intake_submitted_at": item.intake_submitted_at,
        "evaluation_status": "FINALIZED" if item.evaluation_finalized_at else "DRAFT",
        "evaluation_finalized_at": item.evaluation_finalized_at,
        "form_revision": _revision(item),
        "appointment": _appointment(item),
        "counseling_encounter": _encounter(item),
        "created_at": item.created_at,
    }


def _counselor_detail(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student": _person(item.student),
        "inventory_context": _inventory_context(item),
        "entry_mode": item.entry_mode,
        "delivery_mode": item.delivery_mode,
        "intake_status": "SUBMITTED" if item.intake_submitted_at else "DRAFT",
        "intake_submitted_at": item.intake_submitted_at,
        "intake": _intake(item) if item.intake_submitted_at else None,
        "evaluation_status": "FINALIZED" if item.evaluation_finalized_at else "DRAFT",
        "evaluation_finalized_at": item.evaluation_finalized_at,
        "evaluation": _evaluation(item),
        "form_revision": _revision(item),
        "appointment": _appointment(item),
        "counseling_encounter": _encounter(item),
        "created_at": item.created_at,
    }


@router.post(
    "/me",
    response=response_with_errors(
        StudentRoutineDetailResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="routineInterviewsEnsureMyForAppointment",
)
def routine_interviews_ensure_my_for_appointment(
    request,
    payload: RoutineAppointmentEnsureRequest,
):
    _require_student(request, "routine_interviews.manage_self")
    try:
        item = ensure_for_appointment(
            student=request.auth_user,
            appointment_id=payload.appointment_id,
            context=_context(request),
        )
    except (RoutineInterviewError, CurrentAcademicYearNotConfigured) as exc:
        _raise(exc)
    return _student_detail(item)


@router.post(
    "",
    response=response_with_errors(
        RoutineReferenceResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="routineInterviewsCreateDirect",
)
def routine_interviews_create_direct(
    request,
    payload: RoutineDirectCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_counselor(request, "routine_interviews.manage_assigned")
    fingerprint = request_fingerprint(
        method="POST",
        route=DIRECT_CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_direct(
            counselor=request.auth_user,
            student_id=payload.student_id,
            entry_mode=payload.entry_mode.value,
            delivery_mode=payload.delivery_mode.value,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
    except (RoutineInterviewError, CurrentAcademicYearNotConfigured) as exc:
        _raise(exc)
    return 201, {"id": item.pk}


@router.get(
    "/me",
    response=response_with_errors(StudentRoutineListResponse, 401, 403),
    auth=session_auth,
    operation_id="routineInterviewsListMine",
)
def routine_interviews_list_mine(request):
    _require_student(request, "routine_interviews.view_self")
    try:
        items = list_mine(request.auth_user)
    except RoutineInterviewError as exc:
        _raise(exc)
    return {"items": [_student_summary(item) for item in items]}


@router.get(
    "/me/{routine_interview_id}",
    response=response_with_errors(StudentRoutineDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="routineInterviewsGetMine",
)
def routine_interviews_get_mine(request, routine_interview_id: UUID):
    _require_student(request, "routine_interviews.view_self")
    try:
        item = get_mine(
            student=request.auth_user,
            routine_interview_id=routine_interview_id,
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _student_detail(item)


@router.put(
    "/me/{routine_interview_id}/intake",
    response=response_with_errors(StudentRoutineDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="routineInterviewsReplaceMyIntake",
)
def routine_interviews_replace_my_intake(
    request,
    routine_interview_id: UUID,
    payload: RoutineIntakePayload,
):
    _require_student(request, "routine_interviews.manage_self")
    try:
        item = replace_my_intake(
            student=request.auth_user,
            routine_interview_id=routine_interview_id,
            values=payload.model_dump(mode="python"),
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _student_detail(item)


@router.post(
    "/me/{routine_interview_id}/submit",
    response=response_with_errors(StudentRoutineDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="routineInterviewsSubmitMyIntake",
)
def routine_interviews_submit_my_intake(request, routine_interview_id: UUID):
    _require_student(request, "routine_interviews.manage_self")
    try:
        item = submit_my_intake(
            student=request.auth_user,
            routine_interview_id=routine_interview_id,
            context=_context(request),
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _student_detail(item)


@router.get(
    "",
    response=response_with_errors(CounselorRoutinePageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="routineInterviewsListAssigned",
)
def routine_interviews_list_assigned(
    request,
    student_id: UUID | None = None,
    academic_year_id: UUID | None = None,
    delivery_mode: DeliveryMode | None = None,
    intake_status: RoutineIntakeStatus | None = None,
    evaluation_status: RoutineEvaluationStatus | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, "routine_interviews.view_assigned")
    try:
        result = list_assigned(
            counselor=request.auth_user,
            student_id=student_id,
            academic_year_id=academic_year_id,
            delivery_mode=delivery_mode.value if delivery_mode is not None else None,
            intake_status=intake_status.value if intake_status is not None else None,
            evaluation_status=(
                evaluation_status.value if evaluation_status is not None else None
            ),
            search=search,
            page=page,
            page_size=page_size,
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return {
        "items": [_counselor_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{routine_interview_id}",
    response=response_with_errors(CounselorRoutineDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="routineInterviewsGetAssigned",
)
def routine_interviews_get_assigned(request, routine_interview_id: UUID):
    _require_counselor(request, "routine_interviews.view_assigned")
    try:
        item = get_assigned(
            counselor=request.auth_user,
            routine_interview_id=routine_interview_id,
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _counselor_detail(item)


@router.put(
    "/{routine_interview_id}/evaluation",
    response=response_with_errors(CounselorRoutineDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="routineInterviewsReplaceAssignedEvaluation",
)
def routine_interviews_replace_assigned_evaluation(
    request,
    routine_interview_id: UUID,
    payload: RoutineEvaluationPayload,
):
    _require_counselor(request, "routine_interviews.manage_assigned")
    try:
        item = replace_assigned_evaluation(
            counselor=request.auth_user,
            routine_interview_id=routine_interview_id,
            values=payload.model_dump(mode="python"),
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _counselor_detail(item)


@router.post(
    "/{routine_interview_id}/evaluation/finalize",
    response=response_with_errors(CounselorRoutineDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="routineInterviewsFinalizeAssignedEvaluation",
)
def routine_interviews_finalize_assigned_evaluation(
    request,
    routine_interview_id: UUID,
    payload: RoutineFinalizeRequest,
):
    _require_counselor(request, "routine_interviews.manage_assigned")
    try:
        item = finalize_assigned_evaluation(
            counselor=request.auth_user,
            routine_interview_id=routine_interview_id,
            encounter_id=payload.encounter_id,
            context=_context(request),
        )
    except RoutineInterviewError as exc:
        _raise(exc)
    return _counselor_detail(item)
