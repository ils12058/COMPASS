from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_service_names(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    Service = apps.get_model("service_catalog", "Service")
    linked_name = Service.objects.filter(pk=OuterRef("service_id")).values("name")[:1]
    Appointment.objects.update(service_name_snapshot=Subquery(linked_name))


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0002_lifecycle_completion"),
        ("service_catalog", "0003_service_requires_current_inventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="service_name_snapshot",
            field=models.CharField(max_length=160, null=True),
        ),
        # Legacy creation-time names cannot be recovered after a prior Service rename.
        # The current linked name is the best available migration-time baseline.
        migrations.RunPython(backfill_service_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="appointment",
            name="service_name_snapshot",
            field=models.CharField(max_length=160),
        ),
    ]
