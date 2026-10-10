"""Persistent singleton state for COMPASS Maintenance Mode."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

MAINTENANCE_SINGLETON_ID = 1
MAINTENANCE_MESSAGE_MAX_LENGTH = 500


class MaintenanceConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=MAINTENANCE_SINGLETON_ID,
        editable=False,
    )
    manual_enabled = models.BooleanField(default=False)
    manual_message = models.CharField(
        max_length=MAINTENANCE_MESSAGE_MAX_LENGTH,
        blank=True,
        default="",
    )
    manual_expected_end_at = models.DateTimeField(blank=True, null=True)
    scheduled_start_at = models.DateTimeField(blank=True, null=True)
    scheduled_end_at = models.DateTimeField(blank=True, null=True)
    scheduled_message = models.CharField(
        max_length=MAINTENANCE_MESSAGE_MAX_LENGTH,
        blank=True,
        default="",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=Q(pk=MAINTENANCE_SINGLETON_ID),
                name="platform_maint_singleton_pk",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scheduled_start_at__isnull=True, scheduled_end_at__isnull=True)
                    | Q(
                        scheduled_start_at__isnull=False,
                        scheduled_end_at__isnull=False,
                        scheduled_end_at__gt=F("scheduled_start_at"),
                    )
                ),
                name="platform_maint_schedule_pair",
            ),
        ]


__all__ = [
    "MAINTENANCE_MESSAGE_MAX_LENGTH",
    "MAINTENANCE_SINGLETON_ID",
    "MaintenanceConfiguration",
]
