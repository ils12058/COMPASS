"""Privacy-bounded E-Counseling workspace, join, and Daily webhook APIs."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Router, Schema
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.integrations.daily import DailyWebhookSignatureInvalid

from .services import (
    ECounselingAppointmentNotEligible,
    ECounselingError,
    ECounselingInvalidProviderResponse,
    ECounselingInvalidWebhook,
    ECounselingJoinNotAvailable,
    ECounselingNotFound,
    ECounselingNotPermitted,
    ECounselingProviderDisabled,
    ECounselingProviderUnavailable,
    ECounselingRoomProvisioningFailed,
    create_join_credential,
    get_counselor_workspace,
    get_student_workspace,
    process_daily_webhook,
)

router = Router(tags=["e-counseling"])
daily_router = Router(tags=["e-counseling"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AppointmentWorkspaceSummary(StrictSchema):
    id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime
    status: str
    delivery_mode: str


class PersonWorkspaceSummary(StrictSchema):
    id: UUID
    display_name: str


class ProviderReadiness(StrictSchema):
    daily_enabled: bool
    room_provisioned: bool
    join_allowed: bool


class StudentRoutineWorkspaceSummary(StrictSchema):
    id: UUID
    intake_status: str


class CounselorRoutineWorkspaceSummary(StudentRoutineWorkspaceSummary):
    evaluation_status: str


class CounselingEncounterWorkspaceSummary(StrictSchema):
    id: UUID
    recorded: bool


class StudentWorkspaceResponse(StrictSchema):
    appointment: AppointmentWorkspaceSummary
    counselor: PersonWorkspaceSummary
    provider_readiness: ProviderReadiness
    routine_interview: StudentRoutineWorkspaceSummary | None


class CounselorWorkspaceResponse(StrictSchema):
    appointment: AppointmentWorkspaceSummary
    student: PersonWorkspaceSummary
    provider_readiness: ProviderReadiness
    routine_interview: CounselorRoutineWorkspaceSummary | None
    counseling_encounter: CounselingEncounterWorkspaceSummary | None


class JoinCredentialResponse(StrictSchema):
    provider: str
    room_url: str
    meeting_token: str
    token_expires_at: datetime
    appointment_id: UUID
    workspace_id: UUID


class WebhookAckResponse(StrictSchema):
    accepted: bool
    duplicate: bool = False


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _raise(exc: Exception) -> NoReturn:
    if isinstance(exc, ECounselingNotFound):
        raise APIError(404, "ecounseling_not_found", str(exc)) from exc
    if isinstance(exc, ECounselingNotPermitted):
        raise APIError(403, "ecounseling_not_permitted", str(exc)) from exc
    if isinstance(exc, ECounselingAppointmentNotEligible):
        raise APIError(409, "ecounseling_appointment_not_eligible", str(exc)) from exc
    if isinstance(exc, ECounselingJoinNotAvailable):
        raise APIError(409, "ecounseling_join_not_available", str(exc)) from exc
    if isinstance(exc, ECounselingProviderDisabled):
        raise APIError(503, "ecounseling_provider_disabled", str(exc)) from exc
    if isinstance(exc, ECounselingProviderUnavailable):
        raise APIError(503, "ecounseling_provider_unavailable", str(exc)) from exc
    if isinstance(exc, ECounselingRoomProvisioningFailed):
        raise APIError(502, "ecounseling_room_provisioning_failed", str(exc)) from exc
    if isinstance(exc, ECounselingInvalidProviderResponse):
        raise APIError(502, "ecounseling_invalid_provider_response", str(exc)) from exc
    if isinstance(exc, ECounselingInvalidWebhook):
        raise APIError(400, "daily_webhook_invalid_payload", str(exc)) from exc
    if isinstance(exc, DailyWebhookSignatureInvalid):
        raise APIError(403, "daily_webhook_signature_invalid", "Daily webhook signature is invalid.") from exc
    if isinstance(exc, ECounselingError):
        raise APIError(500, "internal_error", "The E-Counseling operation could not be completed.") from exc
    raise exc


@router.get(
    "/me/appointments/{appointment_id}",
    response=response_with_errors(StudentWorkspaceResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="eCounselingGetMyWorkspace",
)
def ecounseling_get_my_workspace(request, appointment_id: UUID):
    try:
        return get_student_workspace(student=request.auth_user, appointment_id=appointment_id)
    except ECounselingError as exc:
        _raise(exc)


@router.get(
    "/appointments/{appointment_id}",
    response=response_with_errors(CounselorWorkspaceResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="eCounselingGetAssignedWorkspace",
)
def ecounseling_get_assigned_workspace(request, appointment_id: UUID):
    try:
        return get_counselor_workspace(counselor=request.auth_user, appointment_id=appointment_id)
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/join",
    response=response_with_errors(JoinCredentialResponse, 401, 403, 404, 409, 502, 503),
    auth=session_auth,
    operation_id="eCounselingCreateJoinCredential",
)
def ecounseling_create_join_credential(
    request,
    appointment_id: UUID,
    response: HttpResponse,
):
    try:
        credential = create_join_credential(
            actor=request.auth_user,
            appointment_id=appointment_id,
            context=_context(request),
        )
    except ECounselingError as exc:
        _raise(exc)
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return {
        "provider": "DAILY",
        "room_url": credential.room_url,
        "meeting_token": credential.meeting_token,
        "token_expires_at": credential.token_expires_at,
        "appointment_id": appointment_id,
        "workspace_id": credential.room.pk,
    }


@daily_router.post(
    "/webhook",
    response=response_with_errors(WebhookAckResponse, 400, 403, 503),
    operation_id="eCounselingDailyWebhook",
)
def daily_webhook(request):
    try:
        result = process_daily_webhook(
            raw_body=request.body,
            signature=request.headers.get("X-Webhook-Signature"),
            timestamp=request.headers.get("X-Webhook-Timestamp"),
        )
    except (ECounselingError, DailyWebhookSignatureInvalid) as exc:
        _raise(exc)
    return {"accepted": result.accepted, "duplicate": result.duplicate}
