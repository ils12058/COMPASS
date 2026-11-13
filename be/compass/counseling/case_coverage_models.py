"""Temporal case-task authority; legacy Student grants retain their own lifecycle."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .case_transfer_models import (
    CaseArrangementDecisionReason,
    CaseAuthorizationRoute,
    CaseCommunicationDeferral,
    CaseContinuityReason,
    CaseOfficePreparationReason,
    CaseStudentCommunication,
)


class CaseCoverageState(models.TextChoices):
    PREPARED = "PREPARED", "Prepared"
    AUTHORIZED = "AUTHORIZED", "Authorized"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    CANCELLED = "CANCELLED", "Cancelled"
    REVOKED = "REVOKED", "Revoked"


class CaseCoverageReturnPlan(models.TextChoices):
    RETURN_TO_PRIMARY = "RETURN_TO_PRIMARY", "Return unfinished work to the primary Counselor"
    REVIEW_WITH_PRIMARY = "REVIEW_WITH_PRIMARY", "Return work and review progress with the primary"


class CounselingCaseCoverage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=40, unique=True)
    case = models.ForeignKey(
        "counseling.CounselingCase", on_delete=models.PROTECT, related_name="coverages"
    )
    primary_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="primary_case_coverages"
    )
    receiving_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_case_coverages"
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_case_coverages"
    )
    reason = models.CharField(max_length=40, choices=CaseContinuityReason.choices)
    office_preparation_reason = models.CharField(
        max_length=32, choices=CaseOfficePreparationReason.choices, blank=True, default=""
    )
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    state = models.CharField(max_length=16, choices=CaseCoverageState.choices, default="PREPARED")
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    authorized_version = models.PositiveIntegerField(null=True, blank=True)
    independent_authorization = models.BooleanField(default=True)
    authorization_route = models.CharField(
        max_length=24, choices=CaseAuthorizationRoute.choices, blank=True, default=""
    )
    review_expires_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(
        max_length=32, choices=CaseArrangementDecisionReason.choices, blank=True, default=""
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(
        max_length=32, choices=CaseArrangementDecisionReason.choices, blank=True, default=""
    )
    student_communication = models.CharField(
        max_length=16, choices=CaseStudentCommunication.choices, default="NO"
    )
    communication_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="case_coverage_communications",
    )
    student_informed_at = models.DateTimeField(null=True, blank=True)
    communication_deferral_reason = models.CharField(
        max_length=32, choices=CaseCommunicationDeferral.choices, blank=True, default=""
    )
    communication_task = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="communication_coverages",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def outgoing_counselor_id(self):
        # Shared continuity authorization/communication functions use this historical identity.
        return self.primary_counselor_id

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(fields=("case", "state", "expires_at"), name="cw_coverage_case_idx"),
            models.Index(fields=("receiving_counselor", "state"), name="cw_coverage_receiver_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(version__gte=1), name="cw_coverage_version"),
            models.CheckConstraint(
                condition=~models.Q(primary_counselor=models.F("receiving_counselor")),
                name="cw_coverage_distinct_people",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("starts_at")),
                name="cw_coverage_interval",
            ),
            models.CheckConstraint(
                condition=models.Q(reason__in=CaseContinuityReason.values),
                name="cw_coverage_reason",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=CaseCoverageState.values), name="cw_coverage_state"
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state__in=["AUTHORIZED", "ACCEPTED", "REVOKED"])
                    | models.Q(
                        submitted_at__isnull=False,
                        authorized_at__isnull=False,
                        review_expires_at__isnull=False,
                        authorized_version__isnull=False,
                    )
                ),
                name="cw_coverage_authorization",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state__in=["ACCEPTED", "REVOKED"])
                    | models.Q(
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                    )
                ),
                name="cw_coverage_acceptance",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state="REVOKED")
                    | models.Q(
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                    )
                ),
                name="cw_coverage_revocation",
            ),
        ]


class CounselingCaseCoverageTask(models.Model):
    """A selected task's temporal assignee, deadline and explicit return plan.

    Follow-Up.assigned_to retains the primary assignment. Live coverage overrides that
    assignment only inside the accepted interval; starting/ending authority needs no job.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coverage = models.ForeignKey(
        CounselingCaseCoverage, on_delete=models.CASCADE, related_name="task_plans"
    )
    task = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        related_name="coverage_plans",
    )
    task_version = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=32, null=True, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField()
    return_plan = models.CharField(max_length=24, choices=CaseCoverageReturnPlan.choices)
    delegated_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    recovery_required = models.BooleanField(default=False)
    recovered_at = models.DateTimeField(null=True, blank=True)
    recovered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        default_permissions = ()
        ordering = ("due_at", "id")
        indexes = [
            models.Index(fields=("task", "returned_at"), name="cw_coverage_task_idx"),
            models.Index(fields=("recovery_required", "id"), name="cw_coverage_recovery_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("coverage", "task"), name="cw_coverage_task_once"),
            models.CheckConstraint(
                condition=models.Q(return_plan__in=CaseCoverageReturnPlan.values),
                name="cw_coverage_return_plan",
            ),
            models.CheckConstraint(
                condition=models.Q(task_version__gte=1), name="cw_coverage_task_version"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(returned_at__isnull=True, returned_by__isnull=True)
                    | models.Q(returned_at__isnull=False, returned_by__isnull=False)
                ),
                name="cw_coverage_return_attributed",
            ),
        ]


class CounselingCaseCoverageEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coverage = models.ForeignKey(
        CounselingCaseCoverage, on_delete=models.PROTECT, related_name="history"
    )
    kind = models.CharField(max_length=16)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    occurred_at = models.DateTimeField(default=timezone.now)
    independent_authorization = models.BooleanField()
    authorization_route = models.CharField(max_length=24)

    class Meta:
        default_permissions = ()
        ordering = ("occurred_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("coverage", "version", "kind"), name="cw_coverage_event_once"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=[
                        "prepared",
                        "updated",
                        "submitted",
                        "authorized",
                        "accepted",
                        "declined",
                        "cancelled",
                        "revoked",
                    ]
                ),
                name="cw_coverage_event_kind",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Case coverage history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Case coverage history is append-only.")
