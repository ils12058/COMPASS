"""Normalized booking pathways, preserving all existing flexible booking behavior."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


def backfill_flexible_bookings(apps, schema_editor):
    Service = apps.get_model("service_catalog", "Service")
    Pathway = apps.get_model("service_catalog", "ServiceBookingPathway")
    database = schema_editor.connection.alias
    pending = []
    for service_id in (
        Service.objects.using(database)
        .filter(appointment_booking_enabled=True)
        .values_list("pk", flat=True)
        .iterator(chunk_size=500)
    ):
        pending.append(
            Pathway(
                service_id=service_id,
                code="FLEXIBLE_APPOINTMENT",
            )
        )
        if len(pending) == 500:
            Pathway.objects.using(database).bulk_create(pending, ignore_conflicts=True)
            pending.clear()
    if pending:
        Pathway.objects.using(database).bulk_create(pending, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("service_catalog", "0001_canonical_baseline")]

    operations = [
        migrations.CreateModel(
            name="ServiceBookingPathway",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.CharField(max_length=32, choices=[
                    ("FLEXIBLE_APPOINTMENT", "Flexible individual appointments"),
                    ("FIXED_DATE_SLOT", "Fixed-date appointment slots"),
                    ("GROUP_SESSION", "Group sessions and events"),
                ])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("service", models.ForeignKey(
                    to="service_catalog.service",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="booking_pathways",
                )),
            ],
            options={"default_permissions": (), "ordering": ("code",)},
        ),
        migrations.AddConstraint(
            model_name="servicebookingpathway",
            constraint=models.UniqueConstraint(
                fields=("service", "code"), name="service_booking_pathway_unique",
            ),
        ),
        migrations.RunPython(backfill_flexible_bookings, migrations.RunPython.noop),
    ]
