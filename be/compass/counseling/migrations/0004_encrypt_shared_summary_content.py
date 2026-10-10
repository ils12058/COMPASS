"""Phase A: backfill encrypted bodies; plaintext remains authoritative until Phase B."""

from django.db import migrations, models

from compass.counseling.migrations._shared_summary_content_v1 import encrypt, keyring


def encrypt_legacy_content(apps, schema_editor):
    Summary = apps.get_model("counseling", "CounselingSharedSummary")
    rows = Summary.objects.using(schema_editor.connection.alias)
    ring = keyring()
    for row in rows.order_by("pk").only("pk", "encounter_id", "content").iterator(chunk_size=200):
        rows.filter(pk=row.pk).update(
            content_ciphertext=encrypt(ring, row.pk, row.encounter_id, row.content)
        )


class Migration(migrations.Migration):
    dependencies = [("counseling", "0003_service_name_snapshot")]
    operations = [
        migrations.AddField(
            model_name="counselingsharedsummary",
            name="content_ciphertext",
            field=models.TextField(editable=False, null=True),
        ),
        migrations.RunPython(encrypt_legacy_content, migrations.RunPython.noop),
    ]
