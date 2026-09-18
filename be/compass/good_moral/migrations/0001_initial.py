import decimal
import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("institutional_forms", "0006_good_moral_families"),
        ("inventory", "0001_initial"),
        ("organization", "0002_academic_year"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GoodMoralRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "variant",
                    models.CharField(
                        choices=[
                            ("CURRENT_STUDENT", "Current Student"),
                            ("GRADUATE", "Graduate"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("REQUESTED", "Requested"),
                            ("ISSUED", "Issued"),
                        ],
                        default="REQUESTED",
                        max_length=16,
                    ),
                ),
                (
                    "applicant_name_snapshot",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("major_snapshot", models.CharField(blank=True, default="", max_length=180)),
                (
                    "year_level_snapshot",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "college_snapshot",
                    models.CharField(blank=True, default="", max_length=160),
                ),
                (
                    "course_snapshot",
                    models.CharField(blank=True, default="", max_length=180),
                ),
                (
                    "semester_snapshot",
                    models.CharField(blank=True, default="", max_length=80),
                ),
                (
                    "degree_snapshot",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("graduation_date", models.DateField(blank=True, null=True)),
                (
                    "official_receipt_number",
                    models.CharField(blank=True, default="", max_length=96),
                ),
                ("official_receipt_date", models.DateField(blank=True, null=True)),
                (
                    "official_receipt_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.00"))
                        ],
                    ),
                ),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                (
                    "issued_by_name_snapshot",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "document_template_key",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                (
                    "document_template_version",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="good_moral_requests",
                        to="organization.academicyear",
                    ),
                ),
                (
                    "form_revision",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="good_moral_requests",
                        to="institutional_forms.formrevision",
                    ),
                ),
                (
                    "inventory",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="good_moral_requests",
                        to="inventory.studentinventory",
                    ),
                ),
                (
                    "issued_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="issued_good_moral_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="good_moral_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="goodmoralrequest",
            index=models.Index(
                fields=["student", "created_at"],
                name="good_moral_student_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="goodmoralrequest",
            index=models.Index(
                fields=["status", "created_at"],
                name="good_moral_status_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="goodmoralrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        variant="CURRENT_STUDENT",
                        inventory__isnull=False,
                        academic_year__isnull=False,
                        degree_snapshot="",
                        graduation_date__isnull=True,
                    )
                    | models.Q(
                        variant="GRADUATE",
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
        ),
        migrations.AddConstraint(
            model_name="goodmoralrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="REQUESTED",
                        form_revision__isnull=True,
                        issued_at__isnull=True,
                        issued_by__isnull=True,
                        issued_by_name_snapshot="",
                        document_template_key__isnull=True,
                        document_template_version__isnull=True,
                    )
                    | (
                        models.Q(
                            status="ISSUED",
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
        ),
    ]
