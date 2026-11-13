"""Case responsibility arrangements, separate from the immutable legacy grant vocabulary."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CaseContinuityReason(models.TextChoices):
    IMPARTIALITY_CONCERN = (
        "IMPARTIALITY_CONCERN",
        "Potential conflict of interest or impartiality concern",
    )
    PLANNED_ABSENCE = "PLANNED_ABSENCE", "Planned absence"
    UNEXPECTED_ABSENCE = "UNEXPECTED_ABSENCE", "Unexpected absence"
    TEMPORARY_SUPPORT = "TEMPORARY_SUPPORT", "Temporary support"
    SERVICE_RESPONSIBILITY_CHANGE = "SERVICE_RESPONSIBILITY_CHANGE", "Service responsibility change"


class CaseArrangementState(models.TextChoices):
    PREPARED = "PREPARED", "Prepared"
    AUTHORIZED = "AUTHORIZED", "Authorized"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    CANCELLED = "CANCELLED", "Cancelled"


class CaseArrangementDecisionReason(models.TextChoices):
    NO_CAPACITY = "NO_CAPACITY", "Unable to take the work"
    INFORMATION_INCOMPLETE = "INFORMATION_INCOMPLETE", "More information is needed"
    ARRANGEMENT_NOT_SUITABLE = "ARRANGEMENT_NOT_SUITABLE", "Another arrangement is needed"
    REQUEST_WITHDRAWN = "REQUEST_WITHDRAWN", "Request withdrawn"
    REVIEW_WINDOW_ENDED = "REVIEW_WINDOW_ENDED", "Review window ended"


class CaseAuthorizationRoute(models.TextChoices):
    INDEPENDENT_HEAD = "INDEPENDENT_HEAD", "Independent Head authorization"
    DIRECT_OUTGOING_HEAD = "DIRECT_OUTGOING_HEAD", "Head's own outgoing case"
    OWNER_TO_HEAD = "OWNER_TO_HEAD", "Primary Counselor's request to the Head"


class CaseStudentCommunication(models.TextChoices):
    YES = "YES", "Student informed"
    NO = "NO", "Student not informed"
    DEFERRED = "DEFERRED", "Informing deferred"


class CaseCommunicationDeferral(models.TextChoices):
    STUDENT_UNAVAILABLE = "STUDENT_UNAVAILABLE", "Student unavailable"
    CONTACT_PENDING = "CONTACT_PENDING", "Contact pending"
    SUPPORT_TIMING = "SUPPORT_TIMING", "Timing of support"


class CaseOfficePreparationReason(models.TextChoices):
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE", "Primary Counselor unavailable"
    IMPARTIALITY_CONCERN = "IMPARTIALITY_CONCERN", "Potential impartiality concern"


class CaseTaskDisposition(models.TextChoices):
    TRANSFER = "TRANSFER", "Transfer with the case"
    RETAIN = "RETAIN", "Retain with the current assignee"
    HAND_OVER_AS_NEW = "HAND_OVER_AS_NEW", "Hand over as a new case action"
    RESOLVE_FIRST = "RESOLVE_FIRST", "Complete or cancel first"


class CaseAppointmentDisposition(models.TextChoices):
    REASSIGN = "REASSIGN", "Reassign through Appointments"
    RESCHEDULE = "RESCHEDULE", "Reschedule through Appointments"
    CANCEL = "CANCEL", "Cancel through Appointments"
    RETAIN_WITH_PROVIDER = "RETAIN_WITH_PROVIDER", "Retain with the provider"


class CaseAppointmentRetentionReason(models.TextChoices):
    CONTINUING_SUPPORT = "CONTINUING_SUPPORT", "Continuing support with this provider"
    ARRANGED_WITH_STUDENT = "ARRANGED_WITH_STUDENT", "Arrangement made with the Student"
    SEPARATE_SERVICE_WORK = "SEPARATE_SERVICE_WORK", "Separate planned work"


class CounselingCaseTransfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=40, unique=True)
    case = models.ForeignKey(
        "counseling.CounselingCase", on_delete=models.PROTECT, related_name="transfers"
    )
    outgoing_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="outgoing_case_transfers"
    )
    receiving_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="incoming_case_transfers"
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_case_transfers"
    )
    reason = models.CharField(max_length=40, choices=CaseContinuityReason.choices)
    office_preparation_reason = models.CharField(
        max_length=32, choices=CaseOfficePreparationReason.choices, blank=True, default=""
    )
    state = models.CharField(
        max_length=16, choices=CaseArrangementState.choices, default=CaseArrangementState.PREPARED
    )
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authorized_case_transfers",
        null=True,
        blank=True,
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    authorized_version = models.PositiveIntegerField(null=True, blank=True)
    independent_authorization = models.BooleanField(default=True)
    authorization_route = models.CharField(
        max_length=24, choices=CaseAuthorizationRoute.choices, blank=True, default=""
    )
    review_expires_at = models.DateTimeField(null=True, blank=True)
    # Null marks a pre-CW-3b submitted offer; no handoff is fabricated for existing data.
    handoff_required_at = models.DateTimeField(null=True, blank=True)
    case_handoff = models.ForeignKey(
        "counseling.CounselingCaseHandoff",
        on_delete=models.PROTECT,
        related_name="selected_by_transfers",
        null=True,
        blank=True,
    )
    handoff_exception = models.ForeignKey(
        "counseling.CounselingCaseHandoffException",
        on_delete=models.PROTECT,
        related_name="selected_by_transfers",
        null=True,
        blank=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decided_case_transfers",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(
        max_length=32, choices=CaseArrangementDecisionReason.choices, blank=True, default=""
    )
    student_communication = models.CharField(
        max_length=16, choices=CaseStudentCommunication.choices, default=CaseStudentCommunication.NO
    )
    communication_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_case_transfer_communications",
    )
    student_informed_at = models.DateTimeField(null=True, blank=True)
    communication_deferral_reason = models.CharField(
        max_length=32, choices=CaseCommunicationDeferral.choices, blank=True, default=""
    )
    communication_task = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        related_name="communication_transfers",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("case", "state", "review_expires_at"), name="cw_transfer_case_idx"
            ),
            models.Index(fields=("receiving_counselor", "state"), name="cw_transfer_receiver_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="cw_transfer_version_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(outgoing_counselor=models.F("receiving_counselor")),
                name="cw_transfer_distinct_people",
            ),
            models.CheckConstraint(
                condition=models.Q(reason__in=CaseContinuityReason.values),
                name="cw_transfer_reason_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=CaseArrangementState.values),
                name="cw_transfer_state_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state__in=["AUTHORIZED", "ACCEPTED"])
                    | models.Q(submitted_at__isnull=False)
                ),
                name="cw_transfer_submission_present",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state="ACCEPTED")
                    | models.Q(
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                        review_expires_at__isnull=False,
                    )
                ),
                name="cw_transfer_acceptance_present",
            ),
        ]


class CounselingCaseTransferTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        CounselingCaseTransfer, on_delete=models.CASCADE, related_name="task_plans"
    )
    task = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        related_name="case_transfer_plans",
    )
    disposition = models.CharField(max_length=24, choices=CaseTaskDisposition.choices)
    task_version = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=32, null=True, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    due_at = models.DateTimeField()
    successor_title_ciphertext = models.TextField(null=True, blank=True, editable=False)
    successor_due_at = models.DateTimeField(null=True, blank=True)
    successor = models.ForeignKey(
        "guidance_followups.GuidanceFollowUp",
        on_delete=models.PROTECT,
        related_name="succeeded_transfer_plans",
        null=True,
        blank=True,
    )

    class Meta:
        default_permissions = ()
        ordering = ("due_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("transfer", "task"), name="cw_transfer_task_unique"),
            models.CheckConstraint(
                condition=models.Q(disposition__in=CaseTaskDisposition.values),
                name="cw_transfer_task_plan_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(disposition="HAND_OVER_AS_NEW")
                    | models.Q(
                        successor_title_ciphertext__isnull=False, successor_due_at__isnull=False
                    )
                ),
                name="cw_transfer_successor_present",
            ),
        ]


class CounselingCaseTransferAppointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        CounselingCaseTransfer, on_delete=models.CASCADE, related_name="appointment_plans"
    )
    link = models.ForeignKey(
        "counseling.CounselingCaseAppointment",
        on_delete=models.PROTECT,
        related_name="transfer_plans",
    )
    disposition = models.CharField(max_length=24, choices=CaseAppointmentDisposition.choices)
    retention_reason = models.CharField(
        max_length=32, choices=CaseAppointmentRetentionReason.choices, blank=True, default=""
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        default_permissions = ()
        ordering = ("starts_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("transfer", "link"), name="cw_transfer_appointment_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(disposition__in=CaseAppointmentDisposition.values),
                name="cw_transfer_appointment_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(disposition="RETAIN_WITH_PROVIDER")
                    | models.Q(retention_reason__in=CaseAppointmentRetentionReason.values)
                ),
                name="cw_transfer_retention_reason",
            ),
        ]


class CounselingCaseResponsibility(models.Model):
    """New responsibility periods only. The opening period is derived, never backfilled."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "counseling.CounselingCase", on_delete=models.PROTECT, related_name="responsibility_periods"
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="case_responsibility_periods",
    )
    transfer = models.OneToOneField(
        CounselingCaseTransfer, on_delete=models.PROTECT, related_name="responsibility_period"
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ("started_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("case",),
                condition=models.Q(ended_at__isnull=True),
                name="cw_responsibility_one_current",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F("started_at"))
                ),
                name="cw_responsibility_time_order",
            ),
        ]


class CounselingCaseTransferEvent(models.Model):
    """Content-free append-only lifecycle snapshots, including invalidated authorizations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        CounselingCaseTransfer, on_delete=models.PROTECT, related_name="history"
    )
    kind = models.CharField(max_length=16)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_transfer_events"
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    independent_authorization = models.BooleanField()
    authorization_route = models.CharField(max_length=24)

    class Meta:
        default_permissions = ()
        ordering = ("occurred_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("transfer", "version", "kind"), name="cw_transfer_event_once"
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
                    ]
                ),
                name="cw_transfer_event_kind_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Case transfer history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Case transfer history is append-only.")
