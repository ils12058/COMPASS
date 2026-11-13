"""Case handoff snapshots, attributed additions and receipt; legacy handoffs are independent."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CaseHandoffState(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"


class CaseHandoffUnavailableReason(models.TextChoices):
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE", "Original Counselor unavailable"
    INFORMATION_NOT_OBTAINABLE = "INFORMATION_NOT_OBTAINABLE", "Information cannot be obtained"
    IMPARTIALITY_CONCERN = "IMPARTIALITY_CONCERN", "Handoff cannot appropriately be obtained"


class CounselingCaseHandoff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        "counseling.CounselingCaseTransfer", on_delete=models.PROTECT, related_name="handoffs"
    )
    case = models.ForeignKey(
        "counseling.CounselingCase", on_delete=models.PROTECT, related_name="handoffs"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_handoffs"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_case_handoffs"
    )
    receiving_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_case_handoffs"
    )
    state = models.CharField(max_length=16, choices=CaseHandoffState.choices, default="DRAFT")
    plan_digest = models.CharField(max_length=64)
    content_ciphertext = models.TextField(editable=False)
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("transfer", "state"), name="cw_handoff_transfer_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""), name="cw_handoff_body_present"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="cw_handoff_version_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(author=models.F("receiving_counselor")),
                name="cw_handoff_distinct_people",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state="DRAFT", submitted_at__isnull=True)
                    | models.Q(state="SUBMITTED", submitted_at__isnull=False)
                ),
                name="cw_handoff_submission_present",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            not self._state.adding
            and type(self).objects.filter(pk=self.pk, state="SUBMITTED").exists()
        ):
            raise ValueError("Submitted case handoffs are immutable; add an attributed addendum.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Case handoff history cannot be deleted.")


class CounselingCaseHandoffAddendum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    handoff = models.ForeignKey(
        CounselingCaseHandoff, on_delete=models.PROTECT, related_name="addenda"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_handoff_addenda"
    )
    content_ciphertext = models.TextField(editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""), name="cw_handoff_addendum_present"
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Case handoff addenda are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Case handoff addenda cannot be deleted.")


class CounselingCaseHandoffReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    handoff = models.ForeignKey(
        CounselingCaseHandoff, on_delete=models.PROTECT, related_name="receipts"
    )
    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_handoff_receipts"
    )
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("handoff", "reader"), name="cw_handoff_receipt_once")
        ]


class CounselingCaseHandoffException(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        "counseling.CounselingCaseTransfer",
        on_delete=models.PROTECT,
        related_name="handoff_exceptions",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_handoff_exceptions"
    )
    reason = models.CharField(max_length=32, choices=CaseHandoffUnavailableReason.choices)
    plan_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(reason__in=CaseHandoffUnavailableReason.values),
                name="cw_handoff_exception_reason",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Case handoff exceptions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Case handoff exception history cannot be deleted.")
