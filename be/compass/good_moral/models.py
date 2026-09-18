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


class GoodMoralStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    ISSUED = "ISSUED", "Issued"


class GoodMoralRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="good_moral_requests",
    )
    variant = models.CharField(max_length=24, choices=GoodMoralVariant.choices)
    status = models.CharField(
        max_length=16,
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
                        status=GoodMoralStatus.REQUESTED,
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
        ]
