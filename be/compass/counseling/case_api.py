"""Thin Django Ninja API for Counseling cases (CW-1).

Every response here is a bounded projection for the case's primary Counselor. A linked session is
described by scheduling facts and its original author only; its content stays behind the Encounter
and Student Session Summary endpoints and their own permissions.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.accounts.profile_photos import profile_photo_projection
from compass.appointments.api import AppointmentStatus
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.institutional_time import to_institution_time
from compass.service_catalog.api import DeliveryMode

from .api import (
    AppointmentLinkResponse,
    CounselingCaseStatus,
    CounselingEntryMode,
    IdentitySummaryResponse,
)
from .case_services import (
    MANAGE_CAPABILITY,
    MAX_KNOWN_ACTIVE_CASES,
    VIEW_CAPABILITY,
    CaseOverview,
    CaseSummary,
    CounselingCaseError,
    CounselingCaseOrdering,
    get_case,
    get_opening_context,
    link_session,
    list_my_cases,
    list_session_candidates,
    open_case,
    unlink_session,
)
from .services import DEFAULT_PAGE_SIZE, CounselingError

router = Router(tags=["counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CounselingCaseOrigin(StrEnum):
    INTAKE = "INTAKE"
    APPOINTMENT = "APPOINTMENT"
    ENCOUNTER = "ENCOUNTER"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"


class CounselingCaseSessionRemovalReason(StrEnum):
    BELONGS_TO_ANOTHER_CASE = "BELONGS_TO_ANOTHER_CASE"
    NOT_PART_OF_THIS_CASE = "NOT_PART_OF_THIS_CASE"
    LINKED_BY_MISTAKE = "LINKED_BY_MISTAKE"


class CounselingCaseEventKind(StrEnum):
    OPENED = "OPENED"
    SESSION_LINKED = "SESSION_LINKED"
    SESSION_UNLINKED = "SESSION_UNLINKED"


class CounselingCaseOpenRequest(StrictSchema):
    origin: CounselingCaseOrigin
    # Required for INTAKE. With a source record it may be sent and must match that record.
    student_id: UUID | None = None
    # The Appointment, Encounter or Routine Interview the case starts from; never for INTAKE.
    source_id: UUID | None = None
    # The Counselor's active cases for this Student that were shown before confirming. Opening is
    # refused with ``counseling_case_review_required`` when the current set differs.
    known_active_case_ids: list[UUID] = Field(
        default_factory=list, max_length=MAX_KNOWN_ACTIVE_CASES
    )


class CounselingCaseLinkSessionRequest(StrictSchema):
    encounter_id: UUID
    expected_version: int = Field(ge=1)


class CounselingCaseUnlinkSessionRequest(StrictSchema):
    reason: CounselingCaseSessionRemovalReason
    expected_version: int = Field(ge=1)


class CounselingCaseStudent(IdentitySummaryResponse):
    institutional_id: str | None


class CounselingCasePerson(StrictSchema):
    id: UUID
    display_name: str


class CounselingCaseSummaryResponse(StrictSchema):
    id: UUID
    reference_code: str
    status: CounselingCaseStatus
    student: CounselingCaseStudent
    # The one Counselor currently responsible for this case.
    primary_counselor: IdentitySummaryResponse
    origin: CounselingCaseOrigin
    opened_at: datetime
    # Completed sessions linked to this case; each recorded Encounter counts once.
    session_count: int
    latest_session_at: datetime | None
    version: int


class CounselingCasePageResponse(StrictSchema):
    items: list[CounselingCaseSummaryResponse]
    page: int
    page_size: int
    has_next: bool
    # The ordering applied: the requested one, or the latest activity first.
    ordering: CounselingCaseOrdering


class CounselingCaseSessionResponse(StrictSchema):
    encounter_id: UUID
    started_at: datetime
    ended_at: datetime
    entry_mode: CounselingEntryMode
    delivery_mode: DeliveryMode
    # The Counselor who recorded the session. Linking or transferring a case never changes this.
    counselor: IdentitySummaryResponse
    linked_at: datetime
    # Whether the reader may open the session record itself. The Appointment reference is part of
    # that record, so it is present only when this is true.
    record_accessible: bool
    appointment: AppointmentLinkResponse | None


class CounselingCaseSessionCandidate(StrictSchema):
    encounter_id: UUID
    started_at: datetime
    ended_at: datetime
    entry_mode: CounselingEntryMode
    delivery_mode: DeliveryMode
    appointment: AppointmentLinkResponse | None


class CounselingCaseSessionCandidatePage(StrictSchema):
    items: list[CounselingCaseSessionCandidate]
    page: int
    page_size: int
    has_next: bool


class CounselingCaseOriginAppointment(StrictSchema):
    id: UUID
    reference_code: str
    starts_at: datetime
    status: AppointmentStatus


class CounselingCaseSourceResponse(StrictSchema):
    # Present only while the originating record is still the reader's own.
    appointment: CounselingCaseOriginAppointment | None
    encounter_id: UUID | None
    routine_interview_id: UUID | None


class CounselingCaseEventResponse(StrictSchema):
    id: UUID
    kind: CounselingCaseEventKind
    occurred_at: datetime
    actor: CounselingCasePerson
    # Who was responsible for the case when this happened.
    primary_counselor: CounselingCasePerson
    encounter_id: UUID | None
    encounter_started_at: datetime | None
    # OPENED: the origin. SESSION_UNLINKED: the correction reason. Otherwise absent.
    detail_code: str | None


class CounselingCaseDetailResponse(CounselingCaseSummaryResponse):
    source: CounselingCaseSourceResponse
    sessions: list[CounselingCaseSessionResponse]
    # The originating record's own session when it is recorded, the reader's, and in no case yet.
    unlinked_origin_session: CounselingCaseSessionCandidate | None
    history: list[CounselingCaseEventResponse]
    # Whether the reader may link or correct sessions now.
    can_manage: bool


class CounselingCaseOpeningContextResponse(StrictSchema):
    origin: CounselingCaseOrigin
    student: CounselingCaseStudent
    source: CounselingCaseSourceResponse
    # The recorded session that opening from this context links to the new case.
    session: CounselingCaseSessionCandidate | None
    # The reader's own active cases for this Student, to review before opening another.
    active_cases: list[CounselingCaseSummaryResponse]


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_counselor(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR" or not user.has_capability(capability):
        raise APIError(
            403, "permission_denied", "You don't have permission to use Counseling cases."
        )


def _raise(exc: CounselingError) -> NoReturn:
    if isinstance(exc, CounselingCaseError):
        raise APIError(exc.status, exc.code, str(exc)) from exc
    raise APIError(409, "counseling_not_permitted", str(exc)) from exc


def _institutional(value: datetime | None) -> datetime | None:
    return to_institution_time(value) if value is not None else None


def _identity(user) -> dict[str, object]:
    return {
        "id": user.pk,
        "display_name": user.get_full_name(),
        **profile_photo_projection(user),
    }


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _summary(item: CaseSummary) -> dict[str, object]:
    case = item.case
    return {
        "id": case.pk,
        "reference_code": case.reference_code,
        "status": case.status,
        "student": {
            **_identity(case.student),
            "institutional_id": case.student.institutional_id,
        },
        "primary_counselor": _identity(case.primary_counselor),
        "origin": case.origin,
        "opened_at": _institutional(case.opened_at),
        "session_count": item.session_count,
        "latest_session_at": _institutional(item.latest_session_at),
        "version": case.version,
    }


def _candidate(encounter) -> dict[str, object]:
    return {
        "encounter_id": encounter.pk,
        "started_at": _institutional(encounter.started_at),
        "ended_at": _institutional(encounter.ended_at),
        "entry_mode": encounter.entry_mode,
        "delivery_mode": encounter.delivery_mode,
        "appointment": (
            {
                "id": encounter.appointment_id,
                "reference_code": encounter.appointment.reference_code,
            }
            if encounter.appointment_id is not None
            else None
        ),
    }


def _source(*, appointment, encounter_id, routine_interview_id) -> dict[str, object]:
    return {
        "appointment": (
            {
                "id": appointment.pk,
                "reference_code": appointment.reference_code,
                "starts_at": _institutional(appointment.starts_at),
                "status": appointment.status,
            }
            if appointment is not None
            else None
        ),
        "encounter_id": encounter_id,
        "routine_interview_id": routine_interview_id,
    }


def _detail(overview: CaseOverview) -> dict[str, object]:
    return {
        **_summary(overview.summary),
        "source": _source(
            appointment=overview.origin_appointment,
            encounter_id=overview.origin_encounter_id,
            routine_interview_id=overview.origin_routine_interview_id,
        ),
        "sessions": [
            {
                **_candidate(item.link.encounter),
                "counselor": _identity(item.link.encounter.counselor),
                "linked_at": _institutional(item.link.linked_at),
                "record_accessible": item.record_accessible,
                "appointment": (
                    _candidate(item.link.encounter)["appointment"]
                    if item.record_accessible
                    else None
                ),
            }
            for item in overview.sessions
        ],
        "unlinked_origin_session": (
            _candidate(overview.unlinked_origin_session)
            if overview.unlinked_origin_session is not None
            else None
        ),
        "history": [
            {
                "id": event.pk,
                "kind": event.kind,
                "occurred_at": _institutional(event.occurred_at),
                "actor": _person(event.actor),
                "primary_counselor": _person(event.primary_counselor),
                "encounter_id": event.encounter_id,
                "encounter_started_at": (
                    _institutional(event.encounter.started_at)
                    if event.encounter is not None
                    else None
                ),
                "detail_code": event.detail_code or None,
            }
            for event in overview.events
        ],
        "can_manage": overview.can_manage,
    }


@router.get(
    "",
    response=response_with_errors(CounselingCasePageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="counselingListMyCases",
)
def counseling_list_my_cases(
    request,
    status: CounselingCaseStatus | None = None,
    student_id: UUID | None = None,
    search: str | None = None,
    ordering: CounselingCaseOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, VIEW_CAPABILITY)
    try:
        result = list_my_cases(
            actor=request.auth_user,
            status=status.value if status else None,
            student_id=student_id,
            search=search,
            ordering=ordering,
            page=page,
            page_size=page_size,
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "ordering": result.ordering,
    }


@router.post(
    "",
    response=response_with_errors(
        CounselingCaseDetailResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="counselingOpenCase",
)
def counseling_open_case(request, payload: CounselingCaseOpenRequest):
    _require_counselor(request, MANAGE_CAPABILITY)
    try:
        case = open_case(
            actor=request.auth_user,
            origin=payload.origin.value,
            student_id=payload.student_id,
            source_id=payload.source_id,
            known_active_case_ids=payload.known_active_case_ids,
            context=_context(request),
        )
        overview = get_case(actor=request.auth_user, case_id=case.pk)
    except CounselingError as exc:
        _raise(exc)
    return Status(201, _detail(overview))


@router.get(
    "/opening-context",
    response=response_with_errors(CounselingCaseOpeningContextResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingGetCaseOpeningContext",
)
def counseling_get_case_opening_context(
    request,
    origin: CounselingCaseOrigin,
    student_id: UUID | None = None,
    source_id: UUID | None = None,
):
    _require_counselor(request, MANAGE_CAPABILITY)
    try:
        result = get_opening_context(
            actor=request.auth_user,
            origin=origin.value,
            student_id=student_id,
            source_id=source_id,
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "origin": result.origin,
        "student": {
            **_identity(result.student),
            "institutional_id": result.student.institutional_id,
        },
        "source": _source(
            appointment=result.appointment,
            encounter_id=result.encounter_id,
            routine_interview_id=result.routine_interview_id,
        ),
        "session": _candidate(result.session) if result.session is not None else None,
        "active_cases": [_summary(item) for item in result.active_cases],
    }


@router.get(
    "/{case_id}",
    response=response_with_errors(CounselingCaseDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="counselingGetCase",
)
def counseling_get_case(request, case_id: UUID):
    _require_counselor(request, VIEW_CAPABILITY)
    try:
        overview = get_case(actor=request.auth_user, case_id=case_id)
    except CounselingError as exc:
        _raise(exc)
    return _detail(overview)


@router.get(
    "/{case_id}/session-candidates",
    response=response_with_errors(CounselingCaseSessionCandidatePage, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingListCaseSessionCandidates",
)
def counseling_list_case_session_candidates(
    request,
    case_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_counselor(request, MANAGE_CAPABILITY)
    try:
        result = list_session_candidates(
            actor=request.auth_user, case_id=case_id, page=page, page_size=page_size
        )
    except CounselingError as exc:
        _raise(exc)
    return {
        "items": [_candidate(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.post(
    "/{case_id}/sessions",
    response=response_with_errors(CounselingCaseDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingLinkCaseSession",
)
def counseling_link_case_session(request, case_id: UUID, payload: CounselingCaseLinkSessionRequest):
    _require_counselor(request, MANAGE_CAPABILITY)
    try:
        link_session(
            actor=request.auth_user,
            case_id=case_id,
            encounter_id=payload.encounter_id,
            expected_version=payload.expected_version,
            context=_context(request),
        )
        overview = get_case(actor=request.auth_user, case_id=case_id)
    except CounselingError as exc:
        _raise(exc)
    return _detail(overview)


@router.post(
    "/{case_id}/sessions/{encounter_id}/unlink",
    response=response_with_errors(CounselingCaseDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="counselingUnlinkCaseSession",
)
def counseling_unlink_case_session(
    request,
    case_id: UUID,
    encounter_id: UUID,
    payload: CounselingCaseUnlinkSessionRequest,
):
    _require_counselor(request, MANAGE_CAPABILITY)
    try:
        unlink_session(
            actor=request.auth_user,
            case_id=case_id,
            encounter_id=encounter_id,
            reason=payload.reason.value,
            expected_version=payload.expected_version,
            context=_context(request),
        )
        overview = get_case(actor=request.auth_user, case_id=case_id)
    except CounselingError as exc:
        _raise(exc)
    return _detail(overview)
