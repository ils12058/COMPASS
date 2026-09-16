# Generated for the COMPASS Service Catalog foundation.

import django.core.validators
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Service",
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
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "appointment_policy",
                    models.CharField(
                        choices=[
                            ("NONE", "None"),
                            ("OPTIONAL", "Optional"),
                            ("REQUIRED", "Required"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "default_duration_minutes",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(480),
                        ],
                    ),
                ),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("code",),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="service",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("default_duration_minutes__isnull", True))
                    | models.Q(
                        ("default_duration_minutes__gte", 1),
                        ("default_duration_minutes__lte", 480),
                    )
                ),
                name="service_catalog_duration_range",
            ),
        ),
        migrations.CreateModel(
            name="ServiceDeliveryMode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "mode",
                    models.CharField(
                        choices=[("IN_PERSON", "In person"), ("ONLINE", "Online")],
                        max_length=16,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_mode_assignments",
                        to="service_catalog.service",
                    ),
                ),
            ],
            options={
                "ordering": ("mode",),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="servicedeliverymode",
            constraint=models.UniqueConstraint(
                fields=("service", "mode"),
                name="service_catalog_service_mode_uniq",
            ),
        ),
        migrations.CreateModel(
            name="ServiceProviderRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="service_provider_eligibilities",
                        to="accounts.role",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="provider_role_assignments",
                        to="service_catalog.service",
                    ),
                ),
            ],
            options={
                "ordering": ("role__code",),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="serviceproviderrole",
            constraint=models.UniqueConstraint(
                fields=("service", "role"),
                name="service_catalog_service_provider_role_uniq",
            ),
        ),
    ]
