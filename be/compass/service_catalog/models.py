"""Persistent Service Catalog configuration for COMPASS."""

from __future__ import annotations

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.accounts.models import Role

MIN_SERVICE_DURATION_MINUTES = 1
MAX_SERVICE_DURATION_MINUTES = 480


class AppointmentPolicy(models.TextChoices):
    NONE = "NONE", "None"
    OPTIONAL = "OPTIONAL", "Optional"
    REQUIRED = "REQUIRED", "Required"


class DeliveryMode(models.TextChoices):
    IN_PERSON = "IN_PERSON", "In person"
    ONLINE = "ONLINE", "Online"


class Service(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    appointment_policy = models.CharField(max_length=16, choices=AppointmentPolicy.choices)
    default_duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(MIN_SERVICE_DURATION_MINUTES),
            MaxValueValidator(MAX_SERVICE_DURATION_MINUTES),
        ],
    )
    cancellation_cutoff_minutes = models.PositiveIntegerField(null=True, blank=True)
    requires_current_inventory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(default_duration_minutes__isnull=True)
                    | models.Q(
                        default_duration_minutes__gte=MIN_SERVICE_DURATION_MINUTES,
                        default_duration_minutes__lte=MAX_SERVICE_DURATION_MINUTES,
                    )
                ),
                name="service_catalog_duration_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(cancellation_cutoff_minutes__isnull=True)
                    | models.Q(cancellation_cutoff_minutes__gte=0)
                ),
                name="service_catalog_cancellation_cutoff_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class ServiceDeliveryMode(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="delivery_mode_assignments",
    )
    mode = models.CharField(max_length=16, choices=DeliveryMode.choices)

    class Meta:
        default_permissions = ()
        ordering = ("mode",)
        constraints = [
            models.UniqueConstraint(
                fields=("service", "mode"),
                name="service_catalog_service_mode_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service.code}:{self.mode}"


class ServiceProviderRole(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="provider_role_assignments",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="service_provider_eligibilities",
    )

    class Meta:
        default_permissions = ()
        ordering = ("role__code",)
        constraints = [
            models.UniqueConstraint(
                fields=("service", "role"),
                name="service_catalog_service_provider_role_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service.code}:{self.role.code}"
