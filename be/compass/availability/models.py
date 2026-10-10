"""Persistent recurring Availability configuration and dated unavailability exceptions."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Weekday(models.TextChoices):
    MONDAY = "MONDAY", "Monday"
    TUESDAY = "TUESDAY", "Tuesday"
    WEDNESDAY = "WEDNESDAY", "Wednesday"
    THURSDAY = "THURSDAY", "Thursday"
    FRIDAY = "FRIDAY", "Friday"
    SATURDAY = "SATURDAY", "Saturday"
    SUNDAY = "SUNDAY", "Sunday"


class AvailabilityModeScope(models.TextChoices):
    ALL = "ALL", "All delivery modes"
    IN_PERSON = "IN_PERSON", "In person"
    ONLINE = "ONLINE", "Online"


class OfficeAvailabilityWindow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    weekday = models.CharField(max_length=9, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    mode_scope = models.CharField(max_length=16, choices=AvailabilityModeScope.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("weekday", "start_time", "end_time", "mode_scope", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="availability_office_window_order",
            ),
            models.UniqueConstraint(
                fields=("weekday", "start_time", "end_time", "mode_scope"),
                name="availability_office_window_exact_uniq",
            ),
        ]


class ProviderAvailabilityWindow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="availability_windows",
    )
    weekday = models.CharField(max_length=9, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    mode_scope = models.CharField(max_length=16, choices=AvailabilityModeScope.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("provider_id", "weekday", "start_time", "end_time", "mode_scope", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="availability_provider_window_order",
            ),
            models.UniqueConstraint(
                fields=("provider", "weekday", "start_time", "end_time", "mode_scope"),
                name="availability_provider_window_exact_uniq",
            ),
        ]


class OfficeUnavailability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    mode_scope = models.CharField(max_length=16, choices=AvailabilityModeScope.choices)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_office_unavailability",
    )

    class Meta:
        default_permissions = ()
        ordering = ("starts_at", "ends_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="availability_office_exception_order",
            ),
        ]


class ProviderUnavailability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="unavailability_exceptions",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    mode_scope = models.CharField(max_length=16, choices=AvailabilityModeScope.choices)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_provider_unavailability",
    )

    class Meta:
        default_permissions = ()
        ordering = ("provider_id", "starts_at", "ends_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="availability_provider_exception_order",
            ),
        ]
