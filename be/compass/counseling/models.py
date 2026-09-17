"""Persistent records for completed Counseling encounters."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.appointments.models import Appointment
from compass.service_catalog.models import DeliveryMode, Service


class CounselingEntryMode(models.TextChoices):
    APPOINTMENT = "APPOINTMENT", "Appointment"
    WALK_IN = "WALK_IN", "Walk in"
    CALLED_IN = "CALLED_IN", "Called in"
    REFERRED = "REFERRED", "Referred"


class CounselingEncounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_counseling_encounters",
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="counselor_counseling_encounters",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="counseling_encounters",
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="counseling_encounter",
        null=True,
        blank=True,
    )
    entry_mode = models.CharField(max_length=16, choices=CounselingEntryMode.choices)
    delivery_mode = models.CharField(max_length=16, choices=DeliveryMode.choices)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_counseling_encounters",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-started_at", "id")
        indexes = [
            models.Index(
                fields=("counselor", "started_at"),
                name="counseling_counselor_time_idx",
            ),
            models.Index(
                fields=("student", "started_at"),
                name="counseling_student_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(started_at__lt=models.F("ended_at")),
                name="counseling_time_order",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(entry_mode=CounselingEntryMode.APPOINTMENT)
                    | models.Q(appointment__isnull=False)
                ),
                name="counseling_appointment_mode_requires_link",
            ),
        ]
