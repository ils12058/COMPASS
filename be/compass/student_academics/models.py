"""Shadow current-state academic profile; no SAR-1 consumer reads it."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.organization.models import College, Program


class PlacementVerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"


class StudentAcademicProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_academic_profile",
    )
    current_college = models.ForeignKey(
        College,
        on_delete=models.PROTECT,
        related_name="student_academic_profiles",
        null=True,
        blank=True,
    )
    current_program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="student_academic_programs",
        null=True,
        blank=True,
    )
    placement_verification_status = models.CharField(
        max_length=16,
        choices=PlacementVerificationStatus.choices,
        default=PlacementVerificationStatus.UNVERIFIED,
    )
    placement_effective_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("student_id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    placement_verification_status__in=PlacementVerificationStatus.values
                ),
                name="student_academics_verification_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"StudentAcademicProfile({self.student_id})"
