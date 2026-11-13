"""One retained closure per cycle; only reopening attribution may subsequently change."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CaseClosureReason(models.TextChoices):
    PLANNED_SUPPORT_CONCLUDED = "PLANNED_SUPPORT_CONCLUDED", "Planned support concluded"
    STUDENT_DISCONTINUED = "STUDENT_DISCONTINUED", "Student chose to discontinue"
    CONTACT_NOT_REESTABLISHED = (
        "CONTACT_NOT_REESTABLISHED",
        "Unable to re-establish contact after documented attempts",
    )
    EXTERNAL_HANDOVER_CONFIRMED = (
        "EXTERNAL_HANDOVER_CONFIRMED",
        "External service handover confirmed",
    )
    ELIGIBILITY_ENDED = "ELIGIBILITY_ENDED", "Institutional service eligibility ended"


class CaseClosureOutcome(models.TextChoices):
    GOALS_MET = "GOALS_MET", "Goals met"
    GOALS_PARTLY_MET = "GOALS_PARTLY_MET", "Goals partly met"
    GOALS_NOT_MET = "GOALS_NOT_MET", "Goals not met"
    NOT_ASSESSED = "NOT_ASSESSED", "Not assessed"


class CaseReopenReason(models.TextChoices):
    SAME_CONCERN_RETURNED = "SAME_CONCERN_RETURNED", "Same concern returned"
    FURTHER_SUPPORT_NEEDED = "FURTHER_SUPPORT_NEEDED", "Further support needed"
    CLOSED_IN_ERROR = "CLOSED_IN_ERROR", "Closed in error"


class CounselingCaseClosure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "counseling.CounselingCase", on_delete=models.PROTECT, related_name="closures"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="closed_counseling_cases"
    )
    closed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=40, choices=CaseClosureReason.choices)
    outcome = models.CharField(max_length=24, choices=CaseClosureOutcome.choices)
    content_ciphertext = models.TextField(null=True, blank=True, editable=False)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reopened_counseling_cases",
        null=True,
        blank=True,
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.CharField(
        max_length=32, choices=CaseReopenReason.choices, null=True, blank=True
    )

    class Meta:
        default_permissions = ()
        ordering = ("closed_at", "id")
        indexes = [models.Index(fields=("case", "closed_at"), name="cw_closure_case_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=("case",),
                condition=models.Q(reopened_at__isnull=True),
                name="cw_closure_one_closed_cycle",
            ),
            models.CheckConstraint(
                condition=models.Q(reason__in=CaseClosureReason.values),
                name="cw_closure_reason_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=CaseClosureOutcome.values),
                name="cw_closure_outcome_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        reopened_at__isnull=True,
                        reopened_by__isnull=True,
                        reopen_reason__isnull=True,
                    )
                    | models.Q(
                        reopened_at__isnull=False,
                        reopened_by__isnull=False,
                        reopen_reason__in=CaseReopenReason.values,
                        reopened_at__gte=models.F("closed_at"),
                    )
                ),
                name="cw_closure_reopening_complete",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            fixed = (
                "case_id",
                "closed_by_id",
                "closed_at",
                "reason",
                "outcome",
                "content_ciphertext",
            )
            if any(getattr(previous, name) != getattr(self, name) for name in fixed):
                raise ValueError("Closure records are immutable; reopen the existing cycle.")
            if previous.reopened_at is not None and any(
                getattr(previous, name) != getattr(self, name)
                for name in ("reopened_by_id", "reopened_at", "reopen_reason")
            ):
                raise ValueError("A recorded reopening is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Closure history cannot be deleted.")
