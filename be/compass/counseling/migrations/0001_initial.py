import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appointments", "0001_initial"),
        ("service_catalog", "0002_service_cancellation_cutoff"),
    ]

    operations = [
        migrations.CreateModel(
            name="CounselingEncounter",
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
                    "entry_mode",
                    models.CharField(
                        choices=[
                            ("APPOINTMENT", "Appointment"),
                            ("WALK_IN", "Walk in"),
                            ("CALLED_IN", "Called in"),
                            ("REFERRED", "Referred"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "delivery_mode",
                    models.CharField(
                        choices=[("IN_PERSON", "In person"), ("ONLINE", "Online")],
                        max_length=16,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counseling_encounter",
                        to="appointments.appointment",
                    ),
                ),
                (
                    "counselor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counselor_counseling_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_counseling_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counseling_encounters",
                        to="service_catalog.service",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_counseling_encounters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-started_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="counselingencounter",
            index=models.Index(
                fields=["counselor", "started_at"],
                name="counseling_counselor_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="counselingencounter",
            index=models.Index(
                fields=["student", "started_at"],
                name="counseling_student_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="counselingencounter",
            constraint=models.CheckConstraint(
                condition=models.Q(("started_at__lt", models.F("ended_at"))),
                name="counseling_time_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="counselingencounter",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(("entry_mode", "APPOINTMENT"))
                    | models.Q(("appointment__isnull", False))
                ),
                name="counseling_appointment_mode_requires_link",
            ),
        ),
    ]
