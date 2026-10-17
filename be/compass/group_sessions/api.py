"""REST API endpoints and schemas for Group Sessions, Registrations, and Attendance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from compass.accounts.models import User
from compass.group_sessions.models import (
    GroupSession,
    GroupSessionAttendance,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.group_sessions.services import (
    cancel_group_session,
    cancel_student_registration,
    complete_group_session,
    create_group_session,
    delete_group_session,
    export_roster_csv,
    get_group_session_metrics,
    publish_group_session,
    record_attendance,
    register_student,
    update_group_session,
)
from compass.service_catalog.models import DeliveryMode

router = Router(tags=["group-sessions"])


# Schemas
class GroupSessionFacilitatorResponse(Schema):
    id: uuid.UUID
    counselor_id: uuid.UUID
    counselor_name: str
    is_lead: bool


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
    facilitators: list[GroupSessionFacilitatorResponse]
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
    facilitators: list[GroupSessionFacilitatorResponse]


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


class GroupSessionCancelRequest(Schema):
    reason: str


class GroupSessionRegistrationResponse(Schema):
    id: uuid.UUID
    session_id: uuid.UUID
    session_title: str
    student_id: uuid.UUID
    student_name: str
    student_email: str
    status: str
    registered_at: datetime
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
    capacity_utilization_percent: float
    attended_count: int
    absent_count: int
    attendance_rate_percent: float


# Helper functions
def _serialize_session(session: GroupSession) -> dict[str, Any]:
    active_count = session.registrations.filter(status=RegistrationStatus.REGISTERED).count()
    facilitators = [
        {
            "id": f.id,
            "counselor_id": f.counselor_id,
            "counselor_name": f.counselor.get_full_name() or f.counselor.email,
            "is_lead": f.is_lead,
        }
        for f in session.facilitators.select_related("counselor")
    ]
    return {
        "id": session.id,
        "service_id": session.service_id,
        "service_name": session.service.name,
        "title": session.title,
        "description": session.description,
        "delivery_mode": session.delivery_mode,
        "venue_or_meeting_url": session.venue_or_meeting_url,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "reg_opens_at": session.reg_opens_at,
        "reg_closes_at": session.reg_closes_at,
        "capacity": session.capacity,
        "active_registrations_count": active_count,
        "status": session.status,
        "organizer_id": session.organizer_id,
        "organizer_name": session.organizer.get_full_name() or session.organizer.email,
        "cancellation_reason": session.cancellation_reason,
        "cancelled_at": session.cancelled_at,
        "version": session.version,
        "facilitators": facilitators,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _check_staff_permission(user: User) -> None:
    role_code = getattr(getattr(user, "role", None), "code", None)
    if not (
        user.has_capability("services.manage")
        or user.has_capability("appointments.manage")
        or role_code in ("COUNSELOR", "SUPER_ADMIN", "IT_ADMIN")
    ):
        raise HttpError(403, "Staff authority required for Group Session management.")


# --- STATIC / UNPARAMETERIZED ROUTES FIRST ---


@router.get(
    "/discover",
    response={200: list[StudentGroupSessionResponse]},
    operation_id="groupSessionsDiscover",
    summary="List discoverable group sessions for students",
)
def discover_group_sessions(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
):
    user = request.user
    qs = (
        GroupSession.objects.filter(
            status=GroupSessionStatus.PUBLISHED,
            service__is_active=True,
            starts_at__gt=datetime.now(),
        )
        .select_related("service")
        .prefetch_related("facilitators__counselor", "registrations")
    )
    if service_id:
        qs = qs.filter(service_id=service_id)

    results = []
    for s in qs:
        active_count = s.registrations.filter(status=RegistrationStatus.REGISTERED).count()
        seats_remaining = max(0, s.capacity - active_count)
        is_registered = (
            user.is_authenticated
            and s.registrations.filter(
                student=user, status=RegistrationStatus.REGISTERED
            ).exists()
        )
        facs = [
            {
                "id": f.id,
                "counselor_id": f.counselor_id,
                "counselor_name": f.counselor.get_full_name() or f.counselor.email,
                "is_lead": f.is_lead,
            }
            for f in s.facilitators.all()
        ]
        results.append(
            {
                "id": s.id,
                "service_id": s.service_id,
                "service_name": s.service.name,
                "title": s.title,
                "description": s.description,
                "delivery_mode": s.delivery_mode,
                "venue_or_meeting_url": s.venue_or_meeting_url,
                "starts_at": s.starts_at,
                "ends_at": s.ends_at,
                "reg_opens_at": s.reg_opens_at,
                "reg_closes_at": s.reg_closes_at,
                "capacity": s.capacity,
                "seats_remaining": seats_remaining,
                "is_full": seats_remaining == 0,
                "is_registered_by_me": is_registered,
                "facilitators": facs,
            }
        )
    return 200, results


@router.get(
    "/metrics",
    response={200: GroupSessionMetricsResponse},
    operation_id="groupSessionsGetMetrics",
    summary="Get operational metrics for group sessions",
)
def get_metrics(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
):
    _check_staff_permission(request.user)
    data = get_group_session_metrics(
        service_id=service_id, from_date=from_date, to_date=to_date
    )
    return 200, data


@router.get(
    "/me/registrations",
    response={200: list[GroupSessionRegistrationResponse]},
    operation_id="groupSessionsGetMyRegistrations",
    summary="List current student's group session registrations",
)
def get_my_registrations(request: HttpRequest):
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required.")

    regs = (
        GroupSessionRegistration.objects.filter(student=request.user)
        .select_related("group_session", "student")
        .prefetch_related("attendance")
        .order_by("-registered_at")
    )
    results = []
    for r in regs:
        attended = r.attendance.attended if hasattr(r, "attendance") and r.attendance else None
        notes = r.attendance.notes if hasattr(r, "attendance") and r.attendance else None
        results.append(
            {
                "id": r.id,
                "session_id": r.group_session_id,
                "session_title": r.group_session.title,
                "student_id": r.student_id,
                "student_name": r.student.get_full_name() or r.student.email,
                "student_email": r.student.email or "",
                "status": r.status,
                "registered_at": r.registered_at,
                "cancelled_at": r.cancelled_at,
                "cancellation_reason": r.cancellation_reason,
                "attended": attended,
                "attendance_notes": notes,
            }
        )
    return 200, results


@router.get(
    "",
    response={200: list[GroupSessionResponse]},
    operation_id="groupSessionsListStaff",
    summary="List all group sessions for staff management",
)
def list_group_sessions(
    request: HttpRequest,
    service_id: uuid.UUID | None = None,
    status: str | None = None,
):
    _check_staff_permission(request.user)
    qs = GroupSession.objects.select_related("service", "organizer").prefetch_related(
        "facilitators__counselor", "registrations"
    )
    if service_id:
        qs = qs.filter(service_id=service_id)
    if status:
        qs = qs.filter(status=status)

    return 200, [_serialize_session(s) for s in qs]


# --- CREATION ROUTE ---


@router.post(
    "/create/{service_id}",
    response={201: GroupSessionResponse},
    operation_id="groupSessionsCreate",
    summary="Create a new group session",
)
def create_session(
    request: HttpRequest,
    service_id: uuid.UUID,
    data: GroupSessionCreateRequest,
):
    _check_staff_permission(request.user)
    try:
        session = create_group_session(
            service_id=service_id,
            organizer=request.user,
            title=data.title,
            description=data.description,
            delivery_mode=data.delivery_mode,
            venue_or_meeting_url=data.venue_or_meeting_url,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            reg_opens_at=data.reg_opens_at,
            reg_closes_at=data.reg_closes_at,
            facilitator_ids=data.facilitator_ids,
            lead_facilitator_id=data.lead_facilitator_id,
        )
        return 201, _serialize_session(session)
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


# --- PARAMETERIZED SESSION ROUTES ---


@router.get(
    "/{session_id}",
    response={200: GroupSessionResponse},
    operation_id="groupSessionsGetDetail",
    summary="Get group session details",
)
def get_session(request: HttpRequest, session_id: uuid.UUID):
    session = (
        GroupSession.objects.filter(id=session_id)
        .select_related("service", "organizer")
        .prefetch_related("facilitators__counselor", "registrations")
        .first()
    )
    if not session:
        raise HttpError(404, "Group session not found.")
    return 200, _serialize_session(session)


@router.patch(
    "/{session_id}",
    response={200: GroupSessionResponse},
    operation_id="groupSessionsUpdate",
    summary="Update a group session",
)
def update_session(
    request: HttpRequest,
    session_id: uuid.UUID,
    data: GroupSessionUpdateRequest,
):
    _check_staff_permission(request.user)
    try:
        session = update_group_session(
            session_id=session_id,
            actor=request.user,
            title=data.title,
            description=data.description,
            delivery_mode=data.delivery_mode,
            venue_or_meeting_url=data.venue_or_meeting_url,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            reg_opens_at=data.reg_opens_at,
            reg_closes_at=data.reg_closes_at,
            facilitator_ids=data.facilitator_ids,
            lead_facilitator_id=data.lead_facilitator_id,
        )
        return 200, _serialize_session(session)
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.post(
    "/{session_id}/publish",
    response={200: GroupSessionResponse},
    operation_id="groupSessionsPublish",
    summary="Publish a draft group session",
)
def publish_session(request: HttpRequest, session_id: uuid.UUID):
    _check_staff_permission(request.user)
    try:
        session = publish_group_session(session_id=session_id, actor=request.user)
        return 200, _serialize_session(session)
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.post(
    "/{session_id}/cancel",
    response={200: GroupSessionResponse},
    operation_id="groupSessionsCancel",
    summary="Cancel a group session",
)
def cancel_session(
    request: HttpRequest, session_id: uuid.UUID, data: GroupSessionCancelRequest
):
    _check_staff_permission(request.user)
    try:
        session = cancel_group_session(
            session_id=session_id, actor=request.user, reason=data.reason
        )
        return 200, _serialize_session(session)
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.post(
    "/{session_id}/complete",
    response={200: GroupSessionResponse},
    operation_id="groupSessionsComplete",
    summary="Complete a group session",
)
def complete_session(request: HttpRequest, session_id: uuid.UUID):
    _check_staff_permission(request.user)
    try:
        session = complete_group_session(session_id=session_id, actor=request.user)
        return 200, _serialize_session(session)
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.delete(
    "/{session_id}",
    response={204: None},
    operation_id="groupSessionsDelete",
    summary="Delete a draft group session",
)
def delete_session(request: HttpRequest, session_id: uuid.UUID):
    _check_staff_permission(request.user)
    try:
        delete_group_session(session_id=session_id, actor=request.user)
        return 204, None
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.post(
    "/{session_id}/register",
    response={201: GroupSessionRegistrationResponse},
    operation_id="groupSessionsRegister",
    summary="Student registers for a group session",
)
def register(request: HttpRequest, session_id: uuid.UUID):
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required.")
    try:
        reg = register_student(session_id=session_id, student=request.user)
        return 201, {
            "id": reg.id,
            "session_id": reg.group_session_id,
            "session_title": reg.group_session.title,
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
        raise HttpError(409, str(exc.message if hasattr(exc, "message") else exc))


@router.post(
    "/{session_id}/cancel-registration",
    response={200: GroupSessionRegistrationResponse},
    operation_id="groupSessionsCancelRegistration",
    summary="Student cancels their own registration",
)
def cancel_reg(request: HttpRequest, session_id: uuid.UUID):
    if not request.user.is_authenticated:
        raise HttpError(401, "Authentication required.")
    try:
        reg = cancel_student_registration(session_id=session_id, student=request.user)
        return 200, {
            "id": reg.id,
            "session_id": reg.group_session_id,
            "session_title": reg.group_session.title,
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
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.get(
    "/{session_id}/registrations",
    response={200: list[GroupSessionRegistrationResponse]},
    operation_id="groupSessionsListRegistrations",
    summary="List registrations and attendance for a group session",
)
def list_registrations(request: HttpRequest, session_id: uuid.UUID):
    _check_staff_permission(request.user)
    regs = (
        GroupSessionRegistration.objects.filter(group_session_id=session_id)
        .select_related("group_session", "student")
        .prefetch_related("attendance")
        .order_by("registered_at")
    )
    results = []
    for r in regs:
        attended = r.attendance.attended if hasattr(r, "attendance") and r.attendance else None
        notes = r.attendance.notes if hasattr(r, "attendance") and r.attendance else None
        results.append(
            {
                "id": r.id,
                "session_id": r.group_session_id,
                "session_title": r.group_session.title,
                "student_id": r.student_id,
                "student_name": r.student.get_full_name() or r.student.email,
                "student_email": r.student.email or "",
                "status": r.status,
                "registered_at": r.registered_at,
                "cancelled_at": r.cancelled_at,
                "cancellation_reason": r.cancellation_reason,
                "attended": attended,
                "attendance_notes": notes,
            }
        )
    return 200, results


@router.post(
    "/{session_id}/attendance",
    response={200: AttendanceBatchResponse},
    operation_id="groupSessionsRecordAttendance",
    summary="Record attendance for participants of a group session",
)
def record_session_attendance(
    request: HttpRequest,
    session_id: uuid.UUID,
    data: AttendanceBatchRequest,
):
    _check_staff_permission(request.user)
    try:
        attendances = record_attendance(
            session_id=session_id,
            actor=request.user,
            records=[r.dict() for r in data.records],
        )
        return 200, {"session_id": session_id, "updated_count": len(attendances)}
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))


@router.get(
    "/{session_id}/roster/export",
    operation_id="groupSessionsExportRoster",
    summary="Export participant roster CSV",
)
def export_roster(request: HttpRequest, session_id: uuid.UUID):
    _check_staff_permission(request.user)
    try:
        csv_data = export_roster_csv(session_id=session_id, actor=request.user)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="group-session-roster-{session_id}.csv"'
        )
        return response
    except ValidationError as exc:
        raise HttpError(400, str(exc.message if hasattr(exc, "message") else exc))
