"""Metadata-only professional continuity provenance; no content authority."""

import uuid

from django.conf import settings
from django.db import models


class CoverageKind(models.TextChoices):
    PLANNED_HANDOFF = "PLANNED_HANDOFF", "Planned handoff"
    TEMPORARY_COVERAGE = "TEMPORARY_COVERAGE", "Temporary coverage"


class ContinuityReason(models.TextChoices):
    PLANNED_ABSENCE = "PLANNED_ABSENCE", "Planned absence"
    UNEXPECTED_ABSENCE = "UNEXPECTED_ABSENCE", "Unexpected absence"
    TEMPORARY_SUPPORT = "TEMPORARY_SUPPORT", "Temporary support"


class ContinuityDecision(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    APPROVED = "APPROVED", "Approved"
    DECLINED = "DECLINED", "Declined"
    CANCELLED = "CANCELLED", "Cancelled"
    REVOKED = "REVOKED", "Revoked"


class ContinuityRevocationReason(models.TextChoices):
    COVERAGE_ENDED = "COVERAGE_ENDED", "Coverage ended"
    AUTHORITY_CHANGED = "AUTHORITY_CHANGED", "Authority changed"
    REQUEST_WITHDRAWN = "REQUEST_WITHDRAWN", "Request withdrawn"


class ContinuitySourceKind(models.TextChoices):
    ENCOUNTER = "ENCOUNTER", "Encounter structural metadata"
    ROUTINE_EVALUATION = "ROUTINE_EVALUATION", "Finalized Routine Evaluation reference"


class ContinuityProjection(models.TextChoices):
    ENCOUNTER_METADATA_V1 = "ENCOUNTER_METADATA_V1", "Encounter metadata v1"
    FINALIZED_EVALUATION_V1 = "FINALIZED_EVALUATION_V1", "Finalized Evaluation v1"


class CounselorCaseContinuityGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="continuity_student_grants"
    )
    original_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="continuity_original_grants",
    )
    receiving_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="continuity_received_grants",
    )
    coverage_kind = models.CharField(max_length=24, choices=CoverageKind.choices)
    reason_category = models.CharField(max_length=24, choices=ContinuityReason.choices)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="continuity_requests"
    )
    requested_at = models.DateTimeField()
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    decision = models.CharField(
        max_length=16, choices=ContinuityDecision.choices, default=ContinuityDecision.REQUESTED
    )
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="continuity_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="continuity_revocations",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(
        max_length=24, choices=ContinuityRevocationReason.choices, blank=True, default=""
    )
    version = models.PositiveIntegerField(default=1)
    policy_version = models.CharField(max_length=64)
    policy_evidence = models.CharField(max_length=128)
    policy_digest = models.CharField(max_length=64)
    student_affiliation_marker = models.CharField(max_length=128)
    snapshot_digest = models.CharField(max_length=64)
    # One new client intent uses a UUID, never a bearer credential. Replays bind to snapshot.
    request_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-requested_at", "id")
        indexes = [
            models.Index(
                fields=("student", "receiving_counselor", "coverage_kind", "starts_at"),
                name="continuity_overlap_idx",
            ),
            models.Index(fields=("requested_by", "requested_at"), name="continuity_requester_idx"),
            models.Index(
                fields=("receiving_counselor", "requested_at"), name="continuity_receiver_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("requested_by", "request_id"), name="continuity_request_intent_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0), name="continuity_positive_version"
            ),
            models.CheckConstraint(
                condition=(
                    models.Func(
                        models.F("starts_at"),
                        function="isfinite",
                        output_field=models.BooleanField(),
                    )
                    & models.Func(
                        models.F("expires_at"),
                        function="isfinite",
                        output_field=models.BooleanField(),
                    )
                ),
                name="continuity_finite_interval",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("expires_at")),
                name="continuity_interval_order",
            ),
            models.CheckConstraint(
                condition=models.Q(coverage_kind__in=CoverageKind.values),
                name="continuity_valid_kind",
            ),
            models.CheckConstraint(
                condition=models.Q(reason_category__in=ContinuityReason.values),
                name="continuity_valid_reason",
            ),
            models.CheckConstraint(
                condition=models.Q(decision__in=ContinuityDecision.values),
                name="continuity_valid_decision",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        decision="REQUESTED", decision_by__isnull=True, decided_at__isnull=True
                    )
                    | models.Q(
                        decision__in=["APPROVED", "DECLINED", "CANCELLED", "REVOKED"],
                        decision_by__isnull=False,
                        decided_at__isnull=False,
                    )
                ),
                name="continuity_decision_provenance",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        decision="REVOKED",
                        revoked_by__isnull=False,
                        revoked_at__isnull=False,
                        revocation_reason__in=ContinuityRevocationReason.values,
                    )
                    | (
                        ~models.Q(decision="REVOKED")
                        & models.Q(
                            revoked_by__isnull=True, revoked_at__isnull=True, revocation_reason=""
                        )
                    )
                ),
                name="continuity_revocation_provenance",
            ),
            models.CheckConstraint(
                condition=~models.Q(policy_version="")
                & ~models.Q(policy_evidence="")
                & ~models.Q(policy_digest="")
                & ~models.Q(snapshot_digest=""),
                name="continuity_evidence_present",
            ),
        ]


class CounselorCaseContinuityScope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant = models.ForeignKey(
        CounselorCaseContinuityGrant, on_delete=models.PROTECT, related_name="scopes"
    )
    resource_kind = models.CharField(max_length=24, choices=ContinuitySourceKind.choices)
    source_id = models.UUIDField()
    projection = models.CharField(max_length=32, choices=ContinuityProjection.choices)
    source_revision = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("resource_kind", "source_id", "projection")
        constraints = [
            models.UniqueConstraint(
                fields=("grant", "resource_kind", "source_id", "projection"),
                name="continuity_exact_scope_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(resource_kind="ENCOUNTER", projection="ENCOUNTER_METADATA_V1")
                    | models.Q(
                        resource_kind="ROUTINE_EVALUATION", projection="FINALIZED_EVALUATION_V1"
                    )
                ),
                name="continuity_typed_projection",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_revision=""), name="continuity_revision_present"
            ),
        ]
