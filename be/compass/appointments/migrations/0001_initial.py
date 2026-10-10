import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("service_catalog", "0002_service_cancellation_cutoff"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppointmentReferenceCounter",
            fields=[
                ("year", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("next_value", models.PositiveIntegerField(default=1)),
            ],
            options={"default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="appointmentreferencecounter",
            constraint=models.CheckConstraint(
                condition=models.Q(("next_value__gte", 1)),
                name="appointments_reference_counter_positive",
            ),
        ),
        migrations.CreateModel(
            name="Appointment",
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
                ("reference_code", models.CharField(max_length=32, unique=True)),
                (
                    "delivery_mode",
                    models.CharField(
                        choices=[("IN_PERSON", "In person"), ("ONLINE", "Online")],
                        max_length=16,
                    ),
                ),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[("SCHEDULED", "Scheduled"), ("CANCELLED", "Cancelled")],
                        default="SCHEDULED",
                        max_length=16,
                    ),
                ),
                ("cancellation_cutoff_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cancelled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cancelled_appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="provider_appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="service_catalog.service",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("starts_at", "reference_code", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["provider", "status", "starts_at", "ends_at"],
                name="appt_provider_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["student", "status", "starts_at", "ends_at"],
                name="appt_student_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.CheckConstraint(
                condition=models.Q(("starts_at__lt", models.F("ends_at"))),
                name="appointments_time_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("cancellation_cutoff_minutes__isnull", True))
                    | models.Q(("cancellation_cutoff_minutes__gte", 0))
                ),
                name="appointments_cancellation_cutoff_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("cancelled_at__isnull", True), ("status", "SCHEDULED"))
                    | models.Q(("cancelled_at__isnull", False), ("status", "CANCELLED"))
                ),
                name="appointments_status_cancellation_consistent",
            ),
        ),
    ]
