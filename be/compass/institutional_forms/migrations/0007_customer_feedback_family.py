from django.db import migrations


def add_customer_feedback_family(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormRevision = apps.get_model("institutional_forms", "FormRevision")

    family, _ = FormFamily.objects.get_or_create(
        key="customer_feedback",
        defaults={"title": "Customer Feedback Form"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        official_code="CNSC-OP-GTA-01F14",
        official_revision="0",
        defaults={
            "internal_schema_version": 1,
            "status": "ACTIVE",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("institutional_forms", "0006_good_moral_families")]

    operations = [
        migrations.RunPython(add_customer_feedback_family, migrations.RunPython.noop),
    ]
