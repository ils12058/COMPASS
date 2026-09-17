# Generated for the COMPASS Availability foundation.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficeAvailabilityWindow",
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
                    "weekday",
                    models.CharField(
                        choices=[
                            ("MONDAY", "Monday"),
                            ("TUESDAY", "Tuesday"),
                            ("WEDNESDAY", "Wednesday"),
                            ("THURSDAY", "Thursday"),
                            ("FRIDAY", "Friday"),
                            ("SATURDAY", "Saturday"),
                            ("SUNDAY", "Sunday"),
                        ],
                        max_length=9,
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "mode_scope",
                    models.CharField(
                        choices=[
                            ("ALL", "All delivery modes"),
                            ("IN_PERSON", "In person"),
                            ("ONLINE", "Online"),
                        ],
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("weekday", "start_time", "end_time", "mode_scope", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="OfficeUnavailability",
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
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                (
                    "mode_scope",
                    models.CharField(
                        choices=[
                            ("ALL", "All delivery modes"),
                            ("IN_PERSON", "In person"),
                            ("ONLINE", "Online"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_office_unavailability",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("starts_at", "ends_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="ProviderAvailabilityWindow",
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
                    "weekday",
                    models.CharField(
                        choices=[
                            ("MONDAY", "Monday"),
                            ("TUESDAY", "Tuesday"),
                            ("WEDNESDAY", "Wednesday"),
                            ("THURSDAY", "Thursday"),
                            ("FRIDAY", "Friday"),
                            ("SATURDAY", "Saturday"),
                            ("SUNDAY", "Sunday"),
                        ],
                        max_length=9,
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "mode_scope",
                    models.CharField(
                        choices=[
                            ("ALL", "All delivery modes"),
                            ("IN_PERSON", "In person"),
                            ("ONLINE", "Online"),
                        ],
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="availability_windows",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": (
                    "provider_id",
                    "weekday",
                    "start_time",
                    "end_time",
                    "mode_scope",
                    "id",
                ),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="ProviderUnavailability",
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
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                (
                    "mode_scope",
                    models.CharField(
                        choices=[
                            ("ALL", "All delivery modes"),
                            ("IN_PERSON", "In person"),
                            ("ONLINE", "Online"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_provider_unavailability",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="unavailability_exceptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("provider_id", "starts_at", "ends_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="officeavailabilitywindow",
            constraint=models.CheckConstraint(
                condition=models.Q(("start_time__lt", models.F("end_time"))),
                name="availability_office_window_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="officeavailabilitywindow",
            constraint=models.UniqueConstraint(
                fields=("weekday", "start_time", "end_time", "mode_scope"),
                name="availability_office_window_exact_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="officeunavailability",
            constraint=models.CheckConstraint(
                condition=models.Q(("starts_at__lt", models.F("ends_at"))),
                name="availability_office_exception_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="provideravailabilitywindow",
            constraint=models.CheckConstraint(
                condition=models.Q(("start_time__lt", models.F("end_time"))),
                name="availability_provider_window_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="provideravailabilitywindow",
            constraint=models.UniqueConstraint(
                fields=("provider", "weekday", "start_time", "end_time", "mode_scope"),
                name="availability_provider_window_exact_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="providerunavailability",
            constraint=models.CheckConstraint(
                condition=models.Q(("starts_at__lt", models.F("ends_at"))),
                name="availability_provider_exception_order",
            ),
        ),
    ]
