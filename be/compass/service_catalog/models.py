"""Persistent Service Catalog configuration for COMPASS."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.accounts.models import Role

MIN_SERVICE_DURATION_MINUTES = 1
MAX_SERVICE_DURATION_MINUTES = 480


class DeliveryMode(models.TextChoices):
    IN_PERSON = "IN_PERSON", "In person"
    ONLINE = "ONLINE", "Online"


class ServiceProviderCoverage(models.TextChoices):
    """Which active Counselors are qualified to provide new work for a Service (ADR-089)."""

    ALL_COUNSELORS = "ALL_COUNSELORS", "All Counselors"
    SELECTED_COUNSELORS = "SELECTED_COUNSELORS", "Selected Counselors"


class Service(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    # Whether Students may create new Appointments for this Service. It does not mean other
    # workflows require an Appointment: each domain owns its own direct initiation (ADR-089).
    appointment_booking_enabled = models.BooleanField(default=False)
    # The settings below apply only to new Appointments and stay empty while booking is off.
    default_appointment_duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(MIN_SERVICE_DURATION_MINUTES),
            MaxValueValidator(MAX_SERVICE_DURATION_MINUTES),
        ],
    )
    cancellation_cutoff_minutes = models.PositiveIntegerField(null=True, blank=True)
    # A booking prerequisite only: never a Service-delivery, Counseling, or Routine prerequisite.
    requires_current_inventory = models.BooleanField(default=False)
    provider_coverage = models.CharField(
        max_length=24,
        choices=ServiceProviderCoverage.choices,
        default=ServiceProviderCoverage.ALL_COUNSELORS,
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(default_appointment_duration_minutes__isnull=True)
                    | models.Q(
                        default_appointment_duration_minutes__gte=MIN_SERVICE_DURATION_MINUTES,
                        default_appointment_duration_minutes__lte=MAX_SERVICE_DURATION_MINUTES,
                    )
                ),
                name="service_catalog_duration_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(appointment_booking_enabled=True)
                    | models.Q(
                        default_appointment_duration_minutes__isnull=True,
                        cancellation_cutoff_minutes__isnull=True,
                        requires_current_inventory=False,
                    )
                ),
                name="service_catalog_booking_settings_require_booking",
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
    """Legacy role-level provider configuration (ADR-089).

    Historical rows, including Guidance Services Staff ones, are kept for history only. COMPASS
    no longer writes or reads them for eligibility: Counselor is the one provider class, and
    ``Service.provider_coverage`` with ``ServiceCounselorProvider`` decides qualification.
    """

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


class ServiceCounselorProvider(models.Model):
    """A Counselor qualified to provide new instances of a SELECTED_COUNSELORS Service.

    Qualification only: it carries no College, Availability, routing, or record access.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="counselor_providers",
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="service_provider_qualifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("service", "counselor")
        constraints = [
            models.UniqueConstraint(
                fields=("service", "counselor"),
                name="service_catalog_service_counselor_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service.code}:{self.counselor_id}"
