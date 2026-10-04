"""Operational rules and single-member frozen disposition cases; no domain content."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class RetentionCategory(models.TextChoices):
    GRADUATE_TRACER = "GRADUATE_TRACER", "Graduate Tracer"
    ECOUNSELING_RECORDING = "ECOUNSELING_RECORDING", "E-Counseling recordings"
    ECOUNSELING_TRANSCRIPT = "ECOUNSELING_TRANSCRIPT", "E-Counseling stored transcripts"


class RetentionTrigger(models.TextChoices):
    SUBMITTED_AT = "SUBMITTED_AT", "Submission"
    MEDIA_READY_AT = "MEDIA_READY_AT", "Provider artifact ready"


class DispositionAction(models.TextChoices):
    ANONYMIZE = "ANONYMIZE", "Anonymize"
    DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE = (
        "DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE",
        "Delete provider artifact, keep evidence",
    )


class RetentionRuleStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class DispositionState(models.TextChoices):
    READY = "READY", "Needs review"
    ON_HOLD = "ON_HOLD", "On hold"
    BLOCKED = "BLOCKED", "Blocked"
    NO_LONGER_ELIGIBLE = "NO_LONGER_ELIGIBLE", "No longer eligible"
    APPROVED = "APPROVED", "Approved"
    QUEUED = "QUEUED", "Queued"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED", "Reconciliation required"


class DispositionBlocker(models.TextChoices):
    RULE_INACTIVE = "RULE_INACTIVE", "Rule is inactive or not yet effective"
    SOURCE_CHANGED = "SOURCE_CHANGED", "Source lifecycle changed"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE", "Source is unavailable"
    MEDIA_NOT_TERMINAL = "MEDIA_NOT_TERMINAL", "Media lifecycle is unresolved"
    ARTIFACT_ID_MISSING = "ARTIFACT_ID_MISSING", "Provider artifact ID is missing"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE", "Provider unavailable"
    PROVIDER_REJECTED = "PROVIDER_REJECTED", "Provider rejected the request"
    PROVIDER_UNVERIFIED = "PROVIDER_UNVERIFIED", "Provider outcome unverified"
    EXTERNAL_STORAGE = "EXTERNAL_STORAGE", "External storage requires operator reconciliation"
    VERIFICATION_FAILED = "VERIFICATION_FAILED", "Disposition verification failed"
    WORKER_INTERRUPTED = "WORKER_INTERRUPTED", "Worker interrupted; reconcile before retry"


class OperationalRetentionRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=160)
    category = models.CharField(max_length=32, choices=RetentionCategory.choices)
    trigger = models.CharField(max_length=24, choices=RetentionTrigger.choices)
    duration_days = models.PositiveIntegerField()
    action = models.CharField(max_length=48, choices=DispositionAction.choices)
    policy_reference = models.CharField(max_length=500)
    effective_on = models.DateField()
    status = models.CharField(max_length=16, choices=RetentionRuleStatus.choices, default="DRAFT")
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True)
    retired_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("category",),
                condition=Q(status="ACTIVE"),
                name="one_active_retention_category",
            ),
            models.CheckConstraint(
                condition=Q(duration_days__gte=1, duration_days__lte=365000),
                name="retention_duration_days_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=RetentionRuleStatus.values),
                name="retention_rule_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(category="GRADUATE_TRACER", trigger="SUBMITTED_AT", action="ANONYMIZE")
                    | Q(
                        category__in=("ECOUNSELING_RECORDING", "ECOUNSELING_TRANSCRIPT"),
                        trigger="MEDIA_READY_AT",
                        action="DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE",
                    )
                ),
                name="retention_supported_treatment",
            ),
        ]


class DispositionCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        OperationalRetentionRule, on_delete=models.PROTECT, related_name="cases"
    )
    rule_revision = models.PositiveIntegerField()
    category = models.CharField(max_length=32, choices=RetentionCategory.choices)
    # Internal only. Never projected through DPO APIs or copied into AuditEvent metadata.
    source_id = models.UUIDField()
    source_updated_at = models.DateTimeField()
    eligible_at = models.DateTimeField()
    state = models.CharField(max_length=32, choices=DispositionState.choices, default="READY")
    blocker = models.CharField(max_length=32, choices=DispositionBlocker.choices, null=True)
    revision = models.PositiveIntegerField(default=1)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )
    approved_at = models.DateTimeField(null=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    claim_token = models.UUIDField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    manual_retries = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("eligible_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("category", "source_id"), name="disposition_source_unique"
            ),
            models.CheckConstraint(
                condition=Q(state__in=DispositionState.values), name="disposition_state_valid"
            ),
        ]
        indexes = [
            models.Index(fields=("state", "next_attempt_at"), name="disposition_dispatch_idx")
        ]


class DispositionHold(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(DispositionCase, on_delete=models.PROTECT, related_name="holds")
    reason = models.CharField(max_length=240)
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    placed_at = models.DateTimeField(auto_now_add=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )
    released_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("case",),
                condition=Q(released_at__isnull=True),
                name="one_active_disposition_hold",
            )
        ]
