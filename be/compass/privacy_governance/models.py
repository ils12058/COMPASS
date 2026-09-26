"""Privacy-governance records without underlying confidential domain content."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class RetentionPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    scope_summary = models.TextField(max_length=2_000)
    retention_trigger_summary = models.TextField(max_length=2_000)
    retention_period_summary = models.TextField(max_length=1_000)
    disposition_summary = models.TextField(max_length=2_000)
    policy_reference = models.CharField(max_length=255, blank=True, default="")
    effective_on = models.DateField(null=True, blank=True)
    review_due_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)


class PrivacyNotice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)


class PrivacyNoticeRevisionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class PrivacyNoticeRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice = models.ForeignKey(PrivacyNotice, on_delete=models.PROTECT, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=PrivacyNoticeRevisionStatus.choices,
        default=PrivacyNoticeRevisionStatus.DRAFT,
    )
    title = models.CharField(max_length=200)
    audiences = models.JSONField(default=list)
    summary = models.TextField(max_length=2_000)
    body = models.TextField(max_length=20_000)
    requires_acknowledgment = models.BooleanField(default=False)
    effective_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_privacy_notice_revisions",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_privacy_notice_revisions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ("notice_id", "-revision_number")
        constraints = [
            models.UniqueConstraint(
                fields=("notice", "revision_number"), name="unique_notice_revision_number"
            ),
            models.UniqueConstraint(
                fields=("notice",), condition=Q(status="DRAFT"), name="one_notice_draft"
            ),
            models.UniqueConstraint(
                fields=("notice",), condition=Q(status="PUBLISHED"), name="one_notice_published"
            ),
        ]


class PrivacyNoticeAcknowledgment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="privacy_notice_acknowledgments",
    )
    revision = models.ForeignKey(
        PrivacyNoticeRevision, on_delete=models.PROTECT, related_name="acknowledgments"
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("user", "revision"), name="unique_notice_acknowledgment"
            )
        ]


class ProcessingActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    purpose = models.TextField(max_length=2_000)
    data_subject_categories = models.JSONField(default=list)
    personal_data_categories = models.JSONField(default=list)
    authorized_access_summary = models.TextField(max_length=2_000)
    safeguards_summary = models.TextField(max_length=2_000)
    retention_policy_reference = models.CharField(max_length=255, blank=True, default="")
    retention_policy = models.ForeignKey(
        RetentionPolicy,
        on_delete=models.PROTECT,
        related_name="processing_activities",
        null=True,
        blank=True,
    )
    data_subject_choice_summary = models.TextField(max_length=2_000, blank=True, default="")
    policy_basis_reference = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)


class PrivacyReviewType(models.TextChoices):
    PRIVACY_REVIEW = "PRIVACY_REVIEW", "Privacy review"
    PIA = "PIA", "Privacy impact assessment record"


class PrivacyReviewStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"


class PrivacyReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    processing_activity = models.ForeignKey(
        ProcessingActivity,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    review_type = models.CharField(max_length=32, choices=PrivacyReviewType.choices)
    status = models.CharField(
        max_length=16,
        choices=PrivacyReviewStatus.choices,
        default=PrivacyReviewStatus.OPEN,
    )
    scope_summary = models.TextField(max_length=2_000)
    findings_summary = models.TextField(max_length=4_000, blank=True, default="")
    recommendations_summary = models.TextField(max_length=4_000, blank=True, default="")
    resolution_summary = models.TextField(max_length=4_000, blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="privacy_reviews",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "-id")


class PrivacyIncidentStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ASSESSING = "ASSESSING", "Assessing"
    CONTAINED = "CONTAINED", "Contained"
    RESOLVED = "RESOLVED", "Resolved"


class PrivacyNotificationAssessment(models.TextChoices):
    NOT_ASSESSED = "NOT_ASSESSED", "Not assessed"
    NOT_REQUIRED = "NOT_REQUIRED", "Not required"
    REQUIRED = "REQUIRED", "Required"
    COMPLETED = "COMPLETED", "Completed"


class PrivacyIncident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=32, unique=True, editable=False)
    title = models.CharField(max_length=200)
    summary = models.TextField(max_length=3_000)
    affected_area = models.CharField(max_length=255)
    personal_data_categories = models.JSONField(default=list)
    status = models.CharField(
        max_length=16,
        choices=PrivacyIncidentStatus.choices,
        default=PrivacyIncidentStatus.OPEN,
    )
    occurred_at = models.DateTimeField(blank=True, null=True)
    discovered_at = models.DateTimeField()
    estimated_affected_subjects = models.PositiveIntegerField(blank=True, null=True)
    assessment_summary = models.TextField(max_length=4_000, blank=True, default="")
    containment_summary = models.TextField(max_length=4_000, blank=True, default="")
    notification_assessment = models.CharField(
        max_length=24,
        choices=PrivacyNotificationAssessment.choices,
        default=PrivacyNotificationAssessment.NOT_ASSESSED,
    )
    notification_reference = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "-id")


__all__ = [
    "RetentionPolicy",
    "PrivacyNotice",
    "PrivacyNoticeRevision",
    "PrivacyNoticeRevisionStatus",
    "PrivacyNoticeAcknowledgment",
    "PrivacyIncident",
    "PrivacyIncidentStatus",
    "PrivacyNotificationAssessment",
    "PrivacyReview",
    "PrivacyReviewStatus",
    "PrivacyReviewType",
    "ProcessingActivity",
]
