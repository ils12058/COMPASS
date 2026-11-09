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

from .consent_realtime import consent_changed_on_commit
from .media_realtime import media_changed_on_commit
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


# Recording is the only media capture, so its consent is the only scope (EC-RC-2).
RECORDING_SCOPE = ConsentScope.AUDIO_VIDEO_RECORDING


def _validate_scopes(scopes):
    if not set(scopes) <= {RECORDING_SCOPE}:
        raise ECounselingConsentScopeIncompatible(
            "This recording choice isn't available for the session."
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
        raise ECounselingAppointmentNotEligible("The Appointment isn't for E-Counseling.")
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
    consent = None
    recording = None
    if room is not None:
        consent = next(
            (item for item in room.consents.all() if item.scope == RECORDING_SCOPE), None
        )
        recording = next(
            (item for item in room.media_captures.all() if item.kind == MediaCaptureKind.RECORDING),
            None,
        )
    artifact = (
        ECounselingMediaArtifact.objects.filter(capture=recording).first() if recording else None
    )
    return {
        "recording": {
            "artifact_status": artifact.status if artifact else None,
            "artifact_available": bool(
                artifact
                and artifact.status == MediaArtifactStatus.STORED
                and not artifact.disposed_at
                and not recording.artifact_disposed_at
            ),
            "artifact_disposed_at": recording.artifact_disposed_at if recording else None,
            "consent_status": _consent_status(consent),
            "capture_status": (
                recording.status if recording is not None else MediaCaptureStatus.NOT_STARTED
            ),
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
        raise ECounselingConsentConflict("Choose recording consent.")
    if len(scopes) != len(set(scopes)):
        raise ECounselingConsentConflict("Choose recording consent only once.")
    unsupported = set(scopes) - set(ConsentScope.values)
    if unsupported:
        raise ECounselingConsentConflict("Choose a supported recording option.")

    appointment = _load_eligible_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.manage_media_assigned",
    )

    # Consent needs a stable session anchor before either participant necessarily joins.
    # This creates only the local opaque binding; remote Daily provisioning remains join-driven.
    _validate_scopes(scopes)
    room = _ensure_local_room_binding(appointment)

    with transaction.atomic():
        locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        existing = {
            item.scope: item
            for item in ECounselingConsent.objects.select_for_update().filter(room=locked_room)
        }

        for scope in scopes:
            current = existing.get(scope)
            if current and (
                current.decision == ConsentDecision.DENIED or current.withdrawn_at is not None
            ):
                raise ECounselingConsentConflict(
                    "Denied or withdrawn recording consent can't be reopened for this session."
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
            consent_changed_on_commit(appointment.pk)
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
            "Only current Students can approve E-Counseling consent."
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
        _validate_scopes([consent.scope])
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
        consent_changed_on_commit(appointment.pk)
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
            media_changed_on_commit(capture.room.appointment_id)


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
            scope=RECORDING_SCOPE,
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
        media_changed_on_commit(appointment.pk)

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
        # Serialize with withdrawal after room enablement.
        with transaction.atomic():
            locked_room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
            _require_effective_consent_locked(
                room=locked_room,
                scope=RECORDING_SCOPE,
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


def _prepare_stop_locked(
    *,
    appointment: Appointment,
    room: ECounselingRoom,
    kind: str,
    context: AuditContext,
    publish_hint: bool = True,
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
    if publish_hint:
        media_changed_on_commit(appointment.pk)
    if not already_requested:
        _audit_media_request(
            context=context,
            action=ECOUNSELING_RECORDING_STOP_REQUESTED,
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
        if not capture.provider_instance_id:
            raise DailyInvalidResponse("Couldn't find the Daily recording. Try again.")
        _provider_ack(
            client.stop_recording(
                room_name=room.daily_room_name,
                instance_id=capture.provider_instance_id,
            )
        )
        # Daily has no recording-stopped webhook in the selected subscription. Keep
        # STOP_REQUESTED until artifact readiness/provider reconciliation advances the state.
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
    media_changed = False

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

        _validate_scopes([consent.scope])
        capture = (
            ECounselingMediaCapture.objects.select_for_update()
            .filter(room=locked_room, kind=MediaCaptureKind.RECORDING)
            .first()
        )
        if capture is not None and capture.status in {
            MediaCaptureStatus.START_REQUESTED,
            MediaCaptureStatus.ACTIVE,
            MediaCaptureStatus.ERROR,
            MediaCaptureStatus.STOP_REQUESTED,
        }:
            media_changed = capture.status != MediaCaptureStatus.STOP_REQUESTED
            capture_to_stop, _ = _prepare_stop_locked(
                appointment=appointment,
                room=locked_room,
                kind=MediaCaptureKind.RECORDING,
                context=context,
                publish_hint=False,
            )

        consent_changed_on_commit(appointment.pk)
        if media_changed:
            media_changed_on_commit(appointment.pk)

    # Withdrawal is already durable before any provider call. Provider failure never rolls it back.
    if capture_to_stop is not None:
        _execute_provider_stop(capture=capture_to_stop, room=room, daily_client=daily_client)
    return _consent_dict(ECounselingConsent.objects.get(pk=consent_id))


def process_media_webhook_event(*, event_type, event_id, event_ts, payload):
    from .webhooks import process_event

    if event_type not in MEDIA_WEBHOOK_TYPES:
        return WebhookProcessingResult(accepted=True)
    return process_event(
        event_type=event_type, event_id=event_id, event_ts=event_ts, payload=payload
    )
