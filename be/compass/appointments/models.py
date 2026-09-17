"""Persistent Appointment reservation records and yearly human-reference counters."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.service_catalog.models import DeliveryMode, Service


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    CANCELLED = "CANCELLED", "Cancelled"


class AppointmentReferenceCounter(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(next_value__gte=1),
                name="appointments_reference_counter_positive",
            ),
        ]


class Appointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=32, unique=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_appointments",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="provider_appointments",
    )
    delivery_mode = models.CharField(max_length=16, choices=DeliveryMode.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
    )
    cancellation_cutoff_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("starts_at", "reference_code", "id")
        indexes = [
            models.Index(
                fields=("provider", "status", "starts_at", "ends_at"),
                name="appt_provider_time_idx",
            ),
            models.Index(
                fields=("student", "status", "starts_at", "ends_at"),
                name="appt_student_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="appointments_time_order",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(cancellation_cutoff_minutes__isnull=True)
                    | models.Q(cancellation_cutoff_minutes__gte=0)
                ),
                name="appointments_cancellation_cutoff_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status=AppointmentStatus.SCHEDULED, cancelled_at__isnull=True)
                    | models.Q(status=AppointmentStatus.CANCELLED, cancelled_at__isnull=False)
                ),
                name="appointments_status_cancellation_consistent",
            ),
        ]
