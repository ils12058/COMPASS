"""Session-scoped E-Counseling consent and Daily media-control services."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.appointments.models import Appointment
from compass.audit.actions import (
    ECOUNSELING_CONSENT_APPROVED,
    ECOUNSELING_CONSENT_DENIED,
    ECOUNSELING_CONSENT_REQUESTED,
    ECOUNSELING_CONSENT_WITHDRAWN,
    ECOUNSELING_RECORDING_START_REQUESTED,
    ECOUNSELING_RECORDING_STOP_REQUESTED,
    ECOUNSELING_TRANSCRIPTION_START_REQUESTED,
    ECOUNSELING_TRANSCRIPTION_STOP_REQUESTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.integrations.daily import (
    DailyClient,
    DailyConfigurationError,
    DailyHTTPError,
    DailyInvalidResponse,
    DailyUnavailable,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.service_catalog.models import DeliveryMode

from .models import (
    ConsentDecision,
    ConsentScope,
    DailyWebhookReceipt,
    ECounselingConsent,
    ECounselingMediaCapture,
    ECounselingRoom,
    MediaCaptureKind,
    MediaCaptureStatus,
)
from .services import (
    ECounselingAppointmentNotEligible,
    ECounselingCurrentStudentRequired,
    ECounselingError,
    ECounselingNotFound,
    ECounselingProviderDisabled,
    ECounselingProviderUnavailable,
    WebhookProcessingResult,
    _appointment_queryset,
    _ensure_local_room_binding,
    _join_window_open,
    _load_eligible_appointment,
    _provider_failure,
    _require_counselor_relationship,
    _require_student_relationship,
)

logger = logging.getLogger("compass.ecounseling.media")

MEDIA_WEBHOOK_TYPES = frozenset(
    {
        "recording.started",
        "recording.ready-to-download",
        "recording.error",
        "transcript.started",
        "transcript.ready-to-download",
        "transcript.error",
    }
)


# A late or duplicate "started" delivery must not regress a capture that is already stopping,
# stopped, or finished (ADR-026). STOP_REQUESTED stays pending until provider reconciliation.
_NO_REGRESSION_TO_ACTIVE = frozenset(
    {
        MediaCaptureStatus.STOP_REQUESTED,
        MediaCaptureStatus.STOPPED,
        MediaCaptureStatus.READY,
    }
)


class ECounselingConsentNotFound(ECounselingError):
    pass


class ECounselingConsentConflict(ECounselingError):
    pass


class ECounselingConsentNotApproved(ECounselingError):
    pass


class ECounselingMediaConflict(ECounselingError):
    pass


class ECounselingMediaStopPending(ECounselingError):
    pass


def _load_session_appointment(appointment_id: UUID) -> Appointment:
    """Load historical session ownership without re-applying current start eligibility."""

    appointment = _appointment_queryset().filter(pk=appointment_id).first()
    if appointment is None:
        raise ECounselingNotFound("The requested E-Counseling Appointment was not found.")
    if appointment.delivery_mode != DeliveryMode.ONLINE or appointment.service.code != "COUNSELING":
        raise ECounselingAppointmentNotEligible("The Appointment is not ONLINE Counseling.")
    return appointment


def _require_room_for_appointment(appointment: Appointment) -> ECounselingRoom:
    room = ECounselingRoom.objects.filter(appointment_id=appointment.pk).first()
    if room is None:
        raise ECounselingMediaConflict("The E-Counseling room has not been provisioned.")
    return room


def _require_provisioned_room(appointment: Appointment) -> ECounselingRoom:
    room = _require_room_for_appointment(appointment)
    if not room.provisioned_at or not room.daily_room_url:
        raise ECounselingMediaConflict("The Daily room is not provisioned for media control.")
    return room


def effective_consent(consent: ECounselingConsent | None) -> bool:
    return bool(consent and consent.is_effectively_approved)


def _consent_status(consent: ECounselingConsent | None) -> str:
    if consent is None:
        return "NOT_REQUESTED"
    if consent.withdrawn_at is not None:
        return "WITHDRAWN"
    return consent.decision


def _consent_dict(consent: ECounselingConsent) -> dict[str, object]:
    return {
        "id": consent.pk,
        "scope": consent.scope,
        "decision": consent.decision,
        "requested_at": consent.requested_at,
        "decided_at": consent.decided_at,
        "withdrawn_at": consent.withdrawn_at,
        "effective": consent.is_effectively_approved,
    }


def get_media_projection(room: ECounselingRoom | None) -> dict[str, object]:
    consents: dict[str, ECounselingConsent] = {}
    captures: dict[str, ECounselingMediaCapture] = {}
    if room is not None:
        consents = {item.scope: item for item in room.consents.all()}
        captures = {item.kind: item for item in room.media_captures.all()}
    recording = captures.get(MediaCaptureKind.RECORDING)
    transcription = captures.get(MediaCaptureKind.TRANSCRIPTION)
    return {
        "recording": {
            "consent_status": _consent_status(consents.get(ConsentScope.AUDIO_VIDEO_RECORDING)),
            "capture_status": (
                recording.status if recording is not None else MediaCaptureStatus.NOT_STARTED
            ),
        },
        "transcription": {
            "consent_status": _consent_status(consents.get(ConsentScope.LIVE_TRANSCRIPTION)),
            "storage_consent_status": _consent_status(
                consents.get(ConsentScope.TRANSCRIPT_STORAGE)
            ),
            "capture_status": (
                transcription.status
                if transcription is not None
                else MediaCaptureStatus.NOT_STARTED
            ),
            "storage_enabled": bool(transcription and transcription.transcript_storage_enabled),
        },
    }


def list_my_consents(*, student: User, appointment_id: UUID) -> list[dict[str, object]]:
    appointment = _load_session_appointment(appointment_id)
    _require_student_relationship(
        actor=student,
        appointment=appointment,
        capability="ecounseling.consent_self",
    )
    room = ECounselingRoom.objects.filter(appointment_id=appointment.pk).first()
    if room is None:
        return []
    return [_consent_dict(item) for item in room.consents.order_by("requested_at", "id")]


def list_assigned_consents(*, counselor: User, appointment_id: UUID) -> list[dict[str, object]]:
    appointment = _load_session_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )
    room = ECounselingRoom.objects.filter(appointment_id=appointment.pk).first()
    if room is None:
        return []
    return [_consent_dict(item) for item in room.consents.order_by("requested_at", "id")]


def request_consents(
    *,
    counselor: User,
    appointment_id: UUID,
    scopes: list[str],
    context: AuditContext,
) -> list[dict[str, object]]:
    if not scopes:
        raise ECounselingConsentConflict("At least one consent scope is required.")
    if len(scopes) != len(set(scopes)):
        raise ECounselingConsentConflict("Duplicate consent scopes are not allowed.")
    unsupported = set(scopes) - set(ConsentScope.values)
    if unsupported:
        raise ECounselingConsentConflict("One or more consent scopes are not supported.")

    appointment = _load_eligible_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )

    # Consent needs a stable session anchor before either participant necessarily joins.
    # This creates only the local opaque binding; remote Daily provisioning remains join-driven.
    room = _ensure_local_room_binding(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        existing = {
            item.scope: item
            for item in ECounselingConsent.objects.select_for_update().filter(room=locked_room)
        }

        if ConsentScope.TRANSCRIPT_STORAGE in scopes:
            live = existing.get(ConsentScope.LIVE_TRANSCRIPTION)
            live_requested_together = ConsentScope.LIVE_TRANSCRIPTION in scopes
            existing_live_usable = bool(
                live and live.decision != ConsentDecision.DENIED and live.withdrawn_at is None
            )
            if not live_requested_together and not existing_live_usable:
                raise ECounselingConsentConflict(
                    "Transcript storage consent requires a live transcription consent request."
                )

        for scope in scopes:
            current = existing.get(scope)
            if current and (
                current.decision == ConsentDecision.DENIED or current.withdrawn_at is not None
            ):
                raise ECounselingConsentConflict(
                    "A denied or withdrawn consent scope cannot be reopened for this session."
                )

        result: list[ECounselingConsent] = []
        newly_created: list[ECounselingConsent] = []
        for scope in scopes:
            current = existing.get(scope)
            if current is not None:
                result.append(current)
                continue
            current = ECounselingConsent.objects.create(
                room=locked_room,
                scope=scope,
                requested_by=counselor,
            )
            record_event(
                context=context,
                action=ECOUNSELING_CONSENT_REQUESTED,
                outcome=AuditOutcome.SUCCESS,
                target_type="ecounseling.consent",
                target_id=current.pk,
                metadata={
                    "appointment_id": str(appointment.pk),
                    "room_id": str(locked_room.pk),
                    "scope": scope,
                },
            )
            newly_created.append(current)
            result.append(current)

        if newly_created:
            create_notification_for_event(
                recipient=appointment.student,
                event=NotificationEvent.ECOUNSELING_CONSENT_REQUESTED,
                source_type="ecounseling_consent",
                source_id=newly_created[0].pk,
                target_type="E_COUNSELING",
                target_id=appointment.pk,
            )
        return [_consent_dict(item) for item in result]


def decide_my_consent(
    *,
    student: User,
    appointment_id: UUID,
    consent_id: UUID,
    decision: str,
    context: AuditContext,
) -> dict[str, object]:
    if decision not in {ConsentDecision.APPROVED, ConsentDecision.DENIED}:
        raise ECounselingConsentConflict("Consent decision must be APPROVED or DENIED.")
    appointment = _load_session_appointment(appointment_id)
    _require_student_relationship(
        actor=student,
        appointment=appointment,
        capability="ecounseling.consent_self",
    )
    if decision == ConsentDecision.APPROVED and not is_current_student(student):
        raise ECounselingCurrentStudentRequired(
            "Current Student lifecycle is required to approve E-Counseling consent."
        )
    room = _require_room_for_appointment(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        consent = (
            ECounselingConsent.objects.select_for_update()
            .filter(pk=consent_id, room=locked_room)
            .first()
        )
        if consent is None:
            raise ECounselingConsentNotFound("The requested consent was not found.")
        if consent.decision != ConsentDecision.PENDING or consent.withdrawn_at is not None:
            raise ECounselingConsentConflict("This consent has already been decided.")
        consent.decision = decision
        consent.decided_at = timezone.now()
        consent.save(update_fields=["decision", "decided_at", "updated_at"])
        record_event(
            context=context,
            action=(
                ECOUNSELING_CONSENT_APPROVED
                if decision == ConsentDecision.APPROVED
                else ECOUNSELING_CONSENT_DENIED
            ),
            outcome=AuditOutcome.SUCCESS,
            target_type="ecounseling.consent",
            target_id=consent.pk,
            metadata={
                "appointment_id": str(appointment.pk),
                "room_id": str(locked_room.pk),
                "scope": consent.scope,
                "decision": decision,
            },
        )
        return _consent_dict(consent)


def _daily_client(daily_client: DailyClient | None) -> DailyClient:
    if not settings.DAILY_ENABLED:
        raise ECounselingProviderDisabled("Daily E-Counseling is disabled.")
    if daily_client is not None:
        return daily_client
    try:
        return DailyClient.from_settings()
    except DailyConfigurationError as exc:
        raise ECounselingProviderUnavailable("Daily is not configured correctly.") from exc


def _provider_ack(payload: dict[str, object]) -> None:
    if payload.get("status") == "sent" or payload.get("sent") in {True, "true"}:
        return
    raise DailyInvalidResponse("Daily did not acknowledge the media command.")


def _set_provider_uncertain(capture_id: UUID, *, code: str) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        capture.error_code = code
        capture.save(update_fields=["error_code", "updated_at"])


def _set_known_start_failure(capture_id: UUID) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status == MediaCaptureStatus.START_REQUESTED:
            capture.status = MediaCaptureStatus.ERROR
            capture.failed_at = timezone.now()
            capture.error_code = "PROVIDER_REJECTED"
            capture.save(update_fields=["status", "failed_at", "error_code", "updated_at"])


def _handle_start_provider_failure(capture_id: UUID, exc: Exception) -> None:
    if isinstance(exc, DailyHTTPError):
        _set_known_start_failure(capture_id)
    else:
        _set_provider_uncertain(capture_id, code="PROVIDER_STATE_UNCERTAIN")
    raise _provider_failure(exc) from exc


def _require_effective_consent_locked(
    *,
    room: ECounselingRoom,
    scope: str,
) -> ECounselingConsent:
    consent = ECounselingConsent.objects.select_for_update().filter(room=room, scope=scope).first()
    if not effective_consent(consent):
        raise ECounselingConsentNotApproved(
            "Effective Student consent is required for this media operation."
        )
    assert consent is not None
    return consent


def _get_or_create_capture_locked(
    *,
    room: ECounselingRoom,
    kind: str,
) -> ECounselingMediaCapture:
    capture = (
        ECounselingMediaCapture.objects.select_for_update().filter(room=room, kind=kind).first()
    )
    if capture is None:
        capture = ECounselingMediaCapture.objects.create(room=room, kind=kind)
    return capture


def _audit_media_request(
    *,
    context: AuditContext,
    action: str,
    appointment: Appointment,
    room: ECounselingRoom,
    capture: ECounselingMediaCapture,
) -> None:
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.mediacapture",
        target_id=capture.pk,
        metadata={
            "appointment_id": str(appointment.pk),
            "room_id": str(room.pk),
            "media_kind": capture.kind,
            "provider": "DAILY",
        },
    )


def start_recording(
    *,
    counselor: User,
    appointment_id: UUID,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> ECounselingMediaCapture:
    appointment = _load_eligible_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )
    if not _join_window_open(appointment):
        raise ECounselingMediaConflict("Recording can start only during the session window.")
    room = _require_provisioned_room(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        _require_effective_consent_locked(
            room=locked_room,
            scope=ConsentScope.AUDIO_VIDEO_RECORDING,
        )
        capture = _get_or_create_capture_locked(
            room=locked_room,
            kind=MediaCaptureKind.RECORDING,
        )
        if capture.status != MediaCaptureStatus.NOT_STARTED:
            raise ECounselingMediaConflict(
                "This session recording has already been started or requires reconciliation."
            )
        capture.status = MediaCaptureStatus.START_REQUESTED
        capture.provider_instance_id = str(uuid.uuid4())
        capture.error_code = None
        capture.failed_at = None
        capture.save(
            update_fields=[
                "status",
                "provider_instance_id",
                "error_code",
                "failed_at",
                "updated_at",
            ]
        )
        _audit_media_request(
            context=context,
            action=ECOUNSELING_RECORDING_START_REQUESTED,
            appointment=appointment,
            room=locked_room,
            capture=capture,
        )
        capture_id = capture.pk
        instance_id = capture.provider_instance_id

    client = _daily_client(daily_client)
    assert instance_id is not None
    try:
        # Daily requires recording enablement in room/token policy. COMPASS enables only cloud
        # recording at the room immediately before the backend start command; participant UI,
        # ownership, admin rights, and automatic recording remain disabled.
        client.update_room(
            room_name=room.daily_room_name,
            properties={"enable_recording": "cloud"},
        )
        _provider_ack(
            client.start_recording(
                room_name=room.daily_room_name,
                instance_id=instance_id,
            )
        )
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        _handle_start_provider_failure(capture_id, exc)
    return ECounselingMediaCapture.objects.get(pk=capture_id)


def start_transcription(
    *,
    counselor: User,
    appointment_id: UUID,
    store_transcript: bool,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> ECounselingMediaCapture:
    appointment = _load_eligible_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )
    if not _join_window_open(appointment):
        raise ECounselingMediaConflict("Transcription can start only during the session window.")
    room = _require_provisioned_room(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        _require_effective_consent_locked(
            room=locked_room,
            scope=ConsentScope.LIVE_TRANSCRIPTION,
        )
        if store_transcript:
            _require_effective_consent_locked(
                room=locked_room,
                scope=ConsentScope.TRANSCRIPT_STORAGE,
            )
        capture = _get_or_create_capture_locked(
            room=locked_room,
            kind=MediaCaptureKind.TRANSCRIPTION,
        )
        if capture.status != MediaCaptureStatus.NOT_STARTED:
            raise ECounselingMediaConflict(
                "This session transcription has already been started or requires reconciliation."
            )
        capture.status = MediaCaptureStatus.START_REQUESTED
        capture.provider_instance_id = str(uuid.uuid4())
        capture.error_code = None
        capture.failed_at = None
        capture.save(
            update_fields=[
                "status",
                "provider_instance_id",
                "error_code",
                "failed_at",
                "updated_at",
            ]
        )
        _audit_media_request(
            context=context,
            action=ECOUNSELING_TRANSCRIPTION_START_REQUESTED,
            appointment=appointment,
            room=locked_room,
            capture=capture,
        )
        capture_id = capture.pk
        instance_id = capture.provider_instance_id

    client = _daily_client(daily_client)
    assert instance_id is not None
    try:
        client.update_room(
            room_name=room.daily_room_name,
            properties={"enable_transcription_storage": store_transcript},
        )

        # Re-enter the same room/capture lock boundary before the provider start. Withdrawal uses
        # these locks too, so whichever transition wins is serialized. A withdrawal that commits
        # first makes the pending start ineligible; a start that wins first is visible to withdrawal
        # and is immediately stopped/cleaned up by that path.
        with transaction.atomic():
            locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
            _require_effective_consent_locked(
                room=locked_room,
                scope=ConsentScope.LIVE_TRANSCRIPTION,
            )
            if store_transcript:
                _require_effective_consent_locked(
                    room=locked_room,
                    scope=ConsentScope.TRANSCRIPT_STORAGE,
                )
            capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
            if (
                capture.status != MediaCaptureStatus.START_REQUESTED
                or capture.provider_instance_id != instance_id
            ):
                raise ECounselingMediaConflict(
                    "Transcription start was superseded by a consent or media-state transition."
                )
            capture.transcript_storage_enabled = store_transcript
            capture.save(update_fields=["transcript_storage_enabled", "updated_at"])
            _provider_ack(
                client.start_transcription(
                    room_name=room.daily_room_name,
                    instance_id=instance_id,
                )
            )
    except (ECounselingConsentNotApproved, ECounselingMediaConflict):
        if store_transcript:
            try:
                client.update_room(
                    room_name=room.daily_room_name,
                    properties={"enable_transcription_storage": False},
                )
            except (
                DailyConfigurationError,
                DailyUnavailable,
                DailyHTTPError,
                DailyInvalidResponse,
            ) as cleanup_exc:
                _set_provider_uncertain(capture_id, code="CONSENT_CLEANUP_UNCERTAIN")
                raise _provider_failure(cleanup_exc) from cleanup_exc
        raise
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        _handle_start_provider_failure(capture_id, exc)
    return ECounselingMediaCapture.objects.get(pk=capture_id)


def _prepare_stop_locked(
    *,
    appointment: Appointment,
    room: ECounselingRoom,
    kind: str,
    context: AuditContext,
) -> tuple[ECounselingMediaCapture, bool]:
    capture = (
        ECounselingMediaCapture.objects.select_for_update().filter(room=room, kind=kind).first()
    )
    if capture is None or capture.status == MediaCaptureStatus.NOT_STARTED:
        raise ECounselingMediaConflict("This media capture has not started.")
    if capture.status in {MediaCaptureStatus.STOPPED, MediaCaptureStatus.READY}:
        return capture, False
    if capture.status == MediaCaptureStatus.STOP_REQUESTED:
        return capture, True
    capture.status = MediaCaptureStatus.STOP_REQUESTED
    capture.stop_requested_at = timezone.now()
    capture.save(update_fields=["status", "stop_requested_at", "updated_at"])
    _audit_media_request(
        context=context,
        action=(
            ECOUNSELING_RECORDING_STOP_REQUESTED
            if kind == MediaCaptureKind.RECORDING
            else ECOUNSELING_TRANSCRIPTION_STOP_REQUESTED
        ),
        appointment=appointment,
        room=room,
        capture=capture,
    )
    return capture, True


def _mark_stop_failed(capture_id: UUID) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status == MediaCaptureStatus.STOP_REQUESTED:
            capture.error_code = "STOP_PROVIDER_FAILED"
            capture.save(update_fields=["error_code", "updated_at"])


def _execute_provider_stop(
    *,
    capture: ECounselingMediaCapture,
    room: ECounselingRoom,
    daily_client: DailyClient | None,
) -> ECounselingMediaCapture:
    client = _daily_client(daily_client)
    try:
        if capture.kind == MediaCaptureKind.RECORDING:
            _provider_ack(client.stop_recording(room_name=room.daily_room_name))
            # Daily has no recording-stopped webhook in the selected subscription. Keep
            # STOP_REQUESTED until artifact readiness/provider reconciliation advances the state.
        else:
            if not capture.provider_instance_id:
                raise DailyInvalidResponse("Transcription instance ID is unavailable.")
            _provider_ack(
                client.stop_transcription(
                    room_name=room.daily_room_name,
                    instance_id=capture.provider_instance_id,
                )
            )
            with transaction.atomic():
                locked = ECounselingMediaCapture.objects.select_for_update().get(pk=capture.pk)
                if locked.status == MediaCaptureStatus.STOP_REQUESTED:
                    locked.status = MediaCaptureStatus.STOPPED
                    locked.ended_at = timezone.now()
                    locked.error_code = None
                    locked.save(update_fields=["status", "ended_at", "error_code", "updated_at"])
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        _mark_stop_failed(capture.pk)
        raise _provider_failure(exc) from exc
    return ECounselingMediaCapture.objects.get(pk=capture.pk)


def stop_media_capture(
    *,
    counselor: User,
    appointment_id: UUID,
    kind: str,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> ECounselingMediaCapture:
    appointment = _load_session_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )
    room = _require_provisioned_room(appointment)
    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        capture, provider_stop_needed = _prepare_stop_locked(
            appointment=appointment,
            room=locked_room,
            kind=kind,
            context=context,
        )
    if not provider_stop_needed:
        return capture
    return _execute_provider_stop(
        capture=capture,
        room=room,
        daily_client=daily_client,
    )


def stop_recording(
    *,
    counselor: User,
    appointment_id: UUID,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> ECounselingMediaCapture:
    return stop_media_capture(
        counselor=counselor,
        appointment_id=appointment_id,
        kind=MediaCaptureKind.RECORDING,
        context=context,
        daily_client=daily_client,
    )


def stop_transcription(
    *,
    counselor: User,
    appointment_id: UUID,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> ECounselingMediaCapture:
    return stop_media_capture(
        counselor=counselor,
        appointment_id=appointment_id,
        kind=MediaCaptureKind.TRANSCRIPTION,
        context=context,
        daily_client=daily_client,
    )


def withdraw_my_consent(
    *,
    student: User,
    appointment_id: UUID,
    consent_id: UUID,
    context: AuditContext,
    daily_client: DailyClient | None = None,
) -> dict[str, object]:
    appointment = _load_session_appointment(appointment_id)
    _require_student_relationship(
        actor=student,
        appointment=appointment,
        capability="ecounseling.consent_self",
    )
    room = _require_room_for_appointment(appointment)
    capture_to_stop: ECounselingMediaCapture | None = None
    disable_storage = False

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        consent = (
            ECounselingConsent.objects.select_for_update()
            .filter(pk=consent_id, room=locked_room)
            .first()
        )
        if consent is None:
            raise ECounselingConsentNotFound("The requested consent was not found.")
        if consent.decision != ConsentDecision.APPROVED or consent.withdrawn_at is not None:
            raise ECounselingConsentConflict("Only current approved consent can be withdrawn.")

        consent.withdrawn_at = timezone.now()
        consent.save(update_fields=["withdrawn_at", "updated_at"])
        record_event(
            context=context,
            action=ECOUNSELING_CONSENT_WITHDRAWN,
            outcome=AuditOutcome.SUCCESS,
            target_type="ecounseling.consent",
            target_id=consent.pk,
            metadata={
                "appointment_id": str(appointment.pk),
                "room_id": str(locked_room.pk),
                "scope": consent.scope,
                "decision": ConsentDecision.APPROVED,
            },
        )

        kind = (
            MediaCaptureKind.RECORDING
            if consent.scope == ConsentScope.AUDIO_VIDEO_RECORDING
            else MediaCaptureKind.TRANSCRIPTION
        )
        capture = (
            ECounselingMediaCapture.objects.select_for_update()
            .filter(room=locked_room, kind=kind)
            .first()
        )
        if capture is not None:
            activeish = capture.status in {
                MediaCaptureStatus.START_REQUESTED,
                MediaCaptureStatus.ACTIVE,
                MediaCaptureStatus.ERROR,
                MediaCaptureStatus.STOP_REQUESTED,
            }
            if consent.scope == ConsentScope.AUDIO_VIDEO_RECORDING and activeish:
                capture, _ = _prepare_stop_locked(
                    appointment=appointment,
                    room=locked_room,
                    kind=MediaCaptureKind.RECORDING,
                    context=context,
                )
                capture_to_stop = capture
            elif consent.scope == ConsentScope.LIVE_TRANSCRIPTION and activeish:
                capture, _ = _prepare_stop_locked(
                    appointment=appointment,
                    room=locked_room,
                    kind=MediaCaptureKind.TRANSCRIPTION,
                    context=context,
                )
                capture_to_stop = capture
                disable_storage = capture.transcript_storage_enabled
            elif consent.scope == ConsentScope.TRANSCRIPT_STORAGE:
                pending_storage_start = capture.status == MediaCaptureStatus.START_REQUESTED
                disable_storage = pending_storage_start or bool(capture.transcript_storage_enabled)
                if pending_storage_start or (activeish and capture.transcript_storage_enabled):
                    capture, _ = _prepare_stop_locked(
                        appointment=appointment,
                        room=locked_room,
                        kind=MediaCaptureKind.TRANSCRIPTION,
                        context=context,
                    )
                    capture_to_stop = capture

    # Withdrawal is already durable before any provider call. Provider failure never rolls it back.
    # Stop capture and disable transcript storage are independent mitigations: failure of one must
    # not prevent the other from being attempted.
    provider_error: ECounselingError | None = None
    if capture_to_stop is not None:
        try:
            _execute_provider_stop(
                capture=capture_to_stop,
                room=room,
                daily_client=daily_client,
            )
        except ECounselingError as exc:
            provider_error = exc

    if disable_storage and room.provisioned_at:
        try:
            client = _daily_client(daily_client)
            client.update_room(
                room_name=room.daily_room_name,
                properties={"enable_transcription_storage": False},
            )
        except ECounselingError as exc:
            if provider_error is None:
                provider_error = exc
        except (
            DailyConfigurationError,
            DailyUnavailable,
            DailyHTTPError,
            DailyInvalidResponse,
        ) as exc:
            if provider_error is None:
                provider_error = _provider_failure(exc)
        else:
            with transaction.atomic():
                capture = (
                    ECounselingMediaCapture.objects.select_for_update()
                    .filter(room=room, kind=MediaCaptureKind.TRANSCRIPTION)
                    .first()
                )
                if capture is not None:
                    capture.transcript_storage_enabled = False
                    capture.save(update_fields=["transcript_storage_enabled", "updated_at"])

    if provider_error is not None:
        raise provider_error
    return _consent_dict(ECounselingConsent.objects.get(pk=consent_id))


def _event_time(value: object) -> datetime | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _safe_duration(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    return duration if duration >= 0 else None


def _room_by_name(value: object) -> ECounselingRoom | None:
    if not isinstance(value, str) or not value or len(value) > 128:
        return None
    return ECounselingRoom.objects.filter(daily_room_name=value).first()


def _effective_scope_for_room(room: ECounselingRoom, scope: str) -> bool:
    consent = ECounselingConsent.objects.filter(room=room, scope=scope).first()
    return effective_consent(consent)


def _best_effort_policy_stop(room: ECounselingRoom, capture: ECounselingMediaCapture) -> None:
    if not settings.DAILY_ENABLED or not room.provisioned_at:
        return
    try:
        client = DailyClient.from_settings()
        if capture.kind == MediaCaptureKind.RECORDING:
            _provider_ack(client.stop_recording(room_name=room.daily_room_name))
        elif capture.provider_instance_id:
            _provider_ack(
                client.stop_transcription(
                    room_name=room.daily_room_name,
                    instance_id=capture.provider_instance_id,
                )
            )
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse):
        logger.warning(
            "Daily policy stop could not be completed",
            extra={"event": "daily_media_policy_stop_failed", "media_kind": capture.kind},
        )


def _media_kind_for_event(event_type: str) -> str:
    return (
        MediaCaptureKind.RECORDING
        if event_type.startswith("recording.")
        else MediaCaptureKind.TRANSCRIPTION
    )


def _resolve_event_room(
    *,
    event_type: str,
    payload: dict[str, object],
) -> ECounselingRoom | None:
    if event_type == "recording.started":
        instance_id = payload.get("instance_id")
        if isinstance(instance_id, str) and instance_id:
            capture = (
                ECounselingMediaCapture.objects.select_related("room")
                .filter(
                    kind=MediaCaptureKind.RECORDING,
                    provider_instance_id=instance_id,
                )
                .first()
            )
            return capture.room if capture is not None else None
        return None
    return _room_by_name(payload.get("room_name"))


def process_media_webhook_event(
    *,
    event_type: str,
    event_id: str,
    event_ts: object,
    payload: dict[str, object],
) -> WebhookProcessingResult:
    if event_type not in MEDIA_WEBHOOK_TYPES:
        return WebhookProcessingResult(accepted=True)
    if not event_id or len(event_id) > 160:
        raise ECounselingMediaConflict("Daily media webhook event ID is invalid.")

    room = _resolve_event_room(event_type=event_type, payload=payload)
    kind = _media_kind_for_event(event_type)
    provider_session_id = payload.get("mtg_session_id")
    if not isinstance(provider_session_id, str) or not provider_session_id:
        provider_session_id = None
    occurred_at = _event_time(event_ts)
    stop_for_policy = False
    capture_id: UUID | None = None

    with transaction.atomic():
        receipt, created = DailyWebhookReceipt.objects.get_or_create(
            provider_event_id=event_id,
            defaults={
                "event_type": event_type,
                "ecounseling_room": room,
                "provider_session_id": provider_session_id,
                "provider_occurred_at": occurred_at,
            },
        )
        if not created:
            return WebhookProcessingResult(accepted=True, duplicate=True, supported=True)
        if room is None:
            return WebhookProcessingResult(accepted=True, supported=True)

        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        capture = _get_or_create_capture_locked(room=locked_room, kind=kind)
        capture_id = capture.pk

        if event_type == "recording.started":
            instance_id = payload.get("instance_id")
            recording_id = payload.get("recording_id")
            if isinstance(instance_id, str) and instance_id:
                capture.provider_instance_id = instance_id[:160]
            if isinstance(recording_id, str) and recording_id:
                capture.provider_artifact_id = recording_id[:160]
            capture.started_at = (
                _event_time(payload.get("start_ts")) or occurred_at or timezone.now()
            )
            if not _effective_scope_for_room(locked_room, ConsentScope.AUDIO_VIDEO_RECORDING):
                capture.status = MediaCaptureStatus.STOP_REQUESTED
                capture.stop_requested_at = timezone.now()
                capture.error_code = "CONSENT_NOT_EFFECTIVE"
                stop_for_policy = True
            elif capture.status not in _NO_REGRESSION_TO_ACTIVE:
                capture.status = MediaCaptureStatus.ACTIVE
                capture.error_code = None

        elif event_type == "recording.ready-to-download":
            recording_id = payload.get("recording_id")
            if isinstance(recording_id, str) and recording_id:
                capture.provider_artifact_id = recording_id[:160]
            capture.started_at = _event_time(payload.get("start_ts")) or capture.started_at
            capture.duration_seconds = _safe_duration(payload.get("duration"))
            capture.ready_at = occurred_at or timezone.now()
            if capture.started_at and capture.duration_seconds is not None:
                capture.ended_at = capture.started_at + timedelta(seconds=capture.duration_seconds)
            capture.status = MediaCaptureStatus.READY
            if not _effective_scope_for_room(locked_room, ConsentScope.AUDIO_VIDEO_RECORDING):
                capture.error_code = "CONSENT_NOT_EFFECTIVE"

        elif event_type == "recording.error":
            instance_id = payload.get("instance_id")
            if isinstance(instance_id, str) and instance_id:
                capture.provider_instance_id = instance_id[:160]
            if capture.status != MediaCaptureStatus.READY:
                capture.status = MediaCaptureStatus.ERROR
                capture.failed_at = (
                    _event_time(payload.get("timestamp")) or occurred_at or timezone.now()
                )
                capture.error_code = "PROVIDER_ERROR"

        elif event_type == "transcript.started":
            transcript_id = payload.get("id")
            info = payload.get("info")
            instance_id = info.get("instanceId") if isinstance(info, dict) else None
            if isinstance(instance_id, str) and instance_id:
                capture.provider_instance_id = instance_id[:160]
            if isinstance(transcript_id, str) and transcript_id:
                capture.provider_artifact_id = transcript_id[:160]
            capture.provider_session_id = provider_session_id
            capture.started_at = occurred_at or timezone.now()
            live_ok = _effective_scope_for_room(locked_room, ConsentScope.LIVE_TRANSCRIPTION)
            storage_ok = _effective_scope_for_room(locked_room, ConsentScope.TRANSCRIPT_STORAGE)
            if not live_ok or (capture.transcript_storage_enabled and not storage_ok):
                capture.status = MediaCaptureStatus.STOP_REQUESTED
                capture.stop_requested_at = timezone.now()
                capture.error_code = (
                    "CONSENT_NOT_EFFECTIVE" if not live_ok else "STORAGE_CONSENT_NOT_EFFECTIVE"
                )
                stop_for_policy = True
            elif capture.status not in _NO_REGRESSION_TO_ACTIVE:
                capture.status = MediaCaptureStatus.ACTIVE
                capture.error_code = None

        elif event_type == "transcript.ready-to-download":
            transcript_id = payload.get("id")
            if isinstance(transcript_id, str) and transcript_id:
                capture.provider_artifact_id = transcript_id[:160]
            capture.provider_session_id = provider_session_id
            capture.duration_seconds = _safe_duration(payload.get("duration"))
            capture.ready_at = occurred_at or timezone.now()
            capture.ended_at = occurred_at or capture.ended_at
            capture.status = MediaCaptureStatus.READY
            capture.transcript_storage_enabled = True
            live_ok = _effective_scope_for_room(locked_room, ConsentScope.LIVE_TRANSCRIPTION)
            storage_ok = _effective_scope_for_room(locked_room, ConsentScope.TRANSCRIPT_STORAGE)
            if not live_ok or not storage_ok:
                capture.error_code = (
                    "CONSENT_NOT_EFFECTIVE" if not live_ok else "STORAGE_CONSENT_NOT_EFFECTIVE"
                )

        elif event_type == "transcript.error":
            transcript_id = payload.get("id")
            info = payload.get("info")
            instance_id = info.get("instanceId") if isinstance(info, dict) else None
            if isinstance(instance_id, str) and instance_id:
                capture.provider_instance_id = instance_id[:160]
            if isinstance(transcript_id, str) and transcript_id:
                capture.provider_artifact_id = transcript_id[:160]
            capture.provider_session_id = provider_session_id
            capture.duration_seconds = _safe_duration(payload.get("duration"))
            if capture.status != MediaCaptureStatus.READY:
                capture.status = MediaCaptureStatus.ERROR
                capture.failed_at = occurred_at or timezone.now()
                capture.error_code = "PROVIDER_ERROR"

        capture.save()
        if receipt.ecounseling_room_id != locked_room.pk:
            receipt.ecounseling_room = locked_room
            receipt.save(update_fields=["ecounseling_room"])

    if stop_for_policy and capture_id is not None:
        capture = ECounselingMediaCapture.objects.select_related("room").get(pk=capture_id)
        _best_effort_policy_stop(capture.room, capture)
    return WebhookProcessingResult(accepted=True, supported=True)
