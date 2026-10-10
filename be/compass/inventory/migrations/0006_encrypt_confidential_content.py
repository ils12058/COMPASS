"""Phase A: ciphertext backfill with authoritative plaintext retained."""

from django.db import migrations, models

from compass.inventory.migrations._inventory_confidential_content_v1 import (
    FAMILIES,
    encrypt,
    keyring,
    plaintext,
)


def backfill(apps, schema_editor):
    ring = keyring()
    for name, column, _relation in FAMILIES:
        rows = apps.get_model("inventory", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            rows.filter(pk=row.pk).update(
                **{column: encrypt(ring, row, plaintext(row, name), name)}
            )


class Migration(migrations.Migration):
    dependencies = [
        (
            "inventory",
            "0005_submission_history_reopen",
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
