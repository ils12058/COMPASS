"""Appointment-backed E-Counseling authorization, provisioning, and telemetry services."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.actions import ECOUNSELING_JOIN_AUTHORIZED, ECOUNSELING_ROOM_PROVISIONED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import CounselingError, get_counseling_service
from compass.integrations.daily import (
    DailyClient,
    DailyConfigurationError,
    DailyHTTPError,
    DailyInvalidResponse,
    DailyUnavailable,
    DailyWebhookSignatureInvalid,
    verify_daily_webhook,
)
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import DeliveryMode
from compass.service_catalog.services import provider_role_eligible, service_supports_delivery_mode

from .models import DailyWebhookReceipt, ECounselingRoom


class ECounselingError(RuntimeError):
    pass


class ECounselingNotFound(ECounselingError):
    pass


class ECounselingNotPermitted(ECounselingError):
    pass


class ECounselingAppointmentNotEligible(ECounselingError):
    pass


class ECounselingJoinNotAvailable(ECounselingError):
    pass


class ECounselingProviderDisabled(ECounselingError):
    pass


class ECounselingProviderUnavailable(ECounselingError):
    pass


class ECounselingRoomProvisioningFailed(ECounselingError):
    pass


class ECounselingInvalidProviderResponse(ECounselingError):
    pass


class ECounselingInvalidWebhook(ECounselingError):
    pass


@dataclass(frozen=True, slots=True)
class JoinCredential:
    room: ECounselingRoom
    room_url: str
    meeting_token: str
    token_expires_at: datetime


@dataclass(frozen=True, slots=True)
class WebhookProcessingResult:
    accepted: bool
    duplicate: bool = False
    supported: bool = False


def _appointment_queryset():
    return Appointment.objects.select_related(
        "student",
        "student__role",
        "provider",
        "provider__role",
        "service",
    )


def _load_eligible_appointment(appointment_id: UUID) -> Appointment:
    appointment = _appointment_queryset().filter(pk=appointment_id).first()
    if appointment is None:
        raise ECounselingNotFound("The requested E-Counseling Appointment was not found.")
    try:
        counseling_service = get_counseling_service(require_active=True)
    except CounselingError as exc:
        raise ECounselingAppointmentNotEligible(
            "The canonical COUNSELING Service is not available for E-Counseling."
        ) from exc
    if appointment.service_id != counseling_service.pk:
        raise ECounselingAppointmentNotEligible(
            "The Appointment does not use the canonical COUNSELING Service."
        )
    if appointment.delivery_mode != DeliveryMode.ONLINE:
        raise ECounselingAppointmentNotEligible("The Appointment is not ONLINE Counseling.")
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ECounselingAppointmentNotEligible("The Appointment is not SCHEDULED.")
    if (
        appointment.provider.role.code != "COUNSELOR"
        or not provider_role_eligible(counseling_service, appointment.provider)
        or not service_supports_delivery_mode(counseling_service, DeliveryMode.ONLINE)
    ):
        raise ECounselingAppointmentNotEligible(
            "The assigned provider is not currently eligible for ONLINE Counseling."
        )
    if not appointment.student.is_active or appointment.student.role.code != "STUDENT":
        raise ECounselingAppointmentNotEligible("The Appointment Student is not active.")
    return appointment


def _require_student_relationship(
    *, actor: User, appointment: Appointment, capability: str
) -> None:
    if (
        not actor.is_active
        or actor.role.code != "STUDENT"
        or actor.pk != appointment.student_id
        or not actor.has_capability(capability)
    ):
        raise ECounselingNotPermitted(
            "This E-Counseling workspace is not available to this Student."
        )


def _require_counselor_relationship(
    *, actor: User, appointment: Appointment, capability: str
) -> None:
    if (
        not actor.is_active
        or actor.role.code != "COUNSELOR"
        or actor.pk != appointment.provider_id
        or not actor.has_capability(capability)
    ):
        raise ECounselingNotPermitted(
            "This E-Counseling workspace is not assigned to this Counselor."
        )


def _room_expiry(appointment: Appointment) -> datetime:
    return appointment.ends_at + timedelta(seconds=settings.ECOUNSELING_REJOIN_GRACE_SECONDS)


def _join_window_open(appointment: Appointment, *, now: datetime | None = None) -> bool:
    current = now or timezone.now()
    earliest = appointment.starts_at - timedelta(seconds=settings.ECOUNSELING_JOIN_EARLY_SECONDS)
    return earliest <= current <= _room_expiry(appointment)


def _routine_for_appointment(appointment: Appointment) -> RoutineInterview | None:
    return RoutineInterview.objects.filter(appointment_id=appointment.pk).first()


def _encounter_for_appointment(appointment: Appointment) -> CounselingEncounter | None:
    return CounselingEncounter.objects.filter(appointment_id=appointment.pk).first()


def _room_for_appointment(appointment: Appointment) -> ECounselingRoom | None:
    return (
        ECounselingRoom.objects.prefetch_related("consents", "media_captures")
        .filter(appointment_id=appointment.pk)
        .first()
    )


def _appointment_context(appointment: Appointment) -> dict[str, object]:
    return {
        "id": appointment.pk,
        "reference_code": appointment.reference_code,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "status": appointment.status,
        "delivery_mode": appointment.delivery_mode,
    }


def _provider_readiness(
    appointment: Appointment, room: ECounselingRoom | None
) -> dict[str, object]:
    enabled = bool(settings.DAILY_ENABLED)
    return {
        "daily_enabled": enabled,
        "room_provisioned": bool(room and room.provisioned_at and room.daily_room_url),
        "join_allowed": enabled and _join_window_open(appointment),
    }


def get_student_workspace(*, student: User, appointment_id: UUID) -> dict[str, object]:
    appointment = _load_eligible_appointment(appointment_id)
    _require_student_relationship(
        actor=student,
        appointment=appointment,
        capability="ecounseling.view_self",
    )
    routine = _routine_for_appointment(appointment)
    room = _room_for_appointment(appointment)
    routine_summary = None
    if routine is not None and routine.student_id == student.pk:
        routine_summary = {
            "id": routine.pk,
            "intake_status": "SUBMITTED" if routine.intake_submitted_at else "DRAFT",
        }
    from .media import get_media_projection

    return {
        "appointment": _appointment_context(appointment),
        "counselor": {
            "id": appointment.provider_id,
            "display_name": appointment.provider.get_full_name(),
        },
        "provider_readiness": _provider_readiness(appointment, room),
        "routine_interview": routine_summary,
        "media": get_media_projection(room),
    }


def get_counselor_workspace(*, counselor: User, appointment_id: UUID) -> dict[str, object]:
    appointment = _load_eligible_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.view_assigned",
    )
    routine = _routine_for_appointment(appointment)
    room = _room_for_appointment(appointment)
    encounter = _encounter_for_appointment(appointment)
    routine_summary = None
    if routine is not None and routine.counselor_id == counselor.pk:
        routine_summary = {
            "id": routine.pk,
            "intake_status": "SUBMITTED" if routine.intake_submitted_at else "DRAFT",
            "evaluation_status": "FINALIZED" if routine.evaluation_finalized_at else "DRAFT",
        }
    encounter_summary = None
    if encounter is not None and encounter.counselor_id == counselor.pk:
        encounter_summary = {"id": encounter.pk, "recorded": True}
    from .media import get_media_projection

    return {
        "appointment": _appointment_context(appointment),
        "student": {
            "id": appointment.student_id,
            "display_name": appointment.student.get_full_name(),
        },
        "provider_readiness": _provider_readiness(appointment, room),
        "routine_interview": routine_summary,
        "counseling_encounter": encounter_summary,
        "media": get_media_projection(room),
    }


def _ensure_local_room_binding(appointment: Appointment) -> ECounselingRoom:
    existing = _room_for_appointment(appointment)
    if existing is not None:
        return existing
    room_id = uuid.uuid4()
    try:
        with transaction.atomic():
            return ECounselingRoom.objects.create(
                id=room_id,
                appointment=appointment,
                daily_room_name=f"ec-{room_id.hex}",
            )
    except IntegrityError:
        existing = _room_for_appointment(appointment)
        if existing is None:
            raise
        return existing


def _normalize_provider_room(
    payload: dict[str, object],
    *,
    expected_name: str,
    expected_expiry_epoch: int,
) -> tuple[str | None, str]:
    if payload.get("name") != expected_name or payload.get("privacy") != "private":
        raise ECounselingInvalidProviderResponse(
            "Daily returned room metadata that does not match the expected private room."
        )
    if payload.get("api_created") is False:
        raise ECounselingInvalidProviderResponse(
            "Daily returned a room not created through the API."
        )
    room_url = payload.get("url")
    room_id = payload.get("id")
    config = payload.get("config")
    if not isinstance(room_url, str) or not room_url.startswith("https://"):
        raise ECounselingInvalidProviderResponse("Daily returned an invalid room URL.")
    if room_id is not None and not isinstance(room_id, str):
        raise ECounselingInvalidProviderResponse("Daily returned an invalid room identifier.")
    if not isinstance(config, dict):
        raise ECounselingInvalidProviderResponse("Daily returned an invalid room configuration.")

    expected_config = {
        "exp": expected_expiry_epoch,
        "eject_at_room_exp": False,
        "max_participants": 2,
        "enable_chat": False,
        "enable_screenshare": False,
        "enable_live_captions_ui": False,
        "enforce_unique_user_ids": True,
        "enable_transcription_storage": False,
    }
    for key, expected in expected_config.items():
        if key in config and config[key] != expected:
            raise ECounselingInvalidProviderResponse(
                "Daily returned a room whose security configuration does not match COMPASS policy."
            )
    return room_id, room_url


def _provider_failure(exc: Exception) -> ECounselingError:
    if isinstance(exc, (DailyUnavailable, DailyConfigurationError)):
        return ECounselingProviderUnavailable("Daily is temporarily unavailable.")
    if isinstance(exc, DailyInvalidResponse):
        return ECounselingInvalidProviderResponse("Daily returned an invalid provider response.")
    if isinstance(exc, DailyHTTPError):
        return ECounselingProviderUnavailable("Daily could not complete the requested operation.")
    return ECounselingRoomProvisioningFailed("The Daily room could not be provisioned.")


def _ensure_provider_room(
    *,
    room: ECounselingRoom,
    appointment: Appointment,
    daily_client: DailyClient,
    context: AuditContext,
) -> ECounselingRoom:
    if room.provisioned_at and room.daily_room_url:
        return room

    expiry = _room_expiry(appointment)
    expiry_epoch = int(expiry.timestamp())
    try:
        try:
            payload = daily_client.create_room(
                room_name=room.daily_room_name,
                expires_at_epoch=expiry_epoch,
            )
        except DailyHTTPError as exc:
            if exc.status_code not in {400, 409}:
                raise
            payload = daily_client.get_room(room_name=room.daily_room_name)
        provider_room_id, provider_room_url = _normalize_provider_room(
            payload,
            expected_name=room.daily_room_name,
            expected_expiry_epoch=expiry_epoch,
        )
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        raise _provider_failure(exc) from exc

    with transaction.atomic():
        locked = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
        if locked.provisioned_at and locked.daily_room_url:
            return locked
        locked.daily_room_id = provider_room_id
        locked.daily_room_url = provider_room_url
        locked.room_expires_at = expiry
        locked.provisioned_at = timezone.now()
        locked.save(
            update_fields=[
                "daily_room_id",
                "daily_room_url",
                "room_expires_at",
                "provisioned_at",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=ECOUNSELING_ROOM_PROVISIONED,
            outcome=AuditOutcome.SUCCESS,
            target_type="ecounseling.room",
            target_id=locked.pk,
            metadata={
                "appointment_id": str(appointment.pk),
                "provider": "DAILY",
            },
        )
        return locked


def create_join_credential(
    *,
    actor: User,
    appointment_id: UUID,
    context: AuditContext,
    daily_client: DailyClient | None = None,
    now: datetime | None = None,
) -> JoinCredential:
    appointment = _load_eligible_appointment(appointment_id)
    if actor.role.code == "STUDENT":
        _require_student_relationship(
            actor=actor,
            appointment=appointment,
            capability="ecounseling.join_self",
        )
        participant_type = "STUDENT"
    elif actor.role.code == "COUNSELOR":
        _require_counselor_relationship(
            actor=actor,
            appointment=appointment,
            capability="ecounseling.join_assigned",
        )
        participant_type = "COUNSELOR"
    else:
        raise ECounselingNotPermitted("This account cannot join E-Counseling sessions.")

    current = now or timezone.now()
    if not _join_window_open(appointment, now=current):
        raise ECounselingJoinNotAvailable("E-Counseling join is not available at this time.")
    if not settings.DAILY_ENABLED:
        raise ECounselingProviderDisabled("Daily E-Counseling is disabled.")

    client = daily_client
    if client is None:
        try:
            client = DailyClient.from_settings()
        except DailyConfigurationError as exc:
            raise ECounselingProviderUnavailable("Daily is not configured correctly.") from exc

    room = _ensure_local_room_binding(appointment)
    room = _ensure_provider_room(
        room=room,
        appointment=appointment,
        daily_client=client,
        context=context,
    )
    room_expiry = _room_expiry(appointment)
    token_expiry = min(
        current + timedelta(seconds=settings.DAILY_MEETING_TOKEN_TTL_SECONDS),
        room_expiry,
    )
    if token_expiry <= current:
        raise ECounselingJoinNotAvailable("E-Counseling join is no longer available.")

    display_name = actor.get_full_name().strip() or "Participant"
    try:
        token = client.create_meeting_token(
            room_name=room.daily_room_name,
            user_id=str(actor.pk),
            user_name=display_name,
            expires_at_epoch=int(token_expiry.timestamp()),
        )
    except (DailyConfigurationError, DailyUnavailable, DailyHTTPError, DailyInvalidResponse) as exc:
        raise _provider_failure(exc) from exc

    record_event(
        context=context,
        action=ECOUNSELING_JOIN_AUTHORIZED,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.room",
        target_id=room.pk,
        metadata={
            "appointment_id": str(appointment.pk),
            "participant_type": participant_type,
            "provider": "DAILY",
        },
    )
    if room.daily_room_url is None:
        raise ECounselingInvalidProviderResponse("Daily room URL is unavailable.")
    return JoinCredential(
        room=room,
        room_url=room.daily_room_url,
        meeting_token=token,
        token_expires_at=token_expiry,
    )


def _provider_event_time(event_type: str, payload: dict[str, object]) -> datetime:
    field = "start_ts" if event_type == "meeting.started" else "end_ts"
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ECounselingInvalidWebhook("Daily webhook event timestamp is invalid.")
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ECounselingInvalidWebhook("Daily webhook event timestamp is invalid.") from exc


def process_daily_webhook(
    *,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    now_epoch: float | None = None,
) -> WebhookProcessingResult:
    if not settings.DAILY_ENABLED:
        raise ECounselingProviderDisabled("Daily E-Counseling is disabled.")
    verify_daily_webhook(
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
        secret_b64=settings.DAILY_WEBHOOK_HMAC,
        max_age_seconds=settings.DAILY_WEBHOOK_MAX_AGE_SECONDS,
        now_epoch=now_epoch,
    )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ECounselingInvalidWebhook("Daily webhook payload is invalid JSON.") from exc
    if not isinstance(event, dict):
        raise ECounselingInvalidWebhook("Daily webhook payload must be an object.")
    if event.get("test") == "test":
        return WebhookProcessingResult(accepted=True)

    event_type = event.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ECounselingInvalidWebhook("Daily webhook event type is missing.")

    from .media import MEDIA_WEBHOOK_TYPES, process_media_webhook_event

    supported_types = {"meeting.started", "meeting.ended"} | set(MEDIA_WEBHOOK_TYPES)
    if event_type not in supported_types:
        return WebhookProcessingResult(accepted=True)

    event_id = event.get("id")
    payload = event.get("payload")
    if not isinstance(event_id, str) or not event_id or len(event_id) > 160:
        raise ECounselingInvalidWebhook("Daily webhook event ID is invalid.")
    if not isinstance(payload, dict):
        raise ECounselingInvalidWebhook("Daily webhook event payload is invalid.")

    if event_type in MEDIA_WEBHOOK_TYPES:
        return process_media_webhook_event(
            event_type=event_type,
            event_id=event_id,
            event_ts=event.get("event_ts"),
            payload=payload,
        )

    room_name = payload.get("room")
    meeting_id = payload.get("meeting_id")
    if not isinstance(room_name, str) or not room_name or len(room_name) > 128:
        raise ECounselingInvalidWebhook("Daily webhook room is invalid.")
    if not isinstance(meeting_id, str) or not meeting_id or len(meeting_id) > 160:
        raise ECounselingInvalidWebhook("Daily webhook meeting ID is invalid.")
    occurred_at = _provider_event_time(event_type, payload)
    room = ECounselingRoom.objects.filter(daily_room_name=room_name).first()

    _, created = DailyWebhookReceipt.objects.get_or_create(
        provider_event_id=event_id,
        defaults={
            "event_type": event_type,
            "ecounseling_room": room,
            "provider_session_id": meeting_id,
            "provider_occurred_at": occurred_at,
        },
    )
    return WebhookProcessingResult(
        accepted=True,
        duplicate=not created,
        supported=True,
    )
