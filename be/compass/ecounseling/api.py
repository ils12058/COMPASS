"""Privacy-bounded E-Counseling workspace, consent, media, join, and Daily webhook APIs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Router, Schema
from pydantic import ConfigDict

from compass.appointments.api import AppointmentStatus
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.integrations.daily import DailyWebhookSignatureInvalid
from compass.routine_interviews.api import RoutineEvaluationStatus, RoutineIntakeStatus
from compass.service_catalog.api import DeliveryMode

from .media import (
    ECounselingConsentConflict,
    ECounselingConsentNotApproved,
    ECounselingConsentNotFound,
    ECounselingMediaConflict,
    ECounselingMediaStopPending,
    decide_my_consent,
    list_assigned_consents,
    list_my_consents,
    request_consents,
    start_recording,
    start_transcription,
    stop_recording,
    stop_transcription,
    withdraw_my_consent,
)
from .models import ConsentDecision, ConsentScope, MediaCaptureKind, MediaCaptureStatus
from .services import (
    ECounselingAppointmentNotEligible,
    ECounselingCurrentStudentRequired,
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


class ECounselingConsentScope(StrEnum):
    AUDIO_VIDEO_RECORDING = ConsentScope.AUDIO_VIDEO_RECORDING
    LIVE_TRANSCRIPTION = ConsentScope.LIVE_TRANSCRIPTION
    TRANSCRIPT_STORAGE = ConsentScope.TRANSCRIPT_STORAGE


class ECounselingConsentDecision(StrEnum):
    PENDING = ConsentDecision.PENDING
    APPROVED = ConsentDecision.APPROVED
    DENIED = ConsentDecision.DENIED


class ECounselingConsentStatus(StrEnum):
    """Workspace consent projection; WITHDRAWN derives from an approved, withdrawn decision."""

    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = ConsentDecision.PENDING
    APPROVED = ConsentDecision.APPROVED
    DENIED = ConsentDecision.DENIED
    WITHDRAWN = "WITHDRAWN"


class ECounselingMediaKind(StrEnum):
    RECORDING = MediaCaptureKind.RECORDING
    TRANSCRIPTION = MediaCaptureKind.TRANSCRIPTION


class ECounselingCaptureStatus(StrEnum):
    NOT_STARTED = MediaCaptureStatus.NOT_STARTED
    START_REQUESTED = MediaCaptureStatus.START_REQUESTED
    ACTIVE = MediaCaptureStatus.ACTIVE
    STOP_REQUESTED = MediaCaptureStatus.STOP_REQUESTED
    STOPPED = MediaCaptureStatus.STOPPED
    READY = MediaCaptureStatus.READY
    ERROR = MediaCaptureStatus.ERROR


class ECounselingProvider(StrEnum):
    DAILY = "DAILY"


class AppointmentWorkspaceSummary(StrictSchema):
    id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    delivery_mode: DeliveryMode


class PersonWorkspaceSummary(StrictSchema):
    id: UUID
    display_name: str


class ProviderReadiness(StrictSchema):
    daily_enabled: bool
    room_provisioned: bool
    join_allowed: bool


class StudentRoutineWorkspaceSummary(StrictSchema):
    id: UUID
    intake_status: RoutineIntakeStatus


class CounselorRoutineWorkspaceSummary(StudentRoutineWorkspaceSummary):
    evaluation_status: RoutineEvaluationStatus


class CounselingEncounterWorkspaceSummary(StrictSchema):
    id: UUID
    recorded: bool


class RecordingWorkspaceState(StrictSchema):
    consent_status: ECounselingConsentStatus
    capture_status: ECounselingCaptureStatus


class TranscriptionWorkspaceState(StrictSchema):
    consent_status: ECounselingConsentStatus
    storage_consent_status: ECounselingConsentStatus
    capture_status: ECounselingCaptureStatus
    storage_enabled: bool


class MediaWorkspaceState(StrictSchema):
    recording: RecordingWorkspaceState
    transcription: TranscriptionWorkspaceState


class StudentWorkspaceResponse(StrictSchema):
    appointment: AppointmentWorkspaceSummary
    counselor: PersonWorkspaceSummary
    provider_readiness: ProviderReadiness
    routine_interview: StudentRoutineWorkspaceSummary | None
    media: MediaWorkspaceState


class CounselorWorkspaceResponse(StrictSchema):
    appointment: AppointmentWorkspaceSummary
    student: PersonWorkspaceSummary
    provider_readiness: ProviderReadiness
    routine_interview: CounselorRoutineWorkspaceSummary | None
    counseling_encounter: CounselingEncounterWorkspaceSummary | None
    media: MediaWorkspaceState


class JoinCredentialResponse(StrictSchema):
    provider: ECounselingProvider
    room_url: str
    meeting_token: str
    token_expires_at: datetime
    appointment_id: UUID
    workspace_id: UUID


class ConsentResponse(StrictSchema):
    id: UUID
    scope: ECounselingConsentScope
    decision: ECounselingConsentDecision
    requested_at: datetime
    decided_at: datetime | None
    withdrawn_at: datetime | None
    effective: bool


class ConsentListResponse(StrictSchema):
    items: list[ConsentResponse]


class ConsentRequest(StrictSchema):
    scopes: list[ECounselingConsentScope]


class ConsentDecisionRequest(StrictSchema):
    decision: Literal["APPROVED", "DENIED"]


class TranscriptionStartRequest(StrictSchema):
    store_transcript: bool = False


class MediaCaptureResponse(StrictSchema):
    kind: ECounselingMediaKind
    status: ECounselingCaptureStatus
    storage_enabled: bool


class WebhookAckResponse(StrictSchema):
    accepted: bool
    duplicate: bool = False


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _raise(exc: Exception) -> NoReturn:
    if isinstance(exc, ECounselingCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, ECounselingConsentNotFound):
        raise APIError(404, "ecounseling_consent_not_found", str(exc)) from exc
    if isinstance(exc, ECounselingConsentNotApproved):
        raise APIError(409, "ecounseling_consent_not_approved", str(exc)) from exc
    if isinstance(exc, ECounselingConsentConflict):
        raise APIError(409, "ecounseling_consent_conflict", str(exc)) from exc
    if isinstance(exc, ECounselingMediaStopPending):
        raise APIError(409, "ecounseling_media_stop_pending", str(exc)) from exc
    if isinstance(exc, ECounselingMediaConflict):
        raise APIError(409, "ecounseling_media_conflict", str(exc)) from exc
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
        raise APIError(
            403, "daily_webhook_signature_invalid", "Daily webhook signature is invalid."
        ) from exc
    if isinstance(exc, ECounselingError):
        raise APIError(
            500, "internal_error", "The E-Counseling operation could not be completed."
        ) from exc
    raise exc


def _media_response(capture) -> dict[str, object]:
    return {
        "kind": capture.kind,
        "status": capture.status,
        "storage_enabled": bool(capture.transcript_storage_enabled),
    }


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


@router.get(
    "/me/appointments/{appointment_id}/consents",
    response=response_with_errors(ConsentListResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="eCounselingListMyConsents",
)
def ecounseling_list_my_consents(request, appointment_id: UUID):
    try:
        return {"items": list_my_consents(student=request.auth_user, appointment_id=appointment_id)}
    except ECounselingError as exc:
        _raise(exc)


@router.get(
    "/appointments/{appointment_id}/consents",
    response=response_with_errors(ConsentListResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="eCounselingListAssignedConsents",
)
def ecounseling_list_assigned_consents(request, appointment_id: UUID):
    try:
        return {
            "items": list_assigned_consents(
                counselor=request.auth_user,
                appointment_id=appointment_id,
            )
        }
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/consents",
    response=response_with_errors(ConsentListResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="eCounselingRequestConsent",
)
def ecounseling_request_consent(request, appointment_id: UUID, payload: ConsentRequest):
    try:
        items = request_consents(
            counselor=request.auth_user,
            appointment_id=appointment_id,
            scopes=[scope.value for scope in payload.scopes],
            context=_context(request),
        )
        return {"items": items}
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/me/appointments/{appointment_id}/consents/{consent_id}/decision",
    response=response_with_errors(ConsentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="eCounselingDecideMyConsent",
)
def ecounseling_decide_my_consent(
    request,
    appointment_id: UUID,
    consent_id: UUID,
    payload: ConsentDecisionRequest,
):
    try:
        return decide_my_consent(
            student=request.auth_user,
            appointment_id=appointment_id,
            consent_id=consent_id,
            decision=payload.decision,
            context=_context(request),
        )
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/me/appointments/{appointment_id}/consents/{consent_id}/withdraw",
    response=response_with_errors(ConsentResponse, 401, 403, 404, 409, 502, 503),
    auth=session_auth,
    operation_id="eCounselingWithdrawMyConsent",
)
def ecounseling_withdraw_my_consent(request, appointment_id: UUID, consent_id: UUID):
    try:
        return withdraw_my_consent(
            student=request.auth_user,
            appointment_id=appointment_id,
            consent_id=consent_id,
            context=_context(request),
        )
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/recording/start",
    response=response_with_errors(MediaCaptureResponse, 401, 403, 404, 409, 502, 503),
    auth=session_auth,
    operation_id="eCounselingStartAssignedRecording",
)
def ecounseling_start_assigned_recording(request, appointment_id: UUID):
    try:
        capture = start_recording(
            counselor=request.auth_user,
            appointment_id=appointment_id,
            context=_context(request),
        )
        return _media_response(capture)
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/recording/stop",
    response=response_with_errors(MediaCaptureResponse, 401, 403, 404, 409, 502, 503),
    auth=session_auth,
    operation_id="eCounselingStopAssignedRecording",
)
def ecounseling_stop_assigned_recording(request, appointment_id: UUID):
    try:
        capture = stop_recording(
            counselor=request.auth_user,
            appointment_id=appointment_id,
            context=_context(request),
        )
        return _media_response(capture)
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/transcription/start",
    response=response_with_errors(MediaCaptureResponse, 401, 403, 404, 409, 422, 502, 503),
    auth=session_auth,
    operation_id="eCounselingStartAssignedTranscription",
)
def ecounseling_start_assigned_transcription(
    request,
    appointment_id: UUID,
    payload: TranscriptionStartRequest,
):
    try:
        capture = start_transcription(
            counselor=request.auth_user,
            appointment_id=appointment_id,
            store_transcript=payload.store_transcript,
            context=_context(request),
        )
        return _media_response(capture)
    except ECounselingError as exc:
        _raise(exc)


@router.post(
    "/appointments/{appointment_id}/transcription/stop",
    response=response_with_errors(MediaCaptureResponse, 401, 403, 404, 409, 502, 503),
    auth=session_auth,
    operation_id="eCounselingStopAssignedTranscription",
)
def ecounseling_stop_assigned_transcription(request, appointment_id: UUID):
    try:
        capture = stop_transcription(
            counselor=request.auth_user,
            appointment_id=appointment_id,
            context=_context(request),
        )
        return _media_response(capture)
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
        "provider": ECounselingProvider.DAILY,
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
