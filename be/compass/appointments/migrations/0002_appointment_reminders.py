"""Durable reminder occurrences and bulk request replay protection."""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0001_canonical_baseline"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(model_name="appointment", index=models.Index(
            fields=("status", "starts_at", "id"), name="appt_rem_discovery_idx")),
        migrations.AddField(
            model_name="appointment", name="reminder_revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="appointment", name="reminder_revision_started_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name="AppointmentReminderOccurrence",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("kind", models.CharField(max_length=12, choices=[
                    ("AUTO_24H", "24-hour automatic"), ("AUTO_3H", "3-hour automatic"),
                    ("MANUAL", "Manual"),
                ])),
                ("revision", models.PositiveIntegerField()),
                ("starts_at", models.DateTimeField()),
                ("issued_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("appointment", models.ForeignKey(to="appointments.appointment", on_delete=django.db.models.deletion.PROTECT, related_name="reminder_occurrences")),
                ("recipient", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="appointment_reminders_received")),
                ("issued_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="appointment_reminders_issued")),
            ],
            options={"default_permissions": (), "ordering": ("-issued_at",)},
        ),
        migrations.AddConstraint(
            model_name="appointmentreminderoccurrence",
            constraint=models.UniqueConstraint(
                fields=("appointment", "revision", "kind"),
                condition=Q(kind__in=["AUTO_24H", "AUTO_3H"]),
                name="appt_rem_auto_window_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="appointmentreminderoccurrence",
            index=models.Index(fields=("appointment", "issued_at"), name="appt_rem_cooldown_idx"),
        ),
        migrations.CreateModel(
            name="AppointmentReminderBatch",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("request_key", models.UUIDField()),
                ("selection_digest", models.CharField(max_length=64)),
                ("result", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="appointment_reminder_batches")),
            ],
            options={"default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="appointmentreminderbatch",
            constraint=models.UniqueConstraint(fields=("actor", "request_key"), name="appt_rem_batch_replay_unique"),
        ),
    ]
