"""Source-faithful Referral Slip persistence and yearly human-reference counters."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.institutional_forms.models import FormRevision


class ReferralSubmissionChannel(models.TextChoices):
    LEGACY_UNSPECIFIED = "LEGACY_UNSPECIFIED", "Legacy origin unspecified"
    GCO_RECORDED = "GCO_RECORDED", "GCO recorded"
    FACULTY_PORTAL = "FACULTY_PORTAL", "Faculty digital submission"


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
    submission_channel = models.CharField(
        max_length=24,
        choices=ReferralSubmissionChannel.choices,
        default=ReferralSubmissionChannel.LEGACY_UNSPECIFIED,
        db_default="LEGACY_UNSPECIFIED",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="faculty_submitted_referrals",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    faculty_home_college = models.ForeignKey(
        "organization.College",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="faculty_origin_referrals",
    )
    student_college_at_submission = models.ForeignKey(
        "organization.College",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="student_origin_referrals",
    )
    submission_policy_digest = models.CharField(max_length=64, null=True, blank=True)
    submission_policy_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_faculty_referrals",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_referrals",
    )
    student_name_snapshot = models.CharField(max_length=512)
    course_year_block_snapshot = models.CharField(max_length=255)
    confidential_content_ciphertext = models.TextField(editable=False)
    referred_on = models.DateField()
    received_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="acknowledged_faculty_referrals",
    )
    acknowledgment_policy_digest = models.CharField(max_length=64, null=True, blank=True)
    acknowledgment_policy_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="acknowledgment_approved_referrals",
    )
    administratively_closed_at = models.DateTimeField(null=True, blank=True)
    administratively_closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="administratively_closed_referrals",
    )
    closure_policy_digest = models.CharField(max_length=64, null=True, blank=True)
    closure_policy_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closure_approved_referrals",
    )
    administrative_version = models.PositiveIntegerField(default=1, db_default=1)
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="referrals",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_referrals",
        null=True,
        blank=True,
    )
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
                name="referral_administration_complete",
                condition=(
                    models.Q(
                        acknowledged_by__isnull=True,
                        acknowledgment_policy_digest__isnull=True,
                        acknowledgment_policy_event__isnull=True,
                        administratively_closed_by__isnull=True,
                        administratively_closed_at__isnull=True,
                        closure_policy_digest__isnull=True,
                        closure_policy_event__isnull=True,
                        administrative_version=1,
                    )
                    & (
                        ~models.Q(submission_channel="FACULTY_PORTAL")
                        | models.Q(received_at__isnull=True)
                    )
                )
                | (
                    models.Q(
                        submission_channel="FACULTY_PORTAL",
                        acknowledged_by__isnull=False,
                        received_at__isnull=False,
                        acknowledgment_policy_digest__isnull=False,
                        acknowledgment_policy_digest__regex=r"^[0-9a-f]{64}$",
                        acknowledgment_policy_event__isnull=False,
                    )
                    & (
                        models.Q(
                            administratively_closed_by__isnull=True,
                            administratively_closed_at__isnull=True,
                            closure_policy_digest__isnull=True,
                            closure_policy_event__isnull=True,
                            administrative_version=2,
                        )
                        | models.Q(
                            administratively_closed_by__isnull=False,
                            administratively_closed_at__isnull=False,
                            closure_policy_digest__isnull=False,
                            closure_policy_digest__regex=r"^[0-9a-f]{64}$",
                            closure_policy_event__isnull=False,
                            administrative_version=3,
                        )
                    )
                ),
            ),
            models.CheckConstraint(
                name="referral_administration_chronology",
                condition=(
                    ~models.Q(submission_channel="FACULTY_PORTAL")
                    | models.Q(received_at__isnull=True)
                    | models.Q(received_at__gte=models.F("submitted_at"))
                )
                & (
                    models.Q(administratively_closed_at__isnull=True)
                    | models.Q(administratively_closed_at__gte=models.F("received_at"))
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(submission_channel__in=ReferralSubmissionChannel.values),
                name="referral_submission_channel_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        submission_channel="FACULTY_PORTAL",
                        submitted_by__isnull=False,
                        submitted_at__isnull=False,
                        faculty_home_college__isnull=False,
                        student_college_at_submission__isnull=False,
                        submission_policy_digest__regex=r"^[0-9a-f]{64}$",
                        submission_policy_digest__isnull=False,
                        submission_policy_event__isnull=False,
                        recorded_by__isnull=True,
                    )
                    | (
                        ~models.Q(submission_channel="FACULTY_PORTAL")
                        & models.Q(
                            submitted_by__isnull=True,
                            submitted_at__isnull=True,
                            faculty_home_college__isnull=True,
                            student_college_at_submission__isnull=True,
                            submission_policy_digest__isnull=True,
                            submission_policy_event__isnull=True,
                        )
                    )
                ),
                name="referral_submission_provenance_complete",
            ),
            models.CheckConstraint(
                condition=~models.Q(confidential_content_ciphertext=""),
                name="referral_confidential_ciphertext_present",
            ),
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
    remarks_ciphertext = models.TextField(editable=False)
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
            ),
            models.CheckConstraint(
                condition=~models.Q(remarks_ciphertext=""),
                name="referral_action_ciphertext_present",
            ),
        ]
