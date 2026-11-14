"""Head approval for reassigning a case-linked Appointment (RA-1).

Reassigning one Appointment moves a single session, never the case. When the Appointment is part
of an Active Counseling case, the move follows the case-transfer authorization route: an
independent current Head approves it before it happens, and until then the Appointment stays with
its current Counselor. The request snapshots what was reviewed; any later change to the Appointment
or the case makes it no longer current instead of applying a different change.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .case_models import CounselingCase
from .case_transfer_models import CaseAuthorizationRoute

MAX_REASSIGNMENT_REASON = 500
MAX_DECISION_REASON = 500


class CaseReassignmentState(models.TextChoices):
    PENDING = "PENDING", "Waiting for Head approval"
    APPROVED = "APPROVED", "Approved and applied"
    DECLINED = "DECLINED", "Declined"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"
    EXPIRED = "EXPIRED", "No longer current"


class CaseAppointmentReassignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        "appointments.Appointment", on_delete=models.PROTECT, related_name="case_reassignments"
    )
    case = models.ForeignKey(
        CounselingCase, on_delete=models.PROTECT, related_name="appointment_reassignments"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_case_reassignments",
    )
    # Snapshots of what the Head reviewed. A decision on a changed Appointment never applies.
    from_provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    to_provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    case_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    appointment_starts_at = models.DateTimeField()
    reason = models.CharField(max_length=MAX_REASSIGNMENT_REASON)
    route = models.CharField(max_length=32, choices=CaseAuthorizationRoute.choices)
    state = models.CharField(
        max_length=16, choices=CaseReassignmentState.choices, default=CaseReassignmentState.PENDING
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decided_case_reassignments",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=MAX_DECISION_REASON, blank=True, default="")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(fields=("state", "appointment_starts_at"), name="ra_state_start_idx"),
            models.Index(fields=("appointment", "-created_at"), name="ra_appointment_idx"),
        ]
        constraints = [
            # One open request per Appointment: two would ask the Head to decide the same session.
            models.UniqueConstraint(
                fields=("appointment",),
                condition=models.Q(state="PENDING"),
                name="ra_one_pending_per_appointment",
            ),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="ra_version_positive"),
            models.CheckConstraint(
                condition=~models.Q(from_provider=models.F("to_provider")),
                name="ra_provider_changes",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state="PENDING", decided_at__isnull=True, decided_by__isnull=True)
                    | models.Q(
                        state__in=["APPROVED", "DECLINED"],
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                    )
                    | models.Q(state__in=["WITHDRAWN", "EXPIRED"], decided_at__isnull=False)
                ),
                name="ra_decision_matches_state",
            ),
        ]

    def __str__(self) -> str:
        return f"CaseAppointmentReassignment({self.appointment_id}, {self.state})"
