"""Provider binding, consent, and minimal Daily telemetry persistence for E-Counseling."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from compass.appointments.models import Appointment


class ECounselingRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="ecounseling_room",
    )
    daily_room_name = models.CharField(max_length=128, unique=True)
    daily_room_id = models.CharField(max_length=128, null=True, blank=True)
    daily_room_url = models.URLField(max_length=500, null=True, blank=True)
    room_expires_at = models.DateTimeField(null=True, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")


class ConsentScope(models.TextChoices):
    AUDIO_VIDEO_RECORDING = "AUDIO_VIDEO_RECORDING", "Audio/video recording"
    LIVE_TRANSCRIPTION = "LIVE_TRANSCRIPTION", "Live transcription"
    TRANSCRIPT_STORAGE = "TRANSCRIPT_STORAGE", "Transcript storage"


class ConsentDecision(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    DENIED = "DENIED", "Denied"


class ECounselingConsent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        ECounselingRoom,
        on_delete=models.PROTECT,
        related_name="consents",
    )
    scope = models.CharField(max_length=32, choices=ConsentScope.choices)
    decision = models.CharField(
        max_length=16,
        choices=ConsentDecision.choices,
        default=ConsentDecision.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("requested_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("room", "scope"),
                name="ec_consent_room_scope_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        decision=ConsentDecision.PENDING,
                        decided_at__isnull=True,
                        withdrawn_at__isnull=True,
                    )
                    | Q(
                        decision__in=(ConsentDecision.APPROVED, ConsentDecision.DENIED),
                        decided_at__isnull=False,
                    )
                ),
                name="ec_consent_decision_time_ck",
            ),
            models.CheckConstraint(
                condition=Q(withdrawn_at__isnull=True) | Q(decision=ConsentDecision.APPROVED),
                name="ec_consent_withdrawn_approved_ck",
            ),
        ]

    @property
    def is_effectively_approved(self) -> bool:
        return self.decision == ConsentDecision.APPROVED and self.withdrawn_at is None


class MediaCaptureKind(models.TextChoices):
    RECORDING = "RECORDING", "Recording"
    TRANSCRIPTION = "TRANSCRIPTION", "Transcription"


class MediaCaptureStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    START_REQUESTED = "START_REQUESTED", "Start requested"
    ACTIVE = "ACTIVE", "Active"
    STOP_REQUESTED = "STOP_REQUESTED", "Stop requested"
    STOPPED = "STOPPED", "Stopped"
    READY = "READY", "Ready"
    ERROR = "ERROR", "Error"


class ECounselingMediaCapture(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        ECounselingRoom,
        on_delete=models.PROTECT,
        related_name="media_captures",
    )
    kind = models.CharField(max_length=20, choices=MediaCaptureKind.choices)
    status = models.CharField(
        max_length=20,
        choices=MediaCaptureStatus.choices,
        default=MediaCaptureStatus.NOT_STARTED,
    )
    transcript_storage_enabled = models.BooleanField(default=False)
    provider_instance_id = models.CharField(max_length=160, null=True, blank=True)
    provider_artifact_id = models.CharField(max_length=160, null=True, blank=True)
    provider_session_id = models.CharField(max_length=160, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stop_requested_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    error_code = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("room", "kind"),
                name="ec_media_room_kind_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind=MediaCaptureKind.TRANSCRIPTION)
                    | Q(transcript_storage_enabled=False)
                ),
                name="ec_media_storage_transcription_ck",
            ),
            models.CheckConstraint(
                condition=Q(duration_seconds__isnull=True) | Q(duration_seconds__gte=0),
                name="ec_media_duration_nonnegative_ck",
            ),
        ]


class DailyWebhookReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_event_id = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=80)
    ecounseling_room = models.ForeignKey(
        ECounselingRoom,
        on_delete=models.SET_NULL,
        related_name="daily_webhook_receipts",
        null=True,
        blank=True,
    )
    provider_session_id = models.CharField(max_length=160, null=True, blank=True)
    provider_occurred_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("-received_at", "id")
        indexes = [
            models.Index(fields=("event_type", "-received_at"), name="daily_event_time_idx"),
        ]
