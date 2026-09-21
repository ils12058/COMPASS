"""Source-faithful Referral Slip persistence and yearly human-reference counters."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.institutional_forms.models import FormRevision


class ReferralActionType(models.TextChoices):
    CALL_PARENT_GUARDIAN = "CALL_PARENT_GUARDIAN", "Call the Parent/Guardian"
    SEND_PARENT_NOTIFICATION_LETTER = (
        "SEND_PARENT_NOTIFICATION_LETTER",
        'Send "Parent Notification Letter"',
    )
    SEND_CALL_SLIP_INTERVIEW_PERMIT = (
        "SEND_CALL_SLIP_INTERVIEW_PERMIT",
        'Send "Call Slip/Interview Permit"',
    )


class ReferralReferenceCounter(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(next_value__gte=1),
                name="referral_counter_next_positive",
            )
        ]


class Referral(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=32, unique=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_referrals",
    )
    student_name_snapshot = models.CharField(max_length=512)
    course_year_block_snapshot = models.CharField(max_length=255)
    reason = models.TextField()
    referrer_name = models.CharField(max_length=255)
    referred_on = models.DateField()
    received_at = models.DateTimeField(null=True, blank=True)
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="referrals",
    )
    status_note = models.TextField(blank=True, default="")
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_referrals",
        null=True,
        blank=True,
    )
    void_reason = models.TextField(blank=True, default="", max_length=1000)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_referrals",
        null=True,
        blank=True,
    )
    creation_key_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    creation_request_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "reference_code", "id")
        indexes = [
            models.Index(
                fields=("student", "created_at"),
                name="referral_student_created_idx",
            ),
            models.Index(
                fields=("referred_on", "created_at"),
                name="referral_referred_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(voided_at__isnull=True, void_reason="")
                    | (models.Q(voided_at__isnull=False) & ~models.Q(void_reason=""))
                ),
                name="referral_void_shape",
            )
        ]


class ReferralAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        Referral,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    action_type = models.CharField(max_length=48, choices=ReferralActionType.choices)
    occurred_at = models.DateTimeField()
    remarks = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_referral_actions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("occurred_at", "created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("referral", "action_type"),
                name="referral_action_type_uniq",
            )
        ]
