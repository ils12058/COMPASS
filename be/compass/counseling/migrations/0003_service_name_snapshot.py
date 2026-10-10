from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_service_names(apps, schema_editor):
    CounselingEncounter = apps.get_model("counseling", "CounselingEncounter")
    Service = apps.get_model("service_catalog", "Service")
    linked_name = Service.objects.filter(pk=OuterRef("service_id")).values("name")[:1]
    CounselingEncounter.objects.update(service_name_snapshot=Subquery(linked_name))


class Migration(migrations.Migration):
    dependencies = [
        ("counseling", "0002_counselingsharedsummary"),
        ("service_catalog", "0003_service_requires_current_inventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="counselingencounter",
            name="service_name_snapshot",
            field=models.CharField(max_length=160, null=True),
        ),
        # Existing rows can only capture the linked name as known at migration time.
        migrations.RunPython(backfill_service_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="counselingencounter",
            name="service_name_snapshot",
            field=models.CharField(max_length=160),
        ),
    ]
