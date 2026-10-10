import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("institutional_forms", "0005_call_slip_family"),
        ("referrals", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CallSlip",
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
                ("student_name_snapshot", models.CharField(max_length=512)),
                ("course_year_snapshot", models.CharField(max_length=255)),
                (
                    "destination_type",
                    models.CharField(
                        choices=[
                            ("GUIDANCE_OFFICE", "Guidance Office"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("other_destination", models.CharField(blank=True, default="", max_length=255)),
                ("report_at", models.DateTimeField()),
                ("issued_by_name_snapshot", models.CharField(max_length=512)),
                ("interview_ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "creation_key_digest",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                (
                    "creation_request_fingerprint",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "form_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="call_slips",
                        to="institutional_forms.formrevision",
                    ),
                ),
                (
                    "issued_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="issued_call_slips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recorded_call_slips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "referral",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="call_slip",
                        to="referrals.referral",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_call_slips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-report_at", "-created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="callslip",
            index=models.Index(
                fields=["student", "report_at"],
                name="callslip_student_report_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="callslip",
            index=models.Index(
                fields=["issued_by", "report_at"],
                name="callslip_issuer_report_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="callslip",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(destination_type="GUIDANCE_OFFICE", other_destination="")
                    | (
                        models.Q(destination_type="OTHER")
                        & ~models.Q(other_destination="")
                    )
                ),
                name="callslip_destination_consistency",
            ),
        ),
    ]
