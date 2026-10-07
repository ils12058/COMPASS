"""ADR-089: two-state Appointment booking and Counselor provider coverage.

NONE becomes booking unavailable; OPTIONAL and REQUIRED, which COMPASS never told apart, both
become booking available. A Service without booking keeps no Appointment-only settings. Every
existing Service keeps ALL_COUNSELORS coverage, and historical provider-role rows are untouched.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def map_appointment_policy(apps, schema_editor):
    Service = apps.get_model("service_catalog", "Service")
    Service.objects.filter(appointment_policy__in=("OPTIONAL", "REQUIRED")).update(
        appointment_booking_enabled=True
    )
    Service.objects.filter(appointment_booking_enabled=False).update(
        default_duration_minutes=None,
        cancellation_cutoff_minutes=None,
        requires_current_inventory=False,
    )


def restore_appointment_policy(apps, schema_editor):
    # REQUIRED was never enforced, so reversal restores OPTIONAL for every bookable Service.
    Service = apps.get_model("service_catalog", "Service")
    Service.objects.filter(appointment_booking_enabled=True).update(appointment_policy="OPTIONAL")
    Service.objects.filter(appointment_booking_enabled=False).update(appointment_policy="NONE")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("service_catalog", "0003_service_requires_current_inventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="appointment_booking_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="service",
            name="provider_coverage",
            field=models.CharField(
                choices=[
                    ("ALL_COUNSELORS", "All Counselors"),
                    ("SELECTED_COUNSELORS", "Selected Counselors"),
                ],
                default="ALL_COUNSELORS",
                max_length=24,
            ),
        ),
        migrations.RunPython(map_appointment_policy, restore_appointment_policy),
        migrations.RemoveField(model_name="service", name="appointment_policy"),
        migrations.RemoveConstraint(model_name="service", name="service_catalog_duration_range"),
        migrations.RenameField(
            model_name="service",
            old_name="default_duration_minutes",
            new_name="default_appointment_duration_minutes",
        ),
        migrations.AddConstraint(
            model_name="service",
            constraint=models.CheckConstraint(
                condition=models.Q(default_appointment_duration_minutes__isnull=True)
                | models.Q(
                    default_appointment_duration_minutes__gte=1,
                    default_appointment_duration_minutes__lte=480,
                ),
                name="service_catalog_duration_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="service",
            constraint=models.CheckConstraint(
                condition=models.Q(appointment_booking_enabled=True)
                | models.Q(
                    default_appointment_duration_minutes__isnull=True,
                    cancellation_cutoff_minutes__isnull=True,
                    requires_current_inventory=False,
                ),
                name="service_catalog_booking_settings_require_booking",
            ),
        ),
        migrations.CreateModel(
            name="ServiceCounselorProvider",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "counselor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="service_provider_qualifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="counselor_providers",
                        to="service_catalog.service",
                    ),
                ),
            ],
            options={
                "ordering": ("service", "counselor"),
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("service", "counselor"),
                        name="service_catalog_service_counselor_uniq",
                    )
                ],
            },
        ),
    ]
