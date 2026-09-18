from django.db import migrations


def add_good_moral_families(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormRevision = apps.get_model("institutional_forms", "FormRevision")

    definitions = (
        (
            "good_moral_current_student",
            "Good Moral Character — Current Student",
            "CNSC-OP-GCO-01F4",
        ),
        (
            "good_moral_graduate",
            "Good Moral Character — Graduate",
            "CNSC-OP-GCO-01F6",
        ),
    )
    for key, title, official_code in definitions:
        family, _ = FormFamily.objects.get_or_create(
            key=key,
            defaults={"title": title},
        )
        FormRevision.objects.get_or_create(
            family=family,
            official_code=official_code,
            official_revision="0",
            defaults={
                "internal_schema_version": 1,
                "status": "ACTIVE",
            },
        )


class Migration(migrations.Migration):
    dependencies = [("institutional_forms", "0005_call_slip_family")]

    operations = [
        migrations.RunPython(add_good_moral_families, migrations.RunPython.noop),
    ]
