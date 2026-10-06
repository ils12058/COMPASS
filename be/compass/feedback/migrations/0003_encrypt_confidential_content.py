"""Phase A: nullable envelope backfill; plaintext remains authoritative."""

from django.db import migrations, models
from compass.feedback.migrations._feedback_confidential_content_v1 import (
    FAMILIES,
    COLUMN,
    keyring,
    encrypt,
    plaintext,
)


def backfill(apps, schema_editor):
    ring = keyring()
    for family in FAMILIES:
        rows = apps.get_model("feedback", family).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            rows.filter(pk=row.pk).update(
                **{COLUMN: encrypt(ring, row, plaintext(row, family), family)}
            )


class Migration(migrations.Migration):
    dependencies = [("feedback", "0002_feedback_opportunity")]
    operations = [
        migrations.AddField(
            model_name=family.lower(),
            name=COLUMN,
            field=models.TextField(null=True, editable=False),
        )
        for family in FAMILIES
    ] + [migrations.RunPython(backfill, migrations.RunPython.noop)]
