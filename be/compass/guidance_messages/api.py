"""Small explicit HTTP API. No Redis request/response replay and no socket commands."""

from datetime import datetime
from functools import wraps
from uuid import UUID

from django.http import HttpResponse
from ninja import Router, Schema
from pydantic import ConfigDict, Field, StrictInt, StrictStr

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.operational_students import InvalidOperationalStudentQuery

from . import content, services
from .errors import (
    GuidanceMessageContentUnavailable,
    GuidanceMessagesError,
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    ThreadNotFound,
)
from .models import ThreadKind, ThreadStatus

router = Router(tags=["guidance-messages"], auth=session_auth)


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class GuidancePerson(StrictSchema):
    id: UUID
    display_name: str


class GuidanceCollege(StrictSchema):
    id: UUID
    code: str
    name: str


class GuidanceThreadResponse(StrictSchema):
    id: UUID
    kind: ThreadKind
    status: ThreadStatus
    student: GuidancePerson
    counselor: GuidancePerson | None
    routing_college: GuidanceCollege | None
    assigned_to: GuidancePerson | None
    relationship_appointment_id: UUID | None
    created_at: datetime
    last_message_at: datetime | None
    last_sequence: int
    own_last_read_sequence: int
    unread_count: int


class GuidanceThreadPage(StrictSchema):
    items: list[GuidanceThreadResponse]
    page: int
    page_size: int
    has_next: bool


class GuidanceMessageResponse(StrictSchema):
    id: UUID
    sequence: int
    sender: GuidancePerson
    body: str
    created_at: datetime


class GuidanceMessagePage(StrictSchema):
    items: list[GuidanceMessageResponse]
    has_older: bool


class GuidanceSendRequest(StrictSchema):
    client_message_id: UUID
    body: StrictStr = Field(min_length=1, max_length=content.BODY_LIMIT)


class GuidanceReadRequest(StrictSchema):
    sequence: StrictInt = Field(ge=0)


class GuidanceReadResponse(StrictSchema):
    own_last_read_sequence: int


class GuidanceAssignRequest(StrictSchema):
    handler_id: UUID


class GuidanceOpenResponse(StrictSchema):
    thread: GuidanceThreadResponse
    message: GuidanceMessageResponse


class GuidanceRelationshipOption(StrictSchema):
    appointment_id: UUID
    counselor: GuidancePerson
    starts_at: datetime


class GuidanceRecipientOptions(StrictSchema):
    office_label: str = "Guidance Office"
    counseling_relationships: list[GuidanceRelationshipOption]
    page: int
    page_size: int
    has_next: bool


class GuidanceStudentOption(GuidancePerson):
    institutional_id: str | None
    college: GuidanceCollege | None


class GuidanceStudentPage(StrictSchema):
    items: list[GuidanceStudentOption]
    page: int
    page_size: int
    has_next: bool


def _safe(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        response = kwargs.get("response")
        if response is not None:
            response["Cache-Control"] = "no-store, private"
        try:
            return function(*args, **kwargs)
        except (GuidanceMessagesError, InvalidOperationalStudentQuery) as exc:
            if isinstance(exc, ThreadNotFound):
                status, code = 404, "guidance_thread_not_found"
            elif isinstance(exc, MessagesPermissionDenied):
                status, code = 403, "permission_denied"
            elif isinstance(exc, MessagesConflict):
                status, code = 409, "guidance_messages_conflict"
            elif isinstance(exc, (InvalidMessageInput, InvalidOperationalStudentQuery)):
                status, code = 422, "invalid_guidance_message_input"
            elif isinstance(exc, GuidanceMessageContentUnavailable):
                status, code = 503, "guidance_message_content_unavailable"
            else:
                status, code = 500, "internal_error"
            raise APIError(
                status, code, str(exc), headers={"Cache-Control": "no-store, private"}
            ) from None

    return wrapped


def _person(user):
    return GuidancePerson(id=user.pk, display_name=user.get_full_name()) if user else None


def _thread(thread, actor):
    return GuidanceThreadResponse(
        id=thread.pk,
        kind=thread.kind,
        status=thread.status,
        student=_person(thread.student),
        counselor=_person(thread.counselor),
        routing_college=(
            GuidanceCollege(
                id=thread.routing_college_id,
                code=thread.routing_college.code,
                name=thread.routing_college.name,
            )
            if thread.routing_college_id and actor.role.code != "STUDENT"
            else None
        ),
        assigned_to=_person(thread.assigned_to),
        relationship_appointment_id=thread.relationship_appointment_id,
        created_at=thread.created_at,
        last_message_at=thread.last_message_at,
        last_sequence=thread.last_sequence,
        own_last_read_sequence=thread.own_last_read_sequence,
        unread_count=thread.own_unread_count,
    )


def _message(message):
    return GuidanceMessageResponse(
        id=message.pk,
        sequence=message.sequence,
        sender=_person(message.sender),
        body=content.read_body(message),
        created_at=message.created_at,
    )


def _open(result, actor):
    thread, message = result
    return GuidanceOpenResponse(
        thread=_thread(services.get_thread(actor=actor, thread_id=thread.pk), actor),
        message=_message(message),
    )


ERRORS = (401, 403, 404, 409, 422, 503)


@router.get(
    "/threads",
    response=response_with_errors(GuidanceThreadPage, *ERRORS),
    operation_id="guidanceMessagesListThreads",
)
@_safe
def list_threads(request, response: HttpResponse, page: int = 1, page_size: int = 20):
    rows, has_next = services.list_threads(actor=request.auth_user, page=page, page_size=page_size)
    return GuidanceThreadPage(
        items=[_thread(row, request.auth_user) for row in rows],
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get(
    "/recipient-options",
    response=response_with_errors(GuidanceRecipientOptions, *ERRORS),
    operation_id="guidanceMessagesRecipientOptions",
)
@_safe
def recipient_options(request, response: HttpResponse, page: int = 1, page_size: int = 20):
    rows, has_next = services.recipient_options(
        actor=request.auth_user, page=page, page_size=page_size
    )
    return GuidanceRecipientOptions(
        counseling_relationships=[
            GuidanceRelationshipOption(
                appointment_id=row.pk, counselor=_person(row.provider), starts_at=row.starts_at
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get(
    "/eligible-students",
    response=response_with_errors(GuidanceStudentPage, *ERRORS),
    operation_id="guidanceMessagesEligibleStudents",
)
@_safe
def eligible_students(
    request, response: HttpResponse, search: str | None = None, page: int = 1, page_size: int = 20
):
    result = services.eligible_students(
        actor=request.auth_user, search=search, page=page, page_size=page_size
    )
    return GuidanceStudentPage(
        items=[
            GuidanceStudentOption(
                id=item.id,
                display_name=item.display_name,
                institutional_id=item.institutional_id,
                college=GuidanceCollege(
                    id=item.college.id, code=item.college.code, name=item.college.name
                )
                if item.college
                else None,
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.post(
    "/office-thread",
    response=response_with_errors(GuidanceOpenResponse, *ERRORS),
    operation_id="guidanceMessagesOpenMyOfficeThread",
)
@_safe
def open_my_office(request, response: HttpResponse, payload: GuidanceSendRequest):
    if request.auth_user.role.code != "STUDENT":
        raise MessagesPermissionDenied()
    return _open(
        services.open_office_thread(
            actor=request.auth_user,
            **payload.model_dump(),
            context=AuditContext.from_request(request, actor=request.auth_user),
        ),
        request.auth_user,
    )


@router.post(
    "/students/{student_id}/office-thread",
    response=response_with_errors(GuidanceOpenResponse, *ERRORS),
    operation_id="guidanceMessagesOpenStudentOfficeThread",
)
@_safe
def open_student_office(
    request, response: HttpResponse, student_id: UUID, payload: GuidanceSendRequest
):
    return _open(
        services.open_office_thread(
            actor=request.auth_user,
            student_id=student_id,
            **payload.model_dump(),
            context=AuditContext.from_request(request, actor=request.auth_user),
        ),
        request.auth_user,
    )


@router.post(
    "/appointments/{appointment_id}/counseling-thread",
    response=response_with_errors(GuidanceOpenResponse, *ERRORS),
    operation_id="guidanceMessagesOpenCounselingThread",
)
@_safe
def open_counseling(
    request, response: HttpResponse, appointment_id: UUID, payload: GuidanceSendRequest
):
    return _open(
        services.open_counseling_thread(
            actor=request.auth_user,
            appointment_id=appointment_id,
            **payload.model_dump(),
            context=AuditContext.from_request(request, actor=request.auth_user),
        ),
        request.auth_user,
    )


@router.get(
    "/threads/{thread_id}",
    response=response_with_errors(GuidanceThreadResponse, *ERRORS),
    operation_id="guidanceMessagesGetThread",
)
@_safe
def get_thread(request, response: HttpResponse, thread_id: UUID):
    return _thread(
        services.get_thread(actor=request.auth_user, thread_id=thread_id), request.auth_user
    )


@router.get(
    "/threads/{thread_id}/messages",
    response=response_with_errors(GuidanceMessagePage, *ERRORS),
    operation_id="guidanceMessagesListMessages",
)
@_safe
def list_messages(
    request,
    response: HttpResponse,
    thread_id: UUID,
    before_sequence: int | None = None,
    page_size: int = 20,
):
    rows, has_older = services.list_messages(
        actor=request.auth_user,
        thread_id=thread_id,
        before_sequence=before_sequence,
        page_size=page_size,
    )
    return GuidanceMessagePage(items=[_message(row) for row in rows], has_older=has_older)


@router.post(
    "/threads/{thread_id}/messages",
    response=response_with_errors(GuidanceMessageResponse, *ERRORS),
    operation_id="guidanceMessagesSendMessage",
)
@_safe
def send_message(request, response: HttpResponse, thread_id: UUID, payload: GuidanceSendRequest):
    return _message(
        services.send_message(
            actor=request.auth_user,
            thread_id=thread_id,
            **payload.model_dump(),
            context=AuditContext.from_request(request, actor=request.auth_user),
        )
    )


@router.patch(
    "/threads/{thread_id}/read",
    response=response_with_errors(GuidanceReadResponse, *ERRORS),
    operation_id="guidanceMessagesMarkRead",
)
@_safe
def mark_read(request, response: HttpResponse, thread_id: UUID, payload: GuidanceReadRequest):
    state = services.mark_read(
        actor=request.auth_user, thread_id=thread_id, sequence=payload.sequence
    )
    return GuidanceReadResponse(own_last_read_sequence=state.last_read_sequence)


@router.post(
    "/threads/{thread_id}/resolve",
    response=response_with_errors(GuidanceThreadResponse, *ERRORS),
    operation_id="guidanceMessagesResolveThread",
)
@_safe
def resolve(request, response: HttpResponse, thread_id: UUID):
    services.set_status(
        actor=request.auth_user,
        thread_id=thread_id,
        resolved=True,
        context=AuditContext.from_request(request, actor=request.auth_user),
    )
    return _thread(
        services.get_thread(actor=request.auth_user, thread_id=thread_id), request.auth_user
    )


@router.post(
    "/threads/{thread_id}/reopen",
    response=response_with_errors(GuidanceThreadResponse, *ERRORS),
    operation_id="guidanceMessagesReopenThread",
)
@_safe
def reopen(request, response: HttpResponse, thread_id: UUID):
    services.set_status(
        actor=request.auth_user,
        thread_id=thread_id,
        resolved=False,
        context=AuditContext.from_request(request, actor=request.auth_user),
    )
    return _thread(
        services.get_thread(actor=request.auth_user, thread_id=thread_id), request.auth_user
    )


@router.patch(
    "/threads/{thread_id}/handler",
    response=response_with_errors(GuidanceThreadResponse, *ERRORS),
    operation_id="guidanceMessagesAssignHandler",
)
@_safe
def assign_handler(
    request, response: HttpResponse, thread_id: UUID, payload: GuidanceAssignRequest
):
    services.assign_handler(
        actor=request.auth_user,
        thread_id=thread_id,
        handler_id=payload.handler_id,
        context=AuditContext.from_request(request, actor=request.auth_user),
    )
    return _thread(
        services.get_thread(actor=request.auth_user, thread_id=thread_id), request.auth_user
    )
