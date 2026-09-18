from django.db import migrations


def add_call_slip_family(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormRevision = apps.get_model("institutional_forms", "FormRevision")

    family, _ = FormFamily.objects.get_or_create(
        key="call_slip",
        defaults={"title": "Interview Permit / Call Slip"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="0",
        defaults={
            "internal_schema_version": 1,
            "status": "ACTIVE",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("institutional_forms", "0004_referral_slip_family"),
    ]

    operations = [
        migrations.RunPython(add_call_slip_family, migrations.RunPython.noop),
    ]
