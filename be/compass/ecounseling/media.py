"""Session-scoped E-Counseling consent and Daily media-control services."""

from __future__ import annotations

import logging
import uuid
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
    DailyInvalidAcknowledgment,
    DailyInvalidResponse,
    DailyUnavailable,
    safe_daily_failure_code,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.service_catalog.models import DeliveryMode

from .models import (
    ConsentDecision,
    ConsentScope,
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
    MediaArtifactStatus,
    MediaCaptureKind,
    MediaCaptureStatus,
    MediaPolicyVersion,
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
from .webhook_events import MEDIA_WEBHOOK_TYPES as MEDIA_WEBHOOK_TYPES

logger = logging.getLogger("compass.ecounseling.media")


_TERMINAL_CAPTURE_STATES = frozenset({MediaCaptureStatus.STOPPED, MediaCaptureStatus.READY})


def _has_stop_intent(capture: ECounselingMediaCapture) -> bool:
    # The timestamp also protects older ERROR rows whose Stop intent was obscured by telemetry.
    return bool(capture.stop_requested_at or capture.status == MediaCaptureStatus.STOP_REQUESTED)


def _capture_status_for_event(capture: ECounselingMediaCapture, observation: str) -> str:
    """Intent outranks nonterminal observations; only correlated completion advances it."""
    if observation == "ready":
        return MediaCaptureStatus.READY
    if capture.status in _TERMINAL_CAPTURE_STATES:
        return capture.status
    if _has_stop_intent(capture):
        return MediaCaptureStatus.STOP_REQUESTED
    return MediaCaptureStatus.ERROR if observation == "error" else MediaCaptureStatus.ACTIVE


class ECounselingConsentScopeIncompatible(ECounselingError):
    pass


def media_scope(room, kind):
    if room.media_policy_version == MediaPolicyVersion.V2:
        return ConsentScope.SESSION_MEDIA_CAPTURE
    return (
        ConsentScope.AUDIO_VIDEO_RECORDING
        if kind == MediaCaptureKind.RECORDING
        else ConsentScope.LIVE_TRANSCRIPTION
    )


def _validate_scopes(version, scopes):
    allowed = (
        {ConsentScope.SESSION_MEDIA_CAPTURE, ConsentScope.TRANSCRIPT_STORAGE}
        if version == MediaPolicyVersion.V2
        else {
            ConsentScope.AUDIO_VIDEO_RECORDING,
            ConsentScope.LIVE_TRANSCRIPTION,
            ConsentScope.TRANSCRIPT_STORAGE,
        }
    )
    if not set(scopes) <= allowed:
        raise ECounselingConsentScopeIncompatible(
            "This consent scope is incompatible with the session's media policy."
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

    def artifact_state(capture):
        artifact = (
            ECounselingMediaArtifact.objects.filter(capture=capture).first() if capture else None
        )
        return {
            "artifact_status": artifact.status if artifact else None,
            "artifact_available": bool(
                artifact
                and artifact.status == MediaArtifactStatus.STORED
                and not artifact.disposed_at
                and not capture.artifact_disposed_at
            ),
        }

    version = room.media_policy_version if room else MediaPolicyVersion.V2
    recording_scope = (
        media_scope(room, MediaCaptureKind.RECORDING)
        if room
        else ConsentScope.SESSION_MEDIA_CAPTURE
    )
    transcription_scope = (
        media_scope(room, MediaCaptureKind.TRANSCRIPTION)
        if room
        else ConsentScope.SESSION_MEDIA_CAPTURE
    )
    return {
        "media_policy_version": version,
        "recording": {
            **artifact_state(recording),
            "artifact_disposed_at": recording.artifact_disposed_at if recording else None,
            "consent_status": _consent_status(consents.get(recording_scope)),
            "capture_status": (
                recording.status if recording is not None else MediaCaptureStatus.NOT_STARTED
            ),
        },
        "transcription": {
            **artifact_state(transcription),
            "artifact_disposed_at": transcription.artifact_disposed_at if transcription else None,
            "consent_status": _consent_status(consents.get(transcription_scope)),
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
    existing_room = ECounselingRoom.objects.filter(appointment=appointment).first()
    _validate_scopes(
        existing_room.media_policy_version if existing_room else MediaPolicyVersion.V2, scopes
    )
    room = _ensure_local_room_binding(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        _validate_scopes(locked_room.media_policy_version, scopes)
        existing = {
            item.scope: item
            for item in ECounselingConsent.objects.select_for_update().filter(room=locked_room)
        }

        if ConsentScope.TRANSCRIPT_STORAGE in scopes:
            live_scope = media_scope(locked_room, MediaCaptureKind.TRANSCRIPTION)
            live = existing.get(live_scope)
            live_requested_together = live_scope in scopes
            existing_live_usable = bool(
                live and live.decision != ConsentDecision.DENIED and live.withdrawn_at is None
            )
            if not live_requested_together and not existing_live_usable:
                raise ECounselingConsentConflict(
                    "Transcript storage consent requires a media consent request for this session."
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
        _validate_scopes(locked_room.media_policy_version, [consent.scope])
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
    if isinstance(payload, dict):
        status_ok = payload.get("status") == "sent"
        sent_ok = payload.get("sent") is True or payload.get("sent") == "true"
        if (
            (status_ok or sent_ok)
            and ("status" not in payload or status_ok)
            and ("sent" not in payload or sent_ok)
            and payload.get("error") is None
        ):
            return
    raise DailyInvalidAcknowledgment("Daily did not acknowledge the media command.")


def _set_provider_uncertain(capture_id: UUID, *, code: str) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        capture.error_code = code
        capture.save(update_fields=["error_code", "updated_at"])


def _set_known_start_failure(capture_id: UUID, *, code: str) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status == MediaCaptureStatus.START_REQUESTED:
            capture.status = MediaCaptureStatus.ERROR
            capture.failed_at = timezone.now()
            capture.error_code = code
            capture.save(update_fields=["status", "failed_at", "error_code", "updated_at"])


def _handle_start_provider_failure(capture_id: UUID, exc: Exception) -> None:
    code = f"START_PROVIDER_{safe_daily_failure_code(exc)}"
    if isinstance(exc, DailyHTTPError):
        _set_known_start_failure(capture_id, code=code)
    else:
        _set_provider_uncertain(capture_id, code=code)
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
    metadata = {
        "appointment_id": str(appointment.pk),
        "room_id": str(room.pk),
        "media_kind": capture.kind,
        "provider": "DAILY",
    }
    if action == ECOUNSELING_TRANSCRIPTION_START_REQUESTED:
        # Historical selection/consent evidence, not proof of provider configuration or custody.
        metadata["storage_selected"] = capture.transcript_storage_authorized
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.mediacapture",
        target_id=capture.pk,
        metadata=metadata,
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
            scope=media_scope(locked_room, MediaCaptureKind.RECORDING),
        )
        capture = _get_or_create_capture_locked(
            room=locked_room,
            kind=MediaCaptureKind.RECORDING,
        )
        if capture.status != MediaCaptureStatus.NOT_STARTED or _has_stop_intent(capture):
            raise ECounselingMediaConflict(
                "This session recording has already been started or requires reconciliation."
            )
        capture.status = MediaCaptureStatus.START_REQUESTED
        capture.media_authorized_at = timezone.now()
        capture.provider_instance_id = str(uuid.uuid4())
        capture.error_code = None
        capture.failed_at = None
        capture.save(
            update_fields=[
                "status",
                "media_authorized_at",
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
        # Serialize with withdrawal after room enablement, just as transcription does.
        with transaction.atomic():
            locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
            _require_effective_consent_locked(
                room=locked_room,
                scope=media_scope(locked_room, MediaCaptureKind.RECORDING),
            )
            capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
            if (
                capture.status != MediaCaptureStatus.START_REQUESTED
                or capture.provider_instance_id != instance_id
                or _has_stop_intent(capture)
            ):
                raise ECounselingMediaConflict(
                    "Recording start was superseded by a consent or media-state transition."
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

    # Refuse an enclosing application transaction: intent must commit before external side effects.
    # Django's TestCase wrapper is exempt from the durable-block guard; production requests are
    # autocommit (ATOMIC_REQUESTS is disabled).
    with transaction.atomic(durable=True):
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        _require_effective_consent_locked(
            room=locked_room,
            scope=media_scope(locked_room, MediaCaptureKind.TRANSCRIPTION),
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
        if capture.status != MediaCaptureStatus.NOT_STARTED or _has_stop_intent(capture):
            raise ECounselingMediaConflict(
                "This session transcription has already been started or requires reconciliation."
            )
        capture.status = MediaCaptureStatus.START_REQUESTED
        capture.media_authorized_at = timezone.now()
        capture.provider_instance_id = str(uuid.uuid4())
        capture.transcript_storage_authorized = store_transcript
        capture.error_code = None
        capture.failed_at = None
        capture.save(
            update_fields=[
                "status",
                "media_authorized_at",
                "provider_instance_id",
                "transcript_storage_authorized",
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

        # Commit the acknowledged room setting independently of the external Start transaction.
        # Selection/authorization was already committed with the original intent above. Withdrawal
        # uses the same locks and can supersede either boundary; it never regains authorization.
        with transaction.atomic(durable=True):
            locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
            _require_effective_consent_locked(
                room=locked_room,
                scope=media_scope(locked_room, MediaCaptureKind.TRANSCRIPTION),
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
                or _has_stop_intent(capture)
            ):
                raise ECounselingMediaConflict(
                    "Transcription start was superseded by a consent or media-state transition."
                )
            capture.transcript_storage_enabled = store_transcript
            capture.save(update_fields=["transcript_storage_enabled", "updated_at"])

        # Keep provider Start under the original consent serialization locks. Recheck after the
        # preceding commit: a withdrawal in that gap prevents Start; one blocked behind Start sees
        # its durable reservation and requests Stop. No new command retry is introduced.
        with transaction.atomic():
            locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
            _require_effective_consent_locked(
                room=locked_room,
                scope=media_scope(locked_room, MediaCaptureKind.TRANSCRIPTION),
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
                or _has_stop_intent(capture)
            ):
                raise ECounselingMediaConflict(
                    "Transcription start was superseded by a consent or media-state transition."
                )
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
            else:
                # A manual Stop can supersede Start after the configuration flag committed.
                # Persist this existing cleanup's acknowledgment without erasing historical choice.
                with transaction.atomic():
                    ECounselingRoom.objects.select_for_update().get(pk=room.pk)
                    capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
                    capture.transcript_storage_enabled = False
                    capture.save(update_fields=["transcript_storage_enabled", "updated_at"])
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
    already_requested = _has_stop_intent(capture)
    capture.status = MediaCaptureStatus.STOP_REQUESTED
    capture.stop_requested_at = capture.stop_requested_at or timezone.now()
    capture.save(update_fields=["status", "stop_requested_at", "updated_at"])
    if not already_requested:
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


def _mark_stop_failed(capture_id: UUID, *, code: str) -> None:
    with transaction.atomic():
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status == MediaCaptureStatus.STOP_REQUESTED:
            capture.error_code = code
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
            # "sent" acknowledges the command only. It supplies no finished-job evidence or
            # end timestamp, so retain Stop intent and any uncertainty until correlated completion.
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        _mark_stop_failed(capture.pk, code=f"STOP_PROVIDER_{safe_daily_failure_code(exc)}")
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
    captures_to_stop: list[ECounselingMediaCapture] = []
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

        _validate_scopes(locked_room.media_policy_version, [consent.scope])
        kinds = (
            [MediaCaptureKind.RECORDING, MediaCaptureKind.TRANSCRIPTION]
            if consent.scope == ConsentScope.SESSION_MEDIA_CAPTURE
            else [MediaCaptureKind.RECORDING]
            if consent.scope == ConsentScope.AUDIO_VIDEO_RECORDING
            else [MediaCaptureKind.TRANSCRIPTION]
        )
        for kind in kinds:
            capture = (
                ECounselingMediaCapture.objects.select_for_update()
                .filter(room=locked_room, kind=kind)
                .first()
            )
            if capture is None:
                continue
            activeish = capture.status in {
                MediaCaptureStatus.START_REQUESTED,
                MediaCaptureStatus.ACTIVE,
                MediaCaptureStatus.ERROR,
                MediaCaptureStatus.STOP_REQUESTED,
            }
            if kind == MediaCaptureKind.TRANSCRIPTION:
                pending_storage = capture.status == MediaCaptureStatus.START_REQUESTED
                disable_storage = capture.transcript_storage_enabled or pending_storage
            should_stop = activeish and (
                consent.scope != ConsentScope.TRANSCRIPT_STORAGE or disable_storage
            )
            if should_stop:
                capture, _ = _prepare_stop_locked(
                    appointment=appointment,
                    room=locked_room,
                    kind=kind,
                    context=context,
                )
                captures_to_stop.append(capture)

    # Withdrawal is already durable before any provider call. Provider failure never rolls it back.
    # Stop capture and disable transcript storage are independent mitigations: failure of one must
    # not prevent the other from being attempted.
    provider_error: ECounselingError | None = None
    for capture_to_stop in captures_to_stop:
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


def process_media_webhook_event(*, event_type, event_id, event_ts, payload):
    from .webhooks import process_event

    if event_type not in MEDIA_WEBHOOK_TYPES:
        return WebhookProcessingResult(accepted=True)
    return process_event(
        event_type=event_type, event_id=event_id, event_ts=event_ts, payload=payload
    )
