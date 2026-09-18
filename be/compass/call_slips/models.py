"""Source-faithful Interview Permit / Call Slip persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.institutional_forms.models import FormRevision
from compass.referrals.models import Referral


class CallSlipDestinationType(models.TextChoices):
    GUIDANCE_OFFICE = "GUIDANCE_OFFICE", "Guidance Office"
    OTHER = "OTHER", "Other"


class CallSlip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_call_slips",
    )
    student_name_snapshot = models.CharField(max_length=512)
    course_year_snapshot = models.CharField(max_length=255)
    referral = models.OneToOneField(
        Referral,
        on_delete=models.PROTECT,
        related_name="call_slip",
        null=True,
        blank=True,
    )
    destination_type = models.CharField(max_length=32, choices=CallSlipDestinationType.choices)
    other_destination = models.CharField(max_length=255, blank=True, default="")
    report_at = models.DateTimeField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_call_slips",
    )
    issued_by_name_snapshot = models.CharField(max_length=512)
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="call_slips",
    )
    interview_ended_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_call_slips",
        null=True,
        blank=True,
    )
    creation_key_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    creation_request_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-report_at", "-created_at", "id")
        indexes = [
            models.Index(fields=("student", "report_at"), name="callslip_student_report_idx"),
            models.Index(fields=("issued_by", "report_at"), name="callslip_issuer_report_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        destination_type=CallSlipDestinationType.GUIDANCE_OFFICE,
                        other_destination="",
                    )
                    | (
                        models.Q(destination_type=CallSlipDestinationType.OTHER)
                        & ~models.Q(other_destination="")
                    )
                ),
                name="callslip_destination_consistency",
            )
        ]
