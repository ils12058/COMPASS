"""Good Moral request, issuance provenance, and certificate-local snapshots."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.organization.models import AcademicYear


class GoodMoralVariant(models.TextChoices):
    CURRENT_STUDENT = "CURRENT_STUDENT", "Current Student"
    GRADUATE = "GRADUATE", "Graduate"


class GoodMoralInitiationOrigin(models.TextChoices):
    STUDENT_SELF = "STUDENT_SELF", "Student self-service"
    GCO_ASSISTED = "GCO_ASSISTED", "Guidance Office assisted"
    LEGACY_UNSPECIFIED = "LEGACY_UNSPECIFIED", "Legacy, initiator not verified"


class GoodMoralStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    READY_FOR_ISSUANCE = "READY_FOR_ISSUANCE", "Ready for issuance"
    ISSUED = "ISSUED", "Issued"
    CANCELLED = "CANCELLED", "Cancelled"


CANONICAL_YEAR_LEVELS: tuple[str, ...] = (
    "1st Year",
    "2nd Year",
    "3rd Year",
    "4th Year",
)

CANONICAL_SEMESTERS: tuple[str, ...] = (
    "First Semester",
    "Second Semester",
)


class GoodMoralRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    graduation_opportunity = models.ForeignKey(
        "exit_interviews.ExitInterviewOpportunity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="good_moral_requests",
    )
    exit_interview = models.ForeignKey(
        "exit_interviews.ExitInterview",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="good_moral_requests",
    )
    exit_interview_submitted_at = models.DateTimeField(null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="good_moral_requests",
    )
    # A persistent database default allows old application versions to keep inserting safely.
    initiation_origin = models.CharField(
        max_length=24,
        choices=GoodMoralInitiationOrigin.choices,
        default=GoodMoralInitiationOrigin.LEGACY_UNSPECIFIED,
        db_default=GoodMoralInitiationOrigin.LEGACY_UNSPECIFIED,
        editable=False,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="initiated_good_moral_requests",
        editable=False,
    )
    variant = models.CharField(max_length=24, choices=GoodMoralVariant.choices)
    status = models.CharField(
        max_length=24,
        choices=GoodMoralStatus.choices,
        default=GoodMoralStatus.REQUESTED,
    )

    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.PROTECT,
        related_name="good_moral_requests",
        null=True,
        blank=True,
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="good_moral_requests",
        null=True,
        blank=True,
    )
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="good_moral_requests",
        null=True,
        blank=True,
    )

    applicant_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    major_snapshot = models.CharField(max_length=180, blank=True, default="")

    year_level_snapshot = models.CharField(max_length=64, blank=True, default="")
    college_snapshot = models.CharField(max_length=160, blank=True, default="")
    course_snapshot = models.CharField(max_length=180, blank=True, default="")
    semester_snapshot = models.CharField(max_length=80, blank=True, default="")

    degree_snapshot = models.CharField(max_length=255, blank=True, default="")
    graduation_date = models.DateField(null=True, blank=True)

    official_receipt_number = models.CharField(max_length=96, blank=True, default="")
    official_receipt_date = models.DateField(null=True, blank=True)
    official_receipt_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prepared_good_moral_requests",
        null=True,
        blank=True,
    )
    prepared_receipt_verification = models.ForeignKey(
        "GoodMoralReceiptVerification",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prepared_requests",
    )
    issued_receipt_assignment = models.ForeignKey(
        "GoodMoralReceiptAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="issued_requests",
    )
    issued_receipt_verification = models.ForeignKey(
        "GoodMoralReceiptVerification",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="issued_requests",
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_good_moral_requests",
        null=True,
        blank=True,
    )
    issued_by_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    document_template_key = models.CharField(max_length=128, null=True, blank=True)
    document_template_version = models.PositiveIntegerField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_good_moral_requests",
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(blank=True, default="", max_length=1000)

    creation_key_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    creation_request_fingerprint = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("student", "created_at"),
                name="good_moral_student_created_idx",
            ),
            models.Index(
                fields=("status", "created_at"),
                name="good_moral_status_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        initiation_origin=GoodMoralInitiationOrigin.LEGACY_UNSPECIFIED,
                        initiated_by__isnull=True,
                    )
                    | models.Q(
                        initiation_origin=GoodMoralInitiationOrigin.STUDENT_SELF,
                        initiated_by__isnull=False,
                        initiated_by=models.F("student"),
                    )
                    | models.Q(
                        initiation_origin=GoodMoralInitiationOrigin.GCO_ASSISTED,
                        initiated_by__isnull=False,
                    )
                ),
                name="good_moral_initiation_shape",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(prepared_at__isnull=True, prepared_by__isnull=True)
                        & ~models.Q(status=GoodMoralStatus.READY_FOR_ISSUANCE)
                    )
                    | models.Q(
                        status__in=(
                            GoodMoralStatus.READY_FOR_ISSUANCE,
                            GoodMoralStatus.ISSUED,
                            GoodMoralStatus.CANCELLED,
                        ),
                        prepared_at__isnull=False,
                        prepared_by__isnull=False,
                    )
                ),
                name="good_moral_preparation_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        graduation_opportunity__isnull=True,
                        exit_interview__isnull=True,
                        exit_interview_submitted_at__isnull=True,
                    )
                    | models.Q(
                        variant=GoodMoralVariant.CURRENT_STUDENT,
                        graduation_opportunity__isnull=False,
                        exit_interview__isnull=False,
                        exit_interview_submitted_at__isnull=False,
                    )
                ),
                name="good_moral_exit_prereq_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        variant=GoodMoralVariant.CURRENT_STUDENT,
                        inventory__isnull=False,
                        academic_year__isnull=False,
                        degree_snapshot="",
                        graduation_date__isnull=True,
                    )
                    | models.Q(
                        variant=GoodMoralVariant.GRADUATE,
                        inventory__isnull=True,
                        academic_year__isnull=True,
                        year_level_snapshot="",
                        college_snapshot="",
                        course_snapshot="",
                        semester_snapshot="",
                    )
                ),
                name="good_moral_variant_provenance_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=(
                            GoodMoralStatus.REQUESTED,
                            GoodMoralStatus.READY_FOR_ISSUANCE,
                            GoodMoralStatus.CANCELLED,
                        ),
                        form_revision__isnull=True,
                        issued_at__isnull=True,
                        issued_by__isnull=True,
                        issued_by_name_snapshot="",
                        document_template_key__isnull=True,
                        document_template_version__isnull=True,
                    )
                    | (
                        models.Q(
                            status=GoodMoralStatus.ISSUED,
                            form_revision__isnull=False,
                            issued_at__isnull=False,
                            issued_by__isnull=False,
                            document_template_key__isnull=False,
                            document_template_version__isnull=False,
                        )
                        & ~models.Q(issued_by_name_snapshot="")
                    )
                ),
                name="good_moral_issuance_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=(
                            GoodMoralStatus.REQUESTED,
                            GoodMoralStatus.READY_FOR_ISSUANCE,
                            GoodMoralStatus.ISSUED,
                        ),
                        cancelled_at__isnull=True,
                        cancellation_reason="",
                    )
                    | (
                        models.Q(
                            status=GoodMoralStatus.CANCELLED,
                            cancelled_at__isnull=False,
                        )
                        & ~models.Q(cancellation_reason="")
                    )
                ),
                name="good_moral_cancellation_shape",
            ),
        ]


class ReceiptIdentityState(models.TextChoices):
    BOUND = "BOUND", "Bound"
    LEGACY_AMBIGUOUS = "LEGACY_AMBIGUOUS", "Legacy ownership unresolved"
    DISPUTED = "DISPUTED", "Disputed"


class ReceiptOrigin(models.TextChoices):
    ORDINARY = "ORDINARY", "Operational entry"
    LEGACY_OBSERVED = "LEGACY_OBSERVED", "Historical observation"
    RECONCILED = "RECONCILED", "Reserved for future approved reconciliation"


class ReceiptLedgerMode(models.TextChoices):
    DORMANT = "DORMANT", "Existing writer; ledger not active"
    FENCED = "FENCED", "Good Moral writes fenced for import"
    ACTIVE = "ACTIVE", "Ledger owns receipt writes"


class GoodMoralReceiptImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    source_digest = models.CharField(max_length=64)
    source_count = models.PositiveIntegerField()
    evidence_reference = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class GoodMoralReceiptLedger(models.Model):
    """Database writer fence. No environment flag can activate the ledger."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    mode = models.CharField(max_length=8, choices=ReceiptLedgerMode.choices, default="DORMANT")
    batch = models.ForeignKey(GoodMoralReceiptImportBatch, on_delete=models.PROTECT, null=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="gm_receipt_ledger_singleton"),
            models.CheckConstraint(
                condition=models.Q(mode="DORMANT", batch__isnull=True)
                | models.Q(mode__in=("FENCED", "ACTIVE"), batch__isnull=False),
                name="gm_receipt_ledger_shape",
            ),
        ]


class GoodMoralReceiptIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    normalized_key = models.CharField(max_length=96, db_collation="C")
    normalization_version = models.CharField(max_length=16, default="GM_OR_V1", editable=False)
    bound_request = models.ForeignKey(
        GoodMoralRequest, on_delete=models.PROTECT, null=True, related_name="receipt_reservations"
    )
    state = models.CharField(max_length=20, choices=ReceiptIdentityState.choices)
    reserved_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    origin = models.CharField(max_length=16, choices=ReceiptOrigin.choices)
    import_batch = models.ForeignKey(
        GoodMoralReceiptImportBatch, on_delete=models.PROTECT, null=True
    )

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("normalized_key",), name="gm_receipt_identity_key_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(normalized_key__regex=r"^[ -~]{1,96}$"),
                name="gm_receipt_key_ascii",
            ),
            models.CheckConstraint(
                condition=models.Q(normalization_version="GM_OR_V1"),
                name="gm_receipt_key_version",
            ),
            models.CheckConstraint(
                condition=models.Q(state="BOUND", bound_request__isnull=False)
                | models.Q(state="LEGACY_AMBIGUOUS", bound_request__isnull=True)
                | models.Q(state="DISPUTED"),
                name="gm_receipt_identity_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    origin="ORDINARY", recorded_by__isnull=False, import_batch__isnull=True
                )
                | models.Q(
                    origin="LEGACY_OBSERVED", recorded_by__isnull=True, import_batch__isnull=False
                ),
                name="gm_receipt_reservation_source",
            ),
        ]


class GoodMoralReceiptAssignment(models.Model):
    """Immutable facts; only the one-way, attributable closure is writable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(GoodMoralReceiptIdentity, on_delete=models.PROTECT, null=True)
    request = models.ForeignKey(
        GoodMoralRequest, on_delete=models.PROTECT, related_name="receipt_revisions"
    )
    display_number = models.CharField(max_length=96, blank=True)
    receipt_date = models.DateField(null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    origin = models.CharField(max_length=16, choices=ReceiptOrigin.choices)
    sequence = models.PositiveIntegerField()
    previous = models.ForeignKey("self", on_delete=models.PROTECT, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="recorded_good_moral_receipt_revisions",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    change_kind = models.CharField(
        max_length=16,
        choices=[(s, s) for s in ("ASSIGNED", "REVISED", "REPLACED", "REMOVED", "LEGACY")],
    )
    reason = models.CharField(max_length=500, blank=True)
    is_current = models.BooleanField(default=False)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="closed_good_moral_receipt_revisions",
    )
    closed_at = models.DateTimeField(null=True)
    closure_reason = models.CharField(max_length=32, blank=True)
    import_batch = models.ForeignKey(
        GoodMoralReceiptImportBatch, on_delete=models.PROTECT, null=True
    )

    class Meta:
        default_permissions = ()
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("request", "sequence"), name="gm_receipt_request_seq_uniq"
            ),
            models.UniqueConstraint(
                fields=("request",),
                condition=models.Q(is_current=True),
                name="gm_receipt_request_current",
            ),
            models.UniqueConstraint(
                fields=("identity",),
                condition=models.Q(is_current=True),
                name="gm_receipt_identity_current",
            ),
            models.UniqueConstraint(
                fields=("request",),
                condition=models.Q(origin="LEGACY_OBSERVED"),
                name="gm_receipt_legacy_observation",
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gte=1), name="gm_receipt_positive_sequence"
            ),
            models.CheckConstraint(
                condition=models.Q(is_current=False) | models.Q(identity__isnull=False),
                name="gm_receipt_current_identity",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    closed_at__isnull=True, closed_by__isnull=True, closure_reason=""
                )
                | (
                    models.Q(is_current=False, closed_at__isnull=False, closed_by__isnull=False)
                    & ~models.Q(closure_reason="")
                ),
                name="gm_receipt_closure_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(origin="LEGACY_OBSERVED", is_current=False)
                | models.Q(amount__isnull=True)
                | (models.Q(amount__gte=0) & models.Q(amount__lt=Decimal("10000000000"))),
                name="gm_receipt_amount_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    origin="ORDINARY", recorded_by__isnull=False, import_batch__isnull=True
                )
                | models.Q(
                    origin="LEGACY_OBSERVED", recorded_by__isnull=True, import_batch__isnull=False
                ),
                name="gm_receipt_claim_source",
            ),
        ]


class GoodMoralReceiptMutation(models.Model):
    """A durable receipt of an entire correction, including exact no-ops."""

    operation_id = models.UUIDField(primary_key=True, editable=False)
    request = models.ForeignKey(GoodMoralRequest, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    intended_revision = models.ForeignKey(
        GoodMoralReceiptAssignment,
        on_delete=models.PROTECT,
        null=True,
        related_name="intended_mutations",
    )
    result_revision = models.ForeignKey(
        GoodMoralReceiptAssignment,
        on_delete=models.PROTECT,
        null=True,
        related_name="result_mutations",
    )
    result_request_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class GoodMoralReceiptVerification(models.Model):
    """Personal physical inspection of one immutable claim; never Cashier reconciliation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        GoodMoralReceiptAssignment, on_delete=models.PROTECT, related_name="verifications"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="good_moral_receipt_inspections",
    )
    method = models.CharField(
        max_length=32, choices=[("PHYSICAL_OR_INSPECTION", "Physical OR inspection")]
    )
    verified_at = models.DateTimeField(auto_now_add=True)
    policy_id = models.CharField(max_length=100)
    policy_version = models.CharField(max_length=64)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    fee_decision = models.JSONField()
    operation_id = models.UUIDField(unique=True, editable=False)
    fingerprint = models.CharField(max_length=64)
    invalidated_at = models.DateTimeField(null=True)
    invalidated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="invalidated_good_moral_receipt_inspections",
    )
    invalidation_reason = models.CharField(max_length=32, blank=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["assignment"],
                condition=models.Q(invalidated_at__isnull=True),
                name="gm_receipt_one_inspection",
            ),
            models.CheckConstraint(
                condition=models.Q(method="PHYSICAL_OR_INSPECTION"),
                name="gm_receipt_inspection_method",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="PHP", expected_amount__gt=0),
                name="gm_receipt_inspection_fee",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        invalidated_at__isnull=True,
                        invalidated_by__isnull=True,
                        invalidation_reason="",
                    )
                    | models.Q(
                        invalidated_at__isnull=False,
                        invalidated_by__isnull=False,
                        invalidation_reason__in=["RECEIPT_REVISED", "CANCELLED", "POLICY_CHANGED"],
                    )
                ),
                name="gm_receipt_invalidation_shape",
            ),
        ]
