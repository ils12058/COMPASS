"""Counselor-proposed next sessions (NS-1) and case-linked Call Slips.

A proposal records offered times only. It never reserves a slot: the Appointment exists only after
the Student accepts one option through the ordinary booking service.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from compass.service_catalog.models import DeliveryMode

from .case_models import CounselingCase

MAX_PROPOSAL_OPTIONS = 3


class SessionProposalState(models.TextChoices):
    PENDING = "PENDING", "Waiting for the Student"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"
    EXPIRED = "EXPIRED", "Expired"


class SessionProposalPurpose(models.TextChoices):
    """Closed, neutral purposes. Free text would let case narrative reach the Student."""

    FOLLOW_UP_SESSION = "FOLLOW_UP_SESSION", "Follow-up session"
    CHECK_IN = "CHECK_IN", "Check-in"
    CONTINUING_SESSION = "CONTINUING_SESSION", "Continuing session"


class CounselingSessionProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        CounselingCase, on_delete=models.PROTECT, related_name="session_proposals"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="session_proposals"
    )
    # The Counselor who proposed and who would provide the session.
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="proposed_counseling_sessions",
    )
    service = models.ForeignKey(
        "service_catalog.Service", on_delete=models.PROTECT, related_name="session_proposals"
    )
    purpose = models.CharField(max_length=32, choices=SessionProposalPurpose.choices)
    # The Follow-up the proposal was made from, for the "Complete this follow-up?" prompt only.
    follow_up = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        related_name="session_proposals",
        null=True,
        blank=True,
    )
    call_slip_requested = models.BooleanField(default=False)
    state = models.CharField(
        max_length=16, choices=SessionProposalState.choices, default=SessionProposalState.PENDING
    )
    expires_at = models.DateTimeField()
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    accepted_position = models.PositiveSmallIntegerField(null=True, blank=True)
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="session_proposal",
        null=True,
        blank=True,
    )
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="withdrawn_counseling_session_proposals",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(fields=("case", "-created_at"), name="ns_proposal_case_idx"),
            models.Index(fields=("student", "state", "expires_at"), name="ns_proposal_student_idx"),
        ]
        constraints = [
            # One open proposal per case: two at once would ask the Student the same question.
            models.UniqueConstraint(
                fields=("case",),
                condition=models.Q(state="PENDING"),
                name="ns_proposal_one_pending_per_case",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="ns_proposal_version_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state="PENDING",
                        decided_at__isnull=True,
                        accepted_position__isnull=True,
                        appointment__isnull=True,
                        withdrawn_by__isnull=True,
                    )
                    | models.Q(
                        state="ACCEPTED",
                        decided_at__isnull=False,
                        accepted_position__isnull=False,
                        appointment__isnull=False,
                        withdrawn_by__isnull=True,
                    )
                    | models.Q(
                        state__in=["DECLINED", "EXPIRED"],
                        decided_at__isnull=False,
                        accepted_position__isnull=True,
                        appointment__isnull=True,
                        withdrawn_by__isnull=True,
                    )
                    | models.Q(
                        state="WITHDRAWN",
                        decided_at__isnull=False,
                        accepted_position__isnull=True,
                        appointment__isnull=True,
                        withdrawn_by__isnull=False,
                    )
                ),
                name="ns_proposal_state_shape",
            ),
        ]


class CounselingSessionProposalOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        CounselingSessionProposal, on_delete=models.PROTECT, related_name="options"
    )
    position = models.PositiveSmallIntegerField()
    delivery_mode = models.CharField(max_length=16, choices=DeliveryMode.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        default_permissions = ()
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("proposal", "position"), name="ns_proposal_option_position_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1, position__lte=MAX_PROPOSAL_OPTIONS),
                name="ns_proposal_option_position_range",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="ns_proposal_option_time_order",
            ),
        ]


class CounselingCaseCallSlip(models.Model):
    """A Call Slip issued from a case. Standalone and Referral Call Slips have no row here."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        CounselingCase, on_delete=models.PROTECT, related_name="call_slip_links"
    )
    call_slip = models.OneToOneField(
        "call_slips.CallSlip", on_delete=models.PROTECT, related_name="case_link"
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="case_call_slips",
        null=True,
        blank=True,
    )
    proposal = models.ForeignKey(
        CounselingSessionProposal,
        on_delete=models.PROTECT,
        related_name="call_slip_links",
        null=True,
        blank=True,
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    linked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        indexes = [
            models.Index(fields=("case", "linked_at"), name="ns_case_call_slip_idx"),
            models.Index(fields=("appointment",), name="ns_case_call_slip_appt_idx"),
        ]
