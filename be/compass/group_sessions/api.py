"""REST API endpoints and schemas for Group Sessions, Registrations, and Attendance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, NoReturn

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from ninja import Router, Schema, Status

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.authentication.api import session_auth
from compass.authentication.step_up import require_recent_mfa_for_request
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.group_sessions.access import (
    current_group_session_staff,
    group_session_access,
    require_group_session_access,
    scope_group_sessions,
)
from compass.group_sessions.models import (
    GroupSession,
    GroupSessionFacilitatorKind,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.group_sessions.services import (
    cancel_group_session,
    cancel_student_registration,
    complete_group_session,
    create_group_session,
    export_roster_csv,
    get_group_session_metrics,
    list_group_facilitator_candidates,
    publish_group_session,
    record_attendance,
    register_student,
    update_group_session,
    withdraw_group_session,
)
from compass.service_catalog.models import BookingPathwayCode, DeliveryMode
from compass.service_catalog.scheduling import student_schedule_conflict
from compass.service_catalog.services import service_supports_delivery_mode

router = Router(tags=["group-sessions"])


# Schemas
class GroupSessionFacilitatorResponse(Schema):
    id: uuid.UUID
    kind: GroupSessionFacilitatorKind
    internal_user_id: uuid.UUID | None
    external_display_name: str
    display_name: str
    is_current: bool
    is_lead: bool
    # Compatibility fields remain populated only for internal facilitators.
    counselor_id: uuid.UUID | None
    counselor_name: str | None


class GroupSessionResponse(Schema):
    id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    title: str
    description: str
    delivery_mode: str
    venue_or_meeting_url: str
    starts_at: datetime
    ends_at: datetime
    reg_opens_at: datetime | None
    reg_closes_at: datetime | None
    capacity: int
    active_registrations_count: int
    status: str
    organizer_id: uuid.UUID
    organizer_name: str
    cancellation_reason: str
    cancelled_at: datetime | None
    version: int
    schedule_revision: int
    facilitators: list[GroupSessionFacilitatorResponse]
    can_view: bool
    can_manage: bool
    can_complete: bool
    can_access_participants: bool
    can_record_attendance: bool
    can_export_roster: bool
    created_at: datetime
    updated_at: datetime


class StudentGroupSessionResponse(Schema):
    id: uuid.UUID
    service_id: uuid.UUID
    service_name: str
    title: str
    description: str
    delivery_mode: str
    venue_or_meeting_url: str
    starts_at: datetime
    ends_at: datetime
    reg_opens_at: datetime | None
    reg_closes_at: datetime | None
    capacity: int
    seats_remaining: int
    is_full: bool
    is_registered_by_me: bool
    can_register: bool
    registration_block_reason: str | None
    facilitators: list[GroupSessionFacilitatorResponse]


class GroupSessionFacilitatorRequest(Schema):
    kind: GroupSessionFacilitatorKind
    internal_user_id: uuid.UUID | None = None
    external_display_name: str = ""
    is_lead: bool = False


class GroupSessionCreateRequest(Schema):
    title: str
    description: str = ""
    delivery_mode: DeliveryMode = DeliveryMode.IN_PERSON
    venue_or_meeting_url: str = ""
    starts_at: datetime
    ends_at: datetime
    capacity: int
    reg_opens_at: datetime | None = None
    reg_closes_at: datetime | None = None
    facilitator_ids: list[uuid.UUID] = []
    lead_facilitator_id: uuid.UUID | None = None
    facilitators: list[GroupSessionFacilitatorRequest] | None = None


class GroupSessionUpdateRequest(Schema):
    title: str | None = None
    description: str | None = None
    delivery_mode: DeliveryMode | None = None
    venue_or_meeting_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = None
    reg_opens_at: datetime | None = None
    reg_closes_at: datetime | None = None
    facilitator_ids: list[uuid.UUID] | None = None
    lead_facilitator_id: uuid.UUID | None = None
    facilitators: list[GroupSessionFacilitatorRequest] | None = None


class GroupSessionCancelRequest(Schema):
    reason: str


class GroupSessionWithdrawRequest(Schema):
    reason: str = ""


class GroupSessionRegistrationResponse(Schema):
    id: uuid.UUID
    session_id: uuid.UUID
    session_title: str
    service_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    student_id: uuid.UUID | None
    student_name: str
    student_email: str | None
    status: str
    registered_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str
    attended: bool | None
    attendance_notes: str | None


class AttendanceRecordInput(Schema):
    registration_id: uuid.UUID
    attended: bool
    notes: str = ""


class AttendanceBatchRequest(Schema):
    records: list[AttendanceRecordInput]


class AttendanceBatchResponse(Schema):
    session_id: uuid.UUID
    updated_count: int


class GroupSessionMetricsResponse(Schema):
    total_sessions: int
    published_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    total_capacity: int
    total_registrations: int
    cancelled_registrations: int
    attended_count: int
    absent_count: int
    capacity_utilization_percent: float
    attendance_rate_percent: float


class GroupSessionFacilitatorCandidate(Schema):
    id: uuid.UUID
    display_name: str
    role: str


def _is_staff_authorized(user: User) -> bool:
    return current_group_session_staff(user) is not None


def _require_staff(request: HttpRequest, *, recent_mfa: bool = False) -> User:
    user = request.auth_user
    if not _is_staff_authorized(user):
        raise APIError(
            403,
            "permission_denied",
            "Guidance staff authority with appointments.manage capability is required.",
        )
    if recent_mfa:
        require_recent_mfa_for_request(request)
    return user


def _require_student_view(request: HttpRequest) -> User:
    user = request.auth_user
    role_code = getattr(getattr(user, "role", None), "code", None)
    if not (
        user.is_active and role_code == "STUDENT" and user.has_capability("appointments.view_self")
    ):
        raise APIError(
            403,
            "permission_denied",
            "Student scheduling view authority is required.",
        )
    return user


def _require_student_manage(
    request: HttpRequest, *, require_current_lifecycle: bool = True
) -> User:
    user = request.auth_user
    role_code = getattr(getattr(user, "role", None), "code", None)
    if not (
        user.is_active
        and role_code == "STUDENT"
        and user.has_capability("appointments.manage_self")
    ):
        raise APIError(
            403,
            "permission_denied",
            "Student scheduling management authority is required.",
        )
    if require_current_lifecycle and not is_current_student(user):
        raise APIError(
            403,
            "current_student_required",
            "Current Student lifecycle is required for group session registration.",
        )
    return user


def _raise_group_session_error(exc: ValidationError, *, conflict_default: bool = False) -> NoReturn:
    msg = str(exc.message if hasattr(exc, "message") else exc)
    lowered = msg.lower()
    if "not found" in lowered or "does not exist" in lowered:
        raise APIError(404, "group_session_not_found", msg) from exc
    if conflict_default or any(
        token in lowered
        for token in (
            "already registered",
            "capacity",
            "full",
            "not open",
            "commenced",
            "closed",
            "cannot ",
            "only draft",
            "only published",
        )
    ):
        raise APIError(409, "group_session_conflict", msg) from exc
    raise APIError(422, "invalid_group_session_request", msg) from exc


def _serialize_session(
    session: GroupSession,
    *,
    actor: User | None = None,
    redact_for_unregistered: bool = False,
    active_registration: bool = True,
) -> dict[str, Any]:
    active_count = session.registrations.filter(status=RegistrationStatus.REGISTERED).count()
    access = group_session_access(actor, session) if actor is not None else None
    facilitator_rows = session.facilitators.select_related("internal_user")
    if (access is None and redact_for_unregistered) or (
        access is not None and not access.can_manage
    ):
        facilitator_rows = facilitator_rows.filter(removed_at__isnull=True)
    facilitators = [
        {
            "id": f.id,
            "kind": f.kind,
            "internal_user_id": f.internal_user_id,
            "external_display_name": f.external_display_name,
            "display_name": f.display_name
            or (f.internal_user.get_full_name() if f.internal_user_id else ""),
            "is_current": f.is_current,
            "is_lead": f.is_lead,
            "counselor_id": f.internal_user_id,
            "counselor_name": (
                f.display_name or f.internal_user.get_full_name() if f.internal_user_id else None
            ),
        }
        for f in facilitator_rows
    ]
    venue_or_url = session.venue_or_meeting_url
    if not active_registration and session.delivery_mode == DeliveryMode.ONLINE:
        venue_or_url = ""
    return {
        "id": session.id,
        "service_id": session.service_id,
        "service_name": session.service.name,
        "title": session.title,
        "description": session.description,
        "delivery_mode": session.delivery_mode,
        "venue_or_meeting_url": venue_or_url,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "reg_opens_at": session.reg_opens_at,
        "reg_closes_at": session.reg_closes_at,
        "capacity": session.capacity,
        "active_registrations_count": active_count,
        "status": session.status,
        "organizer_id": session.organizer_id,
        "organizer_name": session.organizer.get_full_name() or session.organizer.email,
        "cancellation_reason": "" if redact_for_unregistered else session.cancellation_reason,
        "cancelled_at": session.cancelled_at,
        "version": session.version,
        "schedule_revision": session.schedule_revision,
        "facilitators": facilitators,
        "can_view": bool(access and access.can_view),
        "can_manage": bool(access and access.can_manage),
        "can_complete": bool(
            access
            and access.can_manage
            and session.status == GroupSessionStatus.PUBLISHED
            and session.ends_at <= timezone.now()
        ),
        "can_access_participants": bool(access and access.can_access_participants),
        "can_record_attendance": bool(access and access.can_record_attendance),
        "can_export_roster": bool(access and access.can_export_roster),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


# --- STATIC / UNPARAMETERIZED ROUTES FIRST ---


@router.get(
    "/discover",
    response=response_with_errors(list[StudentGroupSessionResponse], 401, 403, 422),
    auth=session_auth,
    operation_id="groupSessionsDiscover",
    summary="List discoverable group sessions for students",
)
def discover_group_sessions(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
):
    user = _require_student_view(request)
    if not is_current_student(user):
        return []

    now = timezone.now()
    qs = (
        GroupSession.objects.filter(
            status=GroupSessionStatus.PUBLISHED,
            service__is_active=True,
            service__booking_pathways__code=BookingPathwayCode.GROUP_SESSION,
            starts_at__gt=now,
        )
        .select_related("service")
        .prefetch_related("facilitators__internal_user", "registrations")
        .distinct()
    )
    if service_id:
        qs = qs.filter(service_id=service_id)

    results = []
    for s in qs:
        active_count = s.registrations.filter(status=RegistrationStatus.REGISTERED).count()
        seats_remaining = max(0, s.capacity - active_count)
        is_registered = s.registrations.filter(
            student=user, status=RegistrationStatus.REGISTERED
        ).exists()
        registration_block_reason = None
        if not is_registered:
            if not service_supports_delivery_mode(s.service, s.delivery_mode):
                registration_block_reason = "Registration is unavailable for this delivery mode."
            elif s.reg_opens_at and s.reg_opens_at > now:
                registration_block_reason = "Registration has not opened yet."
            elif s.reg_closes_at and s.reg_closes_at < now:
                registration_block_reason = "Registration has closed."
            elif seats_remaining == 0:
                registration_block_reason = "This session is full."
            elif student_schedule_conflict(
                student_id=user.pk,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                exclude_group_session_id=s.pk,
            ):
                registration_block_reason = (
                    "This session overlaps another Appointment or registered Group Session."
                )
        facs = [
            {
                "id": f.id,
                "kind": f.kind,
                "internal_user_id": f.internal_user_id,
                "external_display_name": f.external_display_name,
                "display_name": f.display_name
                or (f.internal_user.get_full_name() if f.internal_user_id else ""),
                "is_current": True,
                "is_lead": f.is_lead,
                "counselor_id": f.internal_user_id,
                "counselor_name": (
                    f.display_name or f.internal_user.get_full_name()
                    if f.internal_user_id
                    else None
                ),
            }
            for f in s.facilitators.select_related("internal_user").filter(removed_at__isnull=True)
        ]
        venue_or_url = s.venue_or_meeting_url
        if s.delivery_mode == DeliveryMode.ONLINE and not is_registered:
            venue_or_url = ""
        results.append(
            {
                "id": s.id,
                "service_id": s.service_id,
                "service_name": s.service.name,
                "title": s.title,
                "description": s.description,
                "delivery_mode": s.delivery_mode,
                "venue_or_meeting_url": venue_or_url,
                "starts_at": s.starts_at,
                "ends_at": s.ends_at,
                "reg_opens_at": s.reg_opens_at,
                "reg_closes_at": s.reg_closes_at,
                "capacity": s.capacity,
                "seats_remaining": seats_remaining,
                "is_full": seats_remaining == 0,
                "is_registered_by_me": is_registered,
                "can_register": not is_registered and registration_block_reason is None,
                "registration_block_reason": registration_block_reason,
                "facilitators": facs,
            }
        )
    return results


@router.get(
    "/metrics",
    response=response_with_errors(GroupSessionMetricsResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="groupSessionsGetMetrics",
    summary="Get operational metrics for group sessions",
)
def get_metrics(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
):
    actor = _require_staff(request)
    return get_group_session_metrics(
        actor=actor,
        service_id=service_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/me/registrations",
    response=response_with_errors(list[GroupSessionRegistrationResponse], 401, 403),
    auth=session_auth,
    operation_id="groupSessionsGetMyRegistrations",
    summary="List current student's group session registrations",
)
def get_my_registrations(request: HttpRequest):
    student = _require_student_view(request)
    regs = (
        GroupSessionRegistration.objects.filter(student=student)
        .select_related("group_session__service", "student")
        .prefetch_related("attendance")
        .order_by("-registered_at")
    )
    results = []
    for r in regs:
        attended = r.attendance.attended if hasattr(r, "attendance") and r.attendance else None
        results.append(
            {
                "id": r.id,
                "session_id": r.group_session_id,
                "session_title": r.group_session.title,
                "service_id": r.group_session.service_id,
                "starts_at": r.group_session.starts_at,
                "ends_at": r.group_session.ends_at,
                "student_id": r.student_id,
                "student_name": r.student.get_full_name() or r.student.email,
                "student_email": r.student.email or "",
                "status": r.status,
                "registered_at": r.registered_at,
                "cancelled_at": r.cancelled_at,
                "cancellation_reason": r.cancellation_reason,
                "attended": attended,
                # Staff-authored attendance notes are never exposed to student self-service.
                "attendance_notes": None,
            }
        )
    return results


@router.get(
    "/facilitator-candidates",
    response=response_with_errors(list[GroupSessionFacilitatorCandidate], 401, 403, 422),
    auth=session_auth,
    operation_id="groupSessionsListFacilitatorCandidates",
    summary="List facilitator candidates within the actor's direct scope",
)
def list_facilitator_candidates(request: HttpRequest, search: str | None = None):
    actor = _require_staff(request)
    try:
        candidates = list_group_facilitator_candidates(actor=actor, search=search)
    except PermissionError as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
    except ValidationError as exc:
        _raise_group_session_error(exc)
    return [
        {
            "id": item.pk,
            "display_name": item.get_full_name() or item.email,
            "role": item.role.code,
        }
        for item in candidates
    ]


@router.get(
    "",
    response=response_with_errors(list[GroupSessionResponse], 401, 403, 422),
    auth=session_auth,
    operation_id="groupSessionsListStaff",
    summary="List all group sessions for staff management",
)
def list_group_sessions(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
    status: str | None = None,
):
    actor = _require_staff(request)
    qs = GroupSession.objects.select_related("service", "organizer").prefetch_related(
        "facilitators__internal_user", "registrations"
    )
    qs = scope_group_sessions(qs, actor, permission="view")
    if service_id:
        qs = qs.filter(service_id=service_id)
    if status:
        qs = qs.filter(status=status)

    return [_serialize_session(s, actor=actor) for s in qs]


# --- CREATION ROUTE ---


@router.post(
    "/create/{service_id}",
    response=response_with_errors(
        GroupSessionResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="groupSessionsCreate",
    summary="Create a new group session",
)
def create_session(
    request: HttpRequest,
    service_id: uuid.UUID,
    data: GroupSessionCreateRequest,
):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = create_group_session(
            service_id=service_id,
            organizer=actor,
            title=data.title,
            description=data.description,
            delivery_mode=data.delivery_mode,
            venue_or_meeting_url=data.venue_or_meeting_url,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            reg_opens_at=data.reg_opens_at,
            reg_closes_at=data.reg_closes_at,
            facilitators=(
                [item.model_dump() for item in data.facilitators]
                if data.facilitators is not None
                else None
            ),
            facilitator_ids=data.facilitator_ids,
            lead_facilitator_id=data.lead_facilitator_id,
        )
        return Status(201, _serialize_session(session, actor=actor))
    except ValidationError as exc:
        _raise_group_session_error(exc)


# --- PARAMETERIZED SESSION ROUTES ---


@router.get(
    "/{session_id}",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="groupSessionsGetDetail",
    summary="Get group session details",
)
def get_session(request: HttpRequest, session_id: uuid.UUID):
    user = request.auth_user
    is_staff = current_group_session_staff(user) is not None
    role_code = getattr(getattr(user, "role", None), "code", None)
    if not is_staff and not (
        user.is_active and role_code == "STUDENT" and user.has_capability("appointments.view_self")
    ):
        raise APIError(
            403,
            "permission_denied",
            "You do not have permission to view this group session.",
        )

    session = (
        GroupSession.objects.filter(id=session_id)
        .select_related("service", "organizer")
        .prefetch_related("facilitators__internal_user", "registrations")
        .first()
    )
    if not session:
        raise APIError(404, "group_session_not_found", "Group session not found.")

    if not is_staff:
        has_reg = session.registrations.filter(student=user).exists()
        is_active_reg = session.registrations.filter(
            student=user, status=RegistrationStatus.REGISTERED
        ).exists()
        if not has_reg and (
            session.status != GroupSessionStatus.PUBLISHED or not session.service.is_active
        ):
            raise APIError(404, "group_session_not_found", "Group session not found.")
        return _serialize_session(
            session,
            redact_for_unregistered=not has_reg,
            active_registration=is_active_reg,
        )

    if not group_session_access(user, session).can_view:
        raise APIError(404, "group_session_not_found", "Group session not found.")
    return _serialize_session(session, actor=user)


@router.patch(
    "/{session_id}",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsUpdate",
    summary="Update a group session",
)
def update_session(
    request: HttpRequest,
    session_id: uuid.UUID,
    data: GroupSessionUpdateRequest,
):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = update_group_session(
            session_id=session_id,
            actor=actor,
            title=data.title,
            description=data.description,
            delivery_mode=data.delivery_mode,
            venue_or_meeting_url=data.venue_or_meeting_url,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            reg_opens_at=data.reg_opens_at,
            reg_closes_at=data.reg_closes_at,
            reg_opens_at_provided="reg_opens_at" in data.model_fields_set,
            reg_closes_at_provided="reg_closes_at" in data.model_fields_set,
            facilitators=(
                [item.model_dump() for item in data.facilitators]
                if data.facilitators is not None
                else None
            ),
            facilitator_ids=data.facilitator_ids,
            lead_facilitator_id=data.lead_facilitator_id,
        )
        return _serialize_session(session, actor=actor)
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.post(
    "/{session_id}/publish",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsPublish",
    summary="Publish a draft group session",
)
def publish_session(request: HttpRequest, session_id: uuid.UUID):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = publish_group_session(session_id=session_id, actor=actor)
        return _serialize_session(session, actor=actor)
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.post(
    "/{session_id}/cancel",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsCancel",
    summary="Cancel a group session",
)
def cancel_session(request: HttpRequest, session_id: uuid.UUID, data: GroupSessionCancelRequest):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = cancel_group_session(session_id=session_id, actor=actor, reason=data.reason)
        return _serialize_session(session, actor=actor)
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.post(
    "/{session_id}/complete",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsComplete",
    summary="Complete a group session",
)
def complete_session(request: HttpRequest, session_id: uuid.UUID):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = complete_group_session(session_id=session_id, actor=actor)
        return _serialize_session(session, actor=actor)
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.post(
    "/{session_id}/withdraw",
    response=response_with_errors(GroupSessionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsWithdraw",
    summary="Withdraw a draft group session",
)
def withdraw_session(
    request: HttpRequest,
    session_id: uuid.UUID,
    data: GroupSessionWithdrawRequest,
):
    actor = _require_staff(request, recent_mfa=True)
    try:
        session = withdraw_group_session(
            session_id=session_id,
            actor=actor,
            reason=data.reason,
        )
        return _serialize_session(session, actor=actor)
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.post(
    "/{session_id}/register",
    response=response_with_errors(
        GroupSessionRegistrationResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    auth=session_auth,
    operation_id="groupSessionsRegister",
    summary="Student registers for a group session",
)
def register(request: HttpRequest, session_id: uuid.UUID):
    student = _require_student_manage(request, require_current_lifecycle=True)
    try:
        reg = register_student(session_id=session_id, student=student)
        return Status(
            201,
            {
                "id": reg.id,
                "session_id": reg.group_session_id,
                "session_title": reg.group_session.title,
                "service_id": reg.group_session.service_id,
                "starts_at": reg.group_session.starts_at,
                "ends_at": reg.group_session.ends_at,
                "student_id": reg.student_id,
                "student_name": reg.student.get_full_name() or reg.student.email,
                "student_email": reg.student.email or "",
                "status": reg.status,
                "registered_at": reg.registered_at,
                "cancelled_at": reg.cancelled_at,
                "cancellation_reason": reg.cancellation_reason,
                "attended": None,
                "attendance_notes": None,
            },
        )
    except ValidationError as exc:
        _raise_group_session_error(exc, conflict_default=True)


@router.post(
    "/{session_id}/cancel-registration",
    response=response_with_errors(GroupSessionRegistrationResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsCancelRegistration",
    summary="Student cancels their own registration",
)
def cancel_reg(request: HttpRequest, session_id: uuid.UUID):
    student = _require_student_manage(request, require_current_lifecycle=False)
    try:
        reg = cancel_student_registration(session_id=session_id, student=student)
        return {
            "id": reg.id,
            "session_id": reg.group_session_id,
            "session_title": reg.group_session.title,
            "service_id": reg.group_session.service_id,
            "starts_at": reg.group_session.starts_at,
            "ends_at": reg.group_session.ends_at,
            "student_id": reg.student_id,
            "student_name": reg.student.get_full_name() or reg.student.email,
            "student_email": reg.student.email or "",
            "status": reg.status,
            "registered_at": reg.registered_at,
            "cancelled_at": reg.cancelled_at,
            "cancellation_reason": reg.cancellation_reason,
            "attended": None,
            "attendance_notes": None,
        }
    except ValidationError as exc:
        _raise_group_session_error(exc, conflict_default=True)


@router.get(
    "/{session_id}/registrations",
    response=response_with_errors(list[GroupSessionRegistrationResponse], 401, 403, 404, 422),
    auth=session_auth,
    operation_id="groupSessionsListRegistrations",
    summary="List registrations and attendance for a group session",
)
def list_registrations(request: HttpRequest, session_id: uuid.UUID):
    actor = _require_staff(request)
    with transaction.atomic():
        session = (
            GroupSession.objects.filter(id=session_id)
            .select_related("service", "organizer__role")
            .first()
        )
        if session is None:
            raise APIError(404, "group_session_not_found", "Group session not found.")
        try:
            access = require_group_session_access(
                actor=actor,
                session=session,
                permission="can_access_participants",
                lock_supervision=True,
            )
        except ValidationError as exc:
            _raise_group_session_error(exc)
        regs = (
            GroupSessionRegistration.objects.filter(group_session_id=session_id)
            .select_related("group_session", "student")
            .prefetch_related("attendance")
            .order_by("registered_at")
        )
        if not access.can_manage:
            regs = regs.filter(status=RegistrationStatus.REGISTERED)
        results = []
        for r in regs:
            attended = r.attendance.attended if hasattr(r, "attendance") and r.attendance else None
            notes = r.attendance.notes if hasattr(r, "attendance") and r.attendance else None
            results.append(
                {
                    "id": r.id,
                    "session_id": r.group_session_id,
                    "session_title": r.group_session.title,
                    "service_id": r.group_session.service_id,
                    "starts_at": r.group_session.starts_at,
                    "ends_at": r.group_session.ends_at,
                    "student_id": r.student_id if access.can_manage else None,
                    "student_name": (
                        r.student.get_full_name()
                        or (r.student.email if access.can_manage else "Student")
                    ),
                    "student_email": (r.student.email or "") if access.can_manage else None,
                    "status": r.status,
                    "registered_at": r.registered_at if access.can_manage else None,
                    "cancelled_at": r.cancelled_at if access.can_manage else None,
                    "cancellation_reason": r.cancellation_reason if access.can_manage else "",
                    "attended": attended,
                    "attendance_notes": notes if access.can_manage else None,
                }
            )
        return results


@router.post(
    "/{session_id}/attendance",
    response=response_with_errors(AttendanceBatchResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="groupSessionsRecordAttendance",
    summary="Record attendance for participants of a group session",
)
def record_session_attendance(
    request: HttpRequest,
    session_id: uuid.UUID,
    data: AttendanceBatchRequest,
):
    actor = _require_staff(request, recent_mfa=True)
    try:
        attendances = record_attendance(
            session_id=session_id,
            actor=actor,
            records=[r.model_dump() for r in data.records],
        )
        return {"session_id": session_id, "updated_count": len(attendances)}
    except ValidationError as exc:
        _raise_group_session_error(exc)


@router.get(
    "/{session_id}/roster/export",
    auth=session_auth,
    response=response_with_errors(None, 401, 403, 404, 422),
    operation_id="groupSessionsExportRoster",
    summary="Export participant roster CSV",
    openapi_extra={
        "responses": {
            200: {"content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}}}
        }
    },
)
def export_roster(request: HttpRequest, session_id: uuid.UUID):
    actor = _require_staff(request)
    try:
        csv_data = export_roster_csv(session_id=session_id, actor=actor)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="group-session-roster-{session_id}.csv"'
        )
        return response
    except ValidationError as exc:
        _raise_group_session_error(exc)
