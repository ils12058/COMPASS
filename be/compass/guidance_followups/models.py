"""Follow-Up is independently owned; source-domain rows are never mutated."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class FollowUpSource(models.TextChoices):
    COUNSELING_ENCOUNTER = "COUNSELING_ENCOUNTER", "Counseling encounter"
    REFERRAL = "REFERRAL", "Referral"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW", "Routine interview"


class FollowUpVisibility(models.TextChoices):
    OPERATIONAL = "OPERATIONAL", "Operational coordination"
    COUNSELOR_CONFIDENTIAL = "COUNSELOR_CONFIDENTIAL", "Counselor-confidential"


class FollowUpCategory(models.TextChoices):
    ADMINISTRATIVE = "ADMINISTRATIVE", "Administrative coordination"
    STUDENT_CONTACT = "STUDENT_CONTACT", "Student contact"
    COUNSELING = "COUNSELING", "Counseling follow-up"
    REFERRAL_ACTION = "REFERRAL_ACTION", "Referral coordination"


class FollowUpStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class FollowUpEventType(models.TextChoices):
    CREATED = "CREATED", "Created"
    UPDATED = "UPDATED", "Updated"
    REASSIGNED = "REASSIGNED", "Reassigned"
    ACTIVITY_RECORDED = "ACTIVITY_RECORDED", "Activity recorded"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class GuidanceFollowUp(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_guidance_followups",
    )
    source_kind = models.CharField(
        max_length=32, choices=FollowUpSource.choices, null=True, blank=True
    )
    source_id = models.UUIDField(null=True, blank=True)
    visibility = models.CharField(max_length=32, choices=FollowUpVisibility.choices)
    category = models.CharField(max_length=32, choices=FollowUpCategory.choices)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_guidance_followups",
    )
    due_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=FollowUpStatus.choices, default=FollowUpStatus.PENDING
    )
    description_ciphertext = models.TextField(null=True, blank=True, editable=False)
    outcome_ciphertext = models.TextField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_guidance_followups",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="completed_guidance_followups",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_guidance_followups",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    creation_key_digest = models.CharField(max_length=64, unique=True)
    creation_request_fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("due_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(source_kind__isnull=True, source_id__isnull=True)
                    | Q(source_kind__isnull=False, source_id__isnull=False)
                ),
                name="fup_source_pair_consistent",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="fup_version_positive"),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="PENDING",
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        outcome_ciphertext__isnull=True,
                    )
                    | Q(
                        status="COMPLETED",
                        completed_at__isnull=False,
                        completed_by__isnull=False,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        outcome_ciphertext__isnull=False,
                    )
                    | Q(
                        status="CANCELLED",
                        cancelled_at__isnull=False,
                        cancelled_by__isnull=False,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        outcome_ciphertext__isnull=True,
                    )
                ),
                name="fup_terminal_state_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("assigned_to", "status", "due_at", "id"), name="fup_assignment_idx"
            ),
            models.Index(fields=("student", "created_at", "id"), name="fup_student_created_idx"),
            models.Index(fields=("source_kind", "source_id"), name="fup_source_ref_idx"),
        ]


class GuidanceFollowUpEvent(models.Model):
    """Immutable structural/provenance history; no free-form metadata or plaintext."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    followup = models.ForeignKey(GuidanceFollowUp, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=24, choices=FollowUpEventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guidance_followup_events"
    )
    revision = models.PositiveIntegerField()
    old_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    new_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    old_due_at = models.DateTimeField(null=True, blank=True)
    new_due_at = models.DateTimeField(null=True, blank=True)
    remarks_ciphertext = models.TextField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("revision", "created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("followup", "revision"), name="fup_event_revision_unique"
            ),
            models.CheckConstraint(condition=Q(revision__gte=1), name="fup_event_version_positive"),
        ]


class GuidanceFollowUpMutation(models.Model):
    """Durable request identity only; no second business lifecycle or free-text payload."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    followup = models.ForeignKey(
        GuidanceFollowUp, on_delete=models.PROTECT, related_name="mutation_receipts"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="followup_mutation_receipts",
    )
    key_digest = models.CharField(max_length=64, unique=True)
    request_fingerprint = models.CharField(max_length=64)
    action = models.CharField(max_length=32)
    revision = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
