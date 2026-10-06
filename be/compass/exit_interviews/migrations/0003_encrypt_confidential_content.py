"""Phase A: ciphertext backfill with authoritative plaintext retained."""

from django.db import migrations, models

from compass.exit_interviews.migrations._exit_interview_confidential_content_v1 import (
    FAMILIES,
    encrypt,
    keyring,
    plaintext,
)


def backfill(apps, schema_editor):
    ring = keyring()
    for name, column, kind in FAMILIES:
        rows = apps.get_model("exit_interviews", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            rows.filter(pk=row.pk).update(
                **{column: encrypt(ring, row, plaintext(row, kind), kind)}
            )


class Migration(migrations.Migration):
    dependencies = [
        (
            "exit_interviews",
            "0002_exitinterviewopportunity_exitinterview_opportunity_and_more",
        )
    ]
    operations = [
        migrations.AddField(
            model_name=name.lower(),
            name=column,
            field=models.TextField(null=True, editable=False),
        )
        for name, column, _kind in FAMILIES
    ] + [migrations.RunPython(backfill, migrations.RunPython.noop)]
