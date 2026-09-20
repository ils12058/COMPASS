"""Thin Django Ninja API for Appointment reservation workflows."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from ninja import Header, Router, Schema
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import (
    IdempotencyConflict,
    IdempotencyOwnershipError,
    IdempotencyUnavailable,
    RedisIdempotencyStore,
    StoredResponse,
    request_fingerprint,
)
from compass.service_catalog.api import DeliveryMode

from .services import (
    DEFAULT_PAGE_SIZE,
    AppointmentCancellationConflict,
    AppointmentCurrentAcademicYearNotConfigured,
    AppointmentCurrentInventoryRequired,
    AppointmentCurrentStudentRequired,
    AppointmentDefaultProviderUnresolved,
    AppointmentError,
    AppointmentNotFound,
    AppointmentNotSchedulable,
    AppointmentReferenceConflict,
    AppointmentTimeConflict,
    AppointmentTimeUnavailable,
    InvalidAppointmentInput,
    cancel_appointment,
    create_student_appointment,
    get_appointment_for_actor,
    list_eligible_counselors,
    list_managed_appointments,
    list_my_appointments,
)

router = Router(tags=["appointments"])
BOOKING_ROUTE = "/api/v1/appointments"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AppointmentStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"


class AppointmentCreateRequest(StrictSchema):
    service_id: UUID
    provider_id: UUID | None = None
    delivery_mode: DeliveryMode
    starts_at: datetime


class ServiceSummaryResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class ProviderSummaryResponse(StrictSchema):
    id: UUID
    display_name: str


class AppointmentResponse(StrictSchema):
    id: UUID
    reference_code: str
    student_id: UUID
    service: ServiceSummaryResponse
    provider: ProviderSummaryResponse
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    cancellation_cutoff_minutes: int | None
    cancelled_at: datetime | None
    created_at: datetime


class AppointmentPageResponse(StrictSchema):
    items: list[AppointmentResponse]
    page: int
    page_size: int
    has_next: bool


class EligibleCounselorResponse(StrictSchema):
    id: UUID
    display_name: str
    is_default: bool


class EligibleCounselorListResponse(StrictSchema):
    items: list[EligibleCounselorResponse]


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _require_student_self_management(request) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT":
        raise APIError(403, "permission_denied", "Active Student self-service is required.")
    _require(request, "appointments.manage_self")


def _raise(exc: AppointmentError) -> NoReturn:
    if isinstance(exc, AppointmentCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, AppointmentCurrentAcademicYearNotConfigured):
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    if isinstance(exc, AppointmentCurrentInventoryRequired):
        raise APIError(409, "current_inventory_required", str(exc)) from exc
    if isinstance(exc, AppointmentNotFound):
        raise APIError(404, "appointment_not_found", str(exc)) from exc
    if isinstance(exc, InvalidAppointmentInput):
        raise APIError(422, "invalid_appointment_request", str(exc)) from exc
    if isinstance(exc, AppointmentDefaultProviderUnresolved):
        raise APIError(409, "appointment_default_provider_unresolved", str(exc)) from exc
    if isinstance(exc, AppointmentTimeUnavailable):
        raise APIError(409, "appointment_time_unavailable", str(exc)) from exc
    if isinstance(exc, AppointmentTimeConflict):
        raise APIError(409, "appointment_time_conflict", str(exc)) from exc
    if isinstance(exc, AppointmentCancellationConflict):
        message = str(exc)
        code = (
            "appointment_cancellation_cutoff_passed"
            if "cutoff" in message.lower()
            else "appointment_cancellation_conflict"
        )
        raise APIError(409, code, message) from exc
    if isinstance(exc, (AppointmentNotSchedulable, AppointmentReferenceConflict)):
        raise APIError(409, "appointment_not_schedulable", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Appointment operation could not be completed."
    ) from exc


def _institutional(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    from compass.appointments.services import _institution_zone

    return value.astimezone(_institution_zone())


def _appointment(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "student_id": item.student_id,
        "service": {
            "id": item.service_id,
            "code": item.service.code,
            "name": item.service.name,
        },
        "provider": {
            "id": item.provider_id,
            "display_name": item.provider.get_full_name(),
        },
        "delivery_mode": item.delivery_mode,
        "starts_at": _institutional(item.starts_at),
        "ends_at": _institutional(item.ends_at),
        "status": item.status,
        "cancellation_cutoff_minutes": item.cancellation_cutoff_minutes,
        "cancelled_at": _institutional(item.cancelled_at),
        "created_at": _institutional(item.created_at),
    }


def _json_response(payload: dict[str, object], *, status: int) -> JsonResponse:
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _complete_or_503(store, reservation, response: HttpResponse) -> None:
    try:
        store.complete(
            reservation,
            StoredResponse(
                status_code=response.status_code,
                body=bytes(response.content),
                content_type=response.get("Content-Type", "application/json"),
            ),
        )
    except (IdempotencyUnavailable, IdempotencyOwnershipError, ValueError) as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The booking replay boundary could not be completed safely.",
        ) from exc


def _abandon_or_503(store, reservation) -> None:
    try:
        store.abandon(reservation)
    except (IdempotencyUnavailable, IdempotencyOwnershipError) as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The booking replay boundary could not be released safely.",
        ) from exc


@router.get(
    "/me",
    response=response_with_errors(AppointmentPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="appointmentsListMy",
)
def appointments_list_my(
    request,
    status: AppointmentStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "appointments.view_self")
    try:
        result = list_my_appointments(
            actor=request.auth_user,
            status=status.value if status else None,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except AppointmentError as exc:
        _raise(exc)
    return {
        "items": [_appointment(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/booking/counselors",
    response=response_with_errors(EligibleCounselorListResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="appointmentsListEligibleCounselors",
)
def appointments_list_eligible_counselors(
    request,
    service_id: UUID,
    delivery_mode: DeliveryMode,
):
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT":
        raise APIError(403, "permission_denied", "Active Student booking access is required.")
    if not (
        user.has_capability("appointments.view_self")
        or user.has_capability("appointments.manage_self")
    ):
        raise APIError(403, "permission_denied", "Appointment self-service access is required.")
    try:
        rows = list_eligible_counselors(
            student=user,
            service_id=service_id,
            delivery_mode=delivery_mode.value,
        )
    except AppointmentError as exc:
        _raise(exc)
    return {
        "items": [
            {
                "id": row.user.pk,
                "display_name": row.user.get_full_name(),
                "is_default": row.is_default,
            }
            for row in rows
        ]
    }


@router.post(
    "",
    response=response_with_errors(
        AppointmentResponse,
        401,
        403,
        409,
        422,
        503,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="appointmentsCreateMy",
)
def appointments_create_my(
    request,
    payload: AppointmentCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_student_self_management(request)
    store = RedisIdempotencyStore.from_settings()
    fingerprint = request_fingerprint(
        method="POST",
        route=BOOKING_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        decision = store.begin(
            actor_id=str(request.auth_user.pk),
            method="POST",
            route=BOOKING_ROUTE,
            key=idempotency_key,
            fingerprint=fingerprint,
        )
    except ValueError as exc:
        raise APIError(422, "invalid_idempotency_key", str(exc)) from exc
    except IdempotencyConflict as exc:
        raise APIError(
            409,
            "idempotency_key_conflict",
            "The Idempotency-Key was already used for a different booking request.",
        ) from exc
    except IdempotencyUnavailable as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The booking replay boundary is temporarily unavailable.",
        ) from exc

    if decision.outcome == "replay":
        assert decision.response is not None
        return HttpResponse(
            decision.response.body,
            status=decision.response.status_code,
            content_type=decision.response.content_type,
        )
    if decision.outcome == "in_progress":
        raise APIError(
            409,
            "idempotency_in_progress",
            "A booking request with this Idempotency-Key is already in progress.",
        )
    assert decision.reservation is not None

    try:
        item = create_student_appointment(
            student=request.auth_user,
            service_id=payload.service_id,
            provider_id=payload.provider_id,
            delivery_mode=payload.delivery_mode.value,
            starts_at=payload.starts_at,
            context=_context(request),
        )
    except AppointmentError as exc:
        _abandon_or_503(store, decision.reservation)
        _raise(exc)

    response = _json_response(_appointment(item), status=201)
    _complete_or_503(store, decision.reservation, response)
    return response


@router.get(
    "",
    response=response_with_errors(AppointmentPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="appointmentsListManaged",
)
def appointments_list_managed(
    request,
    status: AppointmentStatus | None = None,
    student_id: UUID | None = None,
    provider_id: UUID | None = None,
    service_id: UUID | None = None,
    delivery_mode: DeliveryMode | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "appointments.manage")
    try:
        result = list_managed_appointments(
            actor=request.auth_user,
            status=status.value if status else None,
            student_id=student_id,
            provider_id=provider_id,
            service_id=service_id,
            delivery_mode=delivery_mode.value if delivery_mode else None,
            from_date=from_date,
            to_date=to_date,
            search=search,
            page=page,
            page_size=page_size,
        )
    except AppointmentError as exc:
        _raise(exc)
    return {
        "items": [_appointment(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{appointment_id}",
    response=response_with_errors(AppointmentResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="appointmentsGet",
)
def appointments_get(request, appointment_id: UUID):
    try:
        item = get_appointment_for_actor(appointment_id=appointment_id, actor=request.auth_user)
    except AppointmentError as exc:
        _raise(exc)
    return _appointment(item)


@router.post(
    "/{appointment_id}/cancel",
    response=response_with_errors(AppointmentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="appointmentsCancel",
)
def appointments_cancel(request, appointment_id: UUID):
    actor = request.auth_user
    self_mode = actor.role.code == "STUDENT" and actor.has_capability("appointments.manage_self")
    administrative = False
    if not self_mode:
        _require(request, "appointments.manage", recent_mfa=True)
        administrative = True
    try:
        item = cancel_appointment(
            appointment_id=appointment_id,
            actor=actor,
            administrative=administrative,
            context=_context(request),
        )
    except AppointmentError as exc:
        _raise(exc)
    return _appointment(item)
