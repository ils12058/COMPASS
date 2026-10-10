from django.db import migrations


def add_referral_slip_family(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormRevision = apps.get_model("institutional_forms", "FormRevision")

    family, _ = FormFamily.objects.get_or_create(
        key="referral_slip",
        defaults={"title": "Referral Slip"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
        defaults={
            "internal_schema_version": 1,
            "status": "ACTIVE",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("institutional_forms", "0003_allow_revisions_sharing_schema"),
    ]

    operations = [
        migrations.RunPython(add_referral_slip_family, migrations.RunPython.noop),
    ]
