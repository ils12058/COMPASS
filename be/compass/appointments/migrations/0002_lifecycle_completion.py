import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="appointment",
            name="appointments_status_cancellation_consistent",
        ),
        migrations.AlterField(
            model_name="appointment",
            name="status",
            field=models.CharField(
                choices=[
                    ("SCHEDULED", "Scheduled"),
                    ("CANCELLED", "Cancelled"),
                    ("COMPLETED", "Completed"),
                    ("NO_SHOW", "No show"),
                ],
                default="SCHEDULED",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="completed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="completed_appointments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="no_show_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="no_show_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="no_show_appointments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="SCHEDULED",
                        cancelled_at__isnull=True,
                        completed_at__isnull=True,
                        no_show_at__isnull=True,
                    )
                    | models.Q(
                        status="CANCELLED",
                        cancelled_at__isnull=False,
                        completed_at__isnull=True,
                        no_show_at__isnull=True,
                    )
                    | models.Q(
                        status="COMPLETED",
                        cancelled_at__isnull=True,
                        completed_at__isnull=False,
                        no_show_at__isnull=True,
                    )
                    | models.Q(
                        status="NO_SHOW",
                        cancelled_at__isnull=True,
                        completed_at__isnull=True,
                        no_show_at__isnull=False,
                    )
                ),
                name="appointments_status_terminal_consistent",
            ),
        ),
        migrations.CreateModel(
            name="AppointmentChangeEvent",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("RESCHEDULED", "Rescheduled"),
                            ("REASSIGNED", "Reassigned"),
                        ],
                        max_length=16,
                    ),
                ),
                ("occurred_at", models.DateTimeField()),
                ("reason", models.TextField(blank=True, default="", max_length=1000)),
                ("previous_starts_at", models.DateTimeField(blank=True, null=True)),
                ("previous_ends_at", models.DateTimeField(blank=True, null=True)),
                ("new_starts_at", models.DateTimeField(blank=True, null=True)),
                ("new_ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="change_events",
                        to="appointments.appointment",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointment_change_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "new_provider",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointment_reassignments_to",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "previous_provider",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointment_reassignments_from",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("occurred_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="appointmentchangeevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        event_type="RESCHEDULED",
                        previous_starts_at__isnull=False,
                        previous_ends_at__isnull=False,
                        new_starts_at__isnull=False,
                        new_ends_at__isnull=False,
                        previous_provider__isnull=True,
                        new_provider__isnull=True,
                    )
                    | models.Q(
                        event_type="REASSIGNED",
                        previous_starts_at__isnull=True,
                        previous_ends_at__isnull=True,
                        new_starts_at__isnull=True,
                        new_ends_at__isnull=True,
                        previous_provider__isnull=False,
                        new_provider__isnull=False,
                    )
                ),
                name="appointment_change_event_shape",
            ),
        ),
    ]
