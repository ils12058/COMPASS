"""Provider-binding and minimal Daily telemetry persistence for E-Counseling."""

from __future__ import annotations

import uuid

from django.db import models

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
