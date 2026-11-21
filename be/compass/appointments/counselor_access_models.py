"""Student requests for a different Counselor and Head-approved booking exceptions (ADR-120)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

MAX_DECISION_NOTE_LENGTH = 500


class CounselorBookingRequestState(models.TextChoices):
    PENDING = "PENDING", "Waiting for the Head Guidance Counselor"
    APPROVED = "APPROVED", "Approved"
    DECLINED = "DECLINED", "Declined"


class CounselorBookingRequest(models.Model):
    """A Student's request to the Head Guidance Counselor to book with a different Counselor.

    ``reason_ciphertext`` holds an authenticated encrypted envelope readable only by the
    Head Guidance Counselor. At most one PENDING request may exist per Student.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="counselor_booking_requests",
    )
    preferred_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preferred_counselor_booking_requests",
    )
    reason_ciphertext = models.TextField(null=True, blank=True, editable=False)
    state = models.CharField(
        max_length=16,
        choices=CounselorBookingRequestState.choices,
        default=CounselorBookingRequestState.PENDING,
    )
    approved_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_counselor_booking_requests",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="decided_counselor_booking_requests",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=MAX_DECISION_NOTE_LENGTH, blank=True, default="")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("state", "created_at", "id"),
                name="appt_creq_queue_idx",
            ),
            models.Index(
                fields=("student", "-created_at"),
                name="appt_creq_student_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("student",),
                condition=models.Q(state=CounselorBookingRequestState.PENDING),
                name="appt_creq_one_pending",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="appt_creq_version_pos",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=CounselorBookingRequestState.values),
                name="appt_creq_state_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state=CounselorBookingRequestState.PENDING,
                        decided_at__isnull=True,
                        decided_by__isnull=True,
                        approved_counselor__isnull=True,
                    )
                    | models.Q(
                        state=CounselorBookingRequestState.APPROVED,
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                        approved_counselor__isnull=False,
                    )
                    | models.Q(
                        state=CounselorBookingRequestState.DECLINED,
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                        approved_counselor__isnull=True,
                    )
                ),
                name="appt_creq_decision_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"CounselorBookingRequest({self.pk}, {self.state})"


class StudentCounselorApproval(models.Model):
    """Standing Head Guidance Counselor approval allowing a Student to book another Counselor.

    Lasts until the Head changes or ends it; an inactive approved Counselor falls back to the
    Student's default Counselor automatically at read and booking time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="counselor_booking_approvals",
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_counselor_booking_approvals",
    )
    source_request = models.ForeignKey(
        CounselorBookingRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approvals",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_counselor_booking_approvals",
    )
    approved_at = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ended_counselor_booking_approvals",
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-approved_at", "id")
        indexes = [
            models.Index(
                fields=("ended_at", "-approved_at", "id"),
                name="appt_cappr_active_idx",
            ),
            models.Index(
                fields=("counselor", "ended_at"),
                name="appt_cappr_counselor_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("student",),
                condition=models.Q(ended_at__isnull=True),
                name="appt_cappr_one_active",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="appt_cappr_version_pos",
            ),
            models.CheckConstraint(
                condition=~models.Q(student=models.F("counselor")),
                name="appt_cappr_distinct",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(ended_at__isnull=True, ended_by__isnull=True)
                    | models.Q(ended_at__isnull=False, ended_by__isnull=False)
                ),
                name="appt_cappr_ended_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"StudentCounselorApproval({self.pk}, active={self.ended_at is None})"


__all__ = [
    "CounselorBookingRequest",
    "CounselorBookingRequestState",
    "MAX_DECISION_NOTE_LENGTH",
    "StudentCounselorApproval",
]
